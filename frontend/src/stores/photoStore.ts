/**
 * Photographs found online for the pages in this window, by description.
 *
 * Working state only: held in memory for the life of the window and never
 * written anywhere. The backend keeps its own short cache of the files and its
 * own retention answer (`packs/photos/finder.py`); this is the window's copy of
 * the few a page uses, as `data:` URIs ready to go in (`lib/pagePhotos.ts`).
 *
 * **One request can wait for the person.** The first search of the photo
 * source asks whether it may happen, through the same dialog every other
 * outbound request uses, and `POST /photos/find` stays open until it is
 * answered. So a description being looked for is held with the request that
 * will settle it: it is never asked for twice at once, and a second caller --
 * the page check, say -- waits for that answer rather than going on without it.
 *
 * **An answer is kept, including "no".** A refusal is stored like any other
 * reason, so the page does not ask again every time it is drawn. Asking again
 * is the person's decision: `lookAgain`.
 */
import { create } from 'zustand';

import { photoKey, RETRIABLE_CODES, type PhotoEntry, type PhotoMap } from '@/lib/pagePhotos';

const API = import.meta.env.VITE_ZARAM_API ?? '';

interface PhotoStore {
  found: PhotoMap;
  /** Look up any of `descriptions` not already settled, and wait for those
   *  already being looked for. `request` is the person's own words for the
   *  page, which the backend uses to tell their words from anything remembered. */
  ensure: (descriptions: readonly string[], request: string) => Promise<void>;
  /** Forget the answers that looking again could change, and look again. */
  lookAgain: (descriptions: readonly string[], request: string) => Promise<void>;
}

interface Result {
  description: string;
  data_uri?: string;
  title?: string;
  creator?: string;
  license_label?: string;
  license?: string;
  license_url?: string;
  source_url?: string;
  source?: string;
  error?: string;
  code?: string;
}

function entryOf(result: Result): PhotoEntry {
  if (result.data_uri) {
    return {
      uri: result.data_uri,
      title: result.title ?? '',
      creator: result.creator ?? '',
      license: result.license_label || result.license || '',
      licenseUrl: result.license_url ?? '',
      sourceUrl: result.source_url ?? '',
      source: result.source ?? '',
    };
  }
  return { error: result.error || 'No photo came back.', code: result.code || 'unavailable' };
}

/** Reasons that looking again could change: a refusal, no answer, the
 *  connection, the rate limit or the time budget -- not "nothing matched". */
const RETRIABLE = new Set(RETRIABLE_CODES);

const looking = new Map<string, Promise<void>>();

export const usePhotoStore = create<PhotoStore>((set, get) => {
  async function lookUp(wanted: string[], request: string): Promise<void> {
    try {
      const response = await fetch(`${API}/photos/find`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ descriptions: wanted, request, inline: true }),
      });
      if (!response.ok) return; // Not reachable now: asked for again next time.
      const body = (await response.json()) as { results?: Result[] };
      const answered: PhotoMap = {};
      for (const result of body.results ?? []) {
        answered[photoKey(result.description)] = entryOf(result);
      }
      set((s) => ({ found: { ...s.found, ...answered } }));
    } catch {
      // The backend did not answer: left unsettled rather than recorded as a reason.
    } finally {
      wanted.forEach((d) => looking.delete(photoKey(d)));
    }
  }

  return {
    found: {},
    ensure: async (descriptions, request) => {
      const wanted: string[] = [];
      const waiting = new Set<Promise<void>>();
      for (const d of descriptions) {
        const key = photoKey(d);
        if (!key || key in get().found) continue;
        const running = looking.get(key);
        if (running) {
          waiting.add(running);
          continue;
        }
        if (wanted.some((w) => photoKey(w) === key)) continue;
        wanted.push(d);
      }
      if (wanted.length) {
        const job = lookUp(wanted, request);
        wanted.forEach((d) => looking.set(photoKey(d), job));
        waiting.add(job);
      }
      await Promise.all(waiting);
    },
    lookAgain: async (descriptions, request) => {
      const keys = new Set(descriptions.map(photoKey));
      set((s) => {
        const found = { ...s.found };
        for (const [key, entry] of Object.entries(found)) {
          if (keys.has(key) && 'code' in entry && RETRIABLE.has(entry.code)) delete found[key];
        }
        return { found };
      });
      await get().ensure(descriptions, request);
    },
  };
});
