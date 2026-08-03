import { create } from 'zustand';

interface ChatModeStore {
  chatView: 'landing' | 'chat';
  /** Which surface the conversation was opened over. Decides how much width it
   *  takes: the main event on the landing, an assistant beside your work
   *  elsewhere. */
  context: 'landing' | 'workspace';
  setContext: (c: 'landing' | 'workspace') => void;
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
}

export const useChatModeStore = create<ChatModeStore>((set) => ({
  chatView: 'landing',
  context: 'landing',
  setContext: (context) => set({ context }),
  openChat: () => set({ chatView: 'chat' }),
  closeChat: () => set({ chatView: 'landing' }),
  toggleChat: () => set((s) => ({ chatView: s.chatView === 'landing' ? 'chat' : 'landing' })),
}));
