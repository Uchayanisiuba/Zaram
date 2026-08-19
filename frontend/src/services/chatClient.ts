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

/** One source behind an answer.
 *
 *  The three kinds are the distinction the whole citation UI rests on:
 *  `memory` and `document` stayed on this machine, `web` means bytes left and
 *  there is an egress log row for it. **Never infer a kind here** — the backend
 *  sends it, and inventing one client-side would be the fabrication rule in a
 *  different file. */
export type SourceKind = 'memory' | 'document' | 'web';

export interface ChatSource {
  kind: SourceKind;
  /** Stable identifier, e.g. "memory:1a2b-...". Used for de-duplication. */
  url: string | null;
  /** Filename for a document, the fact itself for a memory, the page title for web. */
  title: string | null;
  /** The passage that bore on the answer. What makes a citation checkable. */
  excerpt: string | null;
  /** Similarity, never the ranking blend. Null when the backend did not send one. */
  relevance: number | null;
  /** Whether it cleared the citation cut. False means recalled but not cited —
   *  it belongs in the panel's quieter section, never as an inline chip. */
  cited: boolean;
  /** Citation number, assigned server-side so chips and panel cards agree.
   *  Null for uncited sources, which carry no number by design. */
  number: number | null;
  /** The egress log row this came from. Web only, and null when the search
   *  path did not report one — shown as absent rather than faked. */
  egressId: string | null;
  bytesSent: number | null;
  /** `user_document` | `conversation` | `generated` | `web`. */
  origin: string | null;
  /** The fact's id, for correct/forget inline in the panel. */
  recordId: string | null;
}

/** Whether a source cost the user any privacy. The one question a citation
 *  exists to answer, and what the chip colour encodes. */
export function sourceLeftDevice(source: ChatSource): boolean {
  return source.kind === 'web';
}

export type ChatEvent =
  | { type: 'token'; content: string }
  /** The model's working, from a `<think>` block, with the tags removed.
   *
   *  Its own event rather than a flag on `token` because the destinations
   *  differ: `token` accumulates into `streamingText`, which is committed to
   *  the transcript and read by `pushSpeech`. Before the backend split these,
   *  a reasoning model's working *was* the answer as far as this client knew —
   *  rendered as the reply, and spoken aloud by Kokoro in avatar mode. */
  | { type: 'reasoning'; content: string }
  | { type: 'source'; source: ChatSource }
  /** A file Zaram made. The same record Work draws a row from, so the card in
   *  the conversation and the row in Work cannot disagree about what exists. */
  | { type: 'artifact'; artifact: Artifact & { download_url: string } }
  /** Something the user needs to know that is not part of the answer — the
   *  first case is a file ingest could not read. Kept separate from `token` so
   *  it is never rendered as the model speaking, and from `error` because
   *  nothing failed in this exchange. `action` names where to go about it. */
  | { type: 'notice'; content: string; kind: string; action: string }
  /** A model has to be loaded before the reply can start. Sent *before*
   *  generation, so the orb can say why the wait is about to happen rather
   *  than after the machine has already gone quiet. `kind` is `load` (cold
   *  start, room to spare) or `swap` (something resident gets evicted). */
  | { type: 'model_load'; kind: 'load' | 'swap'; model: string; evicts: string[] }
  /** Which model is about to answer, and where it runs. Arrives *before* the
   *  first token, so the attribution is present while the reply is read rather
   *  than added underneath it afterwards.
   *
   *  `locality` is null when the backend could not resolve the model — a real
   *  answer, and the reason the field is not a boolean. Rendering "on this
   *  machine" for an unresolved model would be a confident false claim on the
   *  one thing the user is most likely to check. */
  | {
      type: 'answering';
      model: string;
      locality: 'local' | 'cloud' | null;
      provider: string | null;
      chosenBy: string | null;
    }
  | { type: 'status'; state: string }
  | { type: 'error'; message: string }
  | { type: 'done' };

