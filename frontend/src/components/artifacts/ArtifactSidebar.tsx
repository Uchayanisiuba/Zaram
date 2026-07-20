import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Pin,
  Plus,
  FileText,
  Clock,
  Trash2,
  Copy,
  ExternalLink,
  ChevronRight,
  X,
  Tag,
} from 'lucide-react';
import { useArtifactStore } from '@/stores/artifactStore';
import type { ArtifactType, Artifact } from '@/types/artifacts';

const artifactTypeIcons: Record<ArtifactType, string> = {
  text: '📝',
  markdown: '📄',
  code: '💻',
  image: '🖼️',
  pdf: '📕',
  csv: '📊',
  json: '🔧',
  html: '🌐',
  audio: '🎵',
  video: '🎬',
};

function formatTime(timestamp: number) {
  const now = Date.now();
  const diff = now - timestamp;
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return new Date(timestamp).toLocaleDateString();
}

export function ArtifactSidebar() {
  const [localSearchQuery, setLocalSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'pinned' | 'recent'>('all');
  const [selectedType, setSelectedType] = useState<ArtifactType | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newArtifactName, setNewArtifactName] = useState('');
  const [newArtifactType, setNewArtifactType] = useState<ArtifactType>('text');

  const artifacts = useArtifactStore((s) => s.getFilteredArtifacts());
  const searchQueryStore = useArtifactStore((s) => s.searchQuery);
  const pinnedArtifacts = useArtifactStore((s) => s.getPinnedArtifacts());
  const createArtifact = useArtifactStore((s) => s.createArtifact);
  const openArtifact = useArtifactStore((s) => s.openArtifact);
  const togglePin = useArtifactStore((s) => s.togglePin);
  const deleteArtifact = useArtifactStore((s) => s.deleteArtifact);
  const duplicateArtifact = useArtifactStore((s) => s.duplicateArtifact);
  const setSearchQuery = useArtifactStore((s) => s.setSearchQuery);

  const filtered = artifacts.filter((a) => {
    if (activeFilter === 'pinned') return a.pinned;
    if (selectedType) return a.type === selectedType;
    return true;
  });

  const handleCreate = () => {
    if (!newArtifactName.trim()) return;
    createArtifact({
      name: newArtifactName,
      type: newArtifactType,
      content: '',
    });
    setNewArtifactName('');
    setIsCreating(false);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-white/10 space-y-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/40" />
            <input
              type="text"
              value={localSearchQuery}
              onChange={(e) => {
                setLocalSearchQuery(e.target.value);
                useArtifactStore.getState().setSearchQuery(e.target.value);
              }}
              placeholder="Search artifacts..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-8 pr-2 py-1.5 text-xs placeholder:text-white/30 focus:outline-none focus:border-cyan-500/50"
            />
          </div>
          <button
            onClick={() => setIsCreating(true)}
            className="p-1.5 rounded-lg bg-gradient-to-r from-cyan-500 to-orange-500 text-white hover:opacity-90"
            title="New artifact"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        <AnimatePresence>
          {isCreating && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="space-y-2"
            >
              <input
                type="text"
                value={newArtifactName}
                onChange={(e) => setNewArtifactName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                placeholder="Artifact name"
                autoFocus
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs placeholder:text-white/30 focus:outline-none focus:border-cyan-500/50"
              />
              <select
                value={newArtifactType}
                onChange={(e) => setNewArtifactType(e.target.value as ArtifactType)}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:border-cyan-500/50"
              >
                <option value="text">Text</option>
                <option value="markdown">Markdown</option>
                <option value="code">Code</option>
                <option value="json">JSON</option>
                <option value="csv">CSV</option>
                <option value="html">HTML</option>
              </select>
              <div className="flex gap-2">
                <button
                  onClick={handleCreate}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 text-xs hover:bg-cyan-500/30"
                >
                  Create
                </button>
                <button
                  onClick={() => setIsCreating(false)}
                  className="flex-1 px-3 py-1.5 rounded-lg bg-white/5 text-white/60 text-xs hover:bg-white/10"
                >
                  Cancel
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex gap-1">
          {(['all', 'pinned', 'recent'] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={`flex-1 px-2 py-1 rounded text-[10px] uppercase tracking-wider transition-colors ${
                activeFilter === filter
                  ? 'bg-white/10 text-white'
                  : 'text-white/40 hover:text-white/70'
              }`}
            >
              {filter}
            </button>
          ))}
        </div>

        <div className="flex gap-1 flex-wrap">
          {(['text', 'markdown', 'code', 'image', 'pdf', 'csv', 'json', 'html'] as ArtifactType[]).map((type) => (
            <button
              key={type}
              onClick={() => setSelectedType(selectedType === type ? null : type)}
              className={`px-2 py-0.5 rounded text-[10px] uppercase tracking-wider transition-colors ${
                selectedType === type
                  ? 'bg-cyan-500/20 text-cyan-300'
                  : 'bg-white/5 text-white/40 hover:text-white/70'
              }`}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        <AnimatePresence>
          {filtered.map((artifact) => (
            <motion.div
              key={artifact.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              onClick={() => openArtifact(artifact.id)}
              className="group flex items-center gap-2 p-2 rounded-lg hover:bg-white/5 cursor-pointer border border-transparent hover:border-white/10 transition-colors"
            >
              <span className="text-base">{artifactTypeIcons[artifact.type]}</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate text-white/90">{artifact.name}</p>
                <div className="flex items-center gap-2 text-[10px] text-white/40">
                  <span className="uppercase">{artifact.type}</span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatTime(artifact.updatedAt)}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    togglePin(artifact.id);
                  }}
                  className={`p-1 rounded hover:bg-white/10 ${
                    artifact.pinned ? 'text-cyan-400' : 'text-white/40'
                  }`}
                  title={artifact.pinned ? 'Unpin' : 'Pin'}
                >
                  <Pin className="w-3 h-3" fill={artifact.pinned ? 'currentColor' : 'none'} />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    duplicateArtifact(artifact.id);
                  }}
                  className="p-1 rounded hover:bg-white/10 text-white/40"
                  title="Duplicate"
                >
                  <Copy className="w-3 h-3" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteArtifact(artifact.id);
                  }}
                  className="p-1 rounded hover:bg-white/10 text-white/40"
                  title="Delete"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {filtered.length === 0 && (
          <div className="text-center py-8 text-white/30 text-xs">
            <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No artifacts found</p>
            <p className="mt-1">Create one to get started</p>
          </div>
        )}
      </div>
    </div>
  );
}
