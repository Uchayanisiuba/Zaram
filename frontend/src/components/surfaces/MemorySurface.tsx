import { useMemoryStore, MemoryNodeType } from '@/stores/memoryStore';
import SurfaceBody from './SurfaceBody';
import { motion, AnimatePresence } from 'framer-motion';
import { glass } from '@/theme/glass';

const Icon = ({ path, className = 'h-5 w-5' }: { path: string; className?: string }) => (
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

const nodeIcons: Record<MemoryNodeType, React.ReactNode> = {
  code_execution: <Icon path="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25" />,
  knowledge_synthesis: (
    <Icon path="M9.5 13.5a.5.5 0 01-.5.5h-2a.5.5 0 010-1h2a.5.5 0 01.5.5zm0-4a.5.5 0 01-.5.5h-2a.5.5 0 010-1h2a.5.5 0 01.5.5zm5.5 4a.5.5 0 01-.5.5h-2a.5.5 0 010-1h2a.5.5 0 01.5.5zm0-4a.5.5 0 01-.5.5h-2a.5.5 0 010-1h2a.5.5 0 01.5.5zM3 10a7 7 0 1114 0 7 7 0 01-14 0z" />
  ),
  user_intent: <Icon path="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />,
};

const MemorySurface = () => {
  const { nodes } = useMemoryStore();

  return (
    <SurfaceBody>
      <div className="relative h-full w-full overflow-y-auto px-8 py-6">
        {/* Timeline Connector */}
        <div className="absolute left-12 top-0 bottom-0 w-0.5 bg-white/10" />

        <div className="relative flex flex-col gap-4">
          <AnimatePresence initial={false}>
            {nodes.map((node, index) => (
              <motion.div
                key={node.id}
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, transition: { duration: 0.2 } }}
                transition={{ type: 'spring', stiffness: 300, damping: 30, delay: index * 0.05 }}
                className="relative flex items-start gap-6"
              >
                {/* Icon and Connector Dot */}
                <div
                  className="absolute left-12 top-2.5 h-2 w-2 -translate-x-1/2 rounded-full bg-white/30"
                />
                <div
                  className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full text-neutral-400"
                  style={{
                    background: glass.background,
                    border: `1px solid ${glass.border}`,
                  }}
                >
                  {nodeIcons[node.type]}
                </div>

                {/* Content Card */}
                <div
                  className="w-full flex-1 rounded-lg p-4"
                  style={{
                    background: glass.background,
                    border: `1px solid ${glass.border}`,
                    backdropFilter: `blur(${glass.blur})`,
                  }}
                >
                  <p className="text-sm text-neutral-200">{node.content}</p>
                  <p className="mt-2 text-xs text-neutral-500">
                    {node.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </SurfaceBody>
  );
};

export default MemorySurface;