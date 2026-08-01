import React from 'react';

interface SectionHeaderProps {
  children: React.ReactNode;
  className?: string;
}

const SectionHeader: React.FC<SectionHeaderProps> = ({ children, className }) => {
  return (
    <h2 className={`text-lg font-semibold text-neutral-200 mb-4 ${className}`}>
      {children}
    </h2>
  );
};

export default SectionHeader;