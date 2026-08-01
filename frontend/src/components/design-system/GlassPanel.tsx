import React from 'react';
import { glass } from '@/theme/glass';

interface GlassPanelProps {
  children: React.ReactNode;
  className?: string;
}

const GlassPanel: React.FC<GlassPanelProps> = ({ children, className }) => {
  return (
    <div
      className={className}
      style={{
        background: glass.background,
        border: `1px solid ${glass.border}`,
        boxShadow: glass.shadow,
        backdropFilter: `blur(${glass.blur})`,
      }}
    >
      {children}
    </div>
  );
};

export default GlassPanel;