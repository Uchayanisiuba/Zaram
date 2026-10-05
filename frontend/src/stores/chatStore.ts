/**
 * Chat state — messages, their sources, and the state of the connection.
 *
 * This store is the seam between transport and interface. The current chat
 * surface is temporary and will be replaced when the UI spec lands; the new one
 * subscribes to this same store and nothing below it changes.
 *
 * Streaming state lives here rather than in a component on purpose. When it was
 * component-local, navigating away mid-reply cancelled the reply. Holding it in
 * a store is also what makes the conversation-as-persistent-shell change
 * possible later.
 */
import { create } from 'zustand';
import { fetchConversation } from '@/services/conversationsClient';
import {
  streamChat,
  ChatTransportError,
  type ChatSource,
  type ChatRequest,
  type ImageProgress,
  type TokenUsage,
  type ChatTiming,
} from '@/services/chatClient';
import { listArtifacts, type Artifact } from '@/services/artifactsClient';
import { stripCitationMarkers } from '@/lib/markers';
import { useSystemStore } from '@/stores/systemStore';
import { useSessionStatusStore } from '@/stores/sessionStatusStore';
import { useEmbodimentStore } from '@/stores/embodimentStore';
import { useSpeechStore } from '@/stores/speechStore';

/** How long a request may produce nothing before we call it a cold start.
 *  A loaded local model begins emitting well inside this; a cold one does not. */
const WARMING_AFTER_MS = 2500;

/** A file that went with a question, as the message shows it.
 *
 *  Name and kind only — the text was extracted on the backend and the id is
 *  what a follow-up re-sends. The chip on the message is the record that the
 *  file went *with this question*, which is where every other assistant
 *  puts it and where a person looks for it. */
export interface SentAttachment {
  id: string;
  name: string;
  kind: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  /** Files sent with a question. On user messages only; usually empty. */
  attachments?: SentAttachment[];
  /** Set when this question was a correction to an earlier reply — the
   *  question that reply answered, so the transcript can say which. The
   *  earlier reply stays where it was, cards and all: nothing is replaced
   *  in place and nothing branches. `docs/AGENT-UX.md`, *Revise*. */
  revises?: { question: string };
  /** Provenance for an assistant reply: what the answer was grounded in.
   *  Empty means the model answered from its own knowledge, which is a
   *  meaningful state and must not be confused with "sources not loaded". */
  sources: ChatSource[];
  /** Files made during this reply, shown as cards beneath it. Usually empty:
   *  most replies produce no file, and an empty array is the ordinary case
   *  rather than a missing one. */
  artifacts: Artifact[];
  /** Things Zaram needs to say that are not part of the answer — the first is
   *  a file ingest could not read. Kept off `text` deliberately: rendering it
   *  as the reply would attribute it to the model, and it is not something the
   *  model said. */
  notices: ChatNotice[];
  /** Which tools the model used to reach this answer, in the order it used
   *  them, with the gate's verdict on each. Usually empty — most replies call
   *  nothing, and that is the ordinary case rather than a missing one. */
  toolCalls?: ChatToolCall[];
  /** The checklist the model kept for this reply, whole, as it last stood. */
  plan?: ChatPlan;
  timestamp: number;
  /** Which model answered this, and where it ran.
   *
   *  Kept per message rather than as one banner for the conversation, because
   *  the model can change between replies — that is the product's argument, not
   *  an edge case, and a single label would be wrong the moment it happened. */
  answeredBy?: ChatAttribution | null;
  /** What the model worked through before answering, if it showed its
   *  working. Kept on the message so it survives the reply rather than
   *  vanishing when the stream closes — the reason a claim was made is worth
   *  more after the answer than during it. Never part of `text`, so it is
   *  never spoken and never committed as something the model said. */
  reasoning?: string;
  /** Where the time went, measured by the backend. Kept on the message so
   *  a slow reply can be read afterwards: which phase, not just how long. */
  timing?: ChatTiming;
  /** Set when this reply failed or was cut short. Any text already received is
   *  kept — a partial answer is still worth showing, provided it is labelled. */
  error?: string;
}

/** Who answered, from what routing resolved — never inferred here.
 *
 *  `locality` is null when the backend could not place the model. Rendering
 *  "on this machine" for that case would be a confident false claim about the
 *  one thing the user is most likely to check, so the interface says nothing
 *  instead. */
export interface ChatAttribution {
  model: string;
  locality: 'local' | 'cloud' | null;
  provider: string | null;
  chosenBy: string | null;
}

export interface ChatNotice {
  content: string;
  kind: string;
  /** Where to go about it, e.g. "knowledge". Empty when there is nowhere. */
  action: string;
  /** On the "tools" notice: which servers were offered for this reply. */
  servers?: string[];
  /** On the "cloud" offer: the model to ask this step again with. */
  model?: string;
  /** On the "open-project" offer: the folder named and the project's name. */
  path?: string;
  name?: string;
}

/** One line of the model's checklist. See `PlanCard`. */
export interface ChatPlanItem {
  text: string;
  status: string;
  reason?: string;
}

/** The checklist as last sent, and whether it is waiting on Go. */
export interface ChatPlan {
  items: ChatPlanItem[];
  awaitingGo: boolean;
}

/** One tool the model asked for, and the gate's verdict on it.
 *
 *  Kept on the message rather than only in the stream, because the working is
 *  worth more *after* the answer than during it — the same reason `reasoning`
 *  is kept. A reply that says "it returns 9137000000" is a claim; the same
 *  reply with `search_code` and `read_lines` under it is a checkable one. */
