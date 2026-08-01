import React from 'react';
import StatusChip from './StatusChip';

interface ErrorStateProps {
  title: string;
  message: string;
}

const ErrorState: React.FC<ErrorStateProps> = ({ title, message }) => {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-4">
      <StatusChip color="yellow" className="mb-4">Error</StatusChip>
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      <p className="text-neutral-400 mt-2 max-w-md">{message}</p>
    </div>
  );
};

export default ErrorState;