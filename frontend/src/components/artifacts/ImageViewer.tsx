import React from 'react';

export function ImageViewer({ artifact }: { artifact: any }) {
  return (
    <div className="flex items-center justify-center h-full">
      <img
        src={artifact.content}
        alt={artifact.name}
        className="max-w-full max-h-full rounded-lg shadow-2xl object-contain"
      />
    </div>
  );
}
