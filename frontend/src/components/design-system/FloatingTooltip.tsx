import React from 'react';
import { motion } from 'framer-motion';
import GlassPanel from './GlassPanel';

interface FloatingTooltipProps {
  children: React.ReactNode;
  className?: string;
}

const FloatingTooltip: React.FC<FloatingTooltipProps> = ({ children, className }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className={`absolute z-50 ${className}`}
    >
      <GlassPanel className="px-3 py-2 rounded-md text-sm text-neutral-200">
        {children}
      </GlassPanel>
    </motion.div>
  );
};

export default FloatingTooltip;