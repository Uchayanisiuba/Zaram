import React from 'react';
import GlassPanel from './GlassPanel';

interface AgentCardProps {
  children: React.ReactNode;
  className?: string;
}

const AgentCard: React.FC<AgentCardProps> = ({ children, className }) => {
  return (
    <GlassPanel className={`p-4 rounded-lg ${className}`}>
      {children}
    </GlassPanel>
  );
};

export default AgentCard;