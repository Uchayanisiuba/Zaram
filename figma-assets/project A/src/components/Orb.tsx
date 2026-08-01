import { useEffect, useRef } from 'react'

interface Particle {
  id: number
  x: number
  y: number
  size: number
  delay: number
  duration: number
  dx: number
  dy: number
  color: string
}

interface OrbProps {
  size?: 'xl' | 'lg' | 'md' | 'sm'
  mode?: 'idle' | 'thinking' | 'active'
  className?: string
}

const PARTICLE_COLORS = [
  'rgba(129, 140, 248, 0.9)',
  'rgba(34, 211, 238, 0.9)',
  'rgba(139, 92, 246, 0.8)',
  'rgba(255, 255, 255, 0.7)',
  'rgba(96, 165, 250, 0.8)',
]

const SIZES = {
  xl: 280,
  lg: 160,
  md: 96,
  sm: 52,
}

export default function Orb({ size = 'xl', mode = 'idle', className = '' }: OrbProps) {
  const dim = SIZES[size]
  const particles = useRef<Particle[]>(
    Array.from({ length: size === 'xl' ? 18 : size === 'lg' ? 10 : 6 }, (_, i) => ({
      id: i,
      x: 30 + Math.random() * 40,
      y: 30 + Math.random() * 40,
      size: 1.5 + Math.random() * 3,
      delay: Math.random() * 4,
      duration: 2.5 + Math.random() * 3,
      dx: (Math.random() - 0.5) * 60,
      dy: -(20 + Math.random() * 60),
      color: PARTICLE_COLORS[Math.floor(Math.random() * PARTICLE_COLORS.length)],
    }))
  ).current

  const glowSize = dim * 1.6
  const ringCount = size === 'xl' ? 3 : size === 'lg' ? 2 : 1

  return (
    <div
      className={className}
      style={{
        position: 'relative',
        width: dim,
        height: dim,
        flexShrink: 0,
      }}
    >
      {/* Atmospheric outer glow */}
      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '50%',
          width: glowSize,
          height: glowSize,
          marginLeft: -glowSize / 2,
          marginTop: -glowSize / 2,
          borderRadius: '50%',
          background:
            mode === 'thinking'
              ? 'radial-gradient(circle, rgba(139,92,246,0.25) 0%, rgba(6,182,212,0.12) 45%, transparent 70%)'
              : mode === 'active'
              ? 'radial-gradient(circle, rgba(99,102,241,0.35) 0%, rgba(6,182,212,0.18) 45%, transparent 70%)'
              : 'radial-gradient(circle, rgba(99,102,241,0.2) 0%, rgba(6,182,212,0.08) 45%, transparent 70%)',
          filter: 'blur(24px)',
          animation: 'orb-breathe 3.5s ease-in-out infinite',
          pointerEvents: 'none',
        }}
      />

      {/* Expanding energy rings */}
      {Array.from({ length: ringCount }, (_, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: dim * 1.1,
            height: dim * 1.1,
            borderRadius: '50%',
            border: '1px solid rgba(99,102,241,0.35)',
            animation: 'ring-expand 3.2s ease-out infinite',
            animationDelay: `${i * 1.07}s`,
            pointerEvents: 'none',
          }}
        />
      ))}

      {/* Outer rotating plasma layer */}
      <div
        style={{
          position: 'absolute',
          inset: -6,
          borderRadius: '50%',
          background:
            'conic-gradient(from 0deg, #4f46e5, #7c3aed, #0891b2, #1d4ed8, #6366f1, #9333ea, #4f46e5)',
          filter: `blur(${dim * 0.08}px)`,
          animation: 'orb-rotate 6s linear infinite',
          opacity: 0.85,
        }}
      />

      {/* Inner counter-rotating layer */}
      <div
        style={{
          position: 'absolute',
          inset: dim * 0.06,
          borderRadius: '50%',
          background:
            'conic-gradient(from 180deg, #22d3ee, #818cf8, #4f46e5, #7c3aed, #0891b2, #22d3ee)',
          filter: `blur(${dim * 0.06}px)`,
          animation: 'orb-rotate-reverse 4s linear infinite',
          opacity: 0.7,
        }}
      />

      {/* Deep plasma body */}
      <div
        style={{
          position: 'absolute',
          inset: dim * 0.08,
          borderRadius: '50%',
          background:
            'radial-gradient(circle at 40% 38%, rgba(255,255,255,0.5) 0%, rgba(129,140,248,0.95) 25%, rgba(99,102,241,0.9) 50%, rgba(30,20,80,0.7) 80%)',
          filter: `blur(${dim * 0.025}px)`,
          animation: 'orb-breathe 2.8s ease-in-out infinite',
          animationDelay: '0.4s',
        }}
      />

      {/* Bright inner core */}
      <div
        style={{
          position: 'absolute',
          inset: '30%',
          borderRadius: '50%',
          background:
            'radial-gradient(circle at 45% 40%, rgba(255,255,255,1) 0%, rgba(220,225,255,0.9) 30%, rgba(167,139,250,0.6) 65%, transparent 100%)',
          filter: `blur(${dim * 0.012}px)`,
        }}
      />

      {/* Hot white center pinpoint */}
      <div
        style={{
          position: 'absolute',
          inset: '42%',
          borderRadius: '50%',
          background: 'radial-gradient(circle, #ffffff 0%, rgba(255,255,255,0.6) 60%, transparent 100%)',
        }}
      />

      {/* Particles */}
      {(size === 'xl' || size === 'lg') &&
        particles.map((p) => (
          <div
            key={p.id}
            style={{
              position: 'absolute',
              left: `${p.x}%`,
              top: `${p.y}%`,
              width: p.size,
              height: p.size,
              borderRadius: '50%',
              background: p.color,
              boxShadow: `0 0 ${p.size * 3}px ${p.color}`,
              animation: `particle-rise ${p.duration}s ease-out ${p.delay}s infinite`,
              '--px': `${p.dx}px`,
              '--py': `${p.dy}px`,
            } as React.CSSProperties}
          />
        ))}

      {/* Thinking mode overlay */}
      {mode === 'thinking' && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            background:
              'conic-gradient(from 0deg, rgba(139,92,246,0.4), rgba(99,102,241,0.4), rgba(6,182,212,0.4), rgba(139,92,246,0.4))',
            animation: 'orb-rotate 1.5s linear infinite',
            filter: `blur(${dim * 0.04}px)`,
          }}
        />
      )}
    </div>
  )
}
