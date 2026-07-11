import { motion } from 'framer-motion';
import { EnergyRings } from './EnergyRings';
import { ParticleSystem } from './ParticleSystem';
import { useOrbState } from './useOrbState';

export function LivingOrb() {
  const { audioLevel, getColors } = useOrbState();
  const colors = getColors();
  
  const coreScale = 1 + (audioLevel * 0.2);
  const glowScale = 1 + (audioLevel * 0.15);

  return (
    <div className="relative w-[600px] h-[600px] flex items-center justify-center">
      {/* Background Glow - Audio reactive + constant breathing */}
      <motion.div
        className="absolute w-96 h-96 rounded-full blur-3xl"
        style={{ background: colors.glow }}
        animate={{
          scale: [glowScale, glowScale * 1.05, glowScale],
          opacity: [0.2 + (audioLevel * 0.4), 0.3 + (audioLevel * 0.4), 0.2 + (audioLevel * 0.4)],
        }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      />
      
      <EnergyRings />
      <ParticleSystem />
      
      {/* Core Energy - Audio reactive + constant breathing */}
      <motion.div
        className="absolute w-32 h-32 rounded-full"
        style={{
          background: `radial-gradient(circle, ${colors.primary} 0%, ${colors.secondary} 50%, transparent 100%)`,
          boxShadow: `0 0 ${40 + audioLevel * 60}px ${colors.glow}, 0 0 ${80 + audioLevel * 80}px ${colors.glow}`,
        }}
        animate={{
          scale: [coreScale, coreScale * 1.08, coreScale],
        }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      />
      
      {/* Inner Core - Bright center */}
      <motion.div
        className="absolute w-16 h-16 rounded-full"
        style={{
          background: colors.primary,
          boxShadow: `0 0 ${30 + audioLevel * 40}px ${colors.primary}, inset 0 0 20px ${colors.secondary}`,
        }}
        animate={{
          scale: [1, 1.1, 1],
          opacity: [0.8, 1, 0.8],
        }}
        transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}