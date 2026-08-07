/**
 * Chat transport — the frontend's connection to the Zaram backend.
 *
 * Deliberately UI-agnostic: no React, no stores, no rendering concerns. It turns
 * an HTTP response into a stream of typed events. Any interface can consume it,
 * which matters because the current chat surface is temporary.
 *
 * Wire format
 * -----------
 * `POST /chat` responds with newline-delimited JSON (NDJSON), one event per line:
 *
 *     {"type":"source","data":{"kind":"memory","url":"memory:1a2b","title":"..."}}
 *     {"type":"token","data":{"content":"Your "}}
 *     {"type":"token","data":{"content":"deadline "}}
 *     {"type":"done","data":{}}
 *
 * Not Server-Sent Events. There is no `data:` prefix and no double-newline frame,
 * so `EventSource` cannot read it — and `EventSource` cannot issue a POST anyway.
 * Hence `fetch` plus a manual reader.
 *
 * Two details that are easy to get wrong and are handled here:
 *
 * 1. A network chunk does not respect line boundaries. A JSON object can be split
 *    across two chunks, so incomplete trailing text is buffered rather than parsed.
 * 2. A network chunk does not respect character boundaries either. A multi-byte
 *    character such as `£` can be split down the middle, which is why the decoder
 *    is used in streaming mode. Decoding each chunk independently corrupts them.
 */

/** Where the backend lives. Empty string means same-origin, which in development
 *  is the Vite proxy in `vite.config.js` forwarding `/chat` to 127.0.0.1:8420.
 *  Packaged builds can point this at the bundled backend. */
import type { Artifact } from './artifactsClient';

const API_BASE = import.meta.env.VITE_ZARAM_API ?? '';

export interface ChatSource {
  /** Where it came from: "memory" for the Spine, a provider name for search. */
  kind: string;
  /** Stable identifier, e.g. "memory:1a2b-...". Used for de-duplication. */
  url: string | null;
  /** Human-readable snippet. */
  title: string | null;
}

export type ChatEvent =
  | { type: 'token'; content: string }
  | { type: 'source'; source: ChatSource }
  /** A file Zaram made. The same record Work draws a row from, so the card in
   *  the conversation and the row in Work cannot disagree about what exists. */
  | { type: 'artifact'; artifact: Artifact & { download_url: string } }
  | { type: 'status'; state: string }
  | { type: 'error'; message: string }
  | { type: 'done' };

export interface ChatRequest {
  text: string;
  model?: string;
  persona?: string;
  sessionId?: string;
}

/** A failure that should be shown to the user, with the cause preserved. */
export class ChatTransportError extends Error {
  constructor(
    message: string,
    readonly cause?: unknown,
    /** True when the reply had already started. The partial text is still valid. */
    readonly partial: boolean = false,
  ) {
    super(message);
    this.name = 'ChatTransportError';
  }
}

/**
 * Send a message and yield events as they arrive.
 *
 * Throws `ChatTransportError` when the backend cannot be reached or rejects the
 * request. Errors reported *by* the backend mid-stream arrive as `error` events
 * rather than exceptions, because tokens may already have been delivered and
 * that partial answer is worth keeping.
 *
 * Aborting via `signal` ends the generator quietly — a deliberate cancellation
 * is not a failure.
 */
