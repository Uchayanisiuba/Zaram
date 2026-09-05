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
} from '@/services/chatClient';
import type { Artifact } from '@/services/artifactsClient';
import { useSystemStore } from '@/stores/systemStore';
import { useSessionStatusStore } from '@/stores/sessionStatusStore';
import { useEmbodimentStore } from '@/stores/embodimentStore';
import { useSpeechStore } from '@/stores/speechStore';

/** How long a request may produce nothing before we call it a cold start.
 *  A loaded local model begins emitting well inside this; a cold one does not. */
const WARMING_AFTER_MS = 2500;

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
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
}

interface ChatState {
  messages: ChatMessage[];
  /** Text arriving for the in-flight reply. Not yet committed to messages. */
  streamingText: string;
  /** The model's working so far, for the panel above the reply. */
  streamingReasoning: string;
  /** Sources for the in-flight reply. They arrive before the tokens do. */
  streamingSources: ChatSource[];
  /** Files made during the in-flight reply. Arrive after the tokens, since a
   *  document is written from the answer rather than alongside it. */
  streamingArtifacts: Artifact[];
  /** Notices for the in-flight reply. Arrive last, after the answer. */
  streamingNotices: ChatNotice[];
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

  send: (text: string, opts?: Partial<ChatRequest>) => Promise<void>;
  /** Change the active project. Survives across replies; cleared only by the
   *  user, never inferred from what was asked. */
  setProject: (projectId: string | null) => void;
  /** Change which domains questions are asked inside. Same posture as the
   *  project: a working context that survives replies and is cleared only by
   *  the user. */
  setDomains: (domainIds: string[]) => void;
  cancel: () => void;
  clear: () => void;
  /** Reopen a stored conversation, replacing what is on screen.
   *
   *  The transcript comes back as text and attribution and nothing else.
   *  **Sources, artifacts and reasoning are not restored, and that is not an
   *  oversight** — a citation is a claim that *this* answer used *that* fact,
   *  and the fact may since have been corrected or deleted (rule 4). Rendering
   *  yesterday's citation against today's Spine would show provenance that no
   *  longer holds, which is worse than showing none. Reasoning is the model's
   *  working, never part of what it said. */
  resumeConversation: (conversationId: string) => Promise<void>;
}

/** Where the active project is remembered between launches.
 *
 *  Persisted because it is a working context rather than a per-message choice:
 *  someone who spent yesterday on Harbour Lane is still on it this morning, and
 *  making them re-select it every launch is how facts end up captured under the
 *  wrong scope — or under none. */
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

const newId = () =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  streamingText: '',
  streamingReasoning: '',
  streamingSources: [],
  streamingArtifacts: [],
  streamingNotices: [],
  streamingImageProgress: null,
  streamingAnsweredBy: null,
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

  send: async (text, opts = {}) => {
    const trimmed = text.trim();
    if (!trimmed || get().isStreaming) return;

    inFlight?.abort();
    inFlight = new AbortController();

    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: newId(),
          role: 'user',
          text: trimmed,
          sources: [],
          artifacts: [],
          notices: [],
          timestamp: Date.now(),
        },
      ],
      streamingText: '',
      streamingReasoning: '',
      streamingSources: [],
      streamingAnsweredBy: null,
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
    const seen = new Set<string>();
    let replyError: string | undefined;
    let answeredBy: ChatAttribution | null = null;
    let reasoning_ = '';

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
            });
            set({ streamingNotices: [...notices] });
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
      const message =
        err instanceof ChatTransportError
          ? err.message
          : 'Something went wrong talking to the backend.';

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

    settleActivity('idle');

    // Set once the exchange is over, so the bar reports what this reply
    // actually drew on rather than counting up during the stream. Zero is a
    // real answer and is stated as one — "no facts recalled" is information,
    // and a bar that goes quiet instead would read as a missing feature.
    useSessionStatusStore.getState().setRecallCount(sources.length);

    // Commit the reply, including a partial or failed one. Dropping text the
    // backend genuinely produced would be worse than showing it labelled.
    set((s) => ({
      messages:
        text_ || replyError || artifacts.length || notices.length || reasoning_
          ? [
              ...s.messages,
              {
                id: newId(),
                role: 'assistant',
                text: text_,
                sources,
                artifacts,
                notices,
                timestamp: Date.now(),
                answeredBy,
                reasoning: reasoning_ || undefined,
                error: replyError,
              },
            ]
          : s.messages,
      streamingText: '',
      streamingReasoning: '',
      streamingSources: [],
      streamingArtifacts: [],
      streamingNotices: [],
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

  cancel: () => {
    inFlight?.abort();
    inFlight = null;
    set({
      isStreaming: false,
      streamingText: '',
      streamingReasoning: '',
      streamingSources: [],
      streamingNotices: [],
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
      streamingSources: [],
      streamingArtifacts: [],
      streamingNotices: [],
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
      set({
        messages: stored.messages.map((m) => ({
          id: m.id,
          role: m.role,
          text: m.text,
          sources: [],
          artifacts: [],
          notices: [],
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
        streamingText: '',
        streamingReasoning: '',
        streamingSources: [],
        streamingArtifacts: [],
        streamingNotices: [],
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
    } catch (error) {
      set({
        connectionError:
          error instanceof Error ? error.message : 'That conversation could not be opened.',
      });
    }
  },
}));
