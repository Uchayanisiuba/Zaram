import { create } from 'zustand'
import { Message } from '@/types'

interface ChatState {
  messages: Message[]
  isLoading: boolean
  inputValue: string
  addMessage: (message: Message) => void
  setLoading: (loading: boolean) => void
  setInputValue: (value: string) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,
  inputValue: '',
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setLoading: (loading) => set({ isLoading: loading }),
  setInputValue: (value) => set({ inputValue: value }),
  clearMessages: () => set({ messages: [] }),
}))