export async function* streamChat(
  req: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent, void, undefined> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: req.text,
        model: req.model ?? 'gemma3:latest',
        persona: req.persona ?? 'zaram_prime',
        session_id: req.sessionId ?? 'default',
      }),
      signal,
    });
  } catch (err) {
    if (isAbort(err)) return;
    // fetch only rejects for network-level failures: backend down, DNS, refused.
    throw new ChatTransportError(
      'Could not reach the Zaram backend. Is it running on port 8420?',
      err,
    );
  }

  if (!response.ok) {
    // The backend answered, but with an error status. Its body is usually JSON
    // with a `detail`, so surface that rather than a bare status code.
    let detail = '';
    try {
      detail = (await response.text()).slice(0, 500);
    } catch {
      /* body unreadable; the status alone will have to do */
    }

    // In development the Vite proxy sits in front of the backend. When the
    // backend is down the proxy answers 500 with an empty body rather than
    // refusing the connection, so `fetch` resolves and the network-error branch
    // above never runs. Verified by killing the backend and watching the
    // response. Report the actual cause instead of a bare status code.
    const looksLikeDeadUpstream =
      !detail.trim() && [500, 502, 503, 504].includes(response.status);
    if (looksLikeDeadUpstream) {
      throw new ChatTransportError(
        'Could not reach the Zaram backend. Is it running on port 8420?',
      );
    }

    throw new ChatTransportError(
      `Backend returned ${response.status} ${response.statusText}${detail ? `: ${detail}` : ''}`,
    );
  }

  if (!response.body) {
    throw new ChatTransportError('Backend response had no body to stream.');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let sawDone = false;
  let deliveredAnything = false;

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      // stream: true keeps a partial multi-byte character across chunks.
      buffer += decoder.decode(value, { stream: true });

      // Everything before the final newline is complete; the remainder is not.
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        const event = parseLine(line);
        if (!event) continue;
        if (event.type === 'done') sawDone = true;
        deliveredAnything = true;
        yield event;
      }
    }

    // Flush anything the decoder held back, then any final unterminated line.
    buffer += decoder.decode();
    const tail = parseLine(buffer);
    if (tail) {
      if (tail.type === 'done') sawDone = true;
      yield tail;
    }
  } catch (err) {
    if (isAbort(err)) return;
    // The connection dropped part-way. Any tokens already yielded are real and
    // the caller should keep them, so this is flagged as partial.
    throw new ChatTransportError(
      'The connection dropped while the reply was arriving.',
      err,
      deliveredAnything,
    );
  } finally {
    reader.releaseLock();
  }

  // A stream that ends without `done` was truncated — the backend died or a
  // proxy cut it. Silently accepting it would show a half answer as complete.
  if (!sawDone) {
    throw new ChatTransportError(
      'The reply ended unexpectedly before it was complete.',
      undefined,
      deliveredAnything,
    );
  }
}

/**
 * Parse one NDJSON line into an event.
 *
 * Returns null for blank lines, unparseable lines, and event types this client
 * does not model. A malformed line must never abort a stream that is otherwise
 * delivering a usable answer.
 */
function parseLine(line: string): ChatEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    console.warn('[chatClient] skipping unparseable line:', trimmed.slice(0, 120));
    return null;
  }

  if (typeof parsed !== 'object' || parsed === null) return null;
  const evt = parsed as { type?: unknown; data?: Record<string, unknown> };
  const data = evt.data ?? {};

  switch (evt.type) {
    case 'token':
      return { type: 'token', content: String(data.content ?? '') };

    case 'source':
      return {
        type: 'source',
        source: {
          kind: String(data.kind ?? 'unknown'),
          url: data.url == null ? null : String(data.url),
          title: data.title == null ? null : String(data.title),
        },
      };

    case 'artifact': {
      // The backend sends the whole artifact record. Trusted for shape, not
      // for existence: `exists` comes from the backend having stat'd the file,
      // and the card reads it rather than assuming a written file is there.
      const artifact = data as unknown as Artifact & { download_url?: string };
      if (!artifact.id || !artifact.filename) return null;
      return {
        type: 'artifact',
        artifact: {
          ...artifact,
          download_url: artifact.download_url ?? `/artifacts/${artifact.id}/download`,
        },
      };
    }

    case 'status':
      return { type: 'status', state: String(data.state ?? '') };

    case 'error':
      return { type: 'error', message: String(data.content ?? 'Unknown backend error') };

    case 'done':
      return { type: 'done' };

    default:
      // start, step_start, plan_complete and similar are internal execution
      // detail. Ignored rather than treated as an error.
      return null;
  }
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

/** Whether the backend is reachable. Used to show connection state up front. */
export async function checkHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal });
    return res.ok;
  } catch {
    return false;
  }
}
