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
import {
  streamChat,
  ChatTransportError,
  type ChatSource,
  type ChatRequest,
} from '@/services/chatClient';
import type { Artifact } from '@/services/artifactsClient';
import { useSystemStore } from '@/stores/systemStore';
import { useSessionStatusStore } from '@/stores/sessionStatusStore';

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
  /** Set when this reply failed or was cut short. Any text already received is
   *  kept — a partial answer is still worth showing, provided it is labelled. */
  error?: string;
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
  /** Sources for the in-flight reply. They arrive before the tokens do. */
  streamingSources: ChatSource[];
  /** Files made during the in-flight reply. Arrive after the tokens, since a
   *  document is written from the answer rather than alongside it. */
  streamingArtifacts: Artifact[];
  /** Notices for the in-flight reply. Arrive last, after the answer. */
  streamingNotices: ChatNotice[];
  isStreaming: boolean;
  /** Connection-level failure, as opposed to a failure within one reply. */
  connectionError: string | null;
  sessionId: string;
  /** The project this conversation belongs to, or null for none (rule 7i).
   *
   *  Scopes recall to this project plus global, and captures facts under it so
   *  `recalled_in` can accumulate the evidence that later argues for promoting
   *  one to global. Null is a real answer, not a missing one. */
  projectId: string | null;

  send: (text: string, opts?: Partial<ChatRequest>) => Promise<void>;
  /** Change the active project. Survives across replies; cleared only by the
   *  user, never inferred from what was asked. */
  setProject: (projectId: string | null) => void;
  cancel: () => void;
  clear: () => void;
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

/** Cancels the in-flight request. Module-level so `cancel()` can reach it
 *  without putting a non-serialisable object in the store. */
let inFlight: AbortController | null = null;

const newId = () =>
  `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  streamingText: '',
  streamingSources: [],
  streamingArtifacts: [],
  streamingNotices: [],
  isStreaming: false,
  connectionError: null,
  sessionId: `session-${newId()}`,
  projectId: loadProject(),

  setProject: (projectId) => {
    set({ projectId });
    try {
      if (projectId) localStorage.setItem(PROJECT_KEY, projectId);
      else localStorage.removeItem(PROJECT_KEY);
    } catch {
      // The scope still applies to this session; only persistence is lost.
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
      streamingSources: [],
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

    // Accumulated locally as well as in the store: on failure we still need the
    // partial text, and reading it back out of the store mid-teardown is racy.
    let text_ = '';
    const sources: ChatSource[] = [];
    const artifacts: Artifact[] = [];
    const notices: ChatNotice[] = [];
    const seen = new Set<string>();
    let replyError: string | undefined;

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
        { text: trimmed, sessionId: get().sessionId, projectId: get().projectId, ...opts },
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
            set({ streamingArtifacts: [...artifacts] });
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
            if (event.kind === 'swap') {
              useSystemStore.getState().beginModelSwap(event.model);
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
        text_ || replyError || artifacts.length || notices.length
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
                error: replyError,
              },
            ]
          : s.messages,
      streamingText: '',
      streamingSources: [],
      streamingArtifacts: [],
      streamingNotices: [],
      isStreaming: false,
    }));

    inFlight = null;
  },

  cancel: () => {
    inFlight?.abort();
    inFlight = null;
    set({
      isStreaming: false,
      streamingText: '',
      streamingSources: [],
      streamingNotices: [],
    });
  },

  clear: () => {
    inFlight?.abort();
    inFlight = null;
    set({
      messages: [],
      streamingText: '',
      streamingSources: [],
      streamingArtifacts: [],
      streamingNotices: [],
      isStreaming: false,
      connectionError: null,
      sessionId: `session-${newId()}`,
    });
  },
}));
