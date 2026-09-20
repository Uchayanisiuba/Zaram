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

/** The site a cited page came from, or `null` when it is not a web page.
 *
 *  **The signal a row of citations was missing.** A web chip rendered as a
 *  globe and a number, so four sources were four identical globes — and the
 *  domain, which is the thing that actually distinguishes them, was only
 *  visible after opening the panel one at a time.
 *
 *  `www.` is dropped because it is noise on every domain that has it and
 *  absent on every domain that does not, so it carries no information and
 *  costs the width that a longer name needs. Nothing else is trimmed: a
 *  subdomain is part of who published the page, and `docs.example.com` and
 *  `blog.example.com` are not interchangeable.
 *
 *  One implementation, here, because `SourcePanel` already computed this
 *  inline and a second copy is how the panel and the chip come to disagree
 *  about what they are pointing at. */
export function sourceHost(source: ChatSource): string | null {
  return hostOf(source.url ?? '');
}

/** The same question asked of a bare URL, for callers holding one.
 *
 *  `SourcePanel` receives a `url` rather than a `ChatSource` and had its own
 *  inline copy of this. Two implementations of "which site is this" is how the
 *  panel and the chip come to name different things while pointing at the same
 *  page. */
export function hostOf(url: string): string | null {
  if (!/^https?:\/\//i.test(url)) return null;
  try {
    const host = new URL(url).host.toLowerCase();
    return host.startsWith('www.') ? host.slice(4) : host;
  } catch {
    // A malformed URL is not a domain, and inventing one from a substring
    // would put a name on a chip that links somewhere else.
    return null;
  }
}

/** How far through drawing a picture the machine is.
 *
 *  Mirrors `ImageProgress` in `imaging/contracts.py`, field for field, and
 *  carries **no time remaining** — there is no field here that could hold one,
 *  which is the point. A diffusion pipeline emits a callback per denoising
 *  step, so `step` and `percent` are counted; seconds-left would be an
 *  extrapolation from nothing at the moment it would first be shown.
 *
 *  Defined here rather than in the component that draws it: this is what the
 *  backend sends, and a transport type living inside a component is one the
 *  next surface has to import a component to read. */
export interface ImageProgress {
  step: number;
  total_steps: number;
  index: number;
  count: number;
  percent: number;
}

/** What one exchange has cost so far, in tokens.
 *
 *  **Increments, never a running total.** The backend counts where every
 *  generation actually passes and sends what that step spent; this client adds
 *  them up. Nothing derives the same number twice, which is what stops the two
 *  halves disagreeing on screen.
 *
 *  `reclaimed` is the red half and it is a real quantity rather than a
 *  decorative one: at half the window a task compacts itself and drops its
 *  oldest tool results, which removes those tokens from the next request. It is
 *  the only subtraction this product can honestly show — there are no file
 *  edits to count, since every mutative tool is out of scope until v1 ships.
 *
 *  `limit` is the model's loaded window and `measured` says whether it was read
 *  from `/api/ps` or fell back to a constant. They travel together because a
 *  surface must never quote a fallback as a fact about the user's machine —
 *  the discipline `vram_bytes` keeps by returning null rather than zero. */
export interface TokenUsage {
  added: number;
  reclaimed: number;
  limit: number | null;
  measured: boolean;
}

/** See the `timing` event. Milliseconds, or null where not measured. */
export interface ChatTiming {
  recallMs: number | null;
  planMs: number | null;
  stepsMs: number | null;
  firstTokenMs: number | null;
  generationMs: number | null;
  /** Inside tool calls, and in the model rounds after the first — the
   *  loop's share, absent on a reply that called nothing. */
  toolsMs?: number | null;
  roundsMs?: number | null;
  totalMs: number | null;
}

export type ChatEvent =
  | { type: 'token'; content: string }
  | { type: 'usage'; usage: TokenUsage }
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
  /** How far through drawing a picture the machine is.
   *
   *  Its own event rather than a `status`, because this carries a *measured
   *  fraction* — a diffusion pipeline emits a callback per denoising step, so
   *  "step 7 of 30" is counted rather than estimated. There is deliberately no
   *  time remaining in it: seconds-left is a guess until several steps have
   *  run, and a confident wrong number is worse than none. */
  | { type: 'image_progress'; progress: ImageProgress }
  /** Something the user needs to know that is not part of the answer — the
   *  first case is a file ingest could not read. Kept separate from `token` so
   *  it is never rendered as the model speaking, and from `error` because
   *  nothing failed in this exchange. `action` names where to go about it. */
  | {
      type: 'notice';
      content: string;
      kind: string;
      action: string;
      servers?: string[];
      model?: string;
      /** On the "open-project" offer: the folder named and the project's
       *  name. Declared here because the parser has sent them since F1 and
       *  the store, typed against this union, could not read what the type
       *  did not name — which is how the offer shipped with no button. */
      path?: string;
      name?: string;
    }
  /** The model's checklist for this task, whole, each time it changes.
   *  `awaitingGo` means the loop paused before its first change so the
   *  person can read it first. */
  /** `source` is `planner` for the checklist the engine builds from its own
   *  steps (search → answer) and absent for the model's own `plan`. The
   *  first is shown only while the reply is in flight — finished, it would
   *  duplicate the folded row line under the reply — while the second stays,
   *  because Project keeps it. */
  | { type: 'plan'; items: { text: string; status: string; reason?: string }[]; awaitingGo: boolean; source?: 'planner' }
  /** One tool the model asked for, and what the gate said about it.
   *
   *  **Emitted since the tool loop shipped and rendered nowhere until now.**
   *  The backend sent a verdict per call and `parseEvent` dropped it in its
   *  default case, so a reply that searched a repository and then read two
   *  files looked identical to one the model answered from memory. That is the
   *  legibility rule inverted — *"show routing decisions in plain language"* —
   *  and it is the one thing that makes an agent's working checkable.
   *
   *  `verdict` is the gate's word, not the model's: `allow` means it ran,
   *  `confirm` means it is waiting on the user, `refuse` means it will not run
   *  and `reason` says what would change that. */
  | {
      type: 'tool_call';
      server: string;
      tool: string;
      verdict: 'allow' | 'confirm' | 'refuse' | string;
      reason: string;
      /** What the call was aimed at — a path, a search phrase, a line
       *  range. *That* a tool ran is not a checkable claim and what it ran
       *  on is: `readiness.py:156-181` can be opened and "read a file"
       *  cannot. Model-written, bounded by the backend, and rendered as
       *  text rather than markup. Empty when the tool named nothing. */
      target: string;
      /** The head of what came back, bounded by the backend, or `''`. Text,
       *  never markup — it is a file's contents or a search hit. */
      output: string;
      /** A write's unified diff, bounded by the backend, or `''`. */
      diff: string;
      /** Only meaningful on a `confirm`: whether allowing this tool would
       *  let it run. False for a deletion, which keeps asking however much
       *  has been granted — so the row must not offer a button that would
       *  change nothing. Decided by the gate, never by the interface. */
      grantable?: boolean;
      /** The commit a write made, or `''`. What `Revert` reverses. */
      commit: string;
      /** A screenshot `look_at_app` took — a file name in the project's
       *  screens folder — or `''`. */
      image: string;
      /** The URL an app was started on, or `''`. */
      appUrl: string;
      /** The mark this call's egress entries carry, or `''`. */
      stepId: string;
    }
  /** A plan step has begun — a web search, a page read, a drawing — in the
   *  words a row prints while it runs (`doing`) and after (`done`). Yielded
   *  by the backend since 19 September 2026; the events existed from the
   *  first day and reached nothing. A step with no `doing` is one the
   *  backend decided gets no row, and is dropped here for the same reason:
   *  a verb on a status row is a claim, and a guessed one is an invented
   *  value. */
  | {
      type: 'step_start';
      stepId: string;
      capability: string;
      doing: string;
      done: string;
      target: string;
    }
  /** The same step, finished. `detail` is the one thing said after the verb
   *  ("4 results", or what went wrong); `seconds` is measured or null. A
   *  completion with no start — recall, which reports after the fact — is
   *  a row on its own. */
  /** Where the time went in this reply, in milliseconds, measured by the
   *  backend — one per reply, after the text. Any phase that did not happen
   *  is null, never zero; a plain reply has no steps and a failed one no
   *  first token. The instrument behind "Zaram is slow sometimes". */
  | { type: 'timing'; timing: ChatTiming }
  | {
      type: 'step_complete';
      stepId: string;
      capability: string;
      success: boolean;
      done: string;
      target: string;
      detail: string;
      seconds: number | null;
    }
  /** What the reply is waiting for, sent *before* generation so the orb can
   *  say why rather than going quiet and letting the user guess.
   *
   *  Four kinds, matching `SwapPlan`: `resident` (already loaded, nothing to
   *  wait for), `load` (cold start with room to spare), `swap` (something
   *  resident gets evicted) and `oversized` (larger than the whole budget). */
  | {
      type: 'model_load';
      kind: 'resident' | 'load' | 'swap' | 'oversized';
      model: string;
      evicts: string[];
    }
  /** The transcript this reply is being written into.
   *
   *  Sent only when the backend *started* one — the client already knows the
   *  id it sent, and needs to be told the id it did not. Arrives before the
   *  first token, so an interrupted stream still leaves a conversation that
   *  can be reopened rather than a thread with no name. */
  | { type: 'conversation'; conversationId: string; title: string }
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
  /** Files attached to this message, by id from `POST /chat/attachments`.
   *
   *  A third axis, and the narrowest. A project says whose work this is, a
   *  domain says which library to read from, and this says "the document in
   *  front of us right now" - working state that never enters the Spine
   *  unless the user separately decides it should (rule 7d).
   *
   *  Ids rather than text, deliberately. How much of a document fits is a
   *  question about the answering model's context budget, which is known in
   *  the backend and not here; inlining the text would mean choosing on
   *  behalf of a limit this side cannot see.
   */
  attachmentIds?: string[];
  /** Which stored conversation this message continues, or omitted to begin one.
   *
   *  **Not `sessionId`, and the two must not be merged.** A session is a page
   *  load — the frontend mints one per mount. A conversation is a thing a
   *  person comes back to next week. Keying transcripts on the session would
   *  file every reload as a new conversation and every restart as amnesia. */
  conversationId?: string | null;
  /** Pick up a tool loop that stopped with work left, for this session.
   *
   *  The user's **Continue**. `text` is not a new question when this is set —
   *  the backend resumes from the results the task had already gathered and
   *  ignores it. Sent per session, because that is where the stopped loop is
   *  parked: it does not survive a restart, and the notice that offers it
   *  says so rather than implying a durability it does not have. */
  continueTask?: boolean;
  /** The person pressed Go on the plan the task paused to show them. Only
   *  meaningful with `continueTask`. */
  approvePlan?: boolean;
  /** Which rung of Go: `ask` keeps the confirmation before each change,
   *  `full` lets this one plan run without stopping. Chosen for the plan on
   *  screen and never stored — see `PlanCard`. */
  approveLevel?: 'ask' | 'full';
  /** **Revise**: `text` is a correction to an earlier reply, and this is
   *  that reply with the question it answered. The backend composes one
   *  prompt from the three and sends it down the ordinary path — recall,
   *  tools, the gate — so a revision is one exchange like any other. The
   *  reply travels here rather than being re-read from a store (rule 7d).
   *  `docs/AGENT-UX.md`, *Revise*. */
  revise?: { question: string; reply: string };
  /** Which unfinished task to pick up, or omitted for the obvious one.
   *
   *  Named when the user chose it from the list in Project; omitted when they
   *  pressed Continue under a reply, where "the one that just stopped" is the
   *  only thing it could mean. The backend resolves the empty case from this
   *  session and then from this project, which is what makes a task left days
   *  ago findable from a session that shares no id with it. */
  planId?: string;
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
        attachment_ids: req.attachmentIds ?? [],
        conversation_id: req.conversationId ?? '',
        continue_task: req.continueTask ?? false,
        plan_id: req.planId ?? '',
        approve_plan: req.approvePlan ?? false,
        approve_level: req.approveLevel ?? 'ask',
        ...(req.revise ? { revise: { question: req.revise.question, reply: req.revise.reply } } : {}),
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

    case 'usage': {
      // Coerced through Number and floored at zero on both halves. A negative
      // `added` arriving from anywhere would render as a green plus in front of
      // a minus sign, and the sign is meant to live in the field rather than in
      // the value.
      const count = (value: unknown): number => {
        const n = Number(value ?? 0);
        return Number.isFinite(n) && n > 0 ? Math.round(n) : 0;
      };
      // `limit` stays null unless it is a real positive number. Zero is not a
      // small window, it is an unreadable one, and a bar drawn against it would
      // report every conversation as full.
      const rawLimit = Number(data.limit ?? 0);
      const limit = Number.isFinite(rawLimit) && rawLimit > 0 ? Math.round(rawLimit) : null;
      return {
        type: 'usage',
        usage: {
          added: count(data.added),
          reclaimed: count(data.reclaimed),
          limit,
          measured: Boolean(data.measured),
        },
      };
    }

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

    case 'conversation': {
      const conversationId = String(data.conversation_id ?? '').trim();
      if (!conversationId) return null;
      return {
        type: 'conversation',
        conversationId,
        title: String(data.title ?? ''),
      };
    }

    case 'model_load': {
      const kind = String(data.kind ?? '');
      // **`SwapPlan` has four kinds and this parser has now dropped two of
      // them, one at a time, for the same reason.** `oversized` went first.
      // The comment that replaced it asserted `resident` "is deliberately
      // never sent" — it was not deliberate and it was not true: the backend
      // sends it on every reply whose model is already loaded, and discarding
      // it here is what produced **Warming up** under a model that had not
      // moved. `chatStore` has a `resident` branch whose whole job is to
      // cancel that guess, and it was unreachable.
      //
      // Measured in the running app, 31 August 2026: the backend emitted
      // `{"kind": "resident"}` for `Qwen3.8-27B-exl3-2.20bpw` on the third
      // consecutive message and the orb still read "Warming up · Starting the
      // local model."
      //
      // So the list is kept in step with `SwapPlan` rather than with whichever
      // kinds someone happened to need, and a kind Zaram does not recognise
      // is still dropped rather than coerced.
      if (
        kind !== 'resident' &&
        kind !== 'load' &&
        kind !== 'swap' &&
        kind !== 'oversized'
      ) {
        return null;
      }
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

    case 'image_progress': {
      // Every field is read as a number and none is defaulted to something
      // plausible: a bar drawn from an invented denominator is a rendered
      // value nobody measured, which is the thing the UI principles forbid.
      // A payload that cannot supply them is dropped instead.
      const step = Number(data.step);
      const total = Number(data.total_steps);
      const percent = Number(data.percent);
      if (!Number.isFinite(step) || !Number.isFinite(total) || total < 1) return null;
      if (!Number.isFinite(percent)) return null;
      return {
        type: 'image_progress',
        progress: {
          step,
          total_steps: total,
          index: Number(data.index) || 1,
          count: Number(data.count) || 1,
          percent: Math.max(0, Math.min(100, Math.round(percent))),
        },
      };
    }

    case 'notice': {
      const content = String(data.content ?? '').trim();
      // A notice with nothing to say is not a notice.
      if (!content) return null;
      // `servers` rides on the "tools" notice: which servers were offered
      // for this reply. Read as strings only — a stranger's server name is
      // rendered nowhere and compared against 'code' and nothing else.
      const servers = Array.isArray(data.servers)
        ? (data.servers as unknown[]).filter((x): x is string => typeof x === 'string')
        : undefined;
      // `model` rides on the "cloud" offer: which model the button would
      // ask. A string or nothing; it is sent back as the per-message
      // override and rendered nowhere as markup.
      const model = typeof data.model === 'string' && data.model ? data.model : undefined;
      // `path` and `name` ride on the "open-project" offer: the folder the
      // person named and the name the project would get. Strings, rendered
      // as text, sent back only to `POST /projects`.
      const path = typeof data.path === 'string' && data.path ? data.path : undefined;
      const name = typeof data.name === 'string' && data.name ? data.name : undefined;
      return {
        type: 'notice',
        content,
        kind: String(data.kind ?? ''),
        action: String(data.action ?? ''),
        ...(servers && servers.length > 0 ? { servers } : {}),
        ...(model ? { model } : {}),
        ...(path ? { path } : {}),
        ...(name ? { name } : {}),
      };
    }

    case 'plan': {
      const raw = Array.isArray(data.items) ? (data.items as unknown[]) : [];
      const items = raw
        .filter((x): x is Record<string, unknown> => typeof x === 'object' && x !== null)
        .map((x) => ({
          text: String(x.text ?? ''),
          status: String(x.status ?? 'todo'),
          ...(typeof x.reason === 'string' && x.reason ? { reason: x.reason } : {}),
        }))
        .filter((x) => x.text);
      return {
        type: 'plan',
        items,
        awaitingGo: data.awaiting_go === true,
        ...(data.source === 'planner' ? { source: 'planner' as const } : {}),
      };
    }

    case 'tool_call':
      return {
        type: 'tool_call',
        server: String(data.server ?? ''),
        tool: String(data.tool ?? ''),
        verdict: String(data.verdict ?? ''),
        reason: String(data.reason ?? ''),
        target: String(data.target ?? ''),
        output: typeof data.output === 'string' ? data.output : '',
        diff: typeof data.diff === 'string' ? data.diff : '',
        commit: typeof data.commit === 'string' ? data.commit : '',
        image: typeof data.image === 'string' ? data.image : '',
        appUrl: typeof data.app_url === 'string' ? data.app_url : '',
        grantable: data.grantable === true,
        stepId: typeof data.step_id === 'string' ? data.step_id : '',
      };

    case 'step_start':
      return {
        type: 'step_start',
        stepId: String(data.step_id ?? ''),
        capability: String(data.capability_id ?? ''),
        doing: String(data.doing ?? ''),
        done: String(data.done ?? ''),
        target: String(data.target ?? ''),
      };

    case 'step_complete':
      return {
        type: 'step_complete',
        stepId: String(data.step_id ?? ''),
        capability: String(data.capability_id ?? ''),
        success: data.success !== false,
        done: String(data.done ?? ''),
        target: String(data.target ?? ''),
        detail: String(data.detail ?? ''),
        seconds: typeof data.seconds === 'number' ? data.seconds : null,
      };

    case 'timing': {
      const ms = (value: unknown): number | null =>
        typeof value === 'number' && Number.isFinite(value) && value >= 0 ? Math.round(value) : null;
      return {
        type: 'timing',
        timing: {
          recallMs: ms(data.recall_ms),
          planMs: ms(data.plan_ms),
          stepsMs: ms(data.steps_ms),
          firstTokenMs: ms(data.first_token_ms),
          generationMs: ms(data.generation_ms),
          toolsMs: ms(data.tools_ms),
          roundsMs: ms(data.rounds_ms),
          totalMs: ms(data.total_ms),
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
      // start, plan_start, plan_complete and similar are internal execution
      // detail. Ignored rather than treated as an error. (`step_start` and
      // `step_complete` were listed here for a year and are rows now.)
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
