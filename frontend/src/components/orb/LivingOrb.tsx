/**
 * LivingOrb — Project B design, Zaram architecture
 *
 * Globe-based orb with particles and state-driven effects.
 * Driven by orbStore state: idle, listening, thinking, speaking
 *
 * Architecture: Reads orbStore for state, renders globe image with dynamic effects.
 */
import { motion, AnimatePresence } from 'framer-motion';
import { useOrbStore } from '@/stores';
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

export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface LivingOrbProps {
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  /** When true, intensifies the existing glow via brightness amplification.
   *  Derives from existing STATE_CONFIG colors — no new hues introduced. */
  emphasis?: boolean;
}

// Per-state visual configs
const STATE_CONFIG = {
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
};

const LivingOrb = ({ size = 'xl', className = '', emphasis = false }: LivingOrbProps) => {
  const { orbState } = useOrbStore();
  const state = orbState as OrbState;
  const cfg = STATE_CONFIG[state];

  /** Amplify existing glow via brightness — no new colors */
  const orbBrightness = emphasis ? ' brightness(1.4)' : '';

  // Map size to pixel dimensions (matching Project A sizes)
  const sizeMap = { xs: 80, sm: 104, md: 192, lg: 320, xl: 560 };
  const px = sizeMap[size];

  // Component proportions
  const ring1 = Math.round(px * 0.82);
  const ring2 = Math.round(px * 0.71);
  const corePx = Math.round(px * 0.56);
  const outerGlowOffset = Math.round(px * 0.22);

  const showParticles = size === 'xl' || size === 'lg' || size === 'md';
  const showRings = size !== 'xs' && size !== 'sm';

  return (
    <div
      className={`relative flex items-center justify-center shrink-0 ${className}`}
      style={{ width: px, height: px }}
    >
      {/* Outer ambient glow — amplified when emphasis is active */}
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          inset: -outerGlowOffset,
          background: `radial-gradient(circle, ${cfg.glowColor} 0%, ${cfg.glowColor2} 45%, transparent 70%)`,
          filter: `blur(24px)${emphasis ? ' brightness(1.8)' : ''}`,
        }}
        animate={{ scale: cfg.scale, opacity: state === 'idle' ? [0.7, 1, 0.7] : [0.8, 1, 0.8] }}
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

      {/* Energy ring 1 (outer) — STATIC, no rotation */}
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

      {/* Energy ring 2 (inner) — STATIC, no rotation */}
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

      {/* Core globe image — drop-shadow amplified when emphasis is active */}
      <motion.img
        src={globeImage}
        alt="Living Intelligence Orb"
        className="relative z-10 object-contain pointer-events-none select-none"
        style={{ width: corePx + 40, height: corePx + 40, filter: `${cfg.filter}${orbBrightness}` }}
        animate={{ scale: cfg.scale }}
        transition={{ duration: cfg.scaleDuration, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* Inner pulse dot */}
      {(size === 'xl' || size === 'lg') && (
        <motion.div
          className="absolute z-20 rounded-full bg-white pointer-events-none"
          style={{ width: 20, height: 20, boxShadow: '0 0 24px rgba(255,255,255,0.9)' }}
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