export interface ChatRequest {
  text: string;
  model?: string;
  persona?: string;
  sessionId?: string;
  /** Which project this exchange belongs to (rule 7i). Undefined or empty
   *  means none is active, which scopes recall to everything and captures
   *  facts as `global` — a question asked outside a project is not about one. */
  projectId?: string | null;
  /** The knowledge domains this question is asked inside. Empty or undefined
   *  means all of them, which is the ordinary case.
   *
   *  A separate axis from `projectId`: scope is about whose work a fact
   *  belongs to, a domain is about which library the user chose to read from,
   *  and a question can sit inside both at once. Sent as a list because the
   *  backend unions them — asking across *Clients* and *Legal* means either —
   *  even though the control currently offers one at a time. */
  domainIds?: string[];
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
        // Empty means "this request expresses no preference", and the backend
        // then uses the model chosen in Settings, or its own vetted selection.
        //
        // **This was `'gemma3:latest'`** — a model name hardcoded in the
        // transport, on every message, that no control in the interface ever
        // changed. So the provider layer's selection ran, applied its residency
        // and data-policy gates, and was then overridden by a string literal
        // here. No routing decision the backend made was observable, and
        // choosing a cloud model was impossible from the interface however the
        // backend was configured.
        model: req.model ?? '',
        persona: req.persona ?? 'zaram_prime',
        session_id: req.sessionId ?? 'default',
        project_id: req.projectId ?? '',
        domain_ids: req.domainIds ?? [],
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

    case 'reasoning':
      return { type: 'reasoning', content: String(data.content ?? '') };

    case 'source': {
      // An unrecognised kind is dropped rather than coerced. The kind decides
      // whether the UI tells the user their data left the machine, so a
      // default of "memory" would quietly claim a web source stayed local —
      // the one thing this indicator must never get wrong.
      const kind = String(data.kind ?? '');
      if (kind !== 'memory' && kind !== 'document' && kind !== 'web') return null;

      const num = (value: unknown): number | null =>
        value == null || Number.isNaN(Number(value)) ? null : Number(value);

      return {
        type: 'source',
        source: {
          kind,
          url: data.url == null ? null : String(data.url),
          title: data.title == null ? null : String(data.title),
          excerpt: data.excerpt == null ? null : String(data.excerpt),
          relevance: num(data.relevance),
          // Defaults to cited only when the backend omitted the field, which
          // is the pre-citation-UI shape. An explicit false is honoured.
          cited: data.cited === undefined ? true : Boolean(data.cited),
          number: num(data.number),
          egressId: data.egress_id == null ? null : String(data.egress_id),
          bytesSent: num(data.bytes_sent),
          origin: data.origin == null ? null : String(data.origin),
          recordId: data.record_id == null ? null : String(data.record_id),
        },
      };
    }

    case 'model_load': {
      const kind = String(data.kind ?? '');
      if (kind !== 'load' && kind !== 'swap') return null;
      const model = String(data.model ?? '').trim();
      if (!model) return null;
      return {
        type: 'model_load',
        kind,
        model,
        evicts: Array.isArray(data.evicts) ? data.evicts.map(String) : [],
      };
    }

    case 'answering': {
      const model = String(data.model ?? '').trim();
      // Nothing to attribute is not an attribution. The backend sends the
      // event whether or not it could resolve a name, because the absence is
      // itself worth knowing there; the interface has nothing to draw.
      if (!model) return null;
      const locality = String(data.locality ?? '');
      return {
        type: 'answering',
        model,
        // Only the two values the backend defines. Anything else — including
        // the `null` it sends for a model it could not place — becomes null
        // and renders as no claim about where the reply came from, which is
        // the whole reason locality is three-valued on that side.
        locality: locality === 'local' || locality === 'cloud' ? locality : null,
        provider: data.provider == null ? null : String(data.provider),
        chosenBy: data.chosen_by == null ? null : String(data.chosen_by),
      };
    }

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

    case 'notice': {
      const content = String(data.content ?? '').trim();
      // A notice with nothing to say is not a notice.
      if (!content) return null;
      return {
        type: 'notice',
        content,
        kind: String(data.kind ?? ''),
        action: String(data.action ?? ''),
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
