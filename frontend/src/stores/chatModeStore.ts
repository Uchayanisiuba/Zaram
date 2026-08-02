import { create } from 'zustand';

interface ChatModeStore {
  chatView: 'landing' | 'chat';
  openChat: () => void;
  closeChat: () => void;
  toggleChat: () => void;
}

export const useChatModeStore = create<ChatModeStore>((set) => ({
  chatView: 'landing',
  openChat: () => set({ chatView: 'chat' }),
  closeChat: () => set({ chatView: 'landing' }),
  toggleChat: () => set((s) => ({ chatView: s.chatView === 'landing' ? 'chat' : 'landing' })),
}));
