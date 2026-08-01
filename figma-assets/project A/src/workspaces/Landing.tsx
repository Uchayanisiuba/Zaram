import { useState, useRef } from 'react'
import { Code2, Brain, BookOpen, LayoutGrid, Puzzle, Settings } from 'lucide-react'
import Orb from '../components/Orb'

type WorkspaceId = 'build' | 'memory' | 'knowledge' | 'canvas' | 'plugins' | 'settings'

interface OrbitalNode {
  id: WorkspaceId
  icon: React.ReactNode
  label: string
  description: string
  color: string
  glowColor: string
  angle: number
}

const ORBITAL_NODES: OrbitalNode[] = [
  {
    id: 'build', icon: <Code2 size={20} />, label: 'Build',
    description: 'Intelligent IDE', color: '#6366f1', glowColor: 'rgba(99,102,241,0.4)', angle: -90,
  },
  {
    id: 'memory', icon: <Brain size={20} />, label: 'Memory',
    description: 'Semantic graphs', color: '#06b6d4', glowColor: 'rgba(6,182,212,0.4)', angle: -30,
  },
  {
    id: 'knowledge', icon: <BookOpen size={20} />, label: 'Knowledge',
    description: 'Research surface', color: '#10b981', glowColor: 'rgba(16,185,129,0.4)', angle: 30,
  },
  {
    id: 'canvas', icon: <LayoutGrid size={20} />, label: 'Canvas',
    description: 'Infinite workspace', color: '#8b5cf6', glowColor: 'rgba(139,92,246,0.4)', angle: 90,
  },
  {
    id: 'plugins', icon: <Puzzle size={20} />, label: 'Plugins',
    description: 'AI extensions', color: '#f59e0b', glowColor: 'rgba(245,158,11,0.4)', angle: 150,
  },
  {
    id: 'settings', icon: <Settings size={20} />, label: 'Settings',
    description: 'Configuration', color: '#6b7099', glowColor: 'rgba(107,112,153,0.4)', angle: -150,
  },
]

const ORBITAL_RADIUS = 220

interface LandingProps {
  onNavigate: (id: WorkspaceId) => void
}

