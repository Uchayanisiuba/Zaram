import { motion } from 'framer-motion';
import { EnergyRings } from './EnergyRings';
import { ParticleSystem } from './ParticleSystem';
import { useOrbState } from './useOrbState';

export function LivingOrb() {
  const { audioLevel, getColors } = useOrbState();
  const colors = getColors();
  
  return (
    <div className="relative w-[600px] h-[600px] flex items-center justify-center">
      {/* Background Glow */}
      <motion.div
        className="absolute w-96 h-96 rounded-full blur-3xl"
        style={{ background: colors.glow }}
        animate={{
          scale: [1, 1.1 + (audioLevel * 0.2), 1],
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      />
      
      <EnergyRings />
      <ParticleSystem />
      
      {/* Core Energy */}
      <motion.div
        className="absolute w-32 h-32 rounded-full"
        style={{
          background: `radial-gradient(circle, ${colors.primary} 0%, ${colors.secondary} 50%, transparent 100%)`,
          boxShadow: `0 0 60px ${colors.glow}, 0 0 100px ${colors.glow}`,
        }}
        animate={{
          scale: [1, 1.2 + (audioLevel * 0.3), 1],
        }}
        transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
      />
      
      {/* Inner Core */}
      <motion.div
        className="absolute w-16 h-16 rounded-full"
        style={{
          background: colors.primary,
          boxShadow: `0 0 40px ${colors.primary}, inset 0 0 20px ${colors.secondary}`,
        }}
        animate={{
          scale: [1, 1.1, 1],
          opacity: [0.8, 1, 0.8],
        }}
        transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}