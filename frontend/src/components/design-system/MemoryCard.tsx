import React from 'react';
import GlassPanel from './GlassPanel';

interface MemoryCardProps {
  children: React.ReactNode;
  className?: string;
}

const MemoryCard: React.FC<MemoryCardProps> = ({ children, className }) => {
  return (
    <GlassPanel className={`p-4 rounded-lg ${className}`}>
      {children}
    </GlassPanel>
  );
};

export default MemoryCard;