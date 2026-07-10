import React from 'react';
// Fix 1: Use curly braces {} because the store is a named export
import { useZaramStore } from '../store/useZaramStore';

const DebugAdminLayer: React.FC = () => {
  // Fix 2: Added ': any' to the state parameter to kill the implicit any error
  const currentState = useZaramStore((state: any) => state.currentState);
  const environmentMode = useZaramStore((state: any) => state.environmentMode);

  return (
    <div className="absolute top-4 right-4 z-40 bg-black/50 backdrop-blur-md text-white p-4 rounded-lg border border-white/10 text-sm font-mono">
      <h3 className="font-bold mb-2 text-cyan-400 border-b border-white/20 pb-1">Zaram Debug</h3>
      <div className="space-y-1">
        <p><span className="text-gray-400">State:</span> {currentState}</p>
        <p><span className="text-gray-400">Env:</span> {environmentMode}</p>
      </div>
    </div>
  );
};

export default DebugAdminLayer;