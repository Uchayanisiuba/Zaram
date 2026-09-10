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
  /**
   * Along each mote's **own tangent**, in px. This is what makes the field
   * circulate instead of slide.
   *
   * It was a single `drift: {x, y}` applied to every mote, so all ten
   * travelled the same direction at the same moment -- a shoal sliding one way
   * and back, which is most of why the field read as inert rather than alive.
   */
  tangential: number;
  /**
   * Along each mote's **own radius**, in px. Negative draws inward.
   *
   * The docstring above has always said `listening` pulls the motes inward and
   * `speaking` pushes them outward. A shared `(x, y)` vector cannot do that --
   * it moves the mote at the top and the mote at the bottom the same way, so
   * one approaches the centre while the other leaves it. The behaviour was
   * described and not implemented; this is the field it was describing.
   */
  radial: number;
  seconds: number;
  opacity: [number, number, number];
}

/** Everything is measured from the middle of the box the caller gives us. */
const CENTRE_PCT = 50;

const FIELD: Record<OrbState, FieldMotion> = {
  // At rest the field turns and barely breathes. Almost all tangent: a resting
  // system is neither taking in nor giving out, and a mote that visibly
  // approached the orb while nothing was happening would be reporting
  // something.
  idle: { tangential: 15, radial: -3, seconds: 8, opacity: [0.2, 0.9, 0.2] },
  // Gathering: quicker, tighter, drawn in.
  thinking: { tangential: 9, radial: -11, seconds: 5, opacity: [0.25, 1, 0.25] },
  // Idle's field, following the same reversal as `STATE_PULSE.coding`: the
  // 8 September instruction is that the orb keeps its default glow and
  // behaviour while coding, and a field that quickened under a calm orb would
  // be the state announcing itself through the one channel left.
  coding: { tangential: 15, radial: -3, seconds: 8, opacity: [0.2, 0.9, 0.2] },
  // Attending: drawn toward the centre and brighter. The strongest inward pull
  // of the five, because listening is the one state that is entirely intake.
  listening: { tangential: 6, radial: -16, seconds: 4.5, opacity: [0.3, 1, 0.3] },
  // Emanating: pushed outward, in step with the ripples the orb already draws
  // while it speaks. The only state with a positive radius, which is what
  // makes taking-in and giving-out legible without a colour.
  speaking: { tangential: 10, radial: 18, seconds: 3.6, opacity: [0.3, 1, 0.3] },
  // Busy elsewhere. Slow and faint, never still.
  swapping: { tangential: 5, radial: -2, seconds: 12, opacity: [0.12, 0.45, 0.12] },
};

/**
 * Where along the loop each mote is sampled.
 *
 * Nine points from 0 to 2π, so the last equals the first and the loop closes on
 * itself. Eight would leave a seam; more buys nothing a 3-5px dot can show.
 */
const PHASES = Array.from({ length: 9 }, (_, i) => (i * Math.PI * 2) / 8);

/**
 * A mote's displacement at one phase of its loop.
 *
 * **A closed curve through the origin, not a line out and back.** The motion
 * was `[0, offset, 0]`: every mote travelled a straight line, stopped dead,
 * and retraced it. Two full stops per cycle is what made a field of ten dots
 * read as a mechanism rather than as something drifting.
 *
 * Tangential rides `sin`, so it swings one way and then the other. Radial
 * rides `(1 - cos) / 2`, which leaves rest, reaches full displacement at the
 * halfway point and returns. Together they trace a closed lens: the mote is
 * never stationary in both axes at once, so there is no frame where it stops.
 *
 * **It starts and ends at rest**, which is not a nicety — `frames()` parks on
 * the first keyframe when the reader has asked for less motion, and
 * `stillness.ts` is explicit that every looping array here must begin at the
 * resting value so a still mote sits where it belongs rather than mid-drift.
 * At θ=0 both terms are zero.
 */
function displacement(
  phase: number,
  axes: ReturnType<typeof axesFor>,
  tangential: number,
  radial: number,
) {
  const along = tangential * Math.sin(phase);
  const out = (radial * (1 - Math.cos(phase))) / 2;
  return {
    x: axes.tanX * along + axes.outX * out,
    y: axes.tanY * along + axes.outY * out,
  };
}

/**
 * How far this mote swings, as a fraction of the state's amplitude.
 *
 * **Individual, and still deterministic.** `PARTICLES` is fixed precisely so a
 * screenshot can be compared against the last one, and one `Math.random()`
 * here would end that -- the same trap the docstring above names about the
 * waveform bars. So the spread is derived from the delay each mote already
 * carries: 0.78 to 1.22, which is enough that no two neighbours travel the same
 * distance and not so much that one dot becomes the thing you watch.
 */
function amplitudeFor(delay: number) {
  return 0.78 + ((delay * 0.37) % 1) * 0.44;
}

/**
 * A mote's own tangent and radius, from where it sits in the box.
 *
 * Derived rather than authored, so `PARTICLES` stays a list of positions and
 * cannot fall out of step with the directions -- and so a position moved by
 * eye gets the right motion without anyone recomputing an angle.
 *
 * No trigonometry per frame: this is two divisions per mote per render, and
 * the animation itself is still keyframes handed to the compositor.
 */
function axesFor(topPct: number, leftPct: number) {
  const dx = leftPct - CENTRE_PCT;
  const dy = topPct - CENTRE_PCT;
  // A mote exactly on the centre has no radius and therefore no direction to
  // move along. It gets the identity rather than a NaN.
  const len = Math.hypot(dx, dy) || 1;
  const outX = dx / len;
  const outY = dy / len;
  // Perpendicular, taken one way for the whole field so the circulation has a
  // single sense. Alternating it would read as turbulence.
  return { outX, outY, tanX: -outY, tanY: outX };
}

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
      {PARTICLES.map((p, i) => {
        const axes = axesFor(p.top, p.left);
        const amp = amplitudeFor(p.delay);
        // The state supplies the magnitudes, the position supplies the
        // directions, and the mote's own delay supplies how far it goes.
        const path = PHASES.map((phase) =>
          displacement(phase, axes, field.tangential * amp, field.radial * amp),
        );
        return (
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
            y: frames(path.map((d) => d.y), reduced),
            x: frames(path.map((d) => d.x), reduced),
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
            // Linear, unlike the rest of the orb's easing. `easeInOut` over a
            // closed loop slows the mote at the seam and speeds it through the
            // middle, which puts back the pulse the closed curve exists to
            // remove -- and the seam is arbitrary here, since the loop has no
            // beginning the reader can see.
            ...loop(field.seconds, reduced, 'linear'),
            delay: reduced ? 0 : p.delay * (field.seconds / 8),
          }}
        />
        );
      })}
    </>
  );
}
