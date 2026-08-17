/**
 * LivingOrb � Project B design, Zaram architecture
 *
 * Globe-based orb with particles and state-driven effects.
 * Driven by orbStore state: idle, listening, thinking, speaking
 *
 * Architecture: Reads orbStore for state, renders globe image with dynamic effects.
 */
import { motion, AnimatePresence } from 'framer-motion';
import { useOrbStore } from '@/stores';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import type { OrbState } from '@/stores/orbStore';
import globeImage from '@/assets/living-orb-globe.png';
import { frames, loop } from './stillness';

// Deterministic particle positions
const PARTICLES = [
  { top: 10, left: 72, delay: 0,   size: 5,   color: '#818cf8' },
  { top: 72, left: 8,  delay: 0.7, size: 4,   color: '#22d3ee' },
  { top: 28, left: 4,  delay: 1.2, size: 5,   color: '#c084fc' },
  { top: 5,  left: 38, delay: 1.8, size: 3,   color: '#818cf8' },
  { top: 84, left: 58, delay: 0.4, size: 4,   color: '#22d3ee' },
  { top: 50, left: 93, delay: 1.5, size: 4,   color: '#c084fc' },
  { top: 18, left: 91, delay: 1.0, size: 3,   color: '#818cf8' },
  { top: 90, left: 26, delay: 2.0, size: 4,   color: '#22d3ee' },
  { top: 42, left: 2,  delay: 0.6, size: 3,   color: '#c084fc' },
  { top: 64, left: 88, delay: 1.3, size: 4,   color: '#818cf8' },
];

// The waveform bar constants are gone with the bars they drove. Their being a
// hardcoded array is the clearest statement of why: a level meter whose levels
// are `[28, 44, 60, 72, 60, 44, 28]` is a decoration wearing a measurement's
// clothes. See the note where the bars were rendered.

// Re-exported, not redeclared. This file used to define its own four-member
// copy of the union, so adding `swapping` to the store left the orb's own
// config maps typed against a union that no longer matched the store's.
export type { OrbState };

/**
 * The single definition of how the orb behaves.
 *
 * There is one orb in Zaram. It appears on the landing, over the conversation,
 * and in the sub-menu bar, and in each place it must look and behave
 * identically — only its diameter changes. Spreading these values across call
 * sites is how the landing ended up breathing differently from the sub-menu.
 *
 * Pass this at every call site and vary nothing but `px`.
 *
 * Only one instance is ever mounted: the landing renders when the landing is
 * shown and the sub-menu bar renders when it is not, so the animations never
 * run twice.
 */
export const ORB_BEHAVIOUR = {
  emphasis: true,
  /** Deeper than the per-state default, so it reads as alive at any size. */
  pulseAmplitude: 1.4,
  coreDotScale: 1,
} as const;

interface LivingOrbProps {
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  /** When true, intensifies the existing glow via brightness amplification.
   *  Derives from existing STATE_CONFIG colors — no new hues introduced. */
  emphasis?: boolean;
  /** Multiplier on the inner white pulse dot, which is otherwise sized as a
   *  fixed ratio of the rendered globe. */
  coreDotScale?: number;
  /** Multiplies how far the orb breathes. 1 keeps the per-state default; 1.4
   *  makes the same motion 40% deeper without changing its rhythm. */
  pulseAmplitude?: number;
  /** Exact diameter in pixels, overriding the size preset.
   *  The presets are fixed (xs 80 … xl 560), so an orb placed in a container of
   *  another size overflowed it. Everything inside derives from this number, so
   *  the orb stays proportional at any diameter rather than being transform
   *  -scaled, which would blur the glows. */
  px?: number;
}

interface StateConfig {
  glowColor: string;
  glowColor2: string;
  ring1Color: string;
  ring2Color: string;
  // `ring1Duration` / `ring2Duration` were here, set in all five states, and
  // read by nothing: both rings render `animate={{ rotate: 0 }}` with a fixed
  // 0.3s transition and are labelled STATIC where they are drawn. Ten numbers
  // maintained across five states for no effect — the same shape as this
  // repository's unreachable modules, in config rather than in code. Removed
  // from the type first, so the compiler named every state that had to change.
  scale: number[];
  scaleDuration: number;
  filter: string;
}

