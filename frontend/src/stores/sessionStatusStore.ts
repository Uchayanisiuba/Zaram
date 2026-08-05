/**
 * Session status — what the persistent bar reports about the current exchange.
 *
 * One place the whole app can read "what is answering, where, and on what
 * basis" from. The bar is the only consumer today; the point of a store rather
 * than props is that the bar sits outside the workspace tree and must keep
 * reporting while the user is in Memory or Activity, where no chat component is
 * mounted.
 *
 * Deliberately separate from `systemStore`, which describes the *machine*
 * (backend reachable, routing mode, orb activity). This describes the
 * *conversation* — its topic, the model that answered it, and how many facts
 * were recalled into it. They change at different rates and for different
 * reasons, and collapsing them would mean a poll of /health clobbering the
 * recall count of a reply in flight.
 *
 * Every field is nullable and nothing is defaulted to a plausible value.
 * CLAUDE.md: never render invented values — a bar that says "gemma3" because
 * that is a likely model is worse than a bar that says nothing, because it
 * would be believed. Absence renders as an omitted segment, never as a guess.
 */
import { create } from 'zustand';

/** Where the answer was generated. Not the same question as whether some
 *  other route off the machine exists — see systemStore's canLeaveDevice. */
export type Locality = 'local' | 'cloud' | null;

interface SessionStatusState {
  /** What this conversation is about, in the user's words. Null before the
   *  first message — there is no topic yet, and inventing one ("New chat")
   *  puts a label where a fact belongs. */
  topic: string | null;

  /** The model that answered, as the backend reports it. Null until /health
   *  has been read, or when the backend cannot name one. */
  model: string | null;

  /** Local or cloud. Only 'local' is reachable today because only Ollama is
   *  wired; this is read from the backend rather than hardcoded, so it becomes
   *  correct on its own when a cloud provider is added instead of needing to
   *  be remembered. */
  locality: Locality;

  /** Facts recalled into the most recent reply. Null means "not known yet",
   *  which is different from 0 — zero recalled facts is a real and meaningful
   *  answer, and the bar says "no facts recalled" for it. */
  recallCount: number | null;

  /** True while a model swap is in progress. A route that needs a model the
   *  card cannot hold alongside the embedder forces an unload and reload
   *  costing seconds; an invisible swap reads as a broken product. Nothing
   *  sets this yet — the backend does not report swaps — so the bar's swapping
   *  state is reachable but never entered. Wired here so that when residency
   *  reporting lands there is one place to set it. */
  swapping: boolean;

  setTopic: (topic: string | null) => void;
  setRecallCount: (n: number | null) => void;
  setSwapping: (swapping: boolean) => void;
  /** Fold in what a /health poll learned. Called by systemStore. */
  applyHealth: (info: { model: string | null; locality: Locality }) => void;
  reset: () => void;
}

export const useSessionStatusStore = create<SessionStatusState>((set) => ({
  topic: null,
  model: null,
  locality: null,
  recallCount: null,
  swapping: false,

  setTopic: (topic) => set({ topic }),
  setRecallCount: (recallCount) => set({ recallCount }),
  setSwapping: (swapping) => set({ swapping }),
  applyHealth: ({ model, locality }) => set({ model, locality }),

  reset: () => set({ topic: null, recallCount: null, swapping: false }),
}));

/**
 * The bar's mono line, assembled from what is actually known.
 *
 * Returns the segments rather than a string so the caller can style them, and
 * so that "nothing is known" is representable as an empty array instead of as
 * an empty string that still renders a separator.
 */
export function statusSegments(s: {
  model: string | null;
  locality: Locality;
  recallCount: number | null;
  swapping: boolean;
}): string[] {
  const parts: string[] = [];

  // Locality first: it is the privacy-relevant fact and the one the user is
  // most likely to be checking for.
  if (s.locality) parts.push(s.locality);

  if (s.swapping) parts.push('swapping model');
  else if (s.model) parts.push(s.model);

  if (s.recallCount !== null) {
    parts.push(
      s.recallCount === 0
        ? 'no facts recalled'
        : `${s.recallCount} fact${s.recallCount === 1 ? '' : 's'} recalled`,
    );
  }

  return parts;
}
