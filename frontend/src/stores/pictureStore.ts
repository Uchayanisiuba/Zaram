/**
 * The pictures a conversation's pages use, fetched when a reply names one.
 *
 * Working state and nothing more: held in memory for the life of the window,
 * never written anywhere, and keyed by attachment id. The backend holds the
 * bytes for the session (`GET /chat/attachments/{id}/content`) and, beside the
 * conversation, a kept copy (`GET /conversations/{id}/pictures/{attachment}`);
 * this is the window's copy of the few a page actually uses, as `data:` URIs
 * ready to be put into the page (`lib/pagePictures.ts`).
 *
 * **The live copy is asked for first, the kept copy second.** After a restart,
 * or in a conversation reopened from History, the session no longer holds the
 * picture but the conversation does. Only when both say no is it gone.
 *
 * **Three states, kept apart.** A string is the picture. `null` is "neither
 * the session nor the conversation has it" -- removed, or pruned to keep the
 * pictures under their ceiling -- which the page shows as a visible placeholder
 * and the page-check line says in words. An id with no entry has not been asked
 * for yet, or could not be reached; it is asked for again next time rather than
 * recorded as gone, because "the backend did not answer" is not "the picture is
 * gone".
 */
import { create } from 'zustand';
import { keptPictureUrl } from '@/services/conversationsClient';

const API = import.meta.env.VITE_ZARAM_API ?? '';

interface PictureStore {
  held: Record<string, string | null>;
  /** Fetch any of `ids` not already settled. Resolves when all have.
   *  `conversationId`, when there is one, is where the kept copy is looked for. */
  ensure: (sessionId: string, ids: readonly string[], conversationId?: string | null) => Promise<void>;
}

const inFlight = new Map<string, Promise<void>>();

/** The response as a `data:` URI. Its own content type, which the backend read
 *  from the bytes; bytes in chunks, because spreading a photograph into
 *  `fromCharCode` in one call overflows the stack. */
async function asDataUri(response: Response): Promise<string> {
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  const type = response.headers.get('content-type') || 'application/octet-stream';
  return `data:${type};base64,${btoa(binary)}`;
}

export const usePictureStore = create<PictureStore>((set, get) => ({
  held: {},
  ensure: async (sessionId, ids, conversationId) => {
    const wanted = ids.filter((id) => !(id in get().held));
    await Promise.all(
      wanted.map((id) => {
        const running = inFlight.get(id);
        if (running) return running;
        const job = (async () => {
          try {
            const response = await fetch(
              `${API}/chat/attachments/${encodeURIComponent(id)}/content?session_id=${encodeURIComponent(sessionId)}`,
            );
            let found = response;
            if (response.status === 404 && conversationId) {
              // Not in this session: the conversation may have kept it.
              found = await fetch(keptPictureUrl(conversationId, id));
            }
            if (found.status === 404 || found.status === 415) {
              set((s) => ({ held: { ...s.held, [id]: null } }));
              return;
            }
            if (!found.ok) return;
            const uri = await asDataUri(found);
            set((s) => ({ held: { ...s.held, [id]: uri } }));
          } catch {
            // Not reachable right now: left unsettled, asked for again later.
          } finally {
            inFlight.delete(id);
          }
        })();
        inFlight.set(id, job);
        return job;
      }),
    );
  },
}));
