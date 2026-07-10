import { motion } from 'framer-motion';
import { useOrbState } from './useOrbState';

export function EnergyRings() {
  const { state, audioLevel, getColors } = useOrbState();
  const colors = getColors();
  
  const getRotationSpeed = () => {
    switch (state) {
      case 'thinking': return 20;
      case 'speaking': return 15;
      case 'coding': return 18;
      case 'idle': return 30;
      default: return 25;
    }
  };
  
  const scale = 1 + (audioLevel * 0.3);
  
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <svg width="600" height="600" viewBox="0 0 600 600" className="absolute">
        <defs>
          <linearGradient id="ring-gradient-1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={colors.primary}>
              <animate attributeName="stop-color" values={`${colors.primary};${colors.secondary};${colors.primary}`} dur="4s" repeatCount="indefinite" />
            </stop>
            <stop offset="50%" stopColor={colors.secondary}>
              <animate attributeName="stop-color" values={`${colors.secondary};${colors.primary};${colors.secondary}`} dur="4s" repeatCount="indefinite" />
            </stop>
            <stop offset="100%" stopColor={colors.primary}>
              <animate attributeName="stop-color" values={`${colors.primary};${colors.secondary};${colors.primary}`} dur="4s" repeatCount="indefinite" />
            </stop>
          </linearGradient>
          
          <linearGradient id="ring-gradient-2" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={colors.secondary}>
              <animate attributeName="stop-color" values={`${colors.secondary};${colors.primary};${colors.secondary}`} dur="6s" repeatCount="indefinite" />
            </stop>
            <stop offset="100%" stopColor={colors.primary}>
              <animate attributeName="stop-color" values={`${colors.primary};${colors.secondary};${colors.primary}`} dur="6s" repeatCount="indefinite" />
            </stop>
          </linearGradient>
          
          <filter id="glow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        
        {/* Outer Energy Ring */}
        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: getRotationSpeed(), repeat: Infinity, ease: "linear" }}
          style={{ originX: 0.5, originY: 0.5 }}
        >
          <ellipse cx="300" cy="300" rx="240" ry="200" fill="none" stroke="url(#ring-gradient-1)" strokeWidth="3" opacity="0.6" filter="url(#glow)" />
        </motion.g>
        
        {/* Inner Energy Ring */}
        <motion.g
          animate={{ rotate: -360 }}
          transition={{ duration: getRotationSpeed() * 0.7, repeat: Infinity, ease: "linear" }}
          style={{ originX: 0.5, originY: 0.5 }}
        >
          <ellipse cx="300" cy="300" rx="200" ry="240" fill="none" stroke="url(#ring-gradient-2)" strokeWidth="2.5" opacity="0.7" filter="url(#glow)" />
        </motion.g>
        
        {/* Particle Ring */}
        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: getRotationSpeed() * 1.3, repeat: Infinity, ease: "linear" }}
          style={{ originX: 0.5, originY: 0.5 }}
        >
          <ellipse cx="300" cy="300" rx="180" ry="160" fill="none" stroke={colors.primary} strokeWidth="1.5" strokeDasharray="5 10" opacity="0.5" />
        </motion.g>
        
        {/* Core Glow Ring */}
        <motion.circle
          cx="300" cy="300" r="120" fill="none" stroke={colors.glow} strokeWidth="4" opacity="0.4"
          animate={{ scale: [1, scale, 1], opacity: [0.4, 0.6, 0.4] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          style={{ originX: 0.5, originY: 0.5 }}
        />
      </svg>
    </div>
  );
}