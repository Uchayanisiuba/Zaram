/**
 * What the Orb is saying, in words, beneath it.
 *
 * The top bar is hidden on the landing surface, so without this the largest
 * element in the product reports nothing at all — which was the case against
 * keeping it. This is the moment the status matters most: it sits directly
 * under the thing you are about to talk to, at the point of asking.
 *
 * Deliberately quiet. CLAUDE.md: calm over delight, and never claim absolute
 * security — state what is verifiable. So "Inference runs on this machine",
 * not "completely private".
 */
import { motion } from 'framer-motion';
import { useSystemStore, describeSystem } from '@/stores/systemStore';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';

const TONE_COLOR: Record<string, string> = {
  local: 'var(--color-emerald)',
  cloud: 'var(--color-amber)',
  offline: 'var(--color-red)',
  busy: 'var(--color-cyan)',
};

export default function OrbStatusLabel({
  dimmed = false,
  /** Smaller, for use beneath the orb where it must not compete with it. */
  compact = false,
}: {
  dimmed?: boolean;
  compact?: boolean;
}) {
  const reduced = useIsReducedMotion();
  const backendOnline = useSystemStore((s) => s.backendOnline);
  const routing = useSystemStore((s) => s.routing);
  const activity = useSystemStore((s) => s.activity);

  const { label, detail, tone } = describeSystem({ backendOnline, routing, activity });
  const accent = TONE_COLOR[tone] ?? 'var(--color-indigo)';

  return (
    <motion.div
      className="flex flex-col items-center gap-1 select-none pointer-events-none"
      // Announce changes: a status that updates silently is no use to a screen
      // reader, and this is the product's central claim.
      role="status"
      aria-live="polite"
      animate={{ opacity: dimmed ? 0 : 1 }}
      transition={{ duration: reduced ? 0.15 : 0.3 }}
    >
      <span className="flex items-center gap-2">
        <motion.span
          aria-hidden
          className="inline-block rounded-full"
          style={{
            width: compact ? 5 : 6,
            height: compact ? 5 : 6,
            background: accent,
            boxShadow: `0 0 8px ${accent}`,
          }}
          animate={
            reduced || (activity !== 'thinking' && activity !== 'warming')
              ? {}
              : { opacity: [1, 0.35, 1] }
          }
          transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
        />
        <span
          className={`${compact ? 'text-[11px]' : 'text-[13px]'} font-medium tracking-wide`}
          style={{ color: accent, fontFamily: 'var(--font-display)' }}
        >
          {label}
        </span>
      </span>
      <span
        className={`${compact ? 'text-[10px] max-w-[15rem]' : 'text-[11px] max-w-[16rem]'} text-slate-500 text-center leading-snug`}
      >
        {detail}
      </span>
    </motion.div>
  );
}
