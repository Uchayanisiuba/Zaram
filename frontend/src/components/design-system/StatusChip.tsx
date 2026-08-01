import React from 'react';

interface StatusChipProps {
  children: React.ReactNode;
  className?: string;
  color?: 'green' | 'yellow' | 'blue' | 'gray';
}

const colorClasses = {
  green: 'bg-green-500/20 text-green-300',
  yellow: 'bg-yellow-500/20 text-yellow-300',
  blue: 'bg-blue-500/20 text-blue-300',
  gray: 'bg-neutral-500/20 text-neutral-300',
};

const StatusChip: React.FC<StatusChipProps> = ({ children, className, color = 'gray' }) => {
  return (
    <div className={`px-2 py-1 text-xs font-medium rounded-full inline-flex items-center ${colorClasses[color]} ${className}`}>
      {children}
    </div>
  );
};

export default StatusChip;