export interface ChatToolCall {
  server: string;
  tool: string;
  /** `allow` — it ran. `confirm` — waiting on the user. `refuse` — it did not. */
  verdict: string;
  reason: string;
  /** What the call was aimed at, or `''`. See `ChatEvent`'s note. */
  target: string;
  /** The head of what the tool returned, or `''` when it did not run.
   *  Bounded by the backend; rendered as text in a pane of its own. */
  output?: string;
  /** A write's unified diff, when the call changed a file. Rendered as a
   *  `ChangeCard` that is never folded, with the commit it can revert. */
  diff?: string;
  commit?: string;
  /** A screenshot the call produced, and the URL an app started on. Rendered
   *  by `AppCard`, never folded. */
  image?: string;
  appUrl?: string;
  /** On a `confirm`: whether allowing this tool would settle it. See
   *  `ChatEvent`. */
  grantable?: boolean;
  /** Which of the open project’s switches covers this tool — `shell`,
   *  `drives`, `runs`, `writes` — so the permission card can offer *for
   *  this project* as a press rather than a sentence pointing at
   *  Settings. Absent when the server has no opinion, and the card then
   *  shows one rung fewer rather than a control that settles nothing. */
  grantScope?: string;
  /** On a `confirm`: the task this call was parked on, and whether *Run
   *  this once* may be offered. See `ChatEvent`. */
  heldTask?: string;
  once?: boolean;
  /** **A plan step rather than a tool call** — a web search, a page read,
   *  a drawing, recall — rendered on the same row so there is one place the
   *  work lives. `label` is the past-tense phrase ("Searched the web"),
   *  `doing` the present one shown while `verdict` is `running`, and
   *  `stepId` is what the completion event settles. Absent on a tool call,
   *  whose row prints its server and name instead. */
  label?: string;
  doing?: string;
  stepId?: string;
  /** **Which checklist step this call was made for**, by index, or absent.
   *
   *  What turns a run of rows into a record of work: the card nests each call
   *  under the step it belongs to, so 'Add the game loop' carries the two
   *  calls that did it rather than sitting above twenty anonymous rows. The
   *  backend decides it from the checklist at the moment of the call; nothing
   *  here recomputes it, because the model rewrites the plan as it goes and a
   *  second opinion could disagree with the one that was true at the time.
   *
   *  Absent on a reply with no plan, which is most of them, and absent once
   *  every step is ticked — work done after the last claim belongs to none. */
  planStep?: number;
  /** How long a finished step took, measured by the backend, in seconds. */
  seconds?: number | null;
  /** How much of the reply's text (markers stripped) had arrived when this
   *  row did — where it sits between the paragraphs. See `Interleaved`.
   *  Absent on a history restored from before 19 September 2026. */
  at?: number;
}

interface ChatState {
  messages: ChatMessage[];
  /** Text arriving for the in-flight reply. Not yet committed to messages. */
  streamingText: string;
  /** The model's working so far, for the panel above the reply. */
  streamingReasoning: string;
  /** When the model began thinking for the reply in flight, or `null`. Read by
   *  the offer to skip thinking, which appears only once this is old. */
  streamingReasoningSince: number | null;
  /** Sources for the in-flight reply. They arrive before the tokens do. */
  streamingSources: ChatSource[];
  /** Files made during the in-flight reply. Arrive after the tokens, since a
   *  document is written from the answer rather than alongside it. */
  streamingArtifacts: Artifact[];
  /** Notices for the in-flight reply. Arrive last, after the answer. */
  streamingNotices: ChatNotice[];
  /** Tools called by the reply in flight, so the working appears as it happens
   *  rather than all at once when the answer lands. On a tool-using reply the
   *  generation is buffered — the marker cannot be recognised mid-token — so
   *  these are the only thing on screen while the model reads. */
  streamingToolCalls: ChatToolCall[];
  /** The checklist as it stands while the reply is in flight. */
  streamingPlan: ChatPlan | null;
  /** How far through drawing a picture the machine is, or `null`.
   *
   *  Held rather than accumulated: only the latest matters, and keeping the
   *  history of a bar would be a list of numbers nobody reads twice. Cleared
   *  when the artifact arrives, because at that point the picture *is* the
   *  progress report — a bar left at 100% beside the finished image is a
   *  second claim about the same thing. */
  streamingImageProgress: ImageProgress | null;
  /** Who is answering the in-flight reply. Arrives before the first token, so
   *  the attribution is on screen while the answer is being read rather than
   *  appearing under it once the reading is done. */
  streamingAnsweredBy: ChatAttribution | null;
  /** What the exchange in flight has cost, in tokens.
   *
   *  **Per turn, and it survives the turn.** Reset when a message is sent and
   *  accumulated from the increments the backend emits, so during a reply it
   *  counts up and afterwards it stands as what that exchange cost. Clearing it
   *  on `done` would blank the number at the exact moment somebody looks at it.
   *
   *  Accumulated here rather than totalled by the backend because only one of
   *  the two knows what a *turn* is: the backend counts a step, the surface
   *  knows which steps belong to the message on screen. Deriving the same
   *  figure in both places is how two counters end up disagreeing. */
  turnUsage: TokenUsage;
  isStreaming: boolean;
  /** Connection-level failure, as opposed to a failure within one reply. */
  connectionError: string | null;
  sessionId: string;
  /** The stored transcript this conversation is being written into.
   *
   *  Null until the backend names one, which it does on the first reply of a
   *  new conversation. **Distinct from `sessionId`, which is a page load.**
   *  Keying transcripts on the session would file every reload as a new
   *  conversation and every restart as amnesia — the behaviour the store
   *  exists to end. */
  conversationId: string | null;
  /** The project this conversation belongs to, or null for none (rule 7i).
   *
   *  Scopes recall to this project plus global, and captures facts under it so
   *  `recalled_in` can accumulate the evidence that later argues for promoting
   *  one to global. Null is a real answer, not a missing one. */
  projectId: string | null;
  /** The knowledge domains questions are asked inside. Empty means all of
   *  them, which is unrestricted and is the ordinary case.
   *
   *  An array even though the control offers one at a time, because the
   *  backend unions them and the wire format is already a list — so multiple
   *  selection is a control change later, not a protocol change. */
  domainIds: string[];

