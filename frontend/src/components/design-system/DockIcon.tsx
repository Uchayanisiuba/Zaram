import React from 'react';
import { motion } from 'framer-motion';

interface DockIconProps {
  children: React.ReactNode;
  onClick?: () => void;
}

const DockIcon: React.FC<DockIconProps> = ({ children, onClick }) => {
  return (
    <motion.div
      whileHover={{ scale: 1.1, y: -2 }}
      whileTap={{ scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
      onClick={onClick}
      className="p-2 rounded-md cursor-pointer text-neutral-400 hover:text-white"
    >
      {children}
    </motion.div>
  );
};

export default DockIcon;