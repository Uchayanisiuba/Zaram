import { useState } from 'react';
import SurfaceBody from '@/components/surfaces/SurfaceBody';
import SurfaceToolbar from '@/components/surfaces/SurfaceToolbar';
import { useOrbStore } from '@/stores/orbStore';
import { useMemoryStore } from '@/stores/memoryStore';
import { motion } from 'framer-motion';

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

const BuildSurface = () => {
  const { setState } = useOrbStore();
  const { addMemoryNode } = useMemoryStore();
  const [isRunning, setIsRunning] = useState(false);
  const [showTerminal, setShowTerminal] = useState(false);

  const handleRunCode = () => {
    setIsRunning(true);
    setState('thinking');
    addMemoryNode({
      type: 'code_execution',
      content: 'Executed App.tsx script',
    });
    setTimeout(() => {
      setIsRunning(false);
      setState('idle');
    }, 3000);
  };

  return (
    <>
      <SurfaceToolbar>
        <div className="flex items-center gap-2">
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className="p-1.5 rounded-md hover:bg-white/10"
            onClick={handleRunCode}
          >
            <Icon path="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.972l-11.54 6.347a1.125 1.125 0 01-1.667-.986V5.653z" />
          </motion.button>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className={`p-1.5 rounded-md hover:bg-white/10 ${showTerminal ? 'bg-white/10' : ''}`}
            onClick={() => setShowTerminal(!showTerminal)}
          >
            <Icon path="M6.75 7.5l3 2.25-3 2.25m4.5 0h3m-9 8.25h13.5A2.25 2.25 0 0021 18V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v12a2.25 2.25 0 002.25 2.25z" />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className="p-1.5 rounded-md hover:bg-white/10"
          >
            <Icon path="M10.343 3.94c.09-.542.56-1.007 1.11-1.227l.554-.221a1.125 1.125 0 011.33.885l.055.554a1.125 1.125 0 001.33.885l.554-.055a1.125 1.125 0 011.227 1.11l.221.554a1.125 1.125 0 01-.885 1.33l-.554.055a1.125 1.125 0 00-.885 1.33l.055.554a1.125 1.125 0 01-1.11 1.227l-.554.221a1.125 1.125 0 01-1.33-.885l-.055-.554a1.125 1.125 0 00-1.33-.885l-.554.055a1.125 1.125 0 01-1.227-1.11l-.221-.554a1.125 1.125 0 01.885-1.33l.554-.055a1.125 1.125 0 00.885-1.33l-.055-.554zM4.5 12a7.5 7.5 0 0015 0h-15z" />
          </motion.button>
        </div>
      </SurfaceToolbar>
      <SurfaceBody>
        <div className="flex h-full w-full flex-col">
          {/* Editor Area */}
          <div className="flex-1 flex">
            {/* File Tree */}
            <div className="w-[200px] flex-shrink-0 border-r border-white/10 p-4">
              <h3 className="text-sm font-bold text-neutral-400">Files</h3>
              <ul className="mt-4 space-y-2 text-sm text-neutral-500">
                <li>package.json</li>
                <li>tailwind.config.js</li>
                <li className="text-neutral-300">App.tsx</li>
                <li>main.tsx</li>
              </ul>
            </div>

            {/* Code Editor */}
            <div className="relative flex-1 bg-canvas p-6">
              <textarea
                className="h-full w-full resize-none bg-transparent font-mono text-sm text-neutral-300 focus:outline-none"
                defaultValue={`function App() {
  return (
    <div className="h-screen w-screen overflow-hidden">
      <SpatialBackground />
      <CommandDock />
    </div>
  );
}`}
              />
              {isRunning && (
                <div className="absolute inset-x-0 bottom-4 flex justify-center">
                  <span className="rounded-full bg-black/50 px-3 py-1 text-xs text-neutral-300">
                    Running...
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Terminal Pane */}
          {showTerminal && (
            <div className="h-[200px] flex-shrink-0 border-t border-white/10 bg-canvas p-4 font-mono text-xs text-neutral-400">
              <p>&gt; Zaram Build Environment v0.9</p>
              <p>&gt; Ready.</p>
            </div>
          )}
        </div>
      </SurfaceBody>
    </>
  );
};

export default BuildSurface;