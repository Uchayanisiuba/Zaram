import React from 'react';

interface EmptyStateProps {
  title: string;
  message: string;
  children?: React.ReactNode;
}

const EmptyState: React.FC<EmptyStateProps> = ({ title, message, children }) => {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center">
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <p className="text-neutral-400 mt-2">{message}</p>
      <div className="mt-6">{children}</div>
    </div>
  );
};

export default EmptyState;