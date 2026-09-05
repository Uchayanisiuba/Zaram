/**
 * Files attached to a message — transport for working state, not for the Spine.
 *
 * Separate from `ingestClient` on purpose, and the separation is rule 7d rather
 * than tidiness. `ingestClient` adds a document to Knowledge, where it is
 * indexed and recalled for as long as the user keeps it. These calls hold a
 * file for the conversation it was dropped into and no longer.
 *
 * `keepAttachment` is the one place the two meet. It goes through the ordinary
 * ingest path and streams the same NDJSON every other ingest does, because a
 * kept file must become an ordinary source — indexed, policied, correctable,
 * removable — and not something promoted by a second mechanism that would then
 * need its own correction loop.
 *
 * The credential is not attached here. `apiCredential` wraps `fetch` once for
 * every client, which is the whole point of it: a header added per client is a
 * header the next client forgets.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

/** One parsed file, as the composer needs to draw it.
 *
 *  No text field, deliberately. A chip needs a name, a size and evidence the
 *  file was read; it does not need the document, and shipping one would put a
 *  whole contract into every listing response. */
export interface ChatAttachment {
  id: string;
  name: string;
  suffix: string;
  /** Characters extracted. Measured by the parser, never estimated. */
  chars: number;
  /** Pages where the format has them, 0 where it does not. Not a guess. */
  pages: number;
  /** Which parser read it, so "how do you know that" has an answer. */
  parser: string;
  /** `document` or `image`. Not decoration: a document becomes text in the
   *  prompt and is excerpted when it does not fit, while an image becomes its
   *  own field on the request, is never excerpted, and can only go to a model
   *  that can see. */
  kind: string;
  created_at: number;
}

/** A file that did not become an attachment, and the sentence explaining why.
 *
 *  Per file rather than per request: dropping four files of which one is a
 *  screenshot should attach three and say what happened to the fourth. */
export interface RefusedAttachment {
  name: string;
  reason: string;
}

export interface AttachResult {
  attached: ChatAttachment[];
  refused: RefusedAttachment[];
  /** Dropped to make room. Named rather than silent — an attachment that
   *  vanished unmentioned leaves the user believing a document is in scope
   *  when it is not, and the next answer is confidently short of it. */
  evicted: ChatAttachment[];
}

/** Shared failure handling. The dev proxy answers 500 with an empty body when
 *  the backend is down, so a bare status is not a useful message. */
async function failure(res: Response, fallback: string): Promise<Error> {
  let detail = '';
  try {
    detail = (await res.text()).slice(0, 300);
  } catch {
    /* body unreadable */
  }
  if (!detail.trim() && [500, 502, 503, 504].includes(res.status)) {
    return new Error('Could not reach the Zaram backend.');
  }
  // FastAPI puts the sentence in `detail`; anything else is shown as it came.
  try {
    const parsed = JSON.parse(detail) as { detail?: string };
    if (parsed.detail) return new Error(parsed.detail);
  } catch {
    /* not JSON */
  }
  return new Error(detail.trim() || `${fallback} (${res.status})`);
}

/** Parse files and hold them for this conversation.
 *
 *  Every file is reported on, attached or not. A partial success is the
 *  ordinary case and is not an error.
 */
export async function attachFiles(
  files: File[],
  sessionId: string,
  signal?: AbortSignal,
): Promise<AttachResult> {
  const form = new FormData();
  form.append('session_id', sessionId);
  for (const file of files) form.append('files', file, file.name);

  const res = await fetch(`${API_BASE}/chat/attachments`, {
    method: 'POST',
    body: form,
    signal,
  });
  if (!res.ok) throw await failure(res, 'Could not attach that');
  return (await res.json()) as AttachResult;
}

/** What this conversation currently holds.
 *
 *  Worth calling on mount: the backend clears attachments when it restarts, so
 *  chips drawn from local state alone would outlive the documents behind them.
 */
export async function listAttachments(
  sessionId: string,
  signal?: AbortSignal,
): Promise<ChatAttachment[]> {
  const res = await fetch(
    `${API_BASE}/chat/attachments?session_id=${encodeURIComponent(sessionId)}`,
    { signal },
  );
  if (!res.ok) throw await failure(res, 'Could not read the attached files');
  const body = (await res.json()) as { attachments: ChatAttachment[] };
  return body.attachments ?? [];
}

/** Detach one. The bytes go with it — this was never storage. */
export async function detachAttachment(id: string, signal?: AbortSignal): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/attachments/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    signal,
  });
  if (!res.ok) throw await failure(res, 'Could not detach that file');
}

/** Add an attached file to Knowledge, because the user said so.
 *
 *  Streams the ordinary ingest NDJSON. The body is consumed rather than parsed
 *  into events: the caller wants to know it worked, and Knowledge is where the
 *  detail belongs. Reading it to completion matters — abandoning the stream
 *  would leave the ingest half-run.
 */
export async function keepAttachment(id: string, signal?: AbortSignal): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/attachments/${encodeURIComponent(id)}/keep`, {
    method: 'POST',
    signal,
  });
  if (!res.ok) throw await failure(res, 'Could not keep that file');
  const reader = res.body?.getReader();
  if (!reader) return;
  // Drained, not inspected. See above.
  for (;;) {
    const { done } = await reader.read();
    if (done) break;
  }
}

/** How big a document is, in the unit a person thinks in.
 *
 *  Pages where the format has them, because "12 pages" is a size somebody can
 *  picture. Characters otherwise — never a byte count, which describes the
 *  file rather than the reading of it, and never a token estimate, which is a
 *  number the user has no way to check.
 */
export function attachmentSize(item: ChatAttachment): string {
  // An image has no characters and no pages, and "0 characters" would read as
  // a file that failed to parse rather than one with nothing to parse.
  if (item.kind === 'image') return 'image';
  if (item.pages > 0) return `${item.pages} page${item.pages === 1 ? '' : 's'}`;
  if (item.chars < 1000) return `${item.chars} characters`;
  return `${Math.round(item.chars / 1000)}k characters`;
}
