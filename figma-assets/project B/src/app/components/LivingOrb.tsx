import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import globeImage from 'figma:asset/ef6432358e70cd07cef418bda499a8b4438f8bd9.png';

// Deterministic particle positions (no Math.random() on render)
const PARTICLES = [
  { top: 10, left: 72, delay: 0,   size: 2.5, color: '#818cf8' },
  { top: 72, left: 8,  delay: 0.7, size: 2,   color: '#22d3ee' },
  { top: 28, left: 4,  delay: 1.2, size: 2.5, color: '#c084fc' },
  { top: 5,  left: 38, delay: 1.8, size: 1.5, color: '#818cf8' },
  { top: 84, left: 58, delay: 0.4, size: 2,   color: '#22d3ee' },
  { top: 50, left: 93, delay: 1.5, size: 2,   color: '#c084fc' },
  { top: 18, left: 91, delay: 1.0, size: 1.5, color: '#818cf8' },
  { top: 90, left: 26, delay: 2.0, size: 2,   color: '#22d3ee' },
  { top: 42, left: 2,  delay: 0.6, size: 1.5, color: '#c084fc' },
  { top: 64, left: 88, delay: 1.3, size: 2,   color: '#818cf8' },
];

// Waveform bars for speaking state
const WAVE_BARS = [0, 1, 2, 3, 4, 5, 6];
const WAVE_HEIGHTS = [14, 22, 30, 36, 30, 22, 14];

export type OrbState = 'idle' | 'listening' | 'thinking' | 'speaking';

interface LivingOrbProps {
  isListening?: boolean;
  isSpeaking?: boolean;
  isThinking?: boolean;
  size?: 'xs' | 'sm' | 'md' | 'lg';
}

function getOrbState(isListening?: boolean, isSpeaking?: boolean, isThinking?: boolean): OrbState {
  if (isListening) return 'listening';
  if (isThinking) return 'thinking';
  if (isSpeaking) return 'speaking';
  return 'idle';
}

// Per-state glow configs
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

export function LivingOrb({ isListening, isSpeaking, isThinking, size = 'lg' }: LivingOrbProps) {
  const state = getOrbState(isListening, isSpeaking, isThinking);
  const cfg = STATE_CONFIG[state];

  const sizeMap = { xs: 40, sm: 80, md: 160, lg: 320 };
  const px = sizeMap[size];

  // Ring sizes relative to orb container (spec: ring1=280/340, ring2=240/340)
  const ring1 = Math.round(px * 0.82);
  const ring2 = Math.round(px * 0.71);
  const corePx = Math.round(px * 0.56);
  const outerGlowOffset = Math.round(px * 0.22);
  const midRingOffset = Math.round(px * 0.1);

  const showParticles = size === 'lg' || size === 'md';
  const showRings = size !== 'xs';

  return (
    <div
      className="relative flex items-center justify-center shrink-0"
      style={{ width: px, height: px }}
    >
      {/* ── Layer 1: Outer ambient glow ─────────────────── */}
      <motion.div
        className="absolute rounded-full pointer-events-none"
        style={{
          inset: -outerGlowOffset,
          background: `radial-gradient(circle, ${cfg.glowColor} 0%, ${cfg.glowColor2} 45%, transparent 70%)`,
          filter: 'blur(24px)',
        }}
        animate={{ scale: cfg.scale, opacity: state === 'idle' ? [0.7, 1, 0.7] : [0.8, 1, 0.8] }}
        transition={{ duration: cfg.scaleDuration, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* ── Thinking multi-color pulse overlay ──────────── */}
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

      {/* ── Layer 2: Energy ring 1 (outer) ──────────────── */}
      {showRings && (
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ring1 + outerGlowOffset,
            height: ring1 + outerGlowOffset,
            border: `1px solid ${cfg.ring1Color}`,
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: cfg.ring1Duration, repeat: Infinity, ease: 'linear' }}
        />
      )}

      {/* ── Layer 3: Energy ring 2 (inner, dashed cyan accent) ── */}
      {showRings && (
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ring2,
            height: ring2,
            border: `1px solid ${cfg.ring2Color}`,
          }}
          animate={{ rotate: -360 }}
          transition={{ duration: cfg.ring2Duration, repeat: Infinity, ease: 'linear' }}
        />
      )}

      {/* ── Speaking waveform rings emanating outward ────── */}
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

      {/* ── Listening active pulse ring ──────────────────── */}
      <AnimatePresence>
        {state === 'listening' && (
          <motion.div
            className="absolute rounded-full pointer-events-none"
            style={{ width: corePx + 16, height: corePx + 16, border: '2px solid rgba(34,211,238,0.55)' }}
            initial={{ scale: 1, opacity: 0 }}
            animate={{ scale: [1, 1.25, 1.5], opacity: [0.7, 0.4, 0] }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }}
          />
        )}
      </AnimatePresence>

      {/* ── Layer 4: Core globe image ─────────────────────── */}
      <motion.img
        src={globeImage}
        alt="Living Intelligence Orb"
        className="relative z-10 object-contain pointer-events-none select-none"
        style={{ width: corePx + 40, height: corePx + 40, filter: cfg.filter }}
        animate={{ scale: cfg.scale }}
        transition={{ duration: cfg.scaleDuration, repeat: Infinity, ease: 'easeInOut' }}
      />

      {/* ── Layer 5: Inner pulse dot ─────────────────────── */}
      {size === 'lg' && (
        <motion.div
          className="absolute z-20 rounded-full bg-white pointer-events-none"
          style={{ width: 10, height: 10, boxShadow: '0 0 12px rgba(255,255,255,0.9)' }}
          animate={{ opacity: [0.35, 0.9, 0.35], scale: [0.8, 1.2, 0.8] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        />
      )}

      {/* ── Floating particles ───────────────────────────── */}
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
            animate={{ y: [0, -12, 0], x: [0, 6, 0], opacity: [0.2, 0.9, 0.2] }}
            transition={{ duration: 3.5 + p.delay, repeat: Infinity, delay: p.delay, ease: 'easeInOut' }}
          />
        ))}

      {/* ── Speaking waveform bars below orb (lg only) ──── */}
      <AnimatePresence>
        {state === 'speaking' && size === 'lg' && (
          <motion.div
            className="absolute flex items-end gap-1 pointer-events-none z-20"
            style={{ bottom: -44, left: '50%', transform: 'translateX(-50%)' }}
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
                  width: 3,
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
}
