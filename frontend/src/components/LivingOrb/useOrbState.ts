import { create } from 'zustand';

export type ConversationState = 
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'generating'
  | 'speaking'
  | 'interrupted'
  | 'error';

export interface OrbColors {
  primary: string;
  secondary: string;
  glow: string;
}

const STATE_COLORS: Record<ConversationState, OrbColors> = {
  idle: { primary: '#3b82f6', secondary: '#06b6d4', glow: 'rgba(59,130,246,0.4)' },
  listening: { primary: '#06b6d4', secondary: '#22d3ee', glow: 'rgba(6,182,212,0.5)' },
  thinking: { primary: '#a855f7', secondary: '#d946ef', glow: 'rgba(168,85,247,0.5)' },
  generating: { primary: '#6366f1', secondary: '#818cf8', glow: 'rgba(99,102,241,0.5)' },
  speaking: { primary: '#10b981', secondary: '#34d399', glow: 'rgba(16,185,129,0.6)' },
  interrupted: { primary: '#f59e0b', secondary: '#fbbf24', glow: 'rgba(245,158,11,0.5)' },
  error: { primary: '#ef4444', secondary: '#f87171', glow: 'rgba(239,68,68,0.6)' },
};

interface ConversationStore {
  state: ConversationState;
  audioLevel: number;
  messages: { role: 'user' | 'assistant'; content: string }[];
  currentAssistantText: string;
  
  setState: (state: ConversationState) => void;
  setAudioLevel: (level: number) => void;
  addMessage: (role: 'user' | 'assistant', content: string) => void;
  appendCurrentText: (text: string) => void;
  clearCurrentText: () => void;
  interrupt: () => void;
  getColors: () => OrbColors;
}

export const useOrbState = create<ConversationStore>((set, get) => ({
  state: 'idle',
  audioLevel: 0,
  messages: [{ role: 'assistant', content: 'Zaram OS initialized. Systems online.' }],
  currentAssistantText: '',

  setState: (state) => set({ state }),
  setAudioLevel: (level) => set({ audioLevel: level }),
  
  addMessage: (role, content) => set((prev) => ({
    messages: [...prev.messages, { role, content }],
    currentAssistantText: ''
  })),
  
  appendCurrentText: (text) => set((prev) => ({ 
    currentAssistantText: prev.currentAssistantText + text 
  })),
  
  clearCurrentText: () => set({ currentAssistantText: '' }),
  
  interrupt: () => set((prev) => ({ 
    state: 'interrupted', 
    audioLevel: 0,
  })),

  getColors: () => STATE_COLORS[get().state],
}));