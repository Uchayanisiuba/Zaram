import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { REGISTRY, type Platform, type Shortcut } from '@/runtime/shortcuts/registry';
import { Keycap } from '@/components/shortcuts/Keycap';

interface HelpOverlayProps {
  open: boolean;
  platform: Platform;
  onClose: () => void;
}

const GROUPS: { id: Shortcut['group']; label: string }[] = [
  { id: 'navigation', label: 'Navigation' },
  { id: 'orb', label: 'Orb' },
  { id: 'window', label: 'Window' },
  { id: 'general', label: 'General' },
];

export default function HelpOverlay({ open, platform, onClose }: HelpOverlayProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          style={{
            position: 'fixed',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(8,10,14,0.65)',
            backdropFilter: 'blur(4px)',
            zIndex: 200,
          }}
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ type: 'tween', duration: 0.15 }}
            style={{
              width: 'min(540px, 90vw)',
              maxHeight: 'min(640px, 80vh)',
              overflow: 'auto',
              background: 'var(--surface-panel)',
              border: '1px solid var(--color-border)',
              borderRadius: 12,
              boxShadow: '0 24px 80px rgba(0,0,0,0.55)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: '16px 20px',
                borderBottom: '1px solid var(--color-border-subtle)',
              }}
            >
              <h2
                style={{
                  margin: 0,
                  fontSize: 18,
                  fontFamily: 'var(--font-display)',
                  color: 'var(--color-text)',
                }}
              >
                Keyboard
              </h2>
            </div>
            <div style={{ padding: '12px 20px' }}>
              {GROUPS.map((g) => {
                const items = REGISTRY.filter((r) => r.group === g.id);
                if (!items.length) return null;
                return (
                  <div key={g.id} style={{ marginBottom: 20 }}>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--color-text-muted)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                        marginBottom: 8,
                      }}
                    >
                      {g.label}
                    </div>
                    {items.map((s) => (
                      <div
                        key={s.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '6px 0',
                          borderBottom: '1px solid var(--color-border-subtle)',
                        }}
                      >
                        <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>{s.label}</span>
                        <Keycap shortcut={s} platform={platform} />
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
