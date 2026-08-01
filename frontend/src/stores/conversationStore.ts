import { create } from 'zustand';

export interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

interface ConversationStore {
  messages: Message[];
  isThinking: boolean;
  showChat: boolean;
  activeNode: string | null;
  inputText: string;
  addMessage: (msg: Message) => void;
  clearMessages: () => void;
  setIsThinking: (v: boolean) => void;
  setShowChat: (v: boolean) => void;
  setActiveNode: (id: string | null) => void;
  setInputText: (text: string) => void;
}

export const useConversationStore = create<ConversationStore>((set) => ({
  messages:    [],
  isThinking:  false,
  showChat:    false,
  activeNode:  null,
  inputText:   '',
  addMessage:    (msg)  => set((s) => ({ messages: [...s.messages, msg] })),
  clearMessages: ()     => set({ messages: [] }),
  setIsThinking: (v)    => set({ isThinking: v }),
  setShowChat:   (v)    => set({ showChat: v }),
  setActiveNode: (id)   => set({ activeNode: id }),
  setInputText:  (text) => set({ inputText: text }),
}));
