/**
 * Open source panels.
 *
 * App-level rather than local to the conversation, because two surfaces need
 * it: the panels render over the orb region, and the orb itself has to recede
 * while any of them are open. Component state could not reach both.
 *
 * Panels are placed by the system, not scattered. Free-floating windows become
 * clutter after about four and hand the user a window-management job — against
 * "calm over delight" and "the target user is not technical". A fixed cascade
 * keeps multiple sources visible and their positions predictable.
 */
import { create } from 'zustand';

export interface OpenSource {
  /** Provenance URL, e.g. "memory:1a2b-...". Doubles as the identity. */
  url: string;
  /** The citation that opened it, so focus can be returned on close. */
  origin: HTMLElement | null;
}

/** Offset between stacked panels, in pixels. */
export const CASCADE_STEP = 26;
/** Beyond this, new panels reuse earlier slots rather than marching off-screen. */
export const CASCADE_WRAP = 5;

interface SourceState {
  open: OpenSource[];
  openSource: (url: string, origin: HTMLElement | null) => void;
  closeSource: (url: string) => void;
  closeAll: () => void;
  /** Removed from the Spine. Kept so the transcript can show them struck out. */
  forgotten: Set<string>;
  markForgotten: (url: string) => void;
}

export const useSourceStore = create<SourceState>((set) => ({
  open: [],
  forgotten: new Set<string>(),

  openSource: (url, origin) =>
    set((s) => {
      // Re-opening an already-open source raises it rather than duplicating it.
      const existing = s.open.find((o) => o.url === url);
      if (existing) {
        return { open: [...s.open.filter((o) => o.url !== url), existing] };
      }
      return { open: [...s.open, { url, origin }] };
    }),

  closeSource: (url) => set((s) => ({ open: s.open.filter((o) => o.url !== url) })),

  closeAll: () => set({ open: [] }),

  markForgotten: (url) =>
    set((s) => ({ forgotten: new Set(s.forgotten).add(url) })),
}));

/** Cascade offset for the nth open panel. */
export function cascadeOffset(index: number) {
  const step = index % CASCADE_WRAP;
  return { x: step * CASCADE_STEP, y: step * CASCADE_STEP };
}
