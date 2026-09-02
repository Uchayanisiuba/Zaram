import type { EmbodimentState } from '@/hooks/useEmbodimentState'

/**
 * The one table both renderers read for what a state looks like.
 *
 * **`CLAUDE.md`: "two renderers reporting one state in different colours is the
 * defect the 13 August narrowing was written to stop."** They were. `LivingOrb`
 * gave `thinking` violet, `speaking` emerald and `idle` indigo, while
 * `RobotAvatar` collapsed thinking, listening and speaking into one cyan and
 * made idle slate. Three of the five states disagreed, and nothing would ever
 * have failed to say so — the two components had separate literals and neither
 * imported the other.
 *
 * So the values live here and both import them. Not because duplication is
 * untidy, but because the rule is that they cannot disagree, and a rule enforced
 * by two people remembering to edit two files is not enforced.
 *
 * **The colours are the orb's**, because the orb is the one the user learns
 * first: it is the landing default, and the avatar is the alternative renderer.
 * A user who switches renderers should not have to re-learn what cyan means.
 *
 * **A note on violet.** `thinking` is `#a855f7`, and `CLAUDE.md` is explicit that
 * the robot's *face* may never be violet, because `docs/UI-SPEC.md` assigns a
 * violet to cloud and a permanently violet face would say "your data left the
 * device" on the one indicator whose whole job is to be trusted. That rule is
 * about the face panel, which is a constant `#818cf8` and stays so. This table
 * drives the backdrop glow, which is transient, matches the orb exactly, and
 * reports the same five states the orb reports — including no locality at all.
 */
export interface StatePulse {
  /** The glow's hue, as the orb renders it. */
  colour: number
  /** How bright the glow sits, relative to the others. Taken from the alpha the
   *  orb gives that state's `glowColor`, so a state that reads as urgent on the
   *  orb reads as urgent here too. */
  weight: number
  /** The breath, as scale multipliers. The orb animates these as keyframes; the
   *  avatar interpolates through them on the same clock. */
  pulse: readonly number[]
  /** Seconds for one full cycle of `pulse`. */
  pulseSeconds: number
}

/**
 * Per state, matching `LivingOrb`'s `STATE_CONFIG` exactly.
 *
 * The rhythms carry as much meaning as the hues, and they are not arbitrary:
 * every working state animates *faster* than idle to signal effort, and
 * `swapping` is the sole exception — slower and dimmer, because a swap is the
 * one state where nothing is resident and nothing is being worked on. Making it
 * a busier `thinking` would say the opposite of what is true.
 */
export const STATE_PULSE: Record<EmbodimentState, StatePulse> = {
  idle: { colour: 0x6366f1, weight: 0.3, pulse: [1, 1.06, 1], pulseSeconds: 8 },
  listening: { colour: 0x22d3ee, weight: 0.45, pulse: [1.08, 1.14, 1.08], pulseSeconds: 2 },
  thinking: { colour: 0xa855f7, weight: 0.45, pulse: [1, 1.05, 1.02, 1.07, 1], pulseSeconds: 1.6 },
  speaking: { colour: 0x10b981, weight: 0.35, pulse: [1, 1.04, 1.08, 1.04, 1], pulseSeconds: 1 },
  swapping: { colour: 0x64748b, weight: 0.3, pulse: [1, 1.03, 1], pulseSeconds: 4 },
}

/** The weight `idle` sits at, so the others can be expressed against it. */
const BASE_WEIGHT = STATE_PULSE.idle.weight

/** How much brighter than idle this state's glow should render. */
export function pulseBrightness(state: EmbodimentState): number {
  return STATE_PULSE[state].weight / BASE_WEIGHT
}

/**
 * Where in the breath a state is at time `t`, in seconds.
 *
 * The orb hands its keyframes to Framer Motion, which eases between them on a
 * loop. There is no Framer in a `requestAnimationFrame` render loop, so the
 * avatar interpolates the same array on the same period — linearly between
 * neighbours, which at these amplitudes (a few percent) is indistinguishable
 * from an eased curve and needs no dependency.
 *
 * Returns 1 for a single-entry or empty array rather than dividing by zero.
 */
export function pulseAt(state: EmbodimentState, t: number): number {
  const { pulse, pulseSeconds } = STATE_PULSE[state]
  if (pulse.length < 2 || pulseSeconds <= 0) return pulse[0] ?? 1
  // The last keyframe repeats the first on every state here, so the loop closes
  // without a seam and the phase can simply wrap.
  const phase = ((t / pulseSeconds) % 1) * (pulse.length - 1)
  const index = Math.floor(phase)
  const mix = phase - index
  const from = pulse[index]
  const to = pulse[Math.min(index + 1, pulse.length - 1)]
  return from + (to - from) * mix
}
