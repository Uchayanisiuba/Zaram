import React from 'react';
import GlassPanel from './GlassPanel';

interface ContextToolbarProps {
  children: React.ReactNode;
  className?: string;
}

const ContextToolbar: React.FC<ContextToolbarProps> = ({ children, className }) => {
  return (
    <GlassPanel className={`flex items-center gap-2 p-2 rounded-lg ${className}`}>
      {children}
    </GlassPanel>
  );
};

export default ContextToolbar;