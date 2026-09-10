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
export const ORB_STATES = [
  'idle',
  'thinking',
  'coding',
  'speaking',
  'listening',
  'swapping',
] as const;

export type OrbState = (typeof ORB_STATES)[number];

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

/**
 * A starting state named in the query string, in development only.
 *
 * **Four of the six states had never been seen on screen**, and the reason was
 * mechanical rather than neglect: `swapping` needs a model swap, `coding` needs
 * a reply that opens a code fence, and the dev server has no backend to produce
 * either. So the rhythms in `STATE_PULSE`, the fields in `OrbitalParticles` and
 * the rings in `OrbAura` were shipped tested and unwatched — which is this
 * repository's most expensive recurring shape, and the gaze-tracking removal is
 * what it costs when the one check nobody made was the one that mattered.
 *
 * `?orb=coding` sets the store's initial value, so every reader sees it: both
 * renderers, the field and the aura. It is a starting value rather than an
 * override, so the system still moves the state normally afterwards and nothing
 * here can make the indicator disagree with what is happening.
 *
 * **Development only, and that is stricter than the debug flags on
 * `RobotAvatar`.** `?noAnim=1` and `?avatarBg` survive into a build because
 * they change how the character is drawn; this changes what the indicator
 * *says*, and `CLAUDE.md` is explicit that a status indicator over invented
 * values is worse than no indicator. Vite folds `import.meta.env.DEV` to a
 * literal, so in a production bundle this collapses to `null` and the parameter
 * does not exist.
 */
function pinnedState(): OrbState | null {
  if (!import.meta.env.DEV || typeof window === 'undefined') return null;
  const raw = new URLSearchParams(window.location.search).get('orb');
  return raw !== null && (ORB_STATES as readonly string[]).includes(raw)
    ? (raw as OrbState)
    : null;
}

/** Read once, so the field and its alias cannot start out disagreeing. */
const START: OrbState = pinnedState() ?? 'idle';

export const useOrbStore = create<OrbStore>((set) => ({
  orbState: START,
  setOrbState: (orbState) => set({ orbState, state: orbState }),
  // Aliases
  state: START,
  setState: (orbState) => set({ orbState, state: orbState }),
}));
