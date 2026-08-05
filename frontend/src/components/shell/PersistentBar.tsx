/**
 * The persistent bar.
 *
 * Always visible, on every surface including the landing. It is the shell's one
 * permanent fixture, and it exists to answer two questions the user should
 * never have to navigate to ask: what am I in the middle of, and on what basis
 * is it being answered.
 *
 * Three parts, left to right:
 *
 *   [orb]  Continuing: <topic>                    ← clickable, returns
 *          local · qwen2.5-coder:14b · 3 facts recalled
 *
 * The topic line is a real button, not a decorated div. UI-SPEC is explicit
 * that the return path must be visible and one click, and that the animation
 * must never be the only route back — a user who cannot find their way back to
 * a live conversation reloads the app and loses it. Before this bar existed
 * there were two routes back (the orb, and Escape from the landing); this is
 * the third and the only one that names what it returns to.
 *
 * Nothing here is invented. Every segment of the mono line is omitted when the
 * value behind it is unknown, so the bar is narrower on a cold start than it is
 * mid-conversation. That is the intended behaviour, not a layout bug: a bar
 * that always renders "local · gemma3 · 0 facts recalled" would be reporting
 * three things it does not know.
 */
import { useEffect } from 'react';

import { useSessionStatusStore, statusSegments } from '@/stores/sessionStatusStore';
import { useSystemStore, describeSystem } from '@/stores/systemStore';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import LivingOrb, { ORB_BEHAVIOUR } from '@/components/orb/LivingOrb';

const TONE_COLOR: Record<string, string> = {
  local: 'var(--color-emerald, #34d399)',
  cloud: 'var(--color-amber, #e5a44c)',
  offline: 'var(--color-red, #f87171)',
  busy: 'var(--color-cyan, #22d3ee)',
};

interface PersistentBarProps {
  /** Leave whatever surface is open and return to the conversation. Supplied by
   *  the shell, the only thing that can navigate. */
  onReturnToConversation: () => void;
}

export default function PersistentBar({ onReturnToConversation }: PersistentBarProps) {
  const reduced = useIsReducedMotion();

  // This component owns the health poll because it is the only one mounted on
  // every surface. It previously lived in Landing, which meant the model and
  // locality went stale the moment you left the landing — exactly where a bar
  // reporting them needs them to be fresh.
  const startPolling = useSystemStore((s) => s.startPolling);
  useEffect(() => startPolling(), [startPolling]);

  const backendOnline = useSystemStore((s) => s.backendOnline);
  const routing = useSystemStore((s) => s.routing);
  const activity = useSystemStore((s) => s.activity);

  const topic = useSessionStatusStore((s) => s.topic);
  const model = useSessionStatusStore((s) => s.model);
  const locality = useSessionStatusStore((s) => s.locality);
  const recallCount = useSessionStatusStore((s) => s.recallCount);
  const swapping = useSessionStatusStore((s) => s.swapping);

  const system = describeSystem({ backendOnline, routing, activity });
  const segments = statusSegments({ model, locality, recallCount, swapping });

  // Five orb states, per UI-SPEC plus the swap. A route needing a model the
  // card cannot hold alongside the embedder forces an unload and reload costing
  // seconds; an invisible swap reads as a broken product, so it gets its own
  // state rather than hiding inside "thinking".
  const orbState = swapping
    ? 'swapping'
    : !backendOnline
      ? 'offline'
      : activity === 'thinking' || activity === 'warming'
        ? 'thinking'
        : locality === 'cloud'
          ? 'cloud'
          : 'local';

  const tone = swapping ? 'busy' : system.tone;
  const busy = orbState === 'thinking' || orbState === 'swapping';

  return (
    <footer
      role="contentinfo"
      aria-label="Session status"
      style={{
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '8px 16px',
        minHeight: 52,
        // Glass: this is chrome, not content.
        background: 'rgba(18, 20, 25, 0.72)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderTop: '0.5px solid rgba(255,255,255,0.08)',
        zIndex: 40,
      }}
    >
      {/* The orb, at indicator size. Its ring carries the state colour. */}
      <div
        title={`${system.label} — ${system.detail}`}
        aria-label={system.label}
        style={{
          position: 'relative',
          width: 20,
          height: 20,
          flexShrink: 0,
          display: 'grid',
          placeItems: 'center',
          borderRadius: '50%',
          boxShadow: `0 0 0 1.5px ${TONE_COLOR[tone] ?? TONE_COLOR.local}`,
          // Motion has a budget. The ring breathes only while genuinely busy,
          // and not at all under reduced motion. The orb itself does not grow,
          // centre or react to the cursor — it is an instrument light.
          transition: 'box-shadow 200ms ease',
          opacity: busy && !reduced ? undefined : 1,
        }}
      >
        {/* `px` rather than a size token: the presets start at 80px and would
            overflow a 20px indicator. */}
        <LivingOrb px={16} emphasis={ORB_BEHAVIOUR.emphasis} />
      </div>

      <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
        {/* Topic line. A button so it is reachable by keyboard and announced as
            an action — this is a navigation control, not a caption. */}
        {topic ? (
          <button
            type="button"
            onClick={onReturnToConversation}
            style={{
              all: 'unset',
              cursor: 'pointer',
              font: '400 13px/1.35 inherit',
              color: '#F2F4F8',
              maxWidth: '52ch',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
            onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
          >
            <span style={{ color: '#6B7280' }}>Continuing: </span>
            {topic}
          </button>
        ) : (
          // No conversation yet. Say so plainly rather than showing an invented
          // title, and still offer the way in.
          <button
            type="button"
            onClick={onReturnToConversation}
            style={{
              all: 'unset',
              cursor: 'pointer',
              font: '400 13px/1.35 inherit',
              color: '#9BA1AC',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.textDecoration = 'underline')}
            onMouseLeave={(e) => (e.currentTarget.style.textDecoration = 'none')}
          >
            Start a conversation
          </button>
        )}

        {/* The mono line. Mono because every value on it is the system
            reporting a fact about itself. */}
        <div
          style={{
            font: '400 11px/1.4 var(--font-mono, ui-monospace, "JetBrains Mono", monospace)',
            color: '#6B7280',
            letterSpacing: '0.01em',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {segments.length > 0 ? (
            segments.join(' · ')
          ) : (
            // Nothing known yet. The bar is honest about that rather than
            // filling the space with a guess.
            <span style={{ opacity: 0.7 }}>
              {backendOnline ? 'connecting…' : 'engine not running'}
            </span>
          )}
        </div>
      </div>
    </footer>
  );
}
