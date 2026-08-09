import { create } from 'zustand';

/**
 * Which renderer embodies the system state.
 *
 * `docs/EMBODIMENT-SPIKE.md`: *"The toggle lives in Settings. The landing gets
 * nothing."* Someone who wants an avatar will look for it once; someone who
 * does not should never see the control, and the landing is the calmest surface
 * in the product.
 *
 * That decision is about where the *control* lives, not where the state lives.
 * The preference is held here so the control can move to Settings without
 * touching either renderer — during this spike a toggle sits on the landing so
 * the two can be compared side by side, which is the only way to answer whether
 * the avatar is worth shipping at all.
 *
 * `<Embodiment />` picks a renderer **at mount and does not crossfade**. A
 * preference changed in Settings does not need to animate on a surface the user
 * is not looking at, and a crossfade between a glowing sphere and a 3D
 * character has no good frame in the middle. It also removes the worst version
 * of the bundle problem: there is never a moment where both renderers are live,
 * so the lazy-loaded VRM adapter is fetched only by people who turned it on and
 * the orb path never pays for `three`.
 */
export type EmbodimentRenderer = 'orb' | 'avatar';

const STORAGE_KEY = 'zaram.embodiment.renderer';

/** Read once at module load. A bad or absent value falls back to the orb —
 *  never to the renderer that costs a megabyte of JavaScript. */
function storedRenderer(): EmbodimentRenderer {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'avatar' ? 'avatar' : 'orb';
  } catch {
    // Private mode, or no DOM (tests). The orb is the safe answer.
    return 'orb';
  }
}

interface EmbodimentStore {
  renderer: EmbodimentRenderer;
  setRenderer: (renderer: EmbodimentRenderer) => void;
}

export const useEmbodimentStore = create<EmbodimentStore>((set) => ({
  renderer: storedRenderer(),
  setRenderer: (renderer) => {
    try {
      localStorage.setItem(STORAGE_KEY, renderer);
    } catch {
      // Preference is not important enough to fail a render over.
    }
    set({ renderer });
  },
}));
