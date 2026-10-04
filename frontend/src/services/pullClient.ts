/**
 * Downloading the model the first-run screen offered.
 *
 * **With no name this fetches the offer, and that part is unchanged.** The
 * backend recomputes the recommendation from the same manifest and the same
 * measured budget that produced it, so what is fetched is what was quoted.
 *
 * **A name may be passed now, because the model browser lets somebody
 * choose.** The guarantee that refused one before is intact: a name
 * *selects a manifest row*, it does not describe it. The size quoted and
 * logged still comes from the manifest, and a name that is not on the list
 * is refused with a 400 before a byte moves. What was being protected was
 * never "no name in the body" — it was that the thing downloaded is the
 * thing the user was quoted a price for.
 *
 * NDJSON, read line by line, on the pattern `ingestClient` already uses. A
 * second streaming format would be a second set of split-chunk bugs.
 *
 * Every event is one of three shapes and the stream always ends with the last
 * two: progress (`stage`, and `completed`/`total` once bytes are moving),
 * `{done: true}`, or `{error}`. The error arrives *in the stream* rather than
 * as a status code, because the body has already started by the time anything
 * can go wrong — a pull is minutes long and the response headers left in the
 * first millisecond.
 */

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface PullEvent {
  /** What is happening, in a person's words. Never a digest or a filename. */
  stage?: string;
  /** Bytes fetched so far, once the download itself has started. */
  completed?: number;
  /** Bytes expected, as the pull itself reports them — not the manifest's
   *  approximation. This is the figure a progress bar may count against. */
  total?: number;
  done?: boolean;
  error?: string;
}

export async function pullRecommendedModel(
  onEvent: (event: PullEvent) => void,
  signal?: AbortSignal,
  /** A row chosen in the catalogue. Omitted, the backend fetches its own
   *  offer, which is what the first-run screen does. */
  name?: string,
): Promise<void> {
  const response = await fetch(`${API_BASE}/providers/pull`, {
    method: 'POST',
    headers: name ? { 'Content-Type': 'application/json' } : undefined,
    body: name ? JSON.stringify({ name }) : undefined,
    signal,
  });

  if (!response.ok || !response.body) {
    let detail = '';
    try {
      detail = ((await response.json()) as { detail?: string }).detail ?? '';
    } catch {
      /* not every failure has a body */
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const flush = (chunk: string) => {
    const line = chunk.trim();
    if (!line) return;
    try {
      onEvent(JSON.parse(line) as PullEvent);
    } catch {
      // One unreadable line is not a failed download. The stream carries its
      // own outcome, and a dropped line costs a progress tick at worst.
    }
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newline = buffer.indexOf('\n');
    while (newline !== -1) {
      flush(buffer.slice(0, newline));
      buffer = buffer.slice(newline + 1);
      newline = buffer.indexOf('\n');
    }
  }

  flush(buffer);
}
