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
  /** What the orb is on right now — `workingLine` — shown in place of the
   *  generic detail while a reply is in flight. A system-reported value, so
   *  it is set in the mono (UI-SPEC). Null means there is nothing specific
   *  to say and the sentence from `describeSystem` stands. */
  working = null,
}: {
  dimmed?: boolean;
  compact?: boolean;
  working?: string | null;
}) {
  const reduced = useIsReducedMotion();
  const backendOnline = useSystemStore((s) => s.backendOnline);
  const routing = useSystemStore((s) => s.routing);
  const activity = useSystemStore((s) => s.activity);
  const swappingTo = useSystemStore((s) => s.swappingTo);
  const cloudAnsweredAt = useSystemStore((s) => s.cloudAnsweredAt);

  const { label, detail, tone } = describeSystem({
    backendOnline, routing, activity, swappingTo, cloudAnsweredAt,
  });
  const accent = TONE_COLOR[tone] ?? 'var(--color-indigo)';

  return (
    <motion.div
      // Compact is the capsule under the orb: one row, the state and its
      // sentence side by side, wrapping only when the sentence is long.
      className={`flex ${compact ? 'flex-row flex-wrap justify-center items-baseline gap-x-3 gap-y-0.5' : 'flex-col items-center gap-1'} select-none pointer-events-none`}
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
          className={`${compact ? 'text-xs' : 'text-[13px]'} font-medium tracking-wide`}
          style={{ color: accent, fontFamily: 'var(--font-display)' }}
        >
          {label}
        </span>
      </span>
      {working && tone === 'busy' ? (
        <span
          className={`${compact ? 'max-w-[18rem]' : 'max-w-[20rem]'} t-mono text-center leading-snug truncate`}
          data-testid="orb-working"
          title={working}
        >
          {working}
        </span>
      ) : compact && tone === 'local' ? null : (
        // In the capsule the sentence appears only when it explains something
        // the label cannot — offline, warming, a switch, cloud used. At rest
        // and local, "Local only" is the whole of it, and the sentence under
        // it was the same claim again in more words.
        <span
          className={`${compact ? 'text-xs max-w-[30rem] truncate' : 'text-xs max-w-[16rem] text-center'} text-slate-500 leading-snug`}
          title={compact ? detail : undefined}
        >
          {detail}
        </span>
      )}
    </motion.div>
  );
}
