import { create } from 'zustand';

export type OrbState = 'idle' | 'thinking' | 'speaking' | 'listening';

interface OrbStore {
  /** Canonical field */
  orbState: OrbState;
  /** Canonical setter */
  setOrbState: (state: OrbState) => void;
  /** @deprecated alias kept for backward-compat — use setOrbState */
  setState: (state: OrbState) => void;
  /** @deprecated alias kept for backward-compat — use orbState */
  state: OrbState;
}

export const useOrbStore = create<OrbStore>((set) => ({
  orbState: 'idle',
  setOrbState: (orbState) => set({ orbState, state: orbState }),
  // Aliases
  state: 'idle',
  setState: (orbState) => set({ orbState, state: orbState }),
}));
