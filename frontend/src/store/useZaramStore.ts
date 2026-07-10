import create from 'zustand';

// Define types for Zustand store
type ZaramState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'working' | 'creative' | 'error';
type EnvironmentMode = 'calm' | 'focus' | 'creative';

// Create the Zustand store with proper TypeScript types and named exports
export const useZaramStore = create<{
  currentState: ZaramState;
  environmentMode: EnvironmentMode;
  setCurrentState: (state: ZaramState) => void;
  setEnvironmentMode: (mode: EnvironmentMode) => void;
}>((set) => ({
  currentState: 'idle',
  environmentMode: 'calm',
  setCurrentState: (state: ZaramState) => set({ currentState: state }),
  setEnvironmentMode: (mode: EnvironmentMode) => set({ environmentMode: mode }),
}));