export default function Landing({ onNavigate }: LandingProps) {
  const [hovered, setHovered] = useState<WorkspaceId | null>(null)
  const [clicked, setClicked] = useState<WorkspaceId | null>(null)

  const handleNodeClick = (id: WorkspaceId) => {
    setClicked(id)
    setTimeout(() => onNavigate(id), 380)
  }

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      overflow: 'hidden',
      background: 'radial-gradient(ellipse 80% 60% at 50% 50%, rgba(30,20,80,0.4) 0%, transparent 70%)',
    }}>
      {/* Ambient background grid */}
      <div style={{
        position: 'absolute',
        inset: 0,
        backgroundImage: `
          linear-gradient(rgba(99,102,241,0.04) 1px, transparent 1px),
          linear-gradient(90deg, rgba(99,102,241,0.04) 1px, transparent 1px)
        `,
        backgroundSize: '48px 48px',
        maskImage: 'radial-gradient(ellipse 70% 70% at center, black 30%, transparent 80%)',
        WebkitMaskImage: 'radial-gradient(ellipse 70% 70% at center, black 30%, transparent 80%)',
      }} />

      {/* Orbital ring guide line */}
      <div style={{
        position: 'absolute',
        left: '50%',
        top: '50%',
        width: ORBITAL_RADIUS * 2,
        height: ORBITAL_RADIUS * 2,
        marginLeft: -ORBITAL_RADIUS,
        marginTop: -ORBITAL_RADIUS,
        borderRadius: '50%',
        border: '1px solid rgba(255,255,255,0.04)',
        pointerEvents: 'none',
      }} />
      <div style={{
        position: 'absolute',
        left: '50%',
        top: '50%',
        width: (ORBITAL_RADIUS + 6) * 2,
        height: (ORBITAL_RADIUS + 6) * 2,
        marginLeft: -(ORBITAL_RADIUS + 6),
        marginTop: -(ORBITAL_RADIUS + 6),
        borderRadius: '50%',
        border: '1px solid rgba(255,255,255,0.02)',
        pointerEvents: 'none',
      }} />

      {/* Slowly rotating orbital ring container */}
      <div style={{
        position: 'absolute',
        left: '50%',
        top: '50%',
        width: 0,
        height: 0,
        animation: 'orbit-ring 90s linear infinite',
      }}>
        {ORBITAL_NODES.map(node => {
          const rad = (node.angle * Math.PI) / 180
          const x = Math.cos(rad) * ORBITAL_RADIUS
          const y = Math.sin(rad) * ORBITAL_RADIUS
          const isHovered = hovered === node.id
          const isClicked = clicked === node.id

          return (
            <div
              key={node.id}
              style={{
                position: 'absolute',
                left: x,
                top: y,
                transform: 'translate(-50%, -50%)',
                animation: 'counter-orbit 90s linear infinite',
              }}
            >
              <button
                onClick={() => handleNodeClick(node.id)}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 8,
                  padding: '14px 18px',
                  borderRadius: 16,
                  background: isHovered
                    ? `rgba(${hexToRgb(node.color)}, 0.12)`
                    : 'rgba(13, 15, 22, 0.75)',
                  backdropFilter: 'blur(20px)',
                  border: `1px solid ${isHovered ? node.color + '50' : 'rgba(255,255,255,0.08)'}`,
                  cursor: 'pointer',
                  transform: `scale(${isHovered ? 1.1 : isClicked ? 0.92 : 1}) translateY(${isHovered ? -4 : 0}px)`,
                  transition: 'all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)',
                  boxShadow: isHovered
                    ? `0 8px 32px ${node.glowColor}, 0 0 0 1px ${node.color}30`
                    : '0 4px 16px rgba(0,0,0,0.4)',
                  minWidth: 88,
                  color: isHovered ? node.color : '#6b7099',
                }}
              >
                <div style={{
                  width: 44,
                  height: 44,
                  borderRadius: 12,
                  background: isHovered
                    ? `linear-gradient(135deg, ${node.color}30, ${node.color}15)`
                    : 'rgba(255,255,255,0.04)',
                  border: `1px solid ${isHovered ? node.color + '40' : 'rgba(255,255,255,0.08)'}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.25s',
                  boxShadow: isHovered ? `0 0 20px ${node.glowColor}` : 'none',
                }}>
                  {node.icon}
                </div>
                <div>
                  <div style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: isHovered ? '#e2e4ee' : '#b0b4cc',
                    fontFamily: "'Space Grotesk', sans-serif",
                    textAlign: 'center',
                    transition: 'color 0.2s',
                  }}>{node.label}</div>
                  <div style={{
                    fontSize: 10,
                    color: isHovered ? node.color : '#4a4f6a',
                    textAlign: 'center',
                    marginTop: 2,
                    transition: 'color 0.2s',
                  }}>{node.description}</div>
                </div>
              </button>
            </div>
          )
        })}
      </div>

      {/* Center Orb */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 24,
        animation: 'fade-in 0.6s ease',
        zIndex: 10,
      }}>
        <Orb size="xl" mode="idle" />

        <div style={{ textAlign: 'center' }}>
          <h1 style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontSize: 32,
            fontWeight: 700,
            letterSpacing: '-0.02em',
            margin: 0,
            lineHeight: 1.1,
          }}
            className="text-gradient-orb"
          >
            Zaram
          </h1>
          <p style={{
            fontSize: 14,
            color: '#4a4f6a',
            margin: '8px 0 0',
            fontWeight: 400,
          }}>
            Your local intelligence is ready
          </p>
        </div>

        {/* Quick hint */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '6px 14px',
          borderRadius: 99,
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(255,255,255,0.06)',
          fontSize: 11,
          color: '#4a4f6a',
        }}>
          <span>Choose a destination</span>
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#3a3f5c' }}>or ⌘K to search</span>
        </div>
      </div>
    </div>
  )
}

function hexToRgb(hex: string): string {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!result) return '99,102,241'
  return `${parseInt(result[1], 16)},${parseInt(result[2], 16)},${parseInt(result[3], 16)}`
}