// Per-state visual configs.
//
// Typed as a total map rather than left inferred: an inferred object literal
// means a new member of `OrbState` produces `cfg === undefined` and a blank
// orb at runtime, with nothing failing at build time. This is the same remedy
// M6 applied to the surface list — let the compiler name every file that needs
// an entry.
const STATE_CONFIG: Record<OrbState, StateConfig> = {
  idle: {
    glowColor: 'rgba(99,102,241,0.30)',
    glowColor2: 'rgba(168,85,247,0.18)',
    ring1Color: 'rgba(34,211,238,0.18)',
    ring2Color: 'rgba(168,85,247,0.28)',
    scale: [1, 1.06, 1],
    // 8s, up from 5s. Idle has no ripples — the pulse the eye reads as one is
    // this breath — and on the landing state it runs continuously, forever,
    // behind whatever the user is actually doing. `UI-SPEC`: calm over
    // delight, and motion has a budget.
    scaleDuration: 8,
    filter: 'drop-shadow(0 0 28px rgba(99,102,241,0.45))',
  },
  listening: {
    glowColor: 'rgba(34,211,238,0.45)',
    glowColor2: 'rgba(6,182,212,0.28)',
    ring1Color: 'rgba(34,211,238,0.40)',
    ring2Color: 'rgba(99,102,241,0.35)',
    scale: [1.08, 1.14, 1.08],
    scaleDuration: 2,
    filter: 'drop-shadow(0 0 36px rgba(34,211,238,0.65))',
  },
  thinking: {
    glowColor: 'rgba(168,85,247,0.45)',
    glowColor2: 'rgba(99,102,241,0.32)',
    ring1Color: 'rgba(168,85,247,0.40)',
    ring2Color: 'rgba(34,211,238,0.35)',
    scale: [1, 1.05, 1.02, 1.07, 1],
    scaleDuration: 1.6,
    filter: 'drop-shadow(0 0 40px rgba(168,85,247,0.65))',
  },
  speaking: {
    glowColor: 'rgba(16,185,129,0.35)',
    glowColor2: 'rgba(34,211,238,0.28)',
    ring1Color: 'rgba(16,185,129,0.35)',
    ring2Color: 'rgba(34,211,238,0.30)',
    scale: [1, 1.04, 1.08, 1.04, 1],
    scaleDuration: 1,
    filter: 'drop-shadow(0 0 32px rgba(16,185,129,0.55))',
  },
  // Dimmer and slower than every other state, deliberately.
  //
  // A swap is the one state where nothing is resident and no work is being
  // done — the machine is moving weights. Every other state animates *faster*
  // to signal effort; this one animates slower and darker to signal that there
  // is nothing to wait on yet. Making it a brighter, busier `thinking` would
  // say the opposite of what is true.
  //
  // Desaturated slate rather than cyan or violet: those two already mean
  // "stayed local" and "left the device" on the orb and in citation chips, and
  // a swap is neither. Spending one of them here would break a meaning that is
  // reused precisely so it needs no legend.
  swapping: {
    glowColor: 'rgba(100,116,139,0.30)',
    glowColor2: 'rgba(71,85,105,0.20)',
    ring1Color: 'rgba(148,163,184,0.22)',
    ring2Color: 'rgba(100,116,139,0.28)',
    scale: [1, 1.03, 1],
    scaleDuration: 4,
    filter: 'drop-shadow(0 0 20px rgba(100,116,139,0.35))',
  },
};

