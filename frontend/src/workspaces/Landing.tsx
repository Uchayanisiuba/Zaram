import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { Brain, BookOpen, Settings } from 'lucide-react'
import LivingOrb from '../components/orb/LivingOrb'
import OrbStatusLabel from '../components/orb/OrbStatusLabel'
import { useChatModeStore } from '@/stores/chatModeStore'
import { useLayoutStore, orbGeometry } from '@/stores/layoutStore'
import { useSourceStore } from '@/stores/sourceStore'
import { useSystemStore } from '@/stores/systemStore'
import { useIsReducedMotion } from '@/hooks/useReducedMotion'
import { useViewport } from '@/hooks/useViewport'

type WorkspaceId = 'memory' | 'knowledge' | 'settings'

// Build, Canvas and Plugins are out of scope for v1 and no longer appear here.
// Their surfaces are preserved in src/legacy/.
const ORBITAL_NODES = [
  { id: 'memory',    label: 'Memory',    icon: <Brain size={24} />,    color: '#c084fc', angle: 210 },
  { id: 'knowledge', label: 'Knowledge', icon: <BookOpen size={24} />, color: '#22d3ee', angle: 330 },
  { id: 'settings',  label: 'Settings',  icon: <Settings size={24} />,  color: '#94a3b8', angle: 90 },
]

interface LandingProps {
  onNavigate: (id: WorkspaceId) => void
  onOrbTap?: () => void
}

const ORB_SIZE = 320
const ORBIT_RADIUS = 240
/** The orbital system is rendered inside this scale, so any transform applied
 *  within it is multiplied by the same factor. See orbGeometry(). */
const CONTAINER_SCALE = 1.4

