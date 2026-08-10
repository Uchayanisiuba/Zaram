import { motion } from 'framer-motion';
import { Bell, User, Cpu, Wifi } from 'lucide-react';

const TopNavigation = () => {
  return (
    <div
      className="fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-5 border-b glass"
      style={{ height: 'var(--nav-height)', borderColor: 'var(--glass-border)' }}
    >
      {/* Left: Branding + Status */}
      <div className="flex items-center gap-3">
        <span
          className="text-sm text-slate-100"
          style={{ fontWeight: 600, letterSpacing: '0.08em' }}
        >
          ZARAM
        </span>
        
        <div
          className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded-full"
          style={{
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <motion.div
            className="w-1.5 h-1.5 rounded-full bg-emerald-400"
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <span
            className="text-xs text-slate-400 uppercase"
            style={{ fontSize: '10px', letterSpacing: '0.06em' }}
          >
            Local Active
          </span>
        </div>
      </div>

      {/* Right: System indicators + Profile */}
      <div className="flex items-center gap-5">
        {/* Neural Engine indicator (hidden on small screens) */}
        <div
          className="hidden md:flex items-center gap-1 text-xs"
          style={{ color: '#475569', fontVariantNumeric: 'tabular-nums', fontSize: '11px' }}
        >
          <Cpu className="w-3 h-3" />
          <span>Neural Engine</span>
        </div>

        {/* Network status */}
        <div className="hidden sm:flex items-center gap-1 text-xs" style={{ color: '#475569', fontSize: '11px' }}>
          <Wifi className="w-3 h-3" />
        </div>

        {/* Notifications */}
        <button
          className="text-slate-600 hover:text-slate-300 transition-colors"
          aria-label="Notifications"
        >
          <Bell className="w-3.5 h-3.5" />
        </button>

        {/* User profile */}
        <div
          className="w-6 h-6 rounded-full flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity"
          style={{
            background: 'rgba(99,102,241,0.35)',
            border: '1px solid rgba(99,102,241,0.4)',
          }}
        >
          <User className="w-3 h-3 text-indigo-200" />
        </div>
      </div>
    </div>
  );
};

export default TopNavigation;
