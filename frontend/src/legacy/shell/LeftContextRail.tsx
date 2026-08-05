import { useState } from 'react';
import { motion } from 'framer-motion';
import { Clock, Bookmark, Database, Package, Search, Settings, User } from 'lucide-react';

const RAIL_ITEMS = [
  { id: 'context',   label: 'Recent Context', icon: Clock },
  { id: 'memory',    label: 'Pinned Memory',  icon: Bookmark },
  { id: 'knowledge', label: 'Knowledge',      icon: Database },
  { id: 'plugins',   label: 'Plugins',        icon: Package },
  { id: 'search',    label: 'Search',         icon: Search },
  { id: 'settings',  label: 'Settings',       icon: Settings },
];

const LeftContextRail = () => {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      className="fixed z-30 flex flex-col border-r overflow-hidden"
      style={{
        top: 'var(--nav-height)',
        bottom: 0,
        left: 0,
        background: 'rgba(6,7,9,0.60)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        borderColor: 'var(--glass-border)',
      }}
      animate={{ width: expanded ? 224 : 56 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      {/* Nav items */}
      <div className="flex-1 py-3 flex flex-col gap-0.5 overflow-hidden">
        {RAIL_ITEMS.map((item) => (
          <button
            key={item.id}
            className="flex items-center gap-3 px-4 py-3 w-full text-left transition-colors hover:bg-white/5"
            style={{ minWidth: 224 }}
          >
            <item.icon
              className="shrink-0 transition-colors text-slate-600 hover:text-slate-400"
              style={{ width: 16, height: 16, minWidth: 16 }}
            />
            <motion.span
              className="text-xs text-slate-500 whitespace-nowrap"
              style={{ letterSpacing: '0.01em' }}
              animate={{ opacity: expanded ? 1 : 0 }}
              transition={{ duration: expanded ? 0.15 : 0.05 }}
            >
              {item.label}
            </motion.span>
          </button>
        ))}
      </div>

      {/* Profile at bottom */}
      <div className="p-3 border-t" style={{ borderColor: 'var(--glass-border)' }}>
        <button
          className="flex items-center gap-3 w-full hover:bg-white/5 p-1.5 rounded-xl transition-colors"
          style={{ minWidth: 200 }}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center shrink-0"
            style={{
              background: 'rgba(99,102,241,0.30)',
              border: '1px solid rgba(99,102,241,0.35)',
            }}
          >
            <User style={{ width: 14, height: 14, color: '#a5b4fc' }} />
          </div>
          <motion.span
            className="text-xs text-slate-500 whitespace-nowrap"
            animate={{ opacity: expanded ? 1 : 0 }}
            transition={{ duration: expanded ? 0.15 : 0.05 }}
          >
            Profile
          </motion.span>
        </button>
      </div>
    </motion.div>
  );
};

export default LeftContextRail;