const LivingOrb = ({
  size = 'xl',
  className = '',
  emphasis = false,
  px: pxOverride,
  coreDotScale = 1,
  pulseAmplitude = 1,
}: LivingOrbProps) => {
  const { orbState } = useOrbStore();
  const state = orbState as OrbState;
  const cfg = STATE_CONFIG[state];

  // `docs/UI-SPEC.md`: "Respect `prefers-reduced-motion` — it disables the orb
  // pulse too." This component is the orb, and it had no gate across seven
  // infinite animations. `loop` and `frames` hold each one at its resting
  // value; colour still transitions, because reduced motion means less
  // movement rather than less information. See `stillness.ts`.
  const reduced = useIsReducedMotion();

  /** Amplify existing glow via brightness � no new colors */
  const orbBrightness = emphasis ? ' brightness(1.4)' : '';

  // Map size to pixel dimensions (matching Project A sizes)
  const sizeMap = { xs: 80, sm: 104, md: 192, lg: 320, xl: 560 };
  const px = pxOverride ?? sizeMap[size];

  // Component proportions
  const ring1 = Math.round(px * 0.82);
  const ring2 = Math.round(px * 0.71);
  const corePx = Math.round(px * 0.56);
  const outerGlowOffset = Math.round(px * 0.22);

  // Derived from the rendered diameter, not the preset name: with an explicit
  // px the preset says nothing about how big the orb actually is, and full-size
  // particles on a 40px orb read as noise.
  const showParticles = px >= 180;
  const showRings = px >= 120;

  // Deepen or soften the breath without altering its timing. The per-state
  // values are deviations from 1, so only the distance from 1 is scaled.
  const scaleKeyframes = (cfg.scale as number[]).map(
    (v) => 1 + (v - 1) * pulseAmplitude,
  );

  // The dot was a fixed 20px while the globe scaled with px, so its visual
  // weight drifted: 9.1% of the globe at lg, 5.7% at xl, 6.9% in the sub-menu.
  // Deriving it from the rendered globe keeps one ratio at every size.
  const visibleGlobePx = corePx + 40;
  const CORE_DOT_RATIO = 0.069;
  const coreDotPx = Math.max(3, Math.round(visibleGlobePx * CORE_DOT_RATIO * coreDotScale));

  return (
    <div
      className={`relative flex items-center justify-center shrink-0 ${className}`}
      style={{ width: px, height: px }}
    >
      {/* Outer ambient glow � amplified when emphasis is active */}
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          inset: -outerGlowOffset,
          background: `radial-gradient(circle, ${cfg.glowColor} 0%, ${cfg.glowColor2} 45%, transparent 70%)`,
          filter: `blur(24px)${emphasis ? ' brightness(1.8)' : ''}`,
        }}
        animate={{
          scale: frames(scaleKeyframes, reduced),
          opacity: frames(state === 'idle' ? [0.7, 1, 0.7] : [0.8, 1, 0.8], reduced),
        }}
        transition={loop(cfg.scaleDuration, reduced)}
      />

      {/* Thinking multi-color pulse overlay */}
      <AnimatePresence>
        {state === 'thinking' && (
          <motion.div
            className="absolute rounded-full pointer-events-none"
            style={{ inset: -outerGlowOffset, filter: 'blur(20px)' }}
            initial={{ opacity: 0 }}
            animate={{
              opacity: [0, 0.6, 0, 0.5, 0],
              background: [
                'radial-gradient(circle, rgba(34,211,238,0.5) 0%, transparent 70%)',
                'radial-gradient(circle, rgba(168,85,247,0.5) 0%, transparent 70%)',
                'radial-gradient(circle, rgba(99,102,241,0.5) 0%, transparent 70%)',
                'radial-gradient(circle, rgba(34,211,238,0.5) 0%, transparent 70%)',
              ],
            }}
            exit={{ opacity: 0 }}
            transition={loop(4, reduced)}
          />
        )}
      </AnimatePresence>

      {/* Energy ring 1 (outer) � STATIC, no rotation */}
      {showRings && (
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ring1 + outerGlowOffset,
            height: ring1 + outerGlowOffset,
            border: `1px solid ${cfg.ring1Color}`,
          }}
          animate={{ rotate: 0 }}
          transition={{ duration: 0.3 }}
        />
      )}

      {/* Energy ring 2 (inner) � STATIC, no rotation */}
      {showRings && (
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ring2,
            height: ring2,
            border: `1px solid ${cfg.ring2Color}`,
          }}
          animate={{ rotate: 0 }}
          transition={{ duration: 0.3 }}
        />
      )}

      {/* Speaking ripples, emanating outward.
       *
       * Calmed on the maintainer's report that they read as blinding and too
       * busy while Zaram speaks. Three changes, and they are separable so the
       * next person can tune one without the others:
       *
       *   rate    — one ripple every 1.2s rather than every 0.6s. With three
       *             rings, spacing is `duration / 3`, so the duration and the
       *             stagger move together or the ring spacing goes uneven.
       *   reach   — 2.2x rather than 2.8x. At 2.8 the outermost ring was the
       *             brightest thing on screen and further out than any other
       *             layer, which is what made it read as a flash rather than
       *             as a ripple.
       *   opacity — starts at 0.3 against a 0.28 border, down from 0.7 against
       *             0.5. `UI-SPEC` puts motion on a budget and this is a
       *             continuous animation on a surface used all day.
       *
       * Not removed. It is the only thing distinguishing speaking from idle on
       * the orb once the bars are gone, and a state indicator that does not
       * indicate is worse than a busy one.
       */}
      <AnimatePresence>
        {state === 'speaking' &&
          [0, 1, 2].map(i => (
            <motion.div
              key={i}
              className="absolute rounded-full pointer-events-none"
              style={{ width: corePx, height: corePx, border: '1px solid rgba(16,185,129,0.28)' }}
              initial={{ scale: 1, opacity: 0.3 }}
              animate={reduced ? { scale: 1, opacity: 0.3 } : { scale: 2.2, opacity: 0 }}
              exit={{ opacity: 0 }}
              // 4s, was 3.6, and the stagger goes to 4/3 so the three ripples
              // stay evenly spaced within one period.
              transition={{ ...loop(4, reduced, 'easeOut'), delay: reduced ? 0 : i * (4 / 3) }}
            />
          ))}
      </AnimatePresence>

      {/* Listening active pulse ring */}
      <AnimatePresence>
        {state === 'listening' && (
          <motion.div
            className="absolute rounded-full pointer-events-none"
            style={{ width: corePx + 32, height: corePx + 32, border: '2px solid rgba(34,211,238,0.55)' }}
            initial={{ scale: 1, opacity: 0 }}
            animate={{
              scale: frames([1, 1.25, 1.5], reduced),
              // Held at 0.7 rather than the array's 0, or a still ring would be
              // an invisible one and listening would lose its only marker.
              opacity: reduced ? 0.7 : [0.7, 0.4, 0],
            }}
            exit={{ opacity: 0 }}
            transition={loop(2, reduced, 'easeOut')}
          />
        )}
      </AnimatePresence>

      {/* Core globe image � drop-shadow amplified when emphasis is active */}
      <motion.img
        src={globeImage}
        alt="Living Intelligence Orb"
        className="relative z-10 object-contain pointer-events-none select-none"
        style={{
          width: corePx + 40,
          height: corePx + 40,
          // Emphasis is suppressed while swapping. `emphasis` is passed at
          // every call site via ORB_BEHAVIOUR, so without this the orb would
          // be brightness-amplified 1.4× in the one state whose whole point is
          // that it is dim.
          filter: `${cfg.filter}${state === 'swapping' ? '' : orbBrightness}`,
        }}
        animate={{
          scale: frames(scaleKeyframes, reduced),
          // The globe fades toward half-present rather than holding steady:
          // the model backing it is, at this moment, genuinely not there.
          // Still, it holds at 0.85 — dimmer than resident, which is the part
          // that carries meaning without moving.
          opacity: state === 'swapping' ? frames([0.85, 0.5, 0.85], reduced) : 1,
        }}
        transition={loop(cfg.scaleDuration, reduced)}
      />

      {/* Inner pulse dot. Shown by rendered diameter rather than preset name:
          it is a fixed size, so on a small orb it reads as a bright blob. */}
      {px >= 60 && (
        <motion.div
          className="absolute z-20 rounded-full bg-white pointer-events-none"
          style={{
            width: coreDotPx,
            height: coreDotPx,
            // Glow scales with the dot, or it stays a soft blob around a small
            // hard edge.
            boxShadow: `0 0 ${Math.max(4, Math.round(coreDotPx * 1.2))}px rgba(255,255,255,0.9)`,
          }}
          animate={{
            // Rests bright rather than at the array's 0.35: the dot is the
            // orb's centre, and a still one at a third opacity looks broken.
            opacity: reduced ? 0.9 : [0.35, 0.9, 0.35],
            scale: reduced ? 1 : [0.8, 1.2, 0.8],
          }}
          transition={loop(4, reduced)}
        />
      )}

      {/* Floating particles */}
      {showParticles &&
        PARTICLES.map((p, i) => (
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
            // they drift through every possible phase relationship and the
            // field never repeats. A shared 8s with staggered starts looks the
            // same at a glance and settles into one rhythm.
            transition={{ ...loop(8, reduced), delay: reduced ? 0 : p.delay }}
          />
        ))}

      {/* The speaking waveform bars are gone, deliberately.
       *
       * Removed on the maintainer's call, and the reasoning is worth keeping
       * because it is not only taste. **The bars were not driven by the
       * audio.** Their heights are a fixed array and their timings are
       * `0.5 + i * 0.05` — a loop that looks like a level meter and measures
       * nothing. `UI-SPEC` says never render invented values, and an
       * always-identical waveform beside real speech is exactly that: it
       * claims to show what Zaram is saying and shows a constant.
       *
       * If a level meter returns it has to read `useSpeechStore`'s audio
       * element, the way the avatar's visemes already do — the seam is there,
       * and lip sync is scrubbed against `audio.currentTime` for precisely
       * this reason. Twelve looping divs are not that.
       */}
    </div>
  );
};

export default LivingOrb;
