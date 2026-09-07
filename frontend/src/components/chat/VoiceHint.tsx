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
 * **It renders in the landing's own footer**, under the orb or the avatar,
 * where "Click Orb to Chat" was a moment ago. Same slot, same face, same
 * `attract-blink` keyframes, same muted grey — one line under the thing you are
 * looking at, replaced by the instruction that is true now. Putting it in the
 * transcript instead was tried first and was wrong twice over: it competed with
 * "Ask Zaram something" for the same job, and it sat on the opposite side of
 * the screen from the orb it belongs under.
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
import { useChatStore } from '@/stores/chatStore';
import { useMicStore } from '@/stores/micStore';

export default function VoiceHint() {
  const reduced = useIsReducedMotion();
  const unavailable = useMicStore((s) => s.unavailableReason);
  const status = useMicStore((s) => s.status);
  const check = useMicStore((s) => s.checkAvailability);
  /** Whether anything has been said yet. Read here rather than passed in: the
   *  component already owns the other two conditions, and a caller that had to
   *  supply one of three would be the place they drift apart. */
  const empty = useChatStore((s) => s.messages.length === 0 && !s.streamingText);

  // Above the early return, or the hooks order changes with the render.
  useEffect(() => {
    void check();
  }, [check]);

  const voice = REGISTRY.find((s) => s.id === 'voice');
  if (!empty || !voice || unavailable !== null || status !== 'idle') return null;

  return (
    <span
      aria-live="off"
      style={{
        // Sized and coloured to sit under the orb where "Click Orb to Chat"
        // sits, because it is the same kind of line in the same place — the
        // instruction for the surface you are now on. Slightly smaller: the
        // landing's is the only thing on screen, and this one shares the
        // surface with a conversation.
        font: '400 15px/1.3 var(--font-mono, ui-monospace, "JetBrains Mono", monospace)',
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
    </span>
  );
}
