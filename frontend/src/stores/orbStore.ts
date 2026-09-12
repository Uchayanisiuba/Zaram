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
  /**
   * What the renderers draw. **Derived, never written directly**: it is
   * `speaking` when a clip is playing and `activity` otherwise. Every reader
   * keeps using this field; only the writers changed.
   */
  orbState: OrbState;
  /**
   * What the system is doing, owned by chat and the model layer: idle,
   * thinking, coding, listening, swapping. Sticky for as long as its owner
   * says so — speech starting and stopping does not touch it.
   */
  activity: OrbActivityState;
  /** Whether sound is coming out. Owned by `speechStore` and nobody else. */
  speaking: boolean;
  /** Chat and the model layer set this. Never `'speaking'`. */
  setActivity: (activity: OrbActivityState) => void;
  /** Speech sets this. */
  setSpeaking: (speaking: boolean) => void;
  /**
   * The old single setter, kept for the command registry and the dev pin.
   * Routes to the field that owns the word: `'speaking'` sets `speaking`,
   * anything else sets `activity`. It cannot clobber the other field, which
   * is the whole point of the split.
   */
  setOrbState: (state: OrbState) => void;
  /** @deprecated alias kept for backward-compat — use setOrbState */
  setState: (state: OrbState) => void;
  /** @deprecated alias kept for backward-compat — use orbState */
  state: OrbState;
}

/** Everything the orb can report except speech, which has its own field. */
export type OrbActivityState = Exclude<OrbState, 'speaking'>;

/**
 * The one rule: speech is drawn over whatever the system is doing.
 *
 * **Two writers, one field, and the guard was the bug — found 12 September
 * 2026.** `preserveSpeaking` stopped chat from overwriting `speaking`, which
 * fixed the mouth never opening (19 August). It did so by refusing *every*
 * chat state while a clip played, so a code fence opening mid-sentence could
 * not turn the orb to `coding`; and when the clip ended, speech stood down to
 * `idle` in the middle of a reply that was still streaming. The state cycled
 * thinking → speaking → idle → coding → speaking, and the maintainer's report
 * was "it doesn't go and stay in the coding state".
 *
 * A guard between two writers of one field is a rule somebody has to remember.
 * Two fields with one owner each is a rule nobody can break: speech cannot
 * clobber `coding` because it never writes `activity`, and chat cannot clobber
 * the mouth because it never writes `speaking`. Pure, so a test can hold it
 * without mounting anything.
 */
export function composeOrbState(activity: OrbActivityState, speaking: boolean): OrbState {
  return speaking ? 'speaking' : activity;
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
const START_SPEAKING = START === 'speaking';
const START_ACTIVITY: OrbActivityState = START === 'speaking' ? 'idle' : START;

export const useOrbStore = create<OrbStore>((set, get) => {
  const publish = (activity: OrbActivityState, speaking: boolean) => {
    const orbState = composeOrbState(activity, speaking);
    set({ activity, speaking, orbState, state: orbState });
  };
  return {
    orbState: START,
    state: START,
    activity: START_ACTIVITY,
    speaking: START_SPEAKING,
    setActivity: (activity) => publish(activity, get().speaking),
    setSpeaking: (speaking) => publish(get().activity, speaking),
    setOrbState: (next) =>
      next === 'speaking' ? publish(get().activity, true) : publish(next, get().speaking),
    setState: (next) => get().setOrbState(next),
  };
});
