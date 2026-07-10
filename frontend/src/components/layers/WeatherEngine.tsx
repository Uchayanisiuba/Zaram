import React from 'react';
import { motion } from 'framer-motion';
import { useZaramStore } from '../../store/useZaramStore';

const WeatherEngine: React.FC = () => {
  const environmentMode = useZaramStore((state: any) => state.environmentMode);

  // CALM MODE: Soft floating particles
  if (environmentMode === 'calm') {
    return (
      <div className="absolute inset-0 z-10 pointer-events-none overflow-hidden">
        {[...Array(20)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-1 h-1 bg-cyan-300/30 rounded-full"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
            }}
            animate={{
              y: [0, -30, 0],
              opacity: [0.3, 0.8, 0.3],
            }}
            transition={{
              duration: 3 + Math.random() * 2,
              repeat: Infinity,
              ease: "easeInOut",
              delay: Math.random() * 2,
            }}
          />
        ))}
      </div>
    );
  }

  // FOCUS MODE: Dark blue fog overlay
  if (environmentMode === 'focus') {
    return (
      <div className="absolute inset-0 z-10 pointer-events-none">
        <motion.div
          className="absolute inset-0 bg-gradient-to-b from-blue-900/20 via-transparent to-blue-900/30"
          animate={{
            opacity: [0.5, 0.8, 0.5],
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      </div>
    );
  }

  // CREATIVE MODE: Golden floating particles
  if (environmentMode === 'creative') {
    return (
      <div className="absolute inset-0 z-10 pointer-events-none overflow-hidden">
        {[...Array(30)].map((_, i) => (
          <motion.div
            key={i}
            className="absolute w-2 h-2 bg-yellow-400/40 rounded-full shadow-[0_0_10px_rgba(250,204,21,0.6)]"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
            }}
            animate={{
              y: [0, -50, 0],
              x: [0, Math.sin(i) * 20, 0],
              opacity: [0.4, 1, 0.4],
              scale: [1, 1.5, 1],
            }}
            transition={{
              duration: 4 + Math.random() * 2,
              repeat: Infinity,
              ease: "easeInOut",
              delay: Math.random() * 3,
            }}
          />
        ))}
      </div>
    );
  }

  return null;
};

export default WeatherEngine;