import { useEffect, useRef, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import GlassPanel from '@/components/design-system/GlassPanel';

interface ContextMenuProps {
  state: {
    x: number;
    y: number;
    items: Array<{
      label: string;
      onClick: () => void;
      disabled?: boolean;
      icon?: ReactNode;
      danger?: boolean;
    }>;
    visible: boolean;
  };
  close: () => void;
}

export default function ContextMenu({ state, close }: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!state.visible) return;

    const handleClickOutside = (event: globalThis.MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        close();
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [state.visible, close]);

  if (!state.visible || state.items.length === 0) return null;

  return (
    <motion.div
      ref={menuRef}
      className="absolute z-50"
      style={{ left: state.x, top: state.y }}
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.12 }}
      role="menu"
      aria-orientation="vertical"
    >
      <GlassPanel className="rounded-md p-1 min-w-[180px] shadow-lg">
        {state.items.map((item, index) => (
          <button
            key={index}
            type="button"
            role="menuitem"
            disabled={item.disabled}
            onClick={() => {
              item.onClick();
              close();
            }}
            className={`flex items-center gap-2 w-full px-3 py-1.5 rounded text-xs text-left transition-colors ${
              item.disabled
                ? 'opacity-40 cursor-not-allowed'
                : 'hover:bg-white/10'
            } ${item.danger ? 'text-amber-300' : 'text-slate-200'}`}
            style={{ outline: 'none' }}
          >
            {item.icon && <span className="shrink-0">{item.icon}</span>}
            <span className="flex-1 truncate">{item.label}</span>
          </button>
        ))}
      </GlassPanel>
    </motion.div>
  );
}