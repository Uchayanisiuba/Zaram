import React from 'react';
import { motion } from 'framer-motion';
import GlassPanel from './GlassPanel';

interface FloatingWindowProps {
  children: React.ReactNode;
  title: string;
  className?: string;
}

const FloatingWindow: React.FC<FloatingWindowProps> = ({ children, title, className }) => {
  return (
    <motion.div
      drag
      dragMomentum={false}
      dragConstraints={{ left: -500, right: 500, top: -300, bottom: 300 }} // Basic constraints
      className={className}
      style={{
        position: 'absolute',
        width: 600,
        borderRadius: '12px',
        overflow: 'hidden',
      }}
    >
      <GlassPanel className="flex flex-col h-full">
        <div className="p-2 bg-white/5 cursor-move font-medium text-sm text-neutral-300">
          {title}
        </div>
        <div className="p-4 flex-grow">
          {children}
        </div>
      </GlassPanel>
    </motion.div>
  );
};

export default FloatingWindow;