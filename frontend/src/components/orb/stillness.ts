/**
 * Holding the orb still for someone who asked their computer for less motion.
 *
 * **`UI-SPEC` requires this and four components did not do it.** "Respect
 * `prefers-reduced-motion` — it disables the orb pulse too." `OrbHint` and
 * `OrbStatus` honoured it; `LivingOrb`, `OrbCore`, `Aura` and `Halo` — the four
 * that draw the orb anyone actually looks at — had no gate at all, across 23
 * infinite animations. On the landing state that runs forever, in the centre of
 * the screen, behind whatever the person is really doing. Continuous motion is
 * a nausea and migraine trigger for people with vestibular disorders, which is
 * the entire reason the operating system offers the setting.
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
 * a breath.
 */
import type { Variants } from 'framer-motion';
import type { OrbState } from '@/stores/orbStore';

/** Matches the rim-light transition in `docs/UI-SPEC.md`. */
export const SETTLE_SECONDS = 0.22;

type Variant = Variants[string];

/**
 * One variant with its movement removed and its colours intact.
 *
 * Keyframe arrays collapse to their resting value and the repeat is dropped.
 * `rotate` is forced to 0 rather than kept at 360: visually the same angle,
 * but a residual 360 invites a future reader to reintroduce the spin.
 */
export function settle(variant: Variant): Variant {
  if (!variant || typeof variant !== 'object') return variant;

  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(variant as Record<string, unknown>)) {
    if (key === 'transition') continue;
    out[key] = Array.isArray(value) ? value[0] : value;
  }
  if ('rotate' in out) out.rotate = 0;

  out.transition = { duration: SETTLE_SECONDS, ease: 'easeInOut' };
  return out as Variant;
}

/** Every state's variant settled at once. */
export function settleAll(variants: Record<OrbState, Variant>): Record<OrbState, Variant> {
  return Object.fromEntries(
    Object.entries(variants).map(([state, variant]) => [state, settle(variant)]),
  ) as Record<OrbState, Variant>;
}

/**
 * A looping transition, or a single settle when motion is reduced.
 *
 * For the components that animate inline rather than through variants.
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
