import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Code2, Brain, BookOpen, LayoutGrid, Puzzle, Settings } from 'lucide-react'
import LivingOrb from '../components/orb/LivingOrb'

type WorkspaceId = 'build' | 'memory' | 'knowledge' | 'canvas' | 'plugins' | 'settings'

const ORBITAL_NODES = [
  { id: 'build',     label: 'Build',     icon: <Code2 size={24} />,  color: '#818cf8', angle: 270 },
  { id: 'memory',    label: 'Memory',    icon: <Brain size={24} />,    color: '#c084fc', angle: 210 },
  { id: 'knowledge', label: 'Knowledge', icon: <BookOpen size={24} />, color: '#22d3ee', angle: 330 },
  { id: 'plugins',   label: 'Plugins',   icon: <Puzzle size={24} />,   color: '#fbbf24', angle: 150 },
  { id: 'canvas',    label: 'Canvas',    icon: <LayoutGrid size={24} />, color: '#34d399', angle: 30 },
  { id: 'settings',  label: 'Settings',  icon: <Settings size={24} />,  color: '#94a3b8', angle: 90 },
]

interface LandingProps {
  onNavigate: (id: WorkspaceId) => void
}

export default function Landing({ onNavigate }: LandingProps) {
  const [_, setHovered] = useState<string | null>(null)
  const [orbitAngle, setOrbitAngle] = useState(0)

  useEffect(() => {
    let start = 0
    let animationId: number

    const animate = (timestamp: number) => {
      if (!start) start = timestamp
      const elapsed = timestamp - start
      const angle = (elapsed / 90000) * 360
      setOrbitAngle(angle % 360)
      animationId = requestAnimationFrame(animate)
    }

    animationId = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(animationId)
  }, [])

  const ORB_SIZE = 320
  const ORBIT_RADIUS = 240

  return (
    <div
       className="h-screen overflow-hidden text-slate-100 flex items-center justify-center w-full flex-1"
      style={{
        background: 'radial-gradient(ellipse at 25% 15%, rgba(99,102,241,0.08) 0%, transparent 52%), radial-gradient(ellipse at 75% 85%, rgba(168,85,247,0.06) 0%, transparent 52%), #08080f',
        fontFamily: "'Space Grotesk', 'Inter', sans-serif",
      }}
    >
      {/* Subtle grid background */}
      <div
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage: 'linear-gradient(rgba(99,102,241,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.6) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
        }}
      />

      {/* Orbital system - NO fixed container, fills the available space */}
      <div className="relative w-full h-full flex items-center justify-center">
        {/* Orbit track rings - centered on the orb */}
        <div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ORBIT_RADIUS * 2 + 60,
            height: ORBIT_RADIUS * 2 + 60,
            border: '1px solid rgba(255,255,255,0.04)',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
          }}
        />
        <div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ORBIT_RADIUS * 2 + 110,
            height: ORBIT_RADIUS * 2 + 110,
            border: '1px solid rgba(255,255,255,0.025)',
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
          }}
        />

        {/* Central Living Orb — STATIC at mathematical center */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 flex flex-col items-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
          >
            <div style={{ width: ORB_SIZE, height: ORB_SIZE }}>
              <LivingOrb size="lg" />
            </div>
          </motion.div>
        </div>

        {/* Orbiting satellite nodes — revolve around orb while maintaining orientation */}
        {ORBITAL_NODES.map((node) => {
          const animatedRad = ((node.angle - 90 + orbitAngle) * Math.PI) / 180
          const x = Math.cos(animatedRad) * ORBIT_RADIUS
          const y = Math.sin(animatedRad) * ORBIT_RADIUS

          return (
            <div
              key={node.id}
              className="absolute z-20 flex flex-col items-center gap-2"
              style={{
                left: '50%',
                top: '50%',
                transform: `translate(-50%, -50%) translate(${x}px, ${y}px)`,
              }}
            >
              <motion.button
                onClick={() => onNavigate(node.id as WorkspaceId)}
                onHoverStart={() => setHovered(node.id)}
                onHoverEnd={() => setHovered(null)}
                className="relative flex flex-col items-center"
                whileHover={{ scale: 1.18 }}
                whileTap={{ scale: 0.94 }}
              >
                <motion.div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center"
                  style={{
                    background: 'rgba(255,255,255,0.05)',
                    border: `1px solid ${node.color}35`,
                    backdropFilter: 'blur(10px)',
                    boxShadow: `0 4px 24px rgba(0,0,0,0.3)`,
                  }}
                  whileHover={{
                    background: `${node.color}18`,
                    borderColor: `${node.color}70`,
                    boxShadow: `0 0 24px ${node.color}50, 0 4px 24px rgba(0,0,0,0.3)`,
                  }}
                  transition={{ duration: 0.2 }}
                >
                  {node.icon}
                </motion.div>
                <span
                  className="text-slate-400 whitespace-nowrap select-none"
                  style={{ fontSize: '11px', letterSpacing: '0.03em' }}
                >
                  {node.label}
                </span>
              </motion.button>
            </div>
          )
        })}
      </div>

      {/* Tagline */}
      <motion.p
        className="text-center text-slate-500 text-xs tracking-widest uppercase absolute bottom-8 left-1/2 -translate-x-1/2"
        style={{ letterSpacing: '0.12em' }}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        Living Intelligence · Local First
      </motion.p>
    </div>
  )
}
