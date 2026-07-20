import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  model?: string
  status?: 'sending' | 'streaming' | 'complete' | 'error'
}

interface ChatState {
  messages: Message[]
  isLoading: boolean
  inputValue: string
  addMessage: (message: Message) => void
  setLoading: (loading: boolean) => void
  setInputValue: (value: string) => void
  clearMessages: () => void
  updateMessage: (id: string, content: string) => void
  regenerateMessage: (id: string) => void
  editMessage: (id: string, content: string) => void
  retryMessage: (id: string) => void
  removeMessage: (id: string) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isLoading: false,
  inputValue: '',
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  setLoading: (loading) => set({ isLoading: loading }),
  setInputValue: (value) => set({ inputValue: value }),
  clearMessages: () => set({ messages: [] }),

  updateMessage: (id, content) => set((state) => ({
    messages: state.messages.map((m) => m.id === id ? { ...m, content, status: 'complete' as const } : m),
  })),

  regenerateMessage: (id) => {
    const state = get()
    const messageIndex = state.messages.findIndex((m) => m.id === id)
    if (messageIndex === -1) return
    const originalMessage = state.messages[messageIndex]
    const newMessages = state.messages.slice(0, messageIndex)
    set({ messages: newMessages, isLoading: true })
    setTimeout(() => {
      set((state) => ({
        messages: [...state.messages, {
          ...originalMessage,
          id: `${Date.now()}`,
          content: `Regenerated: ${originalMessage.content}`,
          timestamp: new Date(),
        }],
        isLoading: false,
      }))
    }, 1000)
  },

  editMessage: (id, content) => set((state) => ({
    messages: state.messages.map((m) => m.id === id ? { ...m, content } : m),
  })),

  retryMessage: (id) => {
    const state = get()
    const messageIndex = state.messages.findIndex((m) => m.id === id)
    if (messageIndex === -1) return
    const message = state.messages[messageIndex]
    set((state) => ({
      messages: state.messages.map((m) => m.id === id ? { ...m, status: 'streaming' as const } : m),
      isLoading: true,
    }))
    setTimeout(() => {
      set((state) => ({
        messages: state.messages.map((m) => m.id === id ? { ...m, content: `Retried: ${message.content}`, status: 'complete' as const } : m),
        isLoading: false,
      }))
    }, 1000)
  },

  removeMessage: (id) => set((state) => ({
    messages: state.messages.filter((m) => m.id !== id),
  })),
}))
