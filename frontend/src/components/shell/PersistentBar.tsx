/**
 * The bottom hint line.
 *
 * This was a full persistent bar — glass panel, orb, clickable topic, and a mono
 * status line. It was replaced on sight: the chrome sat across the bottom of the
 * landing and competed with the orb, which is the actual way in.
 *
 * What remains is one line of type in the same mono face and muted colour the
 * status line used, three times the size, centred horizontally and sitting where
 * the bar used to sit vertically. No panel, no border, no backdrop.
 *
 * Two things went with the panel, and they are worth naming because they were
 * the reason it existed:
 *
 * 1. The clickable topic line, which was the third route back to a live
 *    conversation and the only one that named its destination. The orb and
 *    Escape remain, so the "never let the animation be the only route back"
 *    requirement still holds — but a user in a workspace no longer sees what
 *    they were in the middle of.
 * 2. The `local · <model> · N facts recalled` line. The session status store
 *    still tracks all of it and is still fed by /health and the chat stream, so
 *    this is a display change rather than a loss of the underlying state.
 *    Whatever surface wants to report routing next can read it unchanged.
 */
import { useEffect } from 'react';

import { useSystemStore } from '@/stores/systemStore';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';

interface PersistentBarProps {
  /** Leave whatever surface is open and return to the conversation. Retained
   *  because the shell still owns that transition; nothing here calls it today. */
  onReturnToConversation: () => void;
}

export default function PersistentBar(_props: PersistentBarProps) {
  const reduced = useIsReducedMotion();

  // Still the only component mounted on every surface, so it keeps ownership of
  // the health poll. The bar's chrome is gone; the polling it was doing is not
  // decoration — Settings and the orb both read what it fetches.
  const startPolling = useSystemStore((s) => s.startPolling);
  useEffect(() => startPolling(), [startPolling]);

  return (
    <footer
      role="contentinfo"
      aria-label="Session status"
      style={{
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        // Centred on X. The vertical position is inherited from sitting where
        // the bar sat in the column, so the line lands in the lower portion of
        // the screen without being absolutely positioned against it.
        justifyContent: 'center',
        padding: '8px 16px',
        minHeight: 52,
        // No panel. Nothing to refract, nothing to draw an edge against.
        background: 'transparent',
        zIndex: 40,
        pointerEvents: 'none',
      }}
    >
      <span
        style={{
          // Same face and colour as the status line's "engine not running".
          font: '400 18px/1.3 var(--font-mono, ui-monospace, "JetBrains Mono", monospace)',
          color: '#6B7280',
          letterSpacing: '0.01em',
          userSelect: 'none',
          // Arcade attract loop. Suppressed under reduced motion, where the
          // line simply sits at its bright end — the instruction still reads,
          // it just stops waving.
          opacity: reduced ? 0.72 : undefined,
          animation: reduced ? undefined : 'attract-blink 2.4s ease-in-out infinite',
        }}
      >
        Click orb to begin
      </span>
    </footer>
  );
}
