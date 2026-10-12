/**
 * Zaram's tested starting points for pages, fetched once from the backend.
 *
 * A reply that builds on one names it (`Starting from: voxel-world`) and carries
 * only its changes, so the page cannot be shown until the starting point is here.
 * Held by name for the session; the backend serves them from its own folder.
 */
import { create } from 'zustand';

const API = import.meta.env.VITE_ZARAM_API ?? '';

interface StarterStore {
  codes: Record<string, string>;
  /** Names that could not be fetched, so they are not asked for again. */
  missing: Record<string, true>;
  /** Fetch any of `names` not already held. Resolves when all have settled. */
  ensure: (names: readonly string[]) => Promise<void>;
}

const inFlight = new Map<string, Promise<void>>();

export const useStarterStore = create<StarterStore>((set, get) => ({
  codes: {},
  missing: {},
  ensure: async (names) => {
    const wanted = names.filter((n) => !(n in get().codes) && !get().missing[n]);
    await Promise.all(
      wanted.map((name) => {
        const running = inFlight.get(name);
        if (running) return running;
        const job = (async () => {
          try {
            const response = await fetch(`${API}/starters/${encodeURIComponent(name)}`);
            if (!response.ok) throw new Error(String(response.status));
            const body = (await response.json()) as { code?: unknown };
            if (typeof body.code !== 'string') throw new Error('no code');
            set((s) => ({ codes: { ...s.codes, [name]: body.code as string } }));
          } catch {
            set((s) => ({ missing: { ...s.missing, [name]: true } }));
          } finally {
            inFlight.delete(name);
          }
        })();
        inFlight.set(name, job);
        return job;
      }),
    );
  },
}));
