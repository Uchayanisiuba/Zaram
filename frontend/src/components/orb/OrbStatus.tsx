/**
 * The Orb, at working size.
 *
 * Same object as the landing centrepiece, demoted to a persistent indicator on
 * every working surface. Two jobs, both of which it is defined to have:
 *
 * 1. Report system state — local only, cloud enabled, thinking, offline.
 *    This is the product claim made continuously visible, and it is the one
 *    thing a competitor cannot copy: nothing else can tell you a question
 *    stayed on your machine.
 * 2. Open the conversation from anywhere, so Zaram is always reachable while
 *    you work, without the conversation owning the screen.
 *
 * It reports; it does not perform. Motion is limited to a slow breath at rest
 * and a faster pulse while thinking, and is suppressed entirely under reduced
 * motion.
 */
import { useEffect } from 'react';
import { motion } from 'framer-motion';
import LivingOrb from './LivingOrb';
import { useSystemStore, describeSystem } from '@/stores/systemStore';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';

const TONE_COLOR: Record<string, string> = {
  local: 'var(--color-emerald)',
  cloud: 'var(--color-amber)',
  offline: 'var(--color-red)',
  busy: 'var(--color-cyan)',
};

export default function OrbStatus({ size = 56 }: { size?: number }) {
  const reduced = useIsReducedMotion();
  const backendOnline = useSystemStore((s) => s.backendOnline);
  const routing = useSystemStore((s) => s.routing);
  const activity = useSystemStore((s) => s.activity);
  const startPolling = useSystemStore((s) => s.startPolling);
  const toggleChat = useChatModeStore((s) => s.toggleChat);
  const chatOpen = useChatModeStore((s) => s.chatView) === 'chat';

  useEffect(() => startPolling(), [startPolling]);

  const { label, detail, tone } = describeSystem({ backendOnline, routing, activity });
  const accent = TONE_COLOR[tone] ?? 'var(--color-indigo)';
  const busy = activity === 'thinking';

  return (
    <button
      type="button"
      onClick={toggleChat}
      aria-label={`${label}. ${detail} ${chatOpen ? 'Close' : 'Open'} conversation.`}
      aria-pressed={chatOpen}
      title={`${label} — ${detail}`}
      className="group relative flex items-center gap-2.5 rounded-full pl-1 pr-3 py-1 transition-colors hover:bg-white/5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-indigo)]"
    >
      <span className="relative inline-flex" style={{ width: size, height: size }}>
        <motion.span
          className="absolute inset-0"
          animate={
            reduced
              ? {}
              : busy
                ? { scale: [1, 1.06, 1] }
                : { scale: [1, 1.02, 1] }
          }
          transition={
            reduced
              ? undefined
              : { duration: busy ? 1.6 : 5, repeat: Infinity, ease: 'easeInOut' }
          }
        >
          <LivingOrb size="sm" />
        </motion.span>

        {/* Status ring. The colour is the signal; the orb itself stays neutral
            so its appearance is not confused with brand styling. */}
        <span
          aria-hidden
          className="absolute inset-0 rounded-full pointer-events-none"
          style={{
            border: `1.5px solid ${accent}`,
            opacity: 0.55,
            boxShadow: `0 0 10px ${accent}40`,
          }}
        />
      </span>

      <span className="flex flex-col items-start leading-tight">
        <span
          className="text-[11px] font-medium"
          style={{ color: accent, fontFamily: 'var(--font-display)' }}
        >
          {label}
        </span>
        <span className="text-[9px] text-slate-500">
          {chatOpen ? 'Close chat' : 'Ask Zaram'}
        </span>
      </span>
    </button>
  );
}
