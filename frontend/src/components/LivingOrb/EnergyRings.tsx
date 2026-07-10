import { motion } from 'framer-motion';
import { useOrbState } from './useOrbState';

export function EnergyRings() {
  const { state, audioLevel, hasInteracted, getColors } = useOrbState();
  const colors = getColors();
  
  // REDUCED: All amplitude effects halved
  const ringPulse = 1 + audioLevel * 0.075;
  const glowIntensity = 0.4 + audioLevel * 0.3;
  const strokeWidth = 2 + audioLevel * 1;
  const rotationSpeed = Math.max(8, 30 - audioLevel * 12.5);
  
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
            <feGaussianBlur stdDeviation={3 + audioLevel * 3} result="coloredBlur"/>
            <feMerge>
              <feMergeNode in="coloredBlur"/>
              <feMergeNode in="SourceGraphic"/>
            </feMerge>
          </filter>
        </defs>
        
        {/* Outer Energy Ring */}
        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: rotationSpeed, repeat: Infinity, ease: "linear" }}
          style={{ originX: 0.5, originY: 0.5 }}
        >
          <ellipse
            cx="300"
            cy="300"
            rx={240 * ringPulse}
            ry={200 * ringPulse}
            fill="none"
            stroke="url(#ring-gradient-1)"
            strokeWidth={strokeWidth}
            opacity={glowIntensity}
            filter="url(#glow)"
          />
        </motion.g>
        
        {/* Inner Energy Ring */}
        <motion.g
          animate={{ rotate: -360 }}
          transition={{ duration: rotationSpeed * 0.7, repeat: Infinity, ease: "linear" }}
          style={{ originX: 0.5, originY: 0.5 }}
        >
          <ellipse
            cx="300"
            cy="300"
            rx={200 * ringPulse}
            ry={240 * ringPulse}
            fill="none"
            stroke="url(#ring-gradient-2)"
            strokeWidth={strokeWidth * 0.8}
            opacity={glowIntensity * 0.9}
            filter="url(#glow)"
          />
        </motion.g>
        
        {/* Particle Ring */}
        <motion.g
          animate={{ rotate: 360 }}
          transition={{ duration: rotationSpeed * 1.3, repeat: Infinity, ease: "linear" }}
          style={{ originX: 0.5, originY: 0.5 }}
        >
          <ellipse
            cx="300"
            cy="300"
            rx={180 * ringPulse}
            ry={160 * ringPulse}
            fill="none"
            stroke={colors.primary}
            strokeWidth={1.5 + audioLevel * 0.5}
            strokeDasharray={`${5 + audioLevel * 5} ${10 - audioLevel * 2.5}`}
            opacity={0.5 + audioLevel * 0.15}
          />
        </motion.g>
        
        {/* Core Glow Ring */}
        <motion.circle
          cx="300"
          cy="300"
          r={120 + audioLevel * 15}
          fill="none"
          stroke={colors.glow}
          strokeWidth={3 + audioLevel * 1.5}
          opacity={0.3 + audioLevel * 0.25}
          style={{ originX: 0.5, originY: 0.5 }}
        />
      </svg>
    </div>
  );
}