export default function Landing({ onNavigate, onOrbTap }: LandingProps) {
  const [_, setHovered] = useState<string | null>(null)
  const reduced = useIsReducedMotion()
  const { chatView, closeChat } = useChatModeStore()
  const chat = chatView === 'chat'

  // The orb's position and size are derived from the conversation panel's
  // width, so dragging the panel moves the orb with it.
  const chatFraction = useLayoutStore((s) => s.chatFraction)
  const isResizing = useLayoutStore((s) => s.isResizing)
  // Source panels open in the orb's space. While any is open the orb recedes —
  // blurred and dimmed — so the panel reads as being in front of it rather than
  // competing with it. It returns when the last panel closes.
  const panelsOpen = useSourceStore((s) => s.open.length > 0)
  // The top bar is hidden on this surface, so the landing starts the poll
  // itself rather than depending on a component that is not mounted.
  const startPolling = useSystemStore((s) => s.startPolling)
  useEffect(() => startPolling(), [startPolling])
  const { width: viewportWidth } = useViewport()
  const { shiftX, zoom } = orbGeometry({
    viewportWidth,
    chatFraction,
    chatOpen: chat,
    orbSize: ORB_SIZE,
    containerScale: CONTAINER_SCALE,
  })

  // --- Orbital rAF: gated to 'landing' so the orbit FREEZES during chat.
  // Continuity refs ensure the loop resumes from the frozen angle (no jump to 0).
  const [orbitAngle, setOrbitAngle] = useState(0)
  const rafRef = useRef<number>(0)
  const startRef = useRef<number>(0)
  const offsetRef = useRef<number>(0)
  const elapsedRef = useRef<number>(0)

  useEffect(() => {
    if (chat) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      return
    }
    // On resume, continue from the frozen elapsed time so the angle is continuous.
    if (elapsedRef.current > 0) {
      offsetRef.current = elapsedRef.current
      startRef.current = 0
    }
    const tick = (ts: number) => {
      if (!startRef.current) startRef.current = ts
      const elapsed = (ts - startRef.current) + offsetRef.current
      elapsedRef.current = elapsed
      setOrbitAngle((elapsed / 90000) * 360)
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [chat])

  // Escape reverses the transition (closes chat).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && chat) closeChat()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [chat, closeChat])

  const ring1Size = ORBIT_RADIUS * 2 + 60
  const ring2Size = ORBIT_RADIUS * 2 + 110

  const orbShift = { scale: zoom, x: shiftX, y: 0 }
  const orbTransition = isResizing
    ? // Track the divider exactly while it is being dragged; a spring here
      // makes the orb drift behind the panel edge.
      { duration: 0 }
    : chat
      ? reduced ? { type: 'tween' as const, duration: 0.22 } : { type: 'spring' as const, stiffness: 200, damping: 24 }
      : { type: 'tween' as const, duration: 0.35 }

  return (
    <div
      className="h-screen overflow-hidden text-slate-100 flex items-center justify-center w-full flex-1"
      // Gradient and grid now come from .zaram-backdrop on the app shell, so
      // the landing and the workspaces share one ground instead of the landing
      // painting its own.
      style={{ fontFamily: 'var(--font-display), var(--font-sans), sans-serif' }}
    >
      {/* Orbital system — keeps the same shell; only the orbital motion is gated. */}
      <div
        className="relative w-full h-full flex items-center justify-center"
        style={{ transform: 'scale(1.4)', transformOrigin: 'center center' }}
      >
        {/* Orbit track rings — dissolve / restore (centering via framer offset, never inline transform). */}
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ring1Size, height: ring1Size,
            left: '50%', top: '50%',
            x: -(ring1Size / 2), y: -(ring1Size / 2),
            border: '1px solid rgba(255,255,255,0.04)',
          }}
          initial={false}
          animate={chat ? { opacity: 0, scale: reduced ? 1 : 1.15 } : { opacity: 1, scale: 1 }}
          transition={{ duration: reduced ? 0.2 : 0.4 }}
        />
        <motion.div
          className="absolute rounded-full pointer-events-none"
          style={{
            width: ring2Size, height: ring2Size,
            left: '50%', top: '50%',
            x: -(ring2Size / 2), y: -(ring2Size / 2),
            border: '1px solid rgba(255,255,255,0.025)',
          }}
          initial={false}
          animate={chat ? { opacity: 0, scale: reduced ? 1 : 1.15 } : { opacity: 1, scale: 1 }}
          transition={{ duration: reduced ? 0.2 : 0.4, delay: 0.04 }}
        />

        {/* Central Living Orb — zooms + glides into the open space beside the chat. */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10 flex flex-col items-center">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{
              opacity: panelsOpen ? 0.35 : 1,
              filter: panelsOpen ? 'blur(8px)' : 'blur(0px)',
              ...orbShift,
              scale: orbShift.scale * (panelsOpen ? 0.96 : 1),
            }}
            transition={chat || isResizing ? orbTransition : { duration: 0.4 }}
            whileTap={{ scale: zoom * 0.9 }}
            style={{ cursor: panelsOpen ? 'default' : 'pointer' }}
            onClick={panelsOpen ? undefined : onOrbTap}
          >
            <div style={{ width: ORB_SIZE, height: ORB_SIZE }}>
              <LivingOrb size="lg" emphasis />
            </div>
          </motion.div>

          {/* What the Orb is reporting, in words. The top bar is hidden here,
              so without this the landing has no status at all. Rides with the
              orb so it stays beneath it as the panel is resized. */}
          <motion.div
            className="mt-2"
            animate={{ x: shiftX, opacity: panelsOpen ? 0 : 1 }}
            transition={chat || isResizing ? orbTransition : { duration: 0.4 }}
          >
            <OrbStatusLabel dimmed={panelsOpen} />
          </motion.div>
        </div>

        {/* Orbiting satellite nodes — parent holds the FROZEN orbit (rAF), child
            carries the dispersal via framer so the two transforms never fight. */}
        {ORBITAL_NODES.map((node) => {
          const animatedRad = ((node.angle - 90 + orbitAngle) * Math.PI) / 180
          const restX = Math.cos(animatedRad) * ORBIT_RADIUS
          const restY = Math.sin(animatedRad) * ORBIT_RADIUS
          // Dispersal target: push ~0.8 * ORBIT_RADIUS further along the same angle.
          const dx = Math.cos(animatedRad) * ORBIT_RADIUS * 0.8
          const dy = Math.sin(animatedRad) * ORBIT_RADIUS * 0.8

          const dispersed = chat
            ? reduced ? { opacity: 0 } : { opacity: 0, scale: 0.4, x: dx, y: dy }
            : reduced ? { opacity: 1 } : { opacity: 1, scale: 1, x: 0, y: 0 }
          const childTransition = reduced
            ? { duration: 0.18 }
            : { type: 'spring' as const, stiffness: 240, damping: 26 }

          return (
            <div
              key={node.id}
              className="absolute z-20 flex flex-col items-center gap-2"
              style={{
                left: '50%', top: '50%',
                transform: `translate(-50%, -50%) translate(${restX}px, ${restY}px)`,
                pointerEvents: chat ? 'none' : 'auto',
              }}
            >
              <motion.div
                initial={false}
                animate={dispersed}
                transition={{ ...childTransition, delay: chat ? 0.06 * (node.angle / 60) : 0 }}
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
              </motion.div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
