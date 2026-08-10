/**
 * The landing hint — "Click Orb to Chat".
 *
 * Shown on the landing, and only while the conversation is closed. Tapping the
 * orb opens the conversation and the line goes with it: it is an instruction to
 * do a thing, so it has no reason to persist once the thing is done. It never
 * appears on Work, Memory, Knowledge, Activity or Settings.
 *
 * This was a persistent bar — glass panel, orb, clickable topic, and a mono
 * `local · <model> · N facts recalled` line — replaced on sight because the
 * chrome ran the width of the landing and competed with the orb, which is the
 * actual way in. The session status store still tracks the model, locality and
 * recall count, still fed by /health and the chat stream, so whatever reports
 * routing next reads it unchanged.
 *
 * One thing genuinely went: the clickable topic line was a third route back to
 * a live conversation, and the only one that named its destination. The orb and
 * Escape remain, so "never let the animation be the only route back" still
 * holds, but a user inside a workspace no longer sees what they were mid-way
 * through.
 *
 * The component stays mounted on every surface even though it renders nothing
 * on most of them, because it owns the /health poll. That is not decoration —
 * Settings reads speech availability from it and the orb reads routing. Hooks
 * run regardless of what the render returns, so hiding the line does not stop
 * the polling.
 */
import { useEffect } from 'react';

import { useSystemStore } from '@/stores/systemStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';

interface LandingHintProps {
  /** Whether the landing is the current surface. Passed in rather than read
   *  from a store because the shell owns which workspace is open. */
  isLanding: boolean;
}

export default function LandingHint({ isLanding }: LandingHintProps) {
  const reduced = useIsReducedMotion();
  const chatOpen = useChatModeStore((s) => s.chatView === 'chat');

  // Kept above the early return: this is the only component mounted on every
  // surface, so it owns the poll, and an effect placed after a conditional
  // return would be a hooks-order violation as well as stopping the polling.
  const startPolling = useSystemStore((s) => s.startPolling);
  useEffect(() => startPolling(), [startPolling]);

  if (!isLanding || chatOpen) return null;

  return (
    <footer
      role="contentinfo"
      aria-label="Getting started"
      style={{
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        // Centred on X. Vertical position comes from sitting last in the
        // column, so the line lands in the lower portion of the screen without
        // being absolutely positioned against it.
        justifyContent: 'center',
        padding: '8px 16px',
        minHeight: 52,
        background: 'transparent',
        zIndex: 40,
        // Never intercept a click meant for the orb.
        pointerEvents: 'none',
      }}
    >
      <span
        style={{
          // Same face and colour the status line used for "engine not running".
          font: '400 18px/1.3 var(--font-mono, ui-monospace, "JetBrains Mono", monospace)',
          color: '#6B7280',
          letterSpacing: '0.01em',
          userSelect: 'none',
          // Arcade attract loop, slowed to a breath. Suppressed under reduced
          // motion, where the line sits at its bright end — the instruction
          // still reads, it just stops moving.
          opacity: reduced ? 0.78 : undefined,
          animation: reduced ? undefined : 'attract-blink 4.2s ease-in-out infinite',
        }}
      >
        Click Orb to Chat
      </span>
    </footer>
  );
}
