import React from 'react';

const UnrealContainer: React.FC = () => {
  return (
    <div className="absolute inset-0 z-0 bg-transparent">
      <div id="unreal-stream" className="w-full h-full" />
    </div>
  );
};

export default UnrealContainer;