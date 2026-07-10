import { motion } from 'framer-motion'
import { useThemeStore } from '@/stores/themeStore'
import { cn } from '@/lib/utils'

export function CosmicCore() {
  const { currentTheme } = useThemeStore()

  return (
    <div className="relative w-96 h-96 flex items-center justify-center">
      {/* Outer glow */}
      <motion.div
        animate={{
          scale: [1, 1.1, 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: 4,
          repeat: Infinity,
          ease: "easeInOut"
        }}
        className="absolute inset-0 rounded-full bg-gradient-to-r from-cyan-500/20 to-orange-500/20 blur-3xl"
      />

      {/* Rotating rings */}
      <motion.div
        animate={{ rotate: 360 }}
        transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        className="absolute w-full h-full rounded-full border border-cyan-500/20"
      />
      <motion.div
        animate={{ rotate: -360 }}
        transition={{ duration: 15, repeat: Infinity, ease: "linear" }}
        className="absolute w-4/5 h-4/5 rounded-full border border-orange-500/30"
      />

      {/* Core orb */}
      <motion.div
        animate={{
          scale: [1, 1.05, 1],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut"
        }}
        className={cn(
          "relative w-32 h-32 rounded-full orb-gradient",
          "shadow-[0_0_60px_rgba(14,165,233,0.5)]"
        )}
      >
        {/* Inner glow */}
        <div className="absolute inset-2 rounded-full bg-gradient-to-br from-white/20 to-transparent" />
      </motion.div>

      {/* Particles */}
      {[...Array(8)].map((_, i) => (
        <motion.div
          key={i}
          animate={{
            rotate: 360,
            scale: [1, 1.2, 1],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: "linear",
            delay: i * 0.5
          }}
          className="absolute w-full h-full"
          style={{ transform: `rotate(${i * 45}deg)` }}
        >
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-2 h-2 bg-cyan-400 rounded-full" />
        </motion.div>
      ))}
    </div>
  )
}