  send: (text: string, opts?: Partial<ChatRequest>, attached?: SentAttachment[]) => Promise<void>;
  /** Change the active project. Survives across replies; cleared only by the
   *  user, never inferred from what was asked. */
  setProject: (projectId: string | null) => void;
  /** Change which domains questions are asked inside. Same posture as the
   *  project: a working context that survives replies and is cleared only by
   *  the user. */
  setDomains: (domainIds: string[]) => void;
  cancel: () => void;
  /** Send several requests one after another, each when the last has ended.
   *
   *  Built for *Continue every unfinished task in this project*. It stops the
   *  moment a turn ends waiting on the person -- a plan held for Go, a
   *  permission card, an error -- or the person presses Stop, because running
   *  on would answer a question they have not yet been asked: the next task
   *  would proceed under a decision nobody made. */
  runInOrder: (steps: { text: string; opts?: Partial<ChatRequest> }[]) => Promise<void>;
  /** Give up on a reply that is still thinking and ask the same question again
   *  with thinking off, for this message only. Does nothing unless a reply is
   *  in flight. The abandoned attempt is discarded whole — it never commits a
   *  reasoning-only message to the transcript. */
  answerWithoutThinking: () => Promise<void>;
  /** A held tool has just been allowed, so ask the question again — now, even
   *  if the reply that said "needs your say-so" is still being written.
   *
   *  The permission card appears the moment the gate holds the call, and the
   *  reply goes on to answer *without* the tool, which on a local model takes
   *  as long as any other reply. `send` refuses while a reply is streaming, so
   *  an Allow pressed in that window saved the grant and then asked nothing:
   *  the screen kept the refusal and the person read it as the press doing
   *  nothing. The in-flight attempt is discarded whole, as
   *  `answerWithoutThinking` does, because an answer written without the tool
   *  is not worth finishing once the tool is permitted. */
  askAgainAfterAllowing: (resume?: AllowedResume) => Promise<void>;
  clear: () => void;
  /** Reopen a stored conversation, replacing what is on screen.
   *
   *  The transcript comes back as text, attribution, and what the reply
   *  *did* — its checklist, its tool calls, and the files it produced.
   *
   *  **Citations are restored as history — changed 4 October 2026.** A
   *  citation is a claim that *this* answer used *that* fact, and the fact may
   *  since have been corrected or deleted (rule 4), so yesterday's citation
   *  cannot be drawn as if it still held. The backend keeps only the
   *  *reference* and resolves it against the Spine when the conversation is
   *  reopened (`conversations/citations.py`); each arrives saying whether its
   *  fact is live, corrected, deleted or could not be checked. Reasoning stays
   *  out: it is the model's working, never part of what it said.
   *
   *  **The rest used to be excluded by the same sentence, and should not have
   *  been — corrected 3 October 2026.** The argument above is about claims
   *  that can stop being true. A tool ran or it did not; a checklist had the
   *  steps it had; a file is on disk. Nothing about them goes stale, so there
   *  was never a reason to drop them — they were simply never written down.
   *  See `conversations/turn_notes.py`.
   *
   */
  resumeConversation: (conversationId: string) => Promise<void>;
}

/** Where the active project is remembered between launches.
 *
 *  Persisted because it is a working context rather than a per-message choice:
 *  someone who spent yesterday on Harbour Lane is still on it this morning, and
 *  making them re-select it every launch is how facts end up captured under the
 *  wrong scope — or under none. */
/** The files a conversation produced, by id.
 *
 *  Read fresh from the artifact store rather than copied into the transcript
 *  when the reply was written: a file can be renamed, re-filed or moved to
 *  trash afterwards, and a transcript holding its own copy would be a second
 *  place that disagrees about where somebody's file is.
 *
 *  **Never fatal.** A transcript is text and must open even when this does
 *  not answer — losing the file cards is a smaller failure than refusing to
 *  show somebody their conversation, and an empty map renders exactly as a
 *  reply that made no files. */
async function artifactsForConversation(conversationId: string): Promise<Map<string, Artifact>> {
  try {
    const listing = await listArtifacts({ conversationId });
    return new Map((listing.artifacts ?? []).map((a) => [a.id, a]));
  } catch {
    return new Map();
  }
}

const PROJECT_KEY = 'zaram.activeProject';

function loadProject(): string | null {
  try {
    return localStorage.getItem(PROJECT_KEY) || null;
  } catch {
    // Private mode, or storage disabled. No project is a correct fallback.
    return null;
  }
}

/** Where the chosen knowledge domains are remembered between launches.
 *
 *  Persisted for the same reason the project is — it is a working context, not
 *  a per-message choice. The fallback on any failure is the *empty* list, which
 *  means unrestricted: a storage error must never silently narrow what Zaram is
 *  allowed to read, because the user would see thinner answers with nothing on
 *  screen explaining why. */
const DOMAINS_KEY = 'zaram.activeDomains';

