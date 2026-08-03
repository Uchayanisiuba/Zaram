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
import { useSystemStore } from '@/stores/systemStore';

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
  timestamp: number;
  /** Set when this reply failed or was cut short. Any text already received is
   *  kept — a partial answer is still worth showing, provided it is labelled. */
  error?: string;
}

interface ChatState {
  messages: ChatMessage[];
  /** Text arriving for the in-flight reply. Not yet committed to messages. */
  streamingText: string;
  /** Sources for the in-flight reply. They arrive before the tokens do. */
  streamingSources: ChatSource[];
  isStreaming: boolean;
  /** Connection-level failure, as opposed to a failure within one reply. */
  connectionError: string | null;
  sessionId: string;

  send: (text: string, opts?: Partial<ChatRequest>) => Promise<void>;
  cancel: () => void;
  clear: () => void;
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
  isStreaming: false,
  connectionError: null,
  sessionId: `session-${newId()}`,

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
          timestamp: Date.now(),
        },
      ],
      streamingText: '',
      streamingSources: [],
      isStreaming: true,
      connectionError: null,
    }));

    // Accumulated locally as well as in the store: on failure we still need the
    // partial text, and reading it back out of the store mid-teardown is racy.
    let text_ = '';
    const sources: ChatSource[] = [];
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
      useSystemStore.getState().setActivity(a);
    };

    try {
      for await (const event of streamChat(
        { text: trimmed, sessionId: get().sessionId, ...opts },
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

    // Commit the reply, including a partial or failed one. Dropping text the
    // backend genuinely produced would be worse than showing it labelled.
    set((s) => ({
      messages:
        text_ || replyError
          ? [
              ...s.messages,
              {
                id: newId(),
                role: 'assistant',
                text: text_,
                sources,
                timestamp: Date.now(),
                error: replyError,
              },
            ]
          : s.messages,
      streamingText: '',
      streamingSources: [],
      isStreaming: false,
    }));

    inFlight = null;
  },

  cancel: () => {
    inFlight?.abort();
    inFlight = null;
    set({ isStreaming: false, streamingText: '', streamingSources: [] });
  },

  clear: () => {
    inFlight?.abort();
    inFlight = null;
    set({
      messages: [],
      streamingText: '',
      streamingSources: [],
      isStreaming: false,
      connectionError: null,
      sessionId: `session-${newId()}`,
    });
  },
}));
