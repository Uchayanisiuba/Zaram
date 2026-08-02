import type { Platform, Shortcut } from '@/runtime/shortcuts/registry';
import { chordTokens } from '@/runtime/shortcuts/registry';

interface KeycapProps {
  shortcut: Shortcut;
  platform?: Platform;
  size?: 'sm' | 'md';
}

export function Keycap({ shortcut, platform = 'win', size = 'sm' }: KeycapProps) {
  const chord = chordTokens(shortcut, platform);
  return (
    <span
      aria-hidden={shortcut.keys.key === '?'}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 2,
        padding: size === 'sm' ? '2px 6px' : '4px 10px',
        fontSize: size === 'sm' ? 10 : 12,
        lineHeight: 1,
        fontFamily: 'var(--font-mono)',
        fontWeight: 600,
        border: '1px solid var(--color-border-subtle)',
        borderRadius: 4,
        background: 'var(--color-glass)',
        color: 'var(--color-text-muted)',
        boxShadow: '0 2px 6px rgba(0,0,0,0.4)',
        whiteSpace: 'nowrap',
      }}
      title={shortcut.label}
    >
      {chord}
    </span>
  );
}
