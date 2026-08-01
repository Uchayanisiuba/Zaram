import React from 'react';

interface SurfaceHeaderProps {
  title: string;
  children?: React.ReactNode;
}

const SurfaceHeader: React.FC<SurfaceHeaderProps> = ({ title, children }) => {
  return (
    <header className="flex items-center justify-between p-4 border-b border-white/10">
      <h1 className="text-lg font-semibold text-white">{title}</h1>
      <div>{children}</div>
    </header>
  );
};

export default SurfaceHeader;