/**
 * The drifting motes around the embodiment, whichever one is mounted.
 *
 * **They lived inside `LivingOrb` and so did not exist on the avatar path.**
 * The orbit rings are rendered by `Landing` and appear behind either renderer;
 * the particles were markup inside the orb component, so choosing the character
 * removed half the atmosphere and left it sitting on a plain background. That
 * is not a small difference — the field is most of what makes the landing feel
 * inhabited rather than empty.
 *
 * Extracted rather than copied. Two particle fields with the same intent would
 * drift the first time anybody tuned one, and the tuning here is already
 * specific enough to be worth protecting: see the note on the shared period.
 *
 * Positioned as percentages of whatever box contains it, so the caller decides
 * the footprint — the orb wraps it in its own square, the avatar path gives it
 * one sized to match. It draws nothing that reports state and it is
 * `pointer-events: none` throughout: the rim light is the state channel, and a
 * mote that could be clicked would be a control nobody meant to make.
 */
import { motion } from 'framer-motion';

import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { useOrbStore } from '@/stores';
import type { OrbState } from '@/stores/orbStore';

import { frames, loop } from './stillness';

/**
 * How the field moves in each state, and the line it does not cross.
 *
 * **It reacts to state, never to a level.** Speaking is a real fact —
 * `speechStore` sets it when a clip starts playing — so the field may answer
 * it. The *amplitude* of that speech is not exposed anywhere, and a field that
 * appeared to pulse with the voice would be the waveform bars again: those
 * were removed on the maintainer's call because their heights were a fixed
 * array, `UI-SPEC` forbids rendering invented values, and an always-identical
 * waveform beside real speech claims to show what Zaram is saying and shows a
 * constant. The same trap is one `Math.random()` away here.
 *
 * So each state gets one honest gesture, and the vocabulary is deliberately
 * small — `CLAUDE.md`: motion has a budget, and the orb does not perform.
 *
 * * **`drift`** is where the motes travel over one period. Negative `y` rises.
 *   `listening` pulls them *inward* and `speaking` pushes them *outward*,
 *   which is the one distinction worth making legible without a colour: the
 *   system is taking something in, or putting something out.
 * * **`seconds`** is the period. Faster reads as busier; it is never fast
 *   enough to be a strobe.
 * * **`opacity`** is the brightness range. Attention brightens, absence dims.
 *
 * `swapping` is dimmed and slowed rather than stopped: a model is loading,
 * which takes 90–180 seconds on this machine by measurement, and a field that
 * froze would read as the application having hung.
 */
interface FieldMotion {
  drift: { x: number; y: number };
  seconds: number;
  opacity: [number, number, number];
}

const FIELD: Record<OrbState, FieldMotion> = {
  idle: { drift: { x: 12, y: -24 }, seconds: 8, opacity: [0.2, 0.9, 0.2] },
  // Gathering: quicker, tighter, drawn slightly in.
  thinking: { drift: { x: -8, y: -16 }, seconds: 5, opacity: [0.25, 1, 0.25] },
  // Working, and it borrows thinking's gesture on purpose. The state was added
  // on 7 September with the note *"no new colour: thinking's violet, a
  // different rhythm"*, and the same reasoning applies to the field — coding
  // is thinking with tools in its hands, not a different kind of activity. A
  // shorter period is the rhythm; the direction is unchanged.
  coding: { drift: { x: -8, y: -16 }, seconds: 3.2, opacity: [0.25, 1, 0.25] },
  // Attending: pulled toward the centre and brighter.
  listening: { drift: { x: -14, y: 14 }, seconds: 4.5, opacity: [0.3, 1, 0.3] },
  // Emanating: pushed outward, in step with the ripples the orb already draws
  // while it speaks.
  speaking: { drift: { x: 20, y: -34 }, seconds: 3.6, opacity: [0.3, 1, 0.3] },
  // Busy elsewhere. Slow and faint, never still.
  swapping: { drift: { x: 6, y: -10 }, seconds: 12, opacity: [0.12, 0.45, 0.12] },
};

/** Deterministic positions — never random, so the field is the same on every
 *  load and a screenshot can be compared against the last one. */
export const PARTICLES = [
  { top: 10, left: 72, delay: 0, size: 5, color: '#818cf8' },
  { top: 72, left: 8, delay: 0.7, size: 4, color: '#22d3ee' },
  { top: 28, left: 4, delay: 1.2, size: 5, color: '#c084fc' },
  { top: 5, left: 38, delay: 1.8, size: 3, color: '#818cf8' },
  { top: 84, left: 58, delay: 0.4, size: 4, color: '#22d3ee' },
  { top: 50, left: 93, delay: 1.5, size: 4, color: '#c084fc' },
  { top: 18, left: 91, delay: 1.0, size: 3, color: '#818cf8' },
  { top: 90, left: 26, delay: 2.0, size: 4, color: '#22d3ee' },
  { top: 42, left: 2, delay: 0.6, size: 3, color: '#c084fc' },
  { top: 64, left: 88, delay: 1.3, size: 4, color: '#818cf8' },
];

export default function OrbitalParticles() {
  const reduced = useIsReducedMotion();
  const state = useOrbStore((s) => s.orbState);
  const field = FIELD[state] ?? FIELD.idle;

  return (
    <>
      {PARTICLES.map((p, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full z-10 pointer-events-none"
          style={{
            width: p.size,
            height: p.size,
            top: `${p.top}%`,
            left: `${p.left}%`,
            background: p.color,
            boxShadow: `0 0 4px ${p.color}`,
          }}
          animate={{
            y: frames([0, field.drift.y, 0], reduced),
            x: frames([0, field.drift.x, 0], reduced),
            opacity: reduced ? 0.55 : field.opacity,
          }}
          // **One period for the whole field, offset by delay — not ten
          // periods.** This was `3.5 + p.delay`, which gave the ten particles
          // ten different durations (3.5s to 5.5s). Ten cycles sharing no
          // common factor is the largest single source of the orb's
          // restlessness: they drift through every possible phase relationship
          // and the field never repeats. One shared period with staggered
          // starts looks the same at a glance and settles into one rhythm —
          // and it is what lets the *state* change the tempo legibly, because
          // there is one tempo to change.
          //
          // The delay is scaled to the period so the stagger stays a fraction
          // of a cycle rather than a fixed number of seconds. Unscaled, the
          // 2.0s offset that reads as a gentle spread over 8s becomes more
          // than half a cycle at 3.6s, and the field tears into two clumps at
          // exactly the moment it should look most coherent.
          transition={{
            ...loop(field.seconds, reduced),
            delay: reduced ? 0 : p.delay * (field.seconds / 8),
          }}
        />
      ))}
    </>
  );
}
