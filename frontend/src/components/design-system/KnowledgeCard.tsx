import React from 'react';
import GlassPanel from './GlassPanel';

interface KnowledgeCardProps {
  children: React.ReactNode;
  className?: string;
}

const KnowledgeCard: React.FC<KnowledgeCardProps> = ({ children, className }) => {
  return (
    <GlassPanel className={`p-4 rounded-lg ${className}`}>
      {children}
    </GlassPanel>
  );
};

export default KnowledgeCard;