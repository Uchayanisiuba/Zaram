import React from 'react';
import GlassPanel from './GlassPanel';

interface ResearchCardProps {
  children: React.ReactNode;
  className?: string;
}

const ResearchCard: React.FC<ResearchCardProps> = ({ children, className }) => {
  return (
    <GlassPanel className={`p-4 rounded-lg ${className}`}>
      {children}
    </GlassPanel>
  );
};

export default ResearchCard;