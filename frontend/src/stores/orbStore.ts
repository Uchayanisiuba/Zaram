import { create } from 'zustand';

/**
 * What the orb is doing, as one word.
 *
 * `swapping` is not a kind of thinking. CLAUDE.md: *"Some model pairs are
 * co-resident; others force an unload/reload costing seconds… a route that
 * requires a swap must be visible in the orb's state. An invisible swap reads
 * as a broken product."*
 *
 * That is the whole reason it is a separate state rather than a slower
 * `thinking`. A model swap is several seconds during which nothing is resident
 * and no tokens are coming, and a user watching a *thinking* orb for eight
 * seconds concludes the product has hung. A user watching a *swapping* orb has
 * been told what the wait is for. The wait is identical; only the honesty
 * differs.
 *
 * This store holds the *visual* state only. Which model is being loaded lives
 * in `systemStore`, which owns the words under the orb — see `beginModelSwap`
 * there, and set both through it rather than calling `setOrbState('swapping')`
 * directly, or the orb turns slate-grey while the label still reads
 * "Local only".
 */
export type OrbState = 'idle' | 'thinking' | 'speaking' | 'listening' | 'swapping';

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
