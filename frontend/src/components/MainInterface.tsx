import React, { useState } from 'react';
import { useZaramStore } from '../store/useZaramStore';

const MainInterface: React.FC = () => {
  const [inputValue, setInputValue] = useState('');
  const currentState = useZaramStore((state: any) => state.currentState);

  return (
    <div className="absolute right-4 top-4 bottom-4 w-96 z-30 flex flex-col bg-white/5 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
      
      {/* Header */}
      <div className="p-4 border-b border-white/10 bg-white/5">
        <h2 className="text-white font-semibold text-lg">Zaram</h2>
        <p className="text-cyan-300 text-xs mt-1">State: {currentState}</p>
      </div>

      {/* Chat Messages Area */}
      <div className="flex-1 p-4 overflow-y-auto">
        <div className="space-y-3">
          <div className="bg-white/10 rounded-lg p-3 text-white text-sm">
            Welcome to Zaram. How can I help you today?
          </div>
        </div>
      </div>

      {/* Input Area */}
      <div className="p-4 border-t border-white/10 bg-white/5">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white placeholder-white/50 focus:outline-none focus:border-cyan-400/50"
          />
          <button className="bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-400/50 text-cyan-300 px-4 py-2 rounded-lg transition-colors">
            Send
          </button>
        </div>
      </div>

    </div>
  );
};

export default MainInterface;