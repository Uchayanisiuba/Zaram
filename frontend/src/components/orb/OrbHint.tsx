/**
 * First-run instruction for the orb.
 *
 * Deliberately self-dismissing. A permanent pulsing prompt teaches for one
 * second and is noise for every session after, and "motion has a budget" is a
 * poor trade for something a user learns once. So:
 *
 *  - it waits a moment before appearing, so the landing is calm on arrival and
 *    anyone who taps the orb immediately never sees it at all;
 *  - it breathes slowly rather than pulsing, which reads as an invitation
 *    rather than an alert;
 *  - once the conversation has been opened, it never returns — remembered
 *    across sessions.
 *
 * Affordance is doing most of the work: the orb already has a pointer cursor
 * and a hover response. This is the backstop for someone who does not try.
 */
import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useChatModeStore } from '@/stores/chatModeStore';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';

/** Long enough that anyone who acts immediately never sees it. */
const APPEAR_AFTER_MS = 2600;

export default function OrbHint({ offsetX = 0 }: { offsetX?: number }) {
  const reduced = useIsReducedMotion();
  const hasOpenedChat = useChatModeStore((s) => s.hasOpenedChat);
  const chatOpen = useChatModeStore((s) => s.chatView) === 'chat';
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (hasOpenedChat) return;
    const t = setTimeout(() => setReady(true), APPEAR_AFTER_MS);
    return () => clearTimeout(t);
  }, [hasOpenedChat]);

  const show = ready && !hasOpenedChat && !chatOpen;

  return (
    <AnimatePresence>
      {show && (
        <motion.p
          className="absolute left-1/2 z-20 text-[12px] tracking-wide pointer-events-none select-none"
          style={{
            bottom: '8%',
            color: 'var(--color-text-muted)',
            fontFamily: 'var(--font-display)',
          }}
          initial={{ opacity: 0, y: 6 }}
          animate={{
            x: `calc(-50% + ${offsetX}px)`,
            y: 0,
            // A slow breath, not a pulse. Suppressed entirely under reduced
            // motion, where it simply sits still.
            opacity: reduced ? 0.7 : [0.35, 0.75, 0.35],
          }}
          exit={{ opacity: 0, y: 4, transition: { duration: 0.25 } }}
          transition={{
            opacity: reduced
              ? { duration: 0.3 }
              : { duration: 4.5, repeat: Infinity, ease: 'easeInOut' },
            y: { duration: 0.4 },
            x: { duration: 0.3 },
          }}
        >
          Click the orb to begin
        </motion.p>
      )}
    </AnimatePresence>
  );
}
