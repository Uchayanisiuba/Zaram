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

/** Conversation panel, as a fraction of viewport width.
 *
 * Two defaults, because the conversation plays a different role in each place.
 * On the landing surface it is the primary act and shares the screen with the
 * orb. On a working surface it is an assistant beside your work, so it takes
 * less — the pattern Gemini uses in Chrome. */
export const CHAT_DEFAULT = 0.45;
export const CHAT_DEFAULT_WORKSPACE = 0.28;
export const CHAT_MIN = 0.22;
export const CHAT_MAX = 0.7;

/** Left rail when expanded, in pixels — it holds text, so it does not scale.
 *
 *  Sized to its widest label rather than to a round number. At `--text-h1`
 *  (24px) "Knowledge" and a 32px icon come to roughly 210px including padding;
 *  the default was 440, which left a band of empty rail about as wide as the
 *  content beside it. Density beats decoration on a surface used daily, and an
 *  expanded rail that takes a third of a laptop screen to show seven words is
 *  the opposite of that. Still draggable — this is where it starts, not a cap. */
export const RAIL_DEFAULT = 260;
export const RAIL_MIN = 220;
export const RAIL_MAX = 640;

/** Left rail when collapsed. Not adjustable: it is an icon strip. */
export const RAIL_COLLAPSED = 112;

export const clamp = (v: number, min: number, max: number) =>
  Math.min(max, Math.max(min, v));

/**
 * Drop a stored rail width so the new default reaches someone who has already
 * opened the app. Without this, a persisted 440 beats `RAIL_DEFAULT` and the
 * change ships looking like it never landed.
 *
 * Only the rail is dropped. The conversation widths are deliberately kept — a
 * panel someone dragged to where they wanted it is not the thing being fixed.
 *
 * **A version-less entry cannot be migrated at all**, and it is not a case
 * worth designing for: zustand gates migration on
 * `typeof stored.version === 'number'`, so an entry with no version key is
 * loaded as-is and this function is never called with `undefined`. Every entry
 * zustand itself has written carries `version: 0`, because that is the default
 * when the option is absent — which is exactly what real users have. The
 * `typeof` check below is for a hand-edited entry, and it is honest about
 * being unreachable through the normal path rather than implying otherwise.
 */
export function migrateLayout(persisted: unknown, from: unknown): unknown {
  const isOld = typeof from !== 'number' || from < 1;
  if (isOld && persisted && typeof persisted === 'object') {
    const { railWidth: _dropped, ...rest } = persisted as Record<string, unknown>;
    return rest;
  }
  return persisted;
}

interface LayoutState {
  /** Conversation panel width as a fraction of the viewport (0–1). */
  chatFraction: number;
  /** Separate width for working surfaces, where the conversation is an
   *  assistant beside your work rather than the main event. */
  chatFractionWorkspace: number;
  /** Expanded left rail width in pixels. */
  railWidth: number;
  /** True while a divider is being dragged. Used to suppress transitions that
   *  would otherwise make a panel lag behind the cursor. */
  isResizing: boolean;

  setChatFraction: (f: number, context?: 'landing' | 'workspace') => void;
  setRailWidth: (px: number) => void;
  setResizing: (v: boolean) => void;
  resetChat: (context?: 'landing' | 'workspace') => void;
  resetRail: () => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set) => ({
      chatFraction: CHAT_DEFAULT,
      chatFractionWorkspace: CHAT_DEFAULT_WORKSPACE,
      railWidth: RAIL_DEFAULT,
      isResizing: false,

      setChatFraction: (f, context = 'landing') =>
        set(
          context === 'workspace'
            ? { chatFractionWorkspace: clamp(f, CHAT_MIN, CHAT_MAX) }
            : { chatFraction: clamp(f, CHAT_MIN, CHAT_MAX) },
        ),
      setRailWidth: (px) => set({ railWidth: clamp(px, RAIL_MIN, RAIL_MAX) }),
      setResizing: (v) => set({ isResizing: v }),
      resetChat: (context = 'landing') =>
        set(
          context === 'workspace'
            ? { chatFractionWorkspace: CHAT_DEFAULT_WORKSPACE }
            : { chatFraction: CHAT_DEFAULT },
        ),
      resetRail: () => set({ railWidth: RAIL_DEFAULT }),
    }),
    {
      name: 'zaram.layout',
      // Bumped when RAIL_DEFAULT dropped from 440 to 260. Without it the new
      // default reaches nobody who has ever opened the app: a persisted 440
      // wins over the constant, so the change would ship looking like it had
      // not landed. Only the rail is dropped — the conversation widths are
      // untouched and a deliberately dragged panel keeps its size.
      version: 1,
      migrate: migrateLayout,
      // isResizing is transient; persisting it would restore a stuck drag state.
      partialize: (s) => ({
        chatFraction: s.chatFraction,
        chatFractionWorkspace: s.chatFractionWorkspace,
        railWidth: s.railWidth,
      }),
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
