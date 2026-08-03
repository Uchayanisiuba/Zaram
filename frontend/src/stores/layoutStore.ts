/**
 * Panel geometry — the sizes of every adjustable division in the shell.
 *
 * One store rather than per-component state, for two reasons. The conversation
 * panel's width and the orb's position are the same number seen from two sides:
 * the orb centres itself in whatever space the panel leaves, so separate copies
 * would drift apart. And a size the user has dragged should survive a reload,
 * which needs somewhere durable to live.
 *
 * Widths are stored as a fraction of the viewport rather than pixels, so a
 * layout set on a large monitor still makes sense on a laptop.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/** Conversation panel, as a fraction of viewport width. */
export const CHAT_DEFAULT = 0.45;
export const CHAT_MIN = 0.25;
export const CHAT_MAX = 0.7;

/** Left rail when expanded, in pixels — it holds text, so it does not scale. */
export const RAIL_DEFAULT = 440;
export const RAIL_MIN = 220;
export const RAIL_MAX = 640;

/** Left rail when collapsed. Not adjustable: it is an icon strip. */
export const RAIL_COLLAPSED = 112;

export const clamp = (v: number, min: number, max: number) =>
  Math.min(max, Math.max(min, v));

interface LayoutState {
  /** Conversation panel width as a fraction of the viewport (0–1). */
  chatFraction: number;
  /** Expanded left rail width in pixels. */
  railWidth: number;
  /** True while a divider is being dragged. Used to suppress transitions that
   *  would otherwise make a panel lag behind the cursor. */
  isResizing: boolean;

  setChatFraction: (f: number) => void;
  setRailWidth: (px: number) => void;
  setResizing: (v: boolean) => void;
  resetChat: () => void;
  resetRail: () => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      chatFraction: CHAT_DEFAULT,
      railWidth: RAIL_DEFAULT,
      isResizing: false,

      setChatFraction: (f) => set({ chatFraction: clamp(f, CHAT_MIN, CHAT_MAX) }),
      setRailWidth: (px) => set({ railWidth: clamp(px, RAIL_MIN, RAIL_MAX) }),
      setResizing: (v) => set({ isResizing: v }),
      resetChat: () => set({ chatFraction: CHAT_DEFAULT }),
      resetRail: () => set({ railWidth: RAIL_DEFAULT }),
    }),
    {
      name: 'zaram.layout',
      // isResizing is transient; persisting it would restore a stuck drag state.
      partialize: (s) => ({ chatFraction: s.chatFraction, railWidth: s.railWidth }),
    },
  ),
);

/**
 * Where the orb should sit, given the conversation panel's width.
 *
 * The orb centres itself in the space the panel leaves. Both values derive from
 * one fraction so they cannot disagree.
 *
 * `containerScale` compensates for the orbital system being rendered inside a
 * scaled wrapper: a transform applied within it is multiplied by that scale, so
 * the offset must be divided by it to land where intended.
 */
export function orbGeometry(opts: {
  viewportWidth: number;
  chatFraction: number;
  chatOpen: boolean;
  orbSize: number;
  containerScale: number;
  maxZoom?: number;
}) {
  const { viewportWidth, chatFraction, chatOpen, orbSize, containerScale } = opts;
  const maxZoom = opts.maxZoom ?? 1.4;

  if (!chatOpen) return { shiftX: 0, zoom: 1 };

  const panelWidth = viewportWidth * chatFraction;
  const freeWidth = viewportWidth - panelWidth;

  // Visually the orb must move from the viewport centre to the centre of the
  // free region — that is half the panel width to the left. Divide by the
  // container scale so the transform lands there rather than overshooting.
  const shiftX = -(panelWidth / 2) / containerScale;

  // Shrink rather than overflow when the free space is narrow. 0.85 leaves a
  // margin so the orb's glow is not clipped by the panel edge.
  const renderedSize = orbSize * containerScale;
  const zoom = clamp((freeWidth * 0.85) / renderedSize, 0.5, maxZoom);

  return { shiftX, zoom };
}
