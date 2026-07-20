import { useState } from 'react';
import { useZaram } from '../../hooks/useZaram';

export const Memory = () => {
  const {
    memories,
    addMemory,
    deleteMemory,
    exportMemories,
    selectedMemory,
    setSelectedMemory,
  } = useZaram();

  const [newMemoryText, setNewMemoryText] = useState('');
  const [filter, setFilter] = useState('all'); // all, important, recent

  const handleAddMemory = () => {
    if (!newMemoryText.trim()) return;
    addMemory({ content: newMemoryText, importance: 'medium' });
    setNewMemoryText('');
  };

  const filteredMemories = memories.filter(m => {
    if (filter === 'important') return m.importance === 'high';
    return true;
  });

  const sorted = [...filteredMemories].sort((a, b) =>
    new Date(b.createdAt) - new Date(a.createdAt)
  );

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="border-b border-cyan-950/30 p-6 space-y-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 mb-2">Memory Bank</h2>
          <p className="text-sm text-slate-400">Store and manage important information, preferences, and learned facts</p>
        </div>

        {/* New Memory Input */}
        <div className="flex gap-2">
          <textarea
            value={newMemoryText}
            onChange={(e) => setNewMemoryText(e.target.value)}
            placeholder="Add something to remember..."
            className="flex-1 px-3 py-2 text-sm bg-slate-800/50 border border-slate-700/50 rounded-lg text-slate-100 placeholder-slate-500 focus:border-cyan-500/50 focus:outline-none focus:ring-1 focus:ring-cyan-500/30 resize-none"
            rows="2"
          />
          <button
            onClick={handleAddMemory}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-white text-sm font-medium transition-colors"
          >
            Save
          </button>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 text-sm bg-slate-800/50 border border-slate-700/50 rounded-lg text-slate-100 focus:border-cyan-500/50 focus:outline-none"
          >
            <option value="all">All Memories</option>
            <option value="important">Important</option>
          </select>
          
          <button
            onClick={exportMemories}
            className="px-4 py-2 text-sm text-cyan-400 hover:bg-cyan-500/10 rounded-lg transition-colors border border-cyan-500/30"
          >
            📥 Export
          </button>
        </div>
      </div>

      {/* Memories List */}
      <div className="flex-1 overflow-y-auto p-6 space-y-3">
        {sorted.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <p className="mb-2">No memories yet</p>
            <p className="text-xs text-slate-600">Start adding things to remember</p>
          </div>
        ) : (
          sorted.map(memory => (
            <div
              key={memory.id}
              onClick={() => setSelectedMemory(memory.id)}
              className={`p-4 rounded-lg border transition-all cursor-pointer ${
                selectedMemory === memory.id
                  ? 'bg-cyan-600/20 border-cyan-500/50'
                  : 'bg-slate-800/30 border-slate-700/30 hover:border-cyan-500/30'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <p className="text-sm text-slate-200 break-words">{memory.content}</p>
                  <div className="mt-2 flex items-center gap-2">
                    <span className={`text-xs px-2 py-1 rounded ${
                      memory.importance === 'high'
                        ? 'bg-red-500/20 text-red-300'
                        : 'bg-slate-700/50 text-slate-400'
                    }`}>
                      {memory.importance === 'high' ? '⭐ High' : 'Normal'}
                    </span>
                    <span className="text-xs text-slate-500">
                      {new Date(memory.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteMemory(memory.id);
                  }}
                  className="p-2 hover:bg-red-500/20 rounded text-red-400 transition-colors"
                  title="Delete memory"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
