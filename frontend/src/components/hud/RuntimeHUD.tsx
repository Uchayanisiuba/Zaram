import { motion } from 'framer-motion';
import { glass } from '@/theme/glass';
import { depth } from '@/theme/depth';
import { useFrameState } from '@/hooks/useFrameState';
import type { PresenceState } from '@/theme/presenceTheme';

const stateColorMap: Record<PresenceState, string> = {
  Idle: 'bg-green-500',
  Listening: 'bg-yellow-500',
  Thinking: 'bg-blue-500',
  Speaking: 'bg-purple-500',
  SearchingMemory: 'bg-cyan-500',
  SearchingWeb: 'bg-cyan-500',
  Planning: 'bg-indigo-500',
  Learning: 'bg-emerald-500',
  Error: 'bg-red-500',
  Success: 'bg-emerald-500',
};

const RuntimeHUD = () => {
  const frame = useFrameState((f) => f);
  const systemState = frame.system.state;
  const gpuUsage = Math.round(frame.visual.activity * 100);
  const memUsage = (frame.visual.presence * 8).toFixed(1);

  return (
    <motion.div
      className="fixed top-6 right-6 flex items-center gap-3 rounded-full px-3 py-1.5 text-xs"
      style={{
        background: glass.background,
        border: `1px solid ${glass.border}`,
        boxShadow: glass.shadow,
        backdropFilter: `blur(${glass.blur})`,
        zIndex: depth.hud,
      }}
    >
      <div className="flex items-center gap-2">
        <div className={`h-2 w-2 rounded-full ${stateColorMap[systemState]}`} />
        <span className="text-neutral-300 capitalize">{systemState.toLowerCase()}</span>
      </div>
      <div className="h-4 w-px bg-white/10" />
      <div className="flex items-center gap-3 text-neutral-400">
        <span>GPU: {gpuUsage}%</span>
        <span>MEM: {memUsage}GB</span>
      </div>
    </motion.div>
  );
};

export default RuntimeHUD;