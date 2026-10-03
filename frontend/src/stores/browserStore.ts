/**
 * Whether the browser pane is open, and what it should open with.
 *
 * **The pane is not a seventh node, and this store is what keeps it from
 * becoming one.** `CLAUDE.md` holds the navigation at six and says tools
 * never get menu items — *"they are actions inside the conversation. This is
 * what lets capability grow without the navigation growing."* So the pane is
 * opened by something happening: a reply that started a dev server, a page
 * Zaram was asked to look at, or the person pressing the address in a card.
 *
 * The maintainer's own words for how it should arrive, 3 October 2026:
 * *"pops up when needed and can be clicked on and opened, similar to the
 * browser that opens the local host."*
 *
 * `pendingUrl` is consumed once, on open. It is not the pane's current
 * address — main owns that, and a second copy here would be a second place
 * that disagrees about what is on screen.
 */
import { create } from 'zustand';

interface BrowserState {
  open: boolean;
  /** Where to go when the pane opens, read once and then cleared. */
  pendingUrl: string | null;
  /** Open the pane, optionally at an address. */
  show: (url?: string) => void;
  hide: () => void;
  /** Read `pendingUrl` and clear it, so a reopen does not re-navigate to
   *  wherever the pane was sent last time. */
  takePending: () => string | null;
}

export const useBrowserStore = create<BrowserState>((set, get) => ({
  open: false,
  pendingUrl: null,
  show: (url) => set({ open: true, pendingUrl: url ?? null }),
  hide: () => set({ open: false }),
  takePending: () => {
    const url = get().pendingUrl;
    if (url) set({ pendingUrl: null });
    return url;
  },
}));
