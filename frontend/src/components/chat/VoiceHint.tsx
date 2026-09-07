/**
 * "Press Shift Space to talk" — the conversation's counterpart to the
 * landing's "Click Orb to Chat".
 *
 * **The same line, in the same voice, one surface along.** The landing's hint
 * names the one gesture that gets you in; this names the one that gets you
 * talking, and it lives here rather than on the landing because that is where
 * the microphone is. A hint on the landing was tried on 7 September 2026 and
 * moved at the maintainer's direction: the landing has one instruction and
 * putting a second beside it asks somebody to choose between two ways in before
 * they have done anything.
 *
 * Deliberately borrowed from `LandingHint`, down to the `attract-blink`
 * keyframes, the mono face and the muted grey — two hints in one product that
 * look like two different products is the cost of writing the second one fresh.
 * It is smaller, because the conversation is a working surface and the landing
 * is not.
 *
 * **Shown only while it is true**, which is three conditions and not one:
 *
 * * Zaram can actually listen. `CLAUDE.md` requires that disabled capabilities
 *   are visible rather than silent, *and* that invented values are never
 *   rendered — and an instruction to press a key that does nothing is the
 *   second of those, not the first. Naming the missing extra and its 81 MB
 *   belongs on the microphone button, where somebody is already asking about
 *   voice.
 * * The conversation is empty. It is an instruction to start, so it goes the
 *   moment anything has been said — the same rule that takes the landing's line
 *   away once the orb has been clicked.
 * * The microphone is not already open. Telling somebody how to start something
 *   they have started reads as the product not knowing.
 *
 * The chord comes from the shortcut registry rather than being typed here, so
 * the line and the matcher cannot drift. That is not caution: this registry has
 * two comments recording occasions when the interface advertised a chord
 * nothing answered to.
 */
import { useEffect } from 'react';

import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { REGISTRY, chordTokens, detectPlatform } from '@/runtime/shortcuts/registry';
import { useMicStore } from '@/stores/micStore';

export default function VoiceHint({
  /** Whether anything has been said yet. */
  empty,
}: {
  empty: boolean;
}) {
  const reduced = useIsReducedMotion();
  const unavailable = useMicStore((s) => s.unavailableReason);
  const status = useMicStore((s) => s.status);
  const check = useMicStore((s) => s.checkAvailability);

  // Above the early return, or the hooks order changes with the render.
  useEffect(() => {
    void check();
  }, [check]);

  const voice = REGISTRY.find((s) => s.id === 'voice');
  if (!empty || !voice || unavailable !== null || status !== 'idle') return null;

  return (
    <p
      aria-live="off"
      style={{
        textAlign: 'center',
        font: '400 13px/1.3 var(--font-mono, ui-monospace, "JetBrains Mono", monospace)',
        color: '#6B7280',
        letterSpacing: '0.01em',
        userSelect: 'none',
        pointerEvents: 'none',
        // The landing's arcade attract loop, at the landing's tempo. Suppressed
        // under reduced motion, where the line sits at its bright end so the
        // instruction still reads.
        opacity: reduced ? 0.78 : undefined,
        animation: reduced ? undefined : 'attract-blink 4.2s ease-in-out infinite',
      }}
    >
      Press {chordTokens(voice, detectPlatform())} to talk
    </p>
  );
}
