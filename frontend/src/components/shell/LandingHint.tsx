/**
 * The line under the orb — one slot, and whichever instruction is true.
 *
 * Closed, it is "Click Orb to Chat" (or "Click Avatar", following the
 * renderer). Open, that instruction has been taken and would be noise, so the
 * same place carries the one that is true now: `VoiceHint`, "Press Shift Space
 * to talk". It never appears on Work, Memory, Knowledge, Activity or Settings.
 *
 * **One slot rather than two lines, decided 7 September 2026.** The voice hint
 * lived briefly on the landing beside this one, and briefly inside the
 * conversation's transcript, and both were wrong for the same reason: an
 * instruction belongs under the thing it is about, and there is only ever one
 * of those true at a time. Two at once asks somebody to choose between ways in
 * before they have done anything; one in the transcript sits on the opposite
 * side of the screen from the orb and competes with "Ask Zaram something".
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
import { useEmbodimentStore } from '@/stores/embodimentStore';
import VoiceHint from '@/components/chat/VoiceHint';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { useViewport } from '@/hooks/useViewport';
import { orbGeometry, useLayoutStore } from '@/stores/layoutStore';

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

  /**
   * What the user is being told to click, which is whatever is on screen.
   *
   * The hint names a target, and the target is a *choice the user already
   * made* — `CLAUDE.md` puts the orb and the avatar behind one toggle and says
   * they read the same state, so the instruction has to follow the toggle.
   * Saying "Orb" to somebody looking at a character is not a small
   * inaccuracy: it is the first line they read, naming a thing that is not
   * there, which reads as the product not knowing what it is showing.
   *
   * It stays "Avatar" rather than becoming the name they gave it. A person who
   * called it Ada would read "Click Ada to Chat" as friendlier, but the hint is
   * an instruction about a control and the name is a fact from `user_settings`
   * that this component would have to fetch — a network call on the landing,
   * for a word. `identity_preamble` is where the name belongs.
   */
  const renderer = useEmbodimentStore((s) => s.renderer);

  /**
   * The line follows the orb sideways, because it is a caption for it.
   *
   * When the conversation opens, the orb travels from the viewport centre to
   * the centre of the space the panel leaves — half the panel's width to the
   * left. The footer did not move, so the hint stayed centred on the *window*
   * while the thing it names sat well to the left of it, and the further the
   * user dragged the panel wider the further apart they drifted.
   *
   * **`orbGeometry` is asked rather than the offset recomputed here**, which
   * is the whole point: two formulae for one position is how a caption comes
   * to disagree with its subject, and this one would only disagree while the
   * panel was being resized — the moment nobody is looking at the footer.
   * `containerScale: 1` because this line is not inside the orb's scaled
   * container, so it wants the plain visual shift; `chatFraction` and not the
   * workspace fraction, because this renders on the landing only.
   *
   * Vertical position is untouched: it comes from sitting last in the column,
   * which already puts it under the orb.
   */
  const { width: viewportWidth } = useViewport();
  const chatFraction = useLayoutStore((s) => s.chatFraction);
  const { shiftX } = orbGeometry({
    viewportWidth,
    chatFraction,
    chatOpen: chatOpen,
    orbSize: 1,
    containerScale: 1,
  });

  // Never on Work, Memory, Knowledge, Activity or Settings.
  if (!isLanding) return null;

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
        // Follows the orb sideways; see the `shiftX` note above. Eased at the
        // panel's own tempo so the caption travels with its subject rather
        // than snapping into place after it.
        transform: shiftX ? `translateX(${shiftX}px)` : undefined,
        transition: reduced ? 'none' : 'transform 0.28s ease',
        background: 'transparent',
        zIndex: 40,
        // Never intercept a click meant for the orb.
        pointerEvents: 'none',
      }}
    >
      {/* **One slot, two instructions, and only ever one of them.**
          Closed, it names the way in. Open, the way in has been taken and the
          line that is true now is how to talk — so the same place under the orb
          carries it, rather than the instruction persisting after the thing it
          instructed, or a second line appearing somewhere else on screen.
          `VoiceHint` decides for itself whether it has anything to say, and
          renders nothing when Zaram cannot listen. */}
      {chatOpen ? (
        <VoiceHint />
      ) : (
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
          {renderer === 'avatar' ? 'Click Avatar to Chat' : 'Click Orb to Chat'}
        </span>
      )}
    </footer>
  );
}
