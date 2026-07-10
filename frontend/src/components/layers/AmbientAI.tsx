import React from 'react';
import { motion } from 'framer-motion';
import { useZaramStore } from '../../store/useZaramStore';

const AmbientAI: React.FC = () => {
  const currentState = useZaramStore((state: any) => state.currentState);

  // If idle or working, hide the ambient layer to keep it clean
  if (currentState === 'idle' || currentState === 'working' || currentState === 'listening') {
    return null;
  }

  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center pointer-events-none overflow-hidden">
      
      {/* THINKING STATE: Pulsing Cyan Rings */}
      {currentState === 'thinking' && (
        <>
          <motion.div
            className="absolute w-64 h-64 rounded-full border-2 border-cyan-400/50"
            animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            className="absolute w-48 h-48 rounded-full border-2 border-cyan-300/80"
            animate={{ scale: [1, 1.2, 1], opacity: [0.8, 0.2, 0.8] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
          />
          <div className="absolute w-3 h-3 bg-cyan-400 rounded-full shadow-[0_0_20px_rgba(34,211,238,0.8)]" />
        </>
      )}

      {/* SPEAKING STATE: Animated Waveform Bars */}
      {currentState === 'speaking' && (
        <div className="flex items-center justify-center gap-2 h-24">
          {[...Array(7)].map((_, i) => (
            <motion.div
              key={i}
              className="w-2 bg-cyan-400 rounded-full shadow-[0_0_10px_rgba(34,211,238,0.5)]"
              animate={{ height: ['15%', '85%', '15%'] }}
              transition={{
                duration: 0.7 + (i * 0.1),
                repeat: Infinity,
                ease: "easeInOut",
                delay: i * 0.1
              }}
            />
          ))}
        </div>
      )}

      {/* CREATIVE STATE: Golden floating particles */}
      {currentState === 'creative' && (
        <div className="relative w-64 h-64">
          {[...Array(12)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-2 h-2 bg-yellow-400 rounded-full shadow-[0_0_10px_rgba(250,204,21,0.8)]"
              style={{ top: '50%', left: '50%' }}
              animate={{
                x: [0, Math.cos(i * 30 * (Math.PI / 180)) * 80],
                y: [0, Math.sin(i * 30 * (Math.PI / 180)) * 80],
                opacity: [0, 1, 0],
                scale: [0, 1.5, 0]
              }}
              transition={{
                duration: 2.5,
                repeat: Infinity,
                ease: "easeOut",
                delay: i * 0.2
              }}
            />
          ))}
        </div>
      )}

      {/* ERROR STATE: Red pulsing alert */}
      {currentState === 'error' && (
        <motion.div
          className="w-16 h-16 rounded-full border-4 border-red-500"
          animate={{ scale: [1, 1.2, 1], opacity: [1, 0.5, 1] }}
          transition={{ duration: 1, repeat: Infinity }}
        />
      )}

    </div>
  );
};

export default AmbientAI;