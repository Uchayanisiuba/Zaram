import React from 'react';
import { motion, type HTMLMotionProps } from 'framer-motion';
import { glass } from '@/theme/glass';

type OrbButtonProps = HTMLMotionProps<'button'>;

const OrbButton: React.FC<OrbButtonProps> = ({ children, ...props }) => {
  return (
    <motion.button
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.9 }}
      transition={{ type: 'spring', stiffness: 500, damping: 15 }}
      {...props}
      style={{
        ...props.style,
        background: 'rgba(255, 255, 255, 0.1)',
        border: `1px solid ${glass.border}`,
        borderRadius: '50%',
        width: '56px',
        height: '56px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: 'white',
        cursor: 'pointer',
        boxShadow: '0px 4px 15px rgba(0, 0, 0, 0.2)',
      }}
    >
      {children}
    </motion.button>
  );
};

export default OrbButton;