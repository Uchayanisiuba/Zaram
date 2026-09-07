import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface ChatModeStore {
  chatView: 'landing' | 'chat';
  /** Which surface the conversation was opened over. Decides how much width it
   *  takes: the main event on the landing, an assistant beside your work
   *  elsewhere. */
  context: 'landing' | 'workspace';
  setContext: (c: 'landing' | 'workspace') => void;
  /** Whether the conversation has ever been opened. Drives the first-run hint,
   *  which must not return once the user has learned the gesture. */
  hasOpenedChat: boolean;
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
  /**
   * How many times a hands-free conversation has been asked for.
   *
   * **A counter rather than a flag**, and that is the whole design. The
   * microphone lives inside the conversation — the transcript has to reach a
   * composer, and only `ChatSurface` knows where that is — while the keystroke
   * that asks for it is global and fires on the landing, where no composer is
   * mounted yet. So the shortcut records a *request* and the conversation acts
   * on it once it exists.
   *
   * A boolean would need clearing, and whoever cleared it would race the
   * mount: set on the landing, read by a `ChatSurface` that has not rendered,
   * cleared by nobody. A counter is monotonic — the conversation remembers
   * which number it has served — so a second press while already listening is
   * a second request rather than an ambiguous `true`, and there is no reset to
   * get wrong.
   *
   * Session state, never persisted: a reload must not reopen the microphone.
   */
  voiceRequests: number;
  /** Ask for one. Opens the conversation, because there is nowhere for a
   *  transcript to land without it. */
  requestVoiceConversation: () => void;
}

export const useChatModeStore = create<ChatModeStore>()(
  persist(
    (set) => ({
      chatView: 'landing',
      context: 'landing',
      hasOpenedChat: false,
      voiceRequests: 0,
      setContext: (context) => set({ context }),
      openChat: () => set({ chatView: 'chat', hasOpenedChat: true }),
      requestVoiceConversation: () =>
        set((s) => ({
          chatView: 'chat',
          hasOpenedChat: true,
          voiceRequests: s.voiceRequests + 1,
        })),
      closeChat: () => set({ chatView: 'landing' }),
      toggleChat: () =>
        set((s) => ({
          chatView: s.chatView === 'landing' ? 'chat' : 'landing',
          hasOpenedChat: s.hasOpenedChat || s.chatView === 'landing',
        })),
    }),
    {
      name: 'zaram.chat-mode',
      // Only the learned-the-gesture flag survives a reload; which view was
      // open is session state and should not be restored.
      partialize: (s) => ({ hasOpenedChat: s.hasOpenedChat }),
    },
  ),
);
