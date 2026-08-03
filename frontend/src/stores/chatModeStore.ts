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
}

export const useChatModeStore = create<ChatModeStore>()(
  persist(
    (set) => ({
      chatView: 'landing',
      context: 'landing',
      hasOpenedChat: false,
      setContext: (context) => set({ context }),
      openChat: () => set({ chatView: 'chat', hasOpenedChat: true }),
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