function loadDomains(): string[] {
  try {
    const raw = localStorage.getItem(DOMAINS_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((d): d is string => typeof d === 'string') : [];
  } catch {
    return [];
  }
}

/** Cancels the in-flight request. Module-level so `cancel()` can reach it
 *  without putting a non-serialisable object in the store. */
let inFlight: AbortController | null = null;
/** Bumped by every Stop, so a queue can tell it was the person who ended a turn. */
let cancelEpoch = 0;

/** The arguments of the last `send`, so "answer without thinking" can ask the
 *  same question again exactly as it was asked — same project, same domains,
 *  same attachments. Module-level for the reason `inFlight` is. */
let lastSend: { text: string; opts: Partial<ChatRequest>; attached: SentAttachment[] } | null = null;

/** Attempts abandoned on purpose, as opposed to cancelled.
 *
 *  An abandoned `send` finishes *after* its replacement has started — an abort
 *  is observed on a later tick — so its cleanup would commit a reasoning-only
 *  message to the transcript and then switch the orb to idle and stop the
 *  speech queue, all under the new request. A discarded attempt does none of
 *  that: it touches nothing shared. */
const discarded = new WeakSet<AbortController>();

const newId = () =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

/** One readable line for a thrown value, whatever kind of thing it is.
 *
 * `String(err)` on a plain object yields "[object Object]", which is the same
 * dead end as the sentence this replaced. A real `Error` already knows how to
 * name itself, and its `name` is kept because "RangeError" and "TypeError"
 * point at different bugs — the first is what a reply too large for the
 * model's window looks like from in here.
 */
function describeThrown(err: unknown): string {
  if (err instanceof Error) {
    return err.message ? `${err.name}: ${err.message}` : err.name;
  }
  if (typeof err === 'string' && err.trim()) return err.trim();
  try {
    return JSON.stringify(err) ?? 'an error with nothing to say for itself';
  } catch {
    return 'an error with nothing to say for itself';
  }
}

/** Abandon the reply in flight and take its question back off the transcript.
 *
 *  The question goes back in when it is sent again; leaving it here would show
 *  it twice. Only the one this attempt added — never an earlier turn. */
function abandonTheAttempt(
  set: (partial: Partial<ChatState> | ((s: ChatState) => Partial<ChatState>)) => void,
  question: string | null,
): void {
  if (inFlight) {
    discarded.add(inFlight);
    inFlight.abort();
    inFlight = null;
  }
  set((s) => {
    const tail = s.messages[s.messages.length - 1];
    const dropTail = question !== null && tail?.role === 'user' && tail.text === question;
    return {
      messages: dropTail ? s.messages.slice(0, -1) : s.messages,
      streamingText: '',
      streamingReasoning: '',
      streamingReasoningSince: null,
      streamingSources: [],
      streamingNotices: [],
      streamingToolCalls: [],
      streamingPlan: null,
      streamingImageProgress: null,
      streamingAnsweredBy: null,
      isStreaming: false,
    };
  });
}

/** What an answer on the permission card carries on from: the task the held
 *  call was parked on, and whether the person said yes to that one call. */
export interface AllowedResume {
  planId: string;
  runHeld: boolean;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  streamingText: '',
  streamingReasoning: '',
  streamingReasoningSince: null,
  streamingSources: [],
  streamingArtifacts: [],
  streamingNotices: [],
  streamingToolCalls: [],
  streamingPlan: null,
  streamingImageProgress: null,
  streamingAnsweredBy: null,
  turnUsage: { added: 0, reclaimed: 0, limit: null, measured: false },
  isStreaming: false,
  connectionError: null,
  sessionId: `session-${newId()}`,
  conversationId: null,
  projectId: loadProject(),
  domainIds: loadDomains(),

  setProject: (projectId) => {
    set({ projectId });
    try {
      if (projectId) localStorage.setItem(PROJECT_KEY, projectId);
      else localStorage.removeItem(PROJECT_KEY);
    } catch {
      // The scope still applies to this session; only persistence is lost.
    }
  },

  setDomains: (domainIds) => {
    set({ domainIds });
    try {
      if (domainIds.length) localStorage.setItem(DOMAINS_KEY, JSON.stringify(domainIds));
      else localStorage.removeItem(DOMAINS_KEY);
    } catch {
      // The narrowing still applies to this session; only persistence is lost.
    }
  },

  send: async (text, opts = {}, attached = []) => {
    const trimmed = text.trim();
    if (!trimmed || get().isStreaming) return;

    inFlight?.abort();
    inFlight = new AbortController();
    const mine = inFlight;
    lastSend = { text: trimmed, opts, attached };

    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: newId(),
          role: 'user',
          text: trimmed,
          ...(attached.length > 0 ? { attachments: attached } : {}),
          ...(opts.revise ? { revises: { question: opts.revise.question } } : {}),
          sources: [],
          artifacts: [],
          notices: [],
          timestamp: Date.now(),
        },
      ],
      streamingText: '',
      streamingReasoning: '',
      streamingReasoningSince: null,
      streamingSources: [],
      streamingAnsweredBy: null,
      turnUsage: { added: 0, reclaimed: 0, limit: null, measured: false },
      isStreaming: true,
      connectionError: null,
    }));

    // The persistent bar names the conversation and reports what went into the
    // reply. The topic is the first thing the user said, because that is the
    // only description of the conversation that exists without asking a model
    // for one. Recall count resets to null — "not known yet" — rather than to
    // 0, which would claim nothing was recalled before anything was tried.
    const status = useSessionStatusStore.getState();
    if (!status.topic) status.setTopic(trimmed);
    status.setRecallCount(null);

    // Speech follows the renderer: the avatar speaks, the orb stays silent.
    //
    // That makes the toggle mean something rather than being a skin, and it is
    // a decision the user has already made — so it needs no second setting,
    // which is the "never make the user choose in advance" rule applied to a
    // preference they expressed by choosing a face.
    //
    // Decided once, here, rather than read again at the end: a renderer change
    // mid-reply would otherwise leave a queue open with nothing to close it, or
    // start speaking a reply whose first half was never queued.
    const speaking = useEmbodimentStore.getState().renderer === 'avatar';
    // Opened before the first token so the queue exists when one arrives. It
    // synthesises nothing until something is pushed.
    if (speaking) useSpeechStore.getState().beginSpeech();

    // Accumulated locally as well as in the store: on failure we still need the
    // partial text, and reading it back out of the store mid-teardown is racy.
    let text_ = '';
    const sources: ChatSource[] = [];
    const artifacts: Artifact[] = [];
    const notices: ChatNotice[] = [];
    const toolCalls: ChatToolCall[] = [];
    let plan: ChatPlan | null = null;
    const seen = new Set<string>();
    let replyError: string | undefined;
    let answeredBy: ChatAttribution | null = null;
    let reasoning_ = '';
    let timing_: ChatTiming | undefined;
    let planIsLiveOnly = false;

    // A cold local model can take many seconds to load before its first token.
    // Left unexplained that silence reads as a hang, so it is named instead.
    const system = useSystemStore.getState();
    system.setActivity('thinking');
    let sawFirstToken = false;
    const warmingTimer = setTimeout(() => {
      if (!sawFirstToken) useSystemStore.getState().setActivity('warming');
    }, WARMING_AFTER_MS);
    const settleActivity = (a: 'idle' | 'thinking') => {
      clearTimeout(warmingTimer);
      const sys = useSystemStore.getState();
      // Leaving a swap has to move the orb as well as the label. `setActivity`
      // clears the model name but knows nothing about the renderer, so calling
      // it here would leave the orb dimmed and slate-grey while tokens stream
      // underneath it — the swap indicator outliving the swap.
      if (sys.activity === 'swapping') sys.endModelSwap(a === 'idle' ? 'idle' : 'thinking');
      else sys.setActivity(a);
    };

    try {
      for await (const event of streamChat(
        // `opts` spreads last so a caller can override the project for one
        // message, but the store's value is the default — the scope is a
        // working context, not something each call site decides afresh.
        {
          text: trimmed,
          sessionId: get().sessionId,
          conversationId: get().conversationId,
          projectId: get().projectId,
          domainIds: get().domainIds,
          ...opts,
        },
        inFlight.signal,
      )) {
        switch (event.type) {
          case 'token':
            if (!sawFirstToken) {
              sawFirstToken = true;
              // Output has started, so whatever warming was happening is done.
              settleActivity('thinking');
            }
            text_ += event.content;
            set({ streamingText: text_ });
            // Speech keeps pace with the text instead of waiting for it.
            // `pushSpeech` queues only sentences that will not change again, so
            // this is safe to call on every token and the first one is being
            // synthesised while the model is still writing the third.
            if (speaking) useSpeechStore.getState().pushSpeech(text_);
            break;

          case 'reasoning':
            // Deliberately not fed to `pushSpeech`. Speech reads the answer,
            // and reading a model's working aloud is what this event exists
            // to stop. It also never joins `text_`, so it cannot be committed
            // to the transcript as something the model said.
            if (!reasoning_) set({ streamingReasoningSince: Date.now() });
            reasoning_ += event.content;
            set({ streamingReasoning: reasoning_ });
            break;

          case 'source': {
            // The backend already de-duplicates, but a UI that shows the same
            // citation twice looks broken, so do not rely on that.
            const key = event.source.url ?? event.source.title ?? '';
            if (key && !seen.has(key)) {
              seen.add(key);
              sources.push(event.source);
              set({ streamingSources: [...sources] });
            }
            break;
          }

          case 'artifact': {
            // A file was written. It appears under the reply that produced it
            // and, from the same record, as a row in Work.
            artifacts.push(event.artifact);
            // The picture replaces its own progress bar. Leaving the bar up
            // beside the finished image would be two claims about one thing,
            // and the second one is stale the moment the first arrives.
            set({ streamingArtifacts: [...artifacts], streamingImageProgress: null });
            break;
          }

          case 'usage': {
            // Summed, because the backend sends what each step spent rather
            // than a running total. `limit` is carried forward when an event
            // does not name one: only the compaction event knows the window,
            // and losing it on the next ordinary step would make the figure
            // flicker between known and unknown.
            const prior = get().turnUsage;
            set({
              turnUsage: {
                added: prior.added + event.usage.added,
                reclaimed: prior.reclaimed + event.usage.reclaimed,
                limit: event.usage.limit ?? prior.limit,
                measured: event.usage.measured || prior.measured,
              },
            });
            break;
          }

          case 'image_progress': {
            // Latest wins. This fires once per denoising step — thirty times
            // for one image — so accumulating would build a list whose only
            // useful member is the last one.
            set({ streamingImageProgress: event.progress });
            break;
          }

          case 'conversation': {
            // The backend opened a transcript for this exchange and is telling
            // us its id. Held so the *next* message continues the same
            // conversation rather than starting another — without this every
            // message would be its own one-line thread.
            set({ conversationId: event.conversationId });
            break;
          }

          case 'model_load': {
            // Arrives before any token, because the backend checks residency
            // before it starts generating. This is what makes the wait
            // explicable rather than merely long.
            //
            // The generic warming timer is cancelled: it exists to guess that
            // silence means a cold model, and we now *know* what the silence
            // is. A specific answer must not be overwritten by a guess five
            // seconds later.
            clearTimeout(warmingTimer);
            if (event.kind === 'resident') {
              // Already in VRAM, so the wait is generation and the orb keeps
              // saying `thinking`. This is the branch the whole event exists
              // for: without a positive "loaded", the timer above could not
              // tell a resident model from an unanswerable pre-flight, guessed
              // cold for both, and put **Warming up** under every single
              // question on a machine whose model had not moved.
              //
              // Nothing is set — `thinking` is already the activity — and that
              // is the point. Cancelling the guess *is* the action.
            } else if (event.kind === 'swap') {
              useSystemStore.getState().beginModelSwap(event.model);
            } else if (event.kind === 'oversized') {
              // Still a warming orb — it really is loading — but the label
              // beneath it must not say the first reply is the slow one. See
              // `describeSystem`.
              useSystemStore.getState().beginOversizedLoad(event.model);
            } else {
              // A cold start with room to spare is warming, not swapping.
              // Same wait, different cause, and only one of them is something
              // the user can act on in Settings.
              useSystemStore.getState().setActivity('warming');
            }
            break;
          }

          case 'notice': {
            // Something worth saying that the model did not say. It arrives
            // after the answer, which is where it is shown.
            notices.push({
              content: event.content,
              kind: event.kind,
              action: event.action,
              ...(event.servers ? { servers: event.servers } : {}),
              ...(event.model ? { model: event.model } : {}),
              // The "open-project" offer is only pressable with these. They
              // were parsed by `chatClient` and dropped here, so the card
              // asked "Open it as a coding project?" with nothing to press
              // — seen 20 September 2026, the first time F1 ran on screen.
              ...(event.path ? { path: event.path } : {}),
              ...(event.name ? { name: event.name } : {}),
            });
            set({ streamingNotices: [...notices] });
            break;
          }

          case 'plan': {
            plan = { items: event.items, awaitingGo: event.awaitingGo };
            // The engine's own step list is live-only; see `ChatEvent`.
            planIsLiveOnly = event.source === 'planner';
            set({ streamingPlan: plan });
            break;
          }

          case 'tool_call': {
            // The model's working, as it happens. These arrive *before* the
            // answer on a tool-using reply — the generation is buffered, so for
            // the seconds it spends reading, this is the only thing on screen
            // saying anything is happening at all.
            toolCalls.push({
              server: event.server,
              tool: event.tool,
              verdict: event.verdict,
              reason: event.reason,
              target: event.target,
              output: event.output,
              at: stripCitationMarkers(text_).length,
              ...(event.diff ? { diff: event.diff } : {}),
              ...(event.commit ? { commit: event.commit } : {}),
              ...(event.image ? { image: event.image } : {}),
              ...(event.appUrl ? { appUrl: event.appUrl } : {}),
              ...(event.grantable ? { grantable: true } : {}),
              ...(event.grantScope ? { grantScope: event.grantScope } : {}),
              ...(event.heldTask ? { heldTask: event.heldTask } : {}),
              ...(event.once ? { once: true } : {}),
              ...(event.stepId ? { stepId: event.stepId } : {}),
              // `!= null` rather than truthy: step 0 is the first step of
              // every plan and is the one most calls belong to.
              ...(event.planStep != null ? { planStep: event.planStep } : {}),
            });
            set({ streamingToolCalls: [...toolCalls] });
            break;
          }

          case 'timing': {
            timing_ = event.timing;
            break;
          }

          case 'step_start': {
            // A step the planner is running, before any token of the reply:
            // the row a person watches while Zaram searches or reads. Settled
            // in place by the matching completion rather than followed by a
            // second row.
            if (!event.doing) break;
            toolCalls.push({
              server: 'zaram',
              tool: event.capability,
              verdict: 'running',
              reason: '',
              target: event.target,
              output: '',
              label: event.done,
              doing: event.doing,
              stepId: event.stepId,
              at: stripCitationMarkers(text_).length,
            });
            set({ streamingToolCalls: [...toolCalls] });
            break;
          }

          case 'step_complete': {
            if (!event.done) break;
            const at = event.stepId ? toolCalls.findIndex((c) => c.stepId === event.stepId) : -1;
            const settled = {
              server: 'zaram',
              tool: event.capability,
              verdict: event.success ? 'allow' : 'refuse',
              reason: event.detail,
              target: event.target,
              output: event.output ?? '',
              label: event.done,
              stepId: event.stepId,
              seconds: event.seconds,
            };
            if (at >= 0) toolCalls[at] = { ...toolCalls[at], ...settled };
            else toolCalls.push({ ...settled, at: stripCitationMarkers(text_).length });
            set({ streamingToolCalls: [...toolCalls] });
            break;
          }

          case 'answering': {
            // Arrives ahead of the first token. Held locally as well as in the
            // store for the same reason the text is: the committed message
            // needs it after the stream has been cleared.
            answeredBy = {
              model: event.model,
              locality: event.locality,
              provider: event.provider,
              chosenBy: event.chosenBy,
            };
            set({ streamingAnsweredBy: answeredBy });
            // The orb's cloud state is fed from here and from nowhere else.
            // It reports that a cloud model *answered*, which is an event, and
            // never that one is *connected*, which is a setting — the previous
            // version lit an amber warning for the second and had no way to
            // observe the first. Only an explicit `cloud` counts: `null` means
            // the backend could not place the model, and treating unresolved
            // as cloud would claim an egress that may not have happened.
            if (event.locality === 'cloud') {
              useSystemStore.getState().noteCloudAnswer();
              // **And there is no local model to warm, so stop guessing that
              // there is.** The timer below fires on silence and says
              // "Warming up · Starting the local model", which for a cloud
              // reply is false in both halves: nothing is loading, and the
              // wait is a provider's round trip. Measured 3 September 2026
              // with a model reached through OpenRouter — the label appeared
              // under a reply that had left the machine.
              //
              // This event arrives ahead of the first token precisely so it
              // can be acted on, and cloud is the one locality where the
              // answer is knowable in advance. `local` and `null` still fall
              // through to the timer: a cold local model is a real wait worth
              // naming, and `null` means the backend could not place the
              // model, where a guess either way is a claim about the user's
              // data.
              clearTimeout(warmingTimer);
            }
            break;
          }

          case 'error':
            // Reported by the backend. Keep whatever text arrived first.
            replyError = event.message;
            break;

          case 'status':
          case 'done':
            break;
        }
      }
    } catch (err) {
      // **Whatever this was, say what it was.** The fallback here used to read
      // "Something went wrong talking to the backend", which was wrong about
      // the subject — a throw in this loop is the renderer's, not the
      // backend's — and silent about the cause, because nothing logged `err`
      // before discarding it. Four unrelated failures wore one sentence and
      // left no trace, which is how the Tetris reply of 28 September 2026 was
      // unreadable to the person who hit it and to the session asked to fix
      // it. Naming the error costs a line and is the difference between a
      // report and a shrug.
      const message =
        err instanceof ChatTransportError
          ? err.message
          : `The reply stopped: ${describeThrown(err)}`;

      // The person reads the sentence above; whoever has to fix it reads this.
      // A renderer failure belongs in the browser console, which is the one
      // place it is already expected to be.
      if (!(err instanceof ChatTransportError)) {
        console.error('[chatStore] the reply stopped and this is why:', err);
      }

      // A failure before any text is a connection problem and belongs at the
      // top of the surface. A failure part-way through belongs on the message,
      // next to the partial answer it explains.
      if (err instanceof ChatTransportError && err.partial) {
        replyError = message;
      } else {
        set({ connectionError: message });
        replyError = message;
      }
    }

    if (discarded.has(mine)) {
      // Abandoned for a retry that has already started. Nothing here is the
      // new request's to inherit: not the activity, not the speech queue, not
      // `inFlight`, and above all not a committed message made of reasoning.
      clearTimeout(warmingTimer);
      return;
    }

    settleActivity('idle');

    // Set once the exchange is over, so the bar reports what this reply
    // actually drew on rather than counting up during the stream. Zero is a
    // real answer and is stated as one — "no facts recalled" is information,
    // and a bar that goes quiet instead would read as a missing feature.
    useSessionStatusStore.getState().setRecallCount(sources.length);

    // A step row still `running` when the stream ended never got its
    // completion — the reply failed or was stopped mid-step. It is settled as
    // not having finished rather than left spinning on a message that is
    // over: a spinner on a finished reply is a status claim that is false.
    for (let i = 0; i < toolCalls.length; i += 1) {
      if (toolCalls[i].verdict === 'running') {
        toolCalls[i] = { ...toolCalls[i], verdict: 'refuse', reason: 'did not finish' };
      }
    }

    // Commit the reply, including a partial or failed one. Dropping text the
    // backend genuinely produced would be worse than showing it labelled.
    set((s) => ({
      messages:
        // A reply that called tools and then failed still has working worth
        // keeping — "it searched and read two files, then broke" is a more
        // useful record than an empty message, so this counts toward whether
        // there is anything to commit.
        text_ || replyError || artifacts.length || notices.length || reasoning_ || toolCalls.length
          ? [
              ...s.messages,
              {
                id: newId(),
                role: 'assistant',
                text: text_,
                sources,
                artifacts,
                notices,
                toolCalls: toolCalls.length ? toolCalls : undefined,
                plan: plan && !planIsLiveOnly ? plan : undefined,
                timestamp: Date.now(),
                answeredBy,
                reasoning: reasoning_ || undefined,
                timing: timing_,
                error: replyError,
              },
            ]
          : s.messages,
      streamingText: '',
      streamingReasoning: '',
      streamingReasoningSince: null,
      streamingSources: [],
      streamingArtifacts: [],
      streamingNotices: [],
  streamingToolCalls: [],
  streamingPlan: null,
      streamingImageProgress: null,
      streamingAnsweredBy: null,
      isStreaming: false,
    }));

    // Speech follows the renderer: the avatar speaks, the orb stays silent.
    //
    // That makes the toggle mean something rather than being a skin, and it is
    // a decision the user has already made — so it needs no second setting,
    // which is the "never make the user choose in advance" rule applied to a
    // preference they expressed by choosing a face.
    //
    // Read, never subscribed: this is a store action, not a render.
    if (speaking) {
      if (text_ && !replyError) {
        // Flush the tail. Everything before it has already been queued and much
        // of it has already been heard — this is the last partial sentence,
        // which was held back because it might still have grown.
        useSpeechStore.getState().pushSpeech(text_);
        useSpeechStore.getState().endSpeech();
      } else {
        // Nothing worth saying, or the reply failed. Release the loop rather
        // than leaving it waiting on a queue nobody will push to again.
        useSpeechStore.getState().stop();
      }
    }

    inFlight = null;
  },

  answerWithoutThinking: async () => {
    const last = lastSend;
    if (!last || !get().isStreaming || !inFlight) return;

    abandonTheAttempt(set, last.text);

    await get().send(last.text, { ...last.opts, thinking: false, retry: true }, last.attached);
  },

  askAgainAfterAllowing: async (resume) => {
    const last = lastSend;
    if (resume) {
      // **Carry the task on, rather than ask it again from nothing.** The
      // held call was parked with the task; continuing runs it first —
      // confirmed if the person pressed *Run this once*, through the gate if
      // they granted the tool. The question stays on screen: it is still the
      // question being answered.
      if (get().isStreaming && inFlight) abandonTheAttempt(set, null);
      await get().send(resume.runHeld ? 'Run it once' : 'Continue', {
        continueTask: true,
        planId: resume.planId,
        ...(resume.runHeld ? { runHeld: true } : {}),
      });
      return;
    }
    if (get().isStreaming && inFlight && last) {
      abandonTheAttempt(set, last.text);
      await get().send(last.text, { ...last.opts, retry: true }, last.attached);
      return;
    }
    // Nothing in flight, which is also what a replayed history looks like:
    // the last thing the person said is the question to ask again.
    const lastAsked = [...get().messages].reverse().find((message) => message.role === 'user');
    if (lastAsked) await get().send(lastAsked.text);
  },

  runInOrder: async (steps) => {
    const epoch = cancelEpoch;
    for (const step of steps) {
      await get().send(step.text, step.opts ?? {});
      if (cancelEpoch !== epoch || get().connectionError) return;
      const last = [...get().messages].reverse().find((m) => m.role === 'assistant');
      if (!last) return;
      if (last.error || last.plan?.awaitingGo) return;
      if (last.toolCalls?.some((call) => call.verdict === 'confirm')) return;
    }
  },

  cancel: () => {
    cancelEpoch += 1;
    inFlight?.abort();
    inFlight = null;
    set({
      isStreaming: false,
      streamingText: '',
      streamingReasoning: '',
      streamingReasoningSince: null,
      streamingSources: [],
      streamingNotices: [],
  streamingToolCalls: [],
  streamingPlan: null,
      streamingImageProgress: null,
      streamingAnsweredBy: null,
    });
  },

  clear: () => {
    inFlight?.abort();
    inFlight = null;
    set({
      messages: [],
      streamingText: '',
      streamingReasoning: '',
      streamingReasoningSince: null,
      streamingSources: [],
      streamingArtifacts: [],
      streamingNotices: [],
  streamingToolCalls: [],
  streamingPlan: null,
      streamingImageProgress: null,
      streamingAnsweredBy: null,
      isStreaming: false,
      connectionError: null,
      sessionId: `session-${newId()}`,
      // Clearing the transcript on screen starts a new one on disk. The old
      // conversation is not deleted -- it is simply no longer the one being
      // written into, which is what "new conversation" means.
      conversationId: null,
    });
  },

  resumeConversation: async (conversationId) => {
    // Anything in flight is abandoned first. A reply still streaming into the
    // old conversation would append itself to the new one on screen, which is
    // the worst kind of wrong: plausible, and attributed to the wrong thread.
    inFlight?.abort();
    inFlight = null;

    try {
      const stored = await fetchConversation(conversationId);
      // The files these replies made, fetched once for the whole transcript
      // rather than once per message. Ids are stored on the message; the
      // records are the artifact store's and may have been renamed, re-filed
      // or trashed since, so they are read fresh and matched up below.
      const byId = await artifactsForConversation(conversationId);
      set({
        messages: stored.messages.map((m) => ({
          id: m.id,
          role: m.role,
          text: m.text,
          // **Restored as history, 4 October 2026.** These arrive resolved by
          // the backend against the Spine as it is now, so a fact that was
          // corrected or deleted since says so (`history.state`) instead of
          // asserting provenance that no longer holds. They are never the
          // live thing: the passage is not restored, and `unchecked` -- the
          // lookup could not be made -- is never rendered as deleted.
          sources: m.sources ?? [],
          // An id whose artifact is gone drops out rather than rendering a
          // card for a file that is not there — the same refusal the live
          // card makes with `exists`.
          artifacts: m.artifactIds.map((id) => byId.get(id)).filter((a): a is Artifact => !!a),
          notices: [],
          ...(m.toolCalls.length ? { toolCalls: m.toolCalls } : {}),
          ...(m.plan ? { plan: m.plan } : {}),
          timestamp: m.createdAt * 1000,
          // Restored where it was recorded. `locality` is '' for a model the
          // backend could not place, and that stays absent rather than
          // becoming "local" -- the same refusal `locality_of` makes.
          answeredBy:
            m.role === 'assistant' && m.model
              ? {
                  model: m.model,
                  // '' means the backend could not place the model, and it
                  // stays absent rather than becoming 'local' -- the same
                  // refusal `locality_of` makes.
                  locality:
                    m.locality === 'local' || m.locality === 'cloud' ? m.locality : null,
                  // Not recorded per message. `null` is the honest value:
                  // reconstructing a provider from the model name would be a
                  // guess rendered as a fact, on a line whose whole job is to
                  // say what actually answered.
                  provider: null,
                  // Why this model answered was true at the time and is not
                  // stored. A restored transcript says what answered, not what
                  // the routing reasoning was.
                  chosenBy: null,
                }
              : null,
        })),
        conversationId: stored.id,
        // **Follow the conversation into its project — rule 7i.**
        //
        // Asked for 3 October 2026, and it is a scoping fault rather than a
        // convenience: opening a Keyline conversation while Ride Share is
        // selected leaves the next question scoped to Ride Share, so facts
        // captured from it land under a project the exchange is not about.
        // 7i's *"default to the current project"* means the project this
        // conversation belongs to, not whichever one was last clicked.
        //
        // `''` clears it, deliberately. Resuming a conversation that belongs
        // to no project while one is selected is the same fault pointing the
        // other way, and an empty project header is true of that thread.
        projectId: stored.projectId || null,
        streamingText: '',
        streamingReasoning: '',
        streamingReasoningSince: null,
        streamingSources: [],
        streamingArtifacts: [],
        streamingNotices: [],
  streamingToolCalls: [],
  streamingPlan: null,
        streamingImageProgress: null,
        streamingAnsweredBy: null,
        isStreaming: false,
        connectionError: null,
        // A new session id: this is a fresh working context over an old
        // transcript. The engine's in-memory turn buffer is per session and
        // holds the *previous* conversation's turns, which must not leak into
        // this one.
        sessionId: `session-${newId()}`,
      });
      // Persisted like any other project change. It is a working context —
      // somebody who reopened a Keyline thread this evening is still on
      // Keyline tomorrow morning — and leaving it only in memory would make
      // the scope disagree with itself across a relaunch.
      try {
        if (stored.projectId) localStorage.setItem(PROJECT_KEY, stored.projectId);
        else localStorage.removeItem(PROJECT_KEY);
      } catch {
        // The scope still applies to this session; only persistence is lost.
      }
    } catch (error) {
      set({
        connectionError:
          error instanceof Error ? error.message : 'That conversation could not be opened.',
      });
    }
  },
}));
