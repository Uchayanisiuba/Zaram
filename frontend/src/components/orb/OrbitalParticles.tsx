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

import { frames, loop } from './stillness';

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
            y: frames([0, -24, 0], reduced),
            x: frames([0, 12, 0], reduced),
            opacity: reduced ? 0.55 : [0.2, 0.9, 0.2],
          }}
          // **One period, offset by delay — not ten periods.**
          // This was `3.5 + p.delay`, which gave the ten particles ten
          // different durations (3.5s to 5.5s). Ten cycles sharing no common
          // factor is the largest single source of the orb's restlessness:
          // they drift through every possible phase relationship and the field
          // never repeats. A shared 8s with staggered starts looks the same at
          // a glance and settles into one rhythm.
          transition={{ ...loop(8, reduced), delay: reduced ? 0 : p.delay }}
        />
      ))}
    </>
  );
}
