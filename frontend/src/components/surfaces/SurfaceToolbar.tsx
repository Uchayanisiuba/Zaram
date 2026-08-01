import type { ReactNode } from 'react';

const SurfaceToolbar = ({ children }: { children?: ReactNode }) => {
  return (
    <div
      className="flex h-10 items-center justify-between border-b border-white/10 px-4"
      style={{ background: 'rgba(0,0,0,0.1)' }}
    >
      {children}
    </div>
  );
};

export default SurfaceToolbar;