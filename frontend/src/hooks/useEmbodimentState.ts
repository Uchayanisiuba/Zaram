import { useOrbStore, type OrbState } from '@/stores/orbStore';

/**
 * The one state the embodiment renderers read.
 *
 * **The avatar embodies what the system is doing. It does not embody which
 * model answered.** That is a narrowing of the original spike constraint,
 * decided 13 August 2026, and it removed `local` and `cloud` from this set.
 *
 * Two reasons, and the first was found by checking rather than by reasoning.
 *
 * *The two renderers disagreed about what they report.* `LivingOrb` reads
 * `orbStore.orbState` directly and has never rendered locality at all — the
 * avatar was the only renderer that did. The spike's claim that both read one
 * derived state was half true: the derivation existed, and only one consumer
 * ever saw it. Two renderings of one status telling the user different things
 * is worse than either choice, and it is the drift this seam was built to stop
 * happening in the other direction.
 *
 * Where locality *is* reported is `OrbStatusLabel`, in words, at the moment of
 * asking: "Local only", "Local · can send", "Cloud enabled". Its own comment
 * records why three labels rather than two — permitting one search host once
 * flipped it to "Cloud enabled" while every answer was still generated on the
 * machine. A rim colour cannot draw that line, so the colour and the label
 * could only ever have agreed by luck.
 *
 * **The gap this leaves, stated rather than papered over:** that label renders
 * only while the conversation is open (`Landing.tsx`), so at rest nothing
 * reports locality. That was already true of the orb path and is now true of
 * both. If it should be visible at rest, the fix is one condition in
 * `Landing.tsx` — not a colour on a face.
 *
 * *A face that reports where an answer came from is a face users read as a
 * someone.* The rule the embodiment exists to hold is that it is a status
 * indicator, not a personality. Attributing routing to an expression is the
 * first step to "she used the cloud", which is exactly the projection the spike
 * was written to prevent.
 *
 * So the vocabulary is now the orb's activity vocabulary, and it is the *same
 * type* rather than a copy of it. `LivingOrb` once declared its own four-member
 * `OrbState` instead of importing the store's, and a renderer written against a
 * private copy of a vocabulary is how the two silently diverge.
 *
 * The hook stays even though it now returns one store's field unchanged. It is
 * the seam: it is what stops a VRM adapter reaching into three stores and
 * slowly acquiring opinions about routing, which is what it would have to do to
 * get locality back.
 */
export type EmbodimentState = OrbState;

export function useEmbodimentState(): EmbodimentState {
  return useOrbStore((s) => s.orbState);
}
