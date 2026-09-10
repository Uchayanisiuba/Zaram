/**
 * The atmosphere around the embodiment — energy rings and drifting motes.
 *
 * **The orb had both and the avatar had neither**, because both were markup
 * inside `LivingOrb`. Choosing the character removed the rings, the particles
 * and the state colour with them, and left a robot standing on a flat
 * background. The orbit *tracks* that `Landing` draws are a different thing —
 * they belong to the six nodes and fade when the conversation opens; these
 * belong to the thing that is thinking.
 *
 * So it is extracted rather than reimplemented, and the colours come from
 * `ringColours` so there is one state→colour table. A second one would
 * eventually disagree with the first about what Zaram is doing, on the
 * indicator whose whole job is to be trusted.
 *
 * **It renders behind whatever it wraps, and that is explicit.** The avatar is
 * a WebGL canvas in normal flow; an absolutely positioned sibling with no
 * stacking of its own would paint over it and put motes across the face. The
 * layer is pinned at `zIndex: 0` and the caller lifts the character above it.
 *
 * It reports no state the rim light does not already report, and it adds no
 * new colour: it is the same two rings and the same ten motes the orb has
 * always drawn.
 */
import { motion } from 'framer-motion';

import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { useOrbStore } from '@/stores';

import OrbitalParticles from './OrbitalParticles';
import { ringColours } from './LivingOrb';

export default function OrbAura({
  /** The embodiment's box, in pixels. The rings are proportions of it, so the
   *  aura is the same shape whichever renderer it sits behind. */
  px,
  /** Dimmed while a source panel is in front of the orb, matching what the
   *  character itself does. */
  dimmed = false,
}: {
  px: number;
  dimmed?: boolean;
}) {
  const reduced = useIsReducedMotion();
  const state = useOrbStore((s) => s.orbState);
  const colours = ringColours(state);

  /**
   * Sized against the **subject**, not against the box — corrected 10 September.
   *
   * These were `LivingOrb`'s own proportions, 0.82 and 0.71, on the reasoning
   * that identical numbers give "an identically sized aura rather than one that
   * happens to look close". Identical proportions of the *container* are not an
   * identical aura, because the two renderers fill their containers completely
   * differently: the orb's sphere occupies about a third of its box, and the
   * character occupies nearly all of it.
   *
   * Measured on the running app, `px` scaling to a 448px canvas: ring 2 came
   * out at **318px inside a 448px character** -- 65px behind it on every side,
   * invisible, which is the ring the maintainer reported missing. Ring 1 came
   * out at 465px against 448px, clearing by 8.5px, so it traced the canvas edge
   * and read as an outline drawn on the character rather than an orbit around
   * it.
   *
   * Ring 1 needs no change: with `outerGlowOffset` added below it already
   * renders at 1.04x the box.
   *
   * **Ring 2 crosses the character rather than clearing it**, and the two
   * failures either side of that are worth keeping. At 0.71 it was entirely
   * inside the silhouette and read as missing. At 0.86 it cleared the shoulders
   * completely, which made it visible and made it a second outline floating
   * free of the subject. At 0.80 it passes *through* the character's shoulders:
   * occluded where the robot is opaque, visible where the canvas is not, which
   * is what reads as an orbit going behind something rather than a circle drawn
   * near it.
   *
   * That occlusion is free and already correct. `OrbAura` sits at `zIndex: 0`
   * inside the embodiment's box and the canvas is mounted above it at `z: 1`
   * with `alpha: true` -- confirmed with `elementsFromPoint` at the robot's
   * centre, which returns the canvas topmost. Nothing needs a mask.
   */
  const ring1 = Math.round(px * 0.82);
  const ring2 = Math.round(px * 0.80);
  const outerGlowOffset = Math.round(px * 0.22);

  // Below the character. See the note above — this is the whole reason the
  // layer exists as a wrapper rather than a fragment.
  return (
    <div
      aria-hidden
      className="absolute inset-0 flex items-center justify-center pointer-events-none"
      style={{
        zIndex: 0,
        opacity: dimmed ? 0.25 : 1,
        transition: 'opacity 0.35s ease',
      }}
    >
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          width: ring1 + outerGlowOffset,
          height: ring1 + outerGlowOffset,
          border: `1px solid ${colours.ring1}`,
        }}
        // Colour is the state channel and it changes; nothing here rotates.
        // `LivingOrb` settled that — a ring that spins is performing, and the
        // orb does not perform.
        animate={{ borderColor: colours.ring1 }}
        transition={{ duration: reduced ? 0 : 0.45 }}
      />
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          width: ring2,
          height: ring2,
          border: `1px solid ${colours.ring2}`,
        }}
        animate={{ borderColor: colours.ring2 }}
        transition={{ duration: reduced ? 0 : 0.45 }}
      />

      <div className="absolute inset-0">
        <OrbitalParticles />
      </div>
    </div>
  );
}
