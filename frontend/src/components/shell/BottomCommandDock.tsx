import React from 'react';
import { motion } from 'framer-motion';
import {
  Search, MessageSquare, Brain, Network, Rss,
  Workflow, Waypoints, LayoutGrid, SlidersHorizontal, Mic, MicOff,
} from 'lucide-react';
import { useOrbStore } from '@/stores';

const DOCK_ITEMS = [
  { id: 'conversation', label: 'Chat',       icon: MessageSquare },
  { id: 'memory',       label: 'Memory',     icon: Brain },
  { id: 'knowledge',    label: 'Knowledge',  icon: Network },
  { id: 'updates',      label: 'Updates',    icon: Rss },
  { id: 'work',         label: 'Work',       icon: Workflow },
  { id: 'agents',       label: 'Agents',     icon: Waypoints },
  { id: 'extensions',   label: 'Extensions', icon: LayoutGrid },
  { id: 'settings',     label: 'Settings',   icon: SlidersHorizontal },
];

interface BottomCommandDockProps {
  activeWorkspace: string;
  onWorkspaceChange: (id: string) => void;
  onSearch: () => void;
}

const BottomCommandDock = ({
  activeWorkspace,
  onWorkspaceChange,
  onSearch,
}: BottomCommandDockProps) => {
  const { orbState, setOrbState } = useOrbStore();
  const isListening = orbState === 'listening';

  const handleVoice = () => {
    setOrbState(isListening ? 'idle' : 'listening');
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
      <div
        className="flex items-center gap-1 px-3 py-2 rounded-2xl pointer-events-auto"
        style={{
          background: 'rgba(6,7,9,0.88)',
          border: '1px solid rgba(255,255,255,0.09)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
        }}
      >
        {/* Search */}
        <DockButton
          label="Search"
          onClick={onSearch}
          active={false}
          aria-label="Search (⌘K)"
        >
          <Search className="w-4 h-4" />
        </DockButton>

        <Divider />

        {/* Workspace items */}
        {DOCK_ITEMS.map((item, i) => (
          <React.Fragment key={item.id}>
            {/* Separator before settings */}
            {i === DOCK_ITEMS.length - 1 && <Divider />}
            <DockButton
              label={item.label}
              onClick={() => onWorkspaceChange(item.id)}
              active={activeWorkspace === item.id}
            >
              <item.icon className="w-4 h-4" />
            </DockButton>
          </React.Fragment>
        ))}

        <Divider />

        {/* Voice toggle */}
        <DockButton
          label={isListening ? 'Stop' : 'Voice'}
          onClick={handleVoice}
          active={isListening}
          activeColor="rgba(239,68,68,0.2)"
          activeTextColor="#f87171"
        >
          {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
        </DockButton>
      </div>
    </div>
  );
};

// ── Sub-components ─────────────────────────────────────────────────────────

interface DockButtonProps {
  label: string;
  onClick: () => void;
  active: boolean;
  activeColor?: string;
  activeTextColor?: string;
  children: React.ReactNode;
  'aria-label'?: string;
}

const DockButton = ({
  label,
  onClick,
  active,
  activeColor = 'rgba(99,102,241,0.20)',
  activeTextColor = '#a5b4fc',
  children,
  'aria-label': ariaLabel,
}: DockButtonProps) => (
  <motion.button
    className="relative flex items-center justify-center w-10 h-10 rounded-xl group"
    style={{
      color:      active ? activeTextColor : '#475569',
      background: active ? activeColor : 'transparent',
      boxShadow:  active ? `0 0 16px ${activeColor}` : 'none',
    }}
    whileHover={{ y: -5, scale: 1.18 }}
    whileTap={{ scale: 0.92 }}
    transition={{ type: 'spring', stiffness: 420, damping: 22 }}
    onClick={onClick}
    aria-label={ariaLabel ?? label}
    title={label}
  >
    {/* Icon — inherits color from parent via currentColor */}
    <span className="group-hover:text-indigo-300 transition-colors">{children}</span>

    {/* Tooltip */}
    <span
      className="absolute -top-9 left-1/2 -translate-x-1/2 text-xs text-slate-300 whitespace-nowrap
                 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none
                 rounded-lg px-2.5 py-1 z-10"
      style={{
        background: 'rgba(10,10,20,0.96)',
        border: '1px solid rgba(255,255,255,0.07)',
      }}
    >
      {label}
    </span>
  </motion.button>
);

const Divider = () => (
  <div className="w-px h-5 mx-0.5 rounded-full" style={{ background: 'rgba(255,255,255,0.08)' }} />
);

export default BottomCommandDock;
