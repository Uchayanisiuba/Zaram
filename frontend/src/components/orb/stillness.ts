/**
 * Holding the orb still for someone who asked their computer for less motion.
 *
 * **`UI-SPEC` requires this and `LivingOrb` did not do it.** "Respect
 * `prefers-reduced-motion` — it disables the orb pulse too." `OrbHint` and
 * `OrbStatus` honoured it; the component that draws the orb anyone actually
 * looks at had no gate at all, across seven infinite animations. On the landing
 * state that runs forever, in the centre of the screen, behind whatever the
 * person is really doing. Continuous motion is a nausea and migraine trigger
 * for people with vestibular disorders, which is the entire reason the
 * operating system offers the setting.
 *
 * **Still is not blank.** Two things are deliberately kept:
 *
 * *Colour still changes.* Reduced motion means less *movement*, not less
 * information — a hue or opacity change carries state without moving anything,
 * so it stays, and it keeps `UI-SPEC`'s rule that a state change is a
 * transition rather than a cut. `SETTLE_SECONDS` is the 0.22s that file already
 * chose for the rim light, so the two channels agree.
 *
 * *The first keyframe is the resting value.* Every looping array in the orb is
 * written to start and end at rest — `[1, 1.06, 1]` — so taking `[0]` leaves
 * the shape the animation would have paused at, not a frame from the middle of
 * a breath. Where the first frame is not the right resting pose the caller says
 * so explicitly; the listening ring holds at 0.7 rather than the array's 0,
 * because a still ring at zero opacity is an invisible one.
 *
 * A `settle`/`settleAll` pair lived here for the variant-driven components —
 * `Aura`, `Halo`, `OrbCore` — and went when they did. They were imported by
 * nothing and never rendered; keeping helpers alive for deleted callers would
 * be the same disease one layer down.
 */

/** Matches the rim-light transition in `docs/UI-SPEC.md`. */
export const SETTLE_SECONDS = 0.22;

/**
 * A looping transition, or a single settle when motion is reduced.
 */
export function loop(
  duration: number,
  reduced: boolean,
  ease: 'easeInOut' | 'easeOut' | 'linear' = 'easeInOut',
) {
  return reduced
    ? { duration: SETTLE_SECONDS, ease: 'easeInOut' as const }
    : { duration, repeat: Infinity, ease };
}

/** Keyframes, or the resting one when motion is reduced. */
export function frames<T>(keyframes: T[], reduced: boolean): T[] | T {
  return reduced ? keyframes[0] : keyframes;
}
