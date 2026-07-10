import { motion } from 'framer-motion';
import { EnergyRings } from './EnergyRings';
import { ParticleSystem } from './ParticleSystem';
import { useOrbState } from './useOrbState';

export function LivingOrb() {
  const { state, audioLevel, hasInteracted, getColors } = useOrbState();
  const colors = getColors();
  
  // REDUCED: Amplitude effects halved (was 0.4, now 0.2)
  const coreScale = 1 + (audioLevel * 0.2);
  const glowScale = 1 + (audioLevel * 0.15);
  
  return (
    <div className="relative w-[600px] h-[600px] flex items-center justify-center">
      {/* Background Glow - REDUCED amplitude */}
      <motion.div
        className="absolute w-96 h-96 rounded-full blur-3xl"
        style={{ background: colors.glow }}
        animate={{
          scale: glowScale,
          opacity: 0.2 + (audioLevel * 0.2),
        }}
        transition={{ duration: 0.1, ease: "linear" }}
      />
      
      {/* Energy Rings */}
      <EnergyRings />
      
      {/* Particle System */}
      <ParticleSystem />
      
      {/* Core Energy - REDUCED amplitude */}
      <motion.div
        className="absolute w-32 h-32 rounded-full"
        style={{
          background: `radial-gradient(circle, ${colors.primary} 0%, ${colors.secondary} 50%, transparent 100%)`,
          boxShadow: `0 0 ${40 + audioLevel * 30}px ${colors.glow}, 0 0 ${80 + audioLevel * 40}px ${colors.glow}`,
        }}
        animate={{
          scale: coreScale,
        }}
        transition={{ duration: 0.1, ease: "linear" }}
      />
      
      {/* Inner Core - REDUCED amplitude */}
      <motion.div
        className="absolute w-16 h-16 rounded-full"
        style={{
          background: colors.primary,
          boxShadow: `0 0 ${30 + audioLevel * 20}px ${colors.primary}, inset 0 0 20px ${colors.secondary}`,
        }}
        animate={{
          scale: 1 + (audioLevel * 0.1),
          opacity: 0.8 + (audioLevel * 0.1),
        }}
        transition={{ duration: 0.1, ease: "linear" }}
      />
    </div>
  );
}