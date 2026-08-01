import React from 'react';

interface CenterWorkspaceProps {
  children: React.ReactNode;
}

const CenterWorkspace = ({ children }: CenterWorkspaceProps) => {
  return (
    <div
      className="fixed flex flex-col min-w-0 min-h-0 overflow-hidden"
      style={{
        top: 'var(--nav-height)',
        right: 0,
        bottom: 0,
        left: 'var(--rail-width)',
      }}
    >
      {children}
    </div>
  );
};

export default CenterWorkspace;
