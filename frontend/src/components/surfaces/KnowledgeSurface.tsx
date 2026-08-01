import { useState } from 'react';
import SurfaceBody from './SurfaceBody';
import SurfaceToolbar from './SurfaceToolbar';
import useStreamingText from '@/hooks/useStreamingText';
import { useOrbStore } from '@/stores/orbStore';
import { useMemoryStore } from '@/stores/memoryStore';
import { motion } from 'framer-motion';

// Mock Data
const sources = [
  { id: 'src-01', title: 'Zaram Core Principles', content: '...' },
  { id: 'src-02', title: 'Q3 2024 Engineering Roadmap', content: '...' },
  { id: 'src-03', title: 'Spatial UI/UX Research', content: '...' },
];

const analysisMap: Record<string, string> = {
  'src-01':
    'The core principles of Zaram emphasize a calm, premium, and spatial user experience. The architecture prioritizes a local-first approach, ensuring user data remains private and performance is maximized. The Living Orb is positioned not as the application itself, but as a companion to the user\'s workflow within the workspace.',
  'src-02':
    'The Q3 roadmap focuses on three key initiatives: completing the Command Palette, integrating the Build and Create engines, and developing the initial persistence layer for workspace state. Stretch goals include real-time collaboration features and a public API for third-party engine development. [1]',
  'src-03':
    'Research into spatial interfaces, particularly from Apple\'s visionOS and early VR prototypes, indicates that users prefer uncluttered environments with clear visual hierarchy. Glassmorphism, depth cues, and responsive motion are critical for establishing a sense of place and reducing cognitive load. [2]',
};

const Icon = ({ path, className = 'h-4 w-4' }: { path: string; className?: string }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
    strokeWidth={1.5}
    stroke="currentColor"
    className={className}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d={path} />
  </svg>
);

const KnowledgeSurface = () => {
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>('src-02');
  const { displayedText, isStreaming, startStreaming } = useStreamingText();
  const { setState } = useOrbStore();
  const { addMemoryNode } = useMemoryStore();

  const handleSelectSource = (id: string) => {
    setSelectedSourceId(id);
    setState('thinking');
    setTimeout(() => {
      startStreaming(analysisMap[id]);
      setState('idle');
    }, 1500);
  };

  const handleSynthesize = () => {
    if (!selectedSourceId) return;
    const sourceTitle = sources.find(s => s.id === selectedSourceId)?.title || 'document';
    setState('thinking');
    addMemoryNode({
      type: 'knowledge_synthesis',
      content: `Synthesized analysis for "${sourceTitle}"`,
    });
    setTimeout(() => {
      startStreaming(analysisMap[selectedSourceId]); // Force restart
      setState('idle');
    }, 2000);
  };

  const handleExport = () => {
    setState('thinking');
    setTimeout(() => setState('idle'), 500);
  };

  return (
    <>
      <SurfaceToolbar>
        <div className="flex items-center gap-2">
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className="p-1.5 rounded-md hover:bg-white/10"
          >
            <Icon path="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </motion.button>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className="p-1.5 rounded-md hover:bg-white/10"
            onClick={handleSynthesize}
          >
            <Icon path="M9.5 13.5a.5.5 0 01-.5.5h-2a.5.5 0 010-1h2a.5.5 0 01.5.5zm0-4a.5.5 0 01-.5.5h-2a.5.5 0 010-1h2a.5.5 0 01.5.5zm5.5 4a.5.5 0 01-.5.5h-2a.5.5 0 010-1h2a.5.5 0 01.5.5zm0-4a.5.5 0 01-.5.5h-2a.5.5 0 010-1h2a.5.5 0 01.5.5zM3 10a7 7 0 1114 0 7 7 0 01-14 0z" />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className="p-1.5 rounded-md hover:bg-white/10"
            onClick={handleExport}
          >
            <Icon path="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
          </motion.button>
        </div>
      </SurfaceToolbar>
      <SurfaceBody>
        <div className="flex h-full w-full">
          {/* Left Pane: Source Material */}
          <div className="w-[30%] flex-shrink-0 border-r border-white/10 pr-6">
            <ul className="space-y-1">
              {sources.map((source) => (
                <li
                  key={source.id}
                  onClick={() => handleSelectSource(source.id)}
                  className={`cursor-pointer rounded-md px-3 py-2 text-sm transition-colors ${
                    selectedSourceId === source.id
                      ? 'bg-white/10 text-neutral-200'
                      : 'text-neutral-400 hover:bg-white/5 hover:text-neutral-300'
                  }`}
                >
                  {source.title}
                </li>
              ))}
            </ul>
          </div>

          {/* Right Pane: AI Synthesis */}
          <div className="w-[70%] flex-shrink-0 pl-6">
            <div className="text-base leading-relaxed text-neutral-300">
              {isStreaming && <span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-green-400" />}
              {displayedText}
            </div>
          </div>
        </div>
      </SurfaceBody>
    </>
  );
};

export default KnowledgeSurface;