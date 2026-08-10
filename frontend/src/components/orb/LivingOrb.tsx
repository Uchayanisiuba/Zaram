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
import type { OrbState } from '@/stores/orbStore';
import globeImage from '@/assets/living-orb-globe.png';

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

// Waveform bars for speaking state
const WAVE_BARS = [0, 1, 2, 3, 4, 5, 6];
const WAVE_HEIGHTS = [28, 44, 60, 72, 60, 44, 28];

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
  ring1Duration: number;
  ring2Duration: number;
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
    ring1Duration: 22,
    ring2Duration: 14,
    scale: [1, 1.06, 1],
    scaleDuration: 5,
    filter: 'drop-shadow(0 0 28px rgba(99,102,241,0.45))',
  },
  listening: {
    glowColor: 'rgba(34,211,238,0.45)',
    glowColor2: 'rgba(6,182,212,0.28)',
    ring1Color: 'rgba(34,211,238,0.40)',
    ring2Color: 'rgba(99,102,241,0.35)',
    ring1Duration: 14,
    ring2Duration: 8,
    scale: [1.08, 1.14, 1.08],
    scaleDuration: 2,
    filter: 'drop-shadow(0 0 36px rgba(34,211,238,0.65))',
  },
  thinking: {
    glowColor: 'rgba(168,85,247,0.45)',
    glowColor2: 'rgba(99,102,241,0.32)',
    ring1Color: 'rgba(168,85,247,0.40)',
    ring2Color: 'rgba(34,211,238,0.35)',
    ring1Duration: 8,
    ring2Duration: 5,
    scale: [1, 1.05, 1.02, 1.07, 1],
    scaleDuration: 1.6,
    filter: 'drop-shadow(0 0 40px rgba(168,85,247,0.65))',
  },
  speaking: {
    glowColor: 'rgba(16,185,129,0.35)',
    glowColor2: 'rgba(34,211,238,0.28)',
    ring1Color: 'rgba(16,185,129,0.35)',
    ring2Color: 'rgba(34,211,238,0.30)',
    ring1Duration: 16,
    ring2Duration: 10,
    scale: [1, 1.04, 1.08, 1.04, 1],
    scaleDuration: 0.9,
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
    ring1Duration: 30,
    ring2Duration: 24,
    scale: [1, 1.03, 1],
    scaleDuration: 3.4,
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
        animate={{ scale: scaleKeyframes, opacity: state === 'idle' ? [0.7, 1, 0.7] : [0.8, 1, 0.8] }}
        transition={{ duration: cfg.scaleDuration, repeat: Infinity, ease: 'easeInOut' }}
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
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
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

      {/* Speaking waveform rings emanating outward */}
      <AnimatePresence>
        {state === 'speaking' &&
          [0, 1, 2].map(i => (
            <motion.div
              key={i}
              className="absolute rounded-full pointer-events-none"
              style={{ width: corePx, height: corePx, border: '1px solid rgba(16,185,129,0.5)' }}
              initial={{ scale: 1, opacity: 0.7 }}
              animate={{ scale: 2.8, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.8, repeat: Infinity, delay: i * 0.6, ease: 'easeOut' }}
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
            animate={{ scale: [1, 1.25, 1.5], opacity: [0.7, 0.4, 0] }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
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
          scale: scaleKeyframes,
          // The globe fades toward half-present rather than holding steady:
          // the model backing it is, at this moment, genuinely not there.
          opacity: state === 'swapping' ? [0.85, 0.5, 0.85] : 1,
        }}
        transition={{ duration: cfg.scaleDuration, repeat: Infinity, ease: 'easeInOut' }}
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
          animate={{ opacity: [0.35, 0.9, 0.35], scale: [0.8, 1.2, 0.8] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
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
            animate={{ y: [0, -24, 0], x: [0, 12, 0], opacity: [0.2, 0.9, 0.2] }}
            transition={{ duration: 3.5 + p.delay, repeat: Infinity, delay: p.delay, ease: 'easeInOut' }}
          />
        ))}

      {/* Speaking waveform bars below orb (xl only) */}
      <AnimatePresence>
        {state === 'speaking' && size === 'xl' && (
          <motion.div
            className="absolute flex items-end gap-1 pointer-events-none z-20"
            style={{ bottom: -88, left: '50%', transform: 'translateX(-50%)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            {WAVE_BARS.map((_, i) => (
              <motion.div
                key={i}
                className="rounded-full"
                style={{
                  width: 6,
                  background: 'linear-gradient(to top, rgba(34,211,238,0.8), rgba(168,85,247,0.8))',
                }}
                animate={{ height: [4, WAVE_HEIGHTS[i], 4] }}
                transition={{ duration: 0.5 + i * 0.05, repeat: Infinity, delay: i * 0.07, ease: 'easeInOut' }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default LivingOrb;
