import React from 'react';
import { motion, type HTMLMotionProps } from 'framer-motion';
import { glass } from '@/theme/glass';

type SpatialButtonProps = HTMLMotionProps<'button'>;

const SpatialButton: React.FC<SpatialButtonProps> = ({ children, ...props }) => {
  return (
    <motion.button
      whileHover={{ scale: 1.05, y: -2 }}
      whileTap={{ scale: 0.95, y: 1 }}
      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
      {...props}
      style={{
        ...props.style,
        background: 'rgba(255, 255, 255, 0.05)',
        border: `1px solid ${glass.border}`,
        borderRadius: '8px',
        padding: '10px 16px',
        color: 'white',
        cursor: 'pointer',
        boxShadow: '0px 2px 10px rgba(0, 0, 0, 0.1)',
      }}
    >
      {children}
    </motion.button>
  );
};

export default SpatialButton;