/**
 * The atmosphere around the embodiment — energy rings and drifting motes.
 *
 * **The orb had both and the avatar had neither**, because both were markup
 * inside `LivingOrb`. Choosing the character removed the rings, the particles
 * and the state colour with them, and left a robot standing on a flat
 * background. The orbit *tracks* that `Landing` draws are a different thing —
 * they belong to the six nodes and fade when the conversation opens; these
 * belong to the thing that is thinking.
 *
 * So it is extracted rather than reimplemented, and the colours come from
 * `ringColours` so there is one state→colour table. A second one would
 * eventually disagree with the first about what Zaram is doing, on the
 * indicator whose whole job is to be trusted.
 *
 * **It renders behind whatever it wraps, and that is explicit.** The avatar is
 * a WebGL canvas in normal flow; an absolutely positioned sibling with no
 * stacking of its own would paint over it and put motes across the face. The
 * layer is pinned at `zIndex: 0` and the caller lifts the character above it.
 *
 * It reports no state the rim light does not already report, and it adds no
 * new colour: it is the same two rings and the same ten motes the orb has
 * always drawn.
 */

import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import { useOrbStore } from '@/stores';

import OrbitalParticles from './OrbitalParticles';
import TrackRing from './TrackRing';
import { useChatModeStore } from '@/stores/chatModeStore';
import { ringColours } from './LivingOrb';

export default function OrbAura({
  /** The embodiment's box, in pixels. The rings are proportions of it, so the
   *  aura is the same shape whichever renderer it sits behind. */
  px,
  /** Dimmed while a source panel is in front of the orb, matching what the
   *  character itself does. */
  dimmed = false,
  /** The drifting motes; off on the landing, which has the ring messengers. */
  motes = true,
}: {
  px: number;
  motes?: boolean;
  dimmed?: boolean;
}) {
  const reduced = useIsReducedMotion();
  const state = useOrbStore((s) => s.orbState);
  const colours = ringColours(state);

  /**
   * Sized against the **subject**, not against the box — corrected 10 September.
   *
   * These were `LivingOrb`'s own proportions, 0.82 and 0.71, on the reasoning
   * that identical numbers give "an identically sized aura rather than one that
   * happens to look close". Identical proportions of the *container* are not an
   * identical aura, because the two renderers fill their containers completely
   * differently: the orb's sphere occupies about a third of its box, and the
   * character occupies nearly all of it.
   *
   * Measured on the running app, `px` scaling to a 448px canvas: ring 2 came
   * out at **318px inside a 448px character** -- 65px behind it on every side,
   * invisible, which is the ring the maintainer reported missing. Ring 1 came
   * out at 465px against 448px, clearing by 8.5px, so it traced the canvas edge
   * and read as an outline drawn on the character rather than an orbit around
   * it.
   *
   * Ring 1 needs no change: with `outerGlowOffset` added below it already
   * renders at 1.04x the box.
   *
   * **Ring 2 crosses the character rather than clearing it**, and the two
   * failures either side of that are worth keeping. At 0.71 it was entirely
   * inside the silhouette and read as missing. At 0.86 it cleared the shoulders
   * completely, which made it visible and made it a second outline floating
   * free of the subject. At 0.80 it passes *through* the character's shoulders:
   * occluded where the robot is opaque, visible where the canvas is not, which
   * is what reads as an orbit going behind something rather than a circle drawn
   * near it.
   *
   * That occlusion is free and already correct. `OrbAura` sits at `zIndex: 0`
   * inside the embodiment's box and the canvas is mounted above it at `z: 1`
   * with `alpha: true` -- confirmed with `elementsFromPoint` at the robot's
   * centre, which returns the canvas topmost. Nothing needs a mask.
   */
  const ring1 = Math.round(px * 0.82);
  const ring2 = Math.round(px * 0.80);
  const outerGlowOffset = Math.round(px * 0.22);
  const chatOpen = useChatModeStore((s) => s.chatView === 'chat');

  // Below the character. See the note above — this is the whole reason the
  // layer exists as a wrapper rather than a fragment.
  return (
    <div
      aria-hidden
      className="absolute inset-0 flex items-center justify-center pointer-events-none"
      style={{
        zIndex: 0,
        opacity: dimmed ? 0.25 : 1,
        transition: 'opacity 0.35s ease',
      }}
    >
      {/* The orb's own ambient glow, at the orb's own size and colour, so
          the two pages are lit alike — the avatar page had none and read
          darker and bluer than the orb's. */}
      <div
        className="absolute rounded-full pointer-events-none"
        style={{
          inset: 0,
          background: `radial-gradient(circle, ${colours.glow} 0%, ${colours.glow2} 22%, transparent 36%)`,
          filter: 'blur(18px)',
          opacity: 0.45,
          transition: 'background 0.45s ease',
        }}
      />
      {/* The same rings the orb draws for itself, in the landing's plane,
          with lights running them, and only while the landing is at rest.
          Drawn in two halves: the back half here, under the character, and
          the front half in `OrbAuraFront` above it — so the ring passes
          behind the head and in front of the body, which is what makes it an
          orbit around a thing rather than a circle drawn near it. */}
      {!chatOpen && (
        <>
          <TrackRing size={ring1 + outerGlowOffset} colour={colours.ring1} half="back" reduced={reduced} />
          <TrackRing size={ring2} colour={colours.ring2} half="back" reduced={reduced} />
        </>
      )}

      <div className="absolute inset-0">
        {motes && <OrbitalParticles />}
      </div>
    </div>
  );
}

/**
 * The front halves of the aura's rings, mounted *above* the character so the
 * near side of each orbit passes in front of its body. The lights ride these
 * halves, since a light behind the character would be a light nobody sees.
 */
export function OrbAuraFront({ px, dimmed = false }: { px: number; dimmed?: boolean }) {
  const reduced = useIsReducedMotion();
  const state = useOrbStore((s) => s.orbState);
  const colours = ringColours(state);
  const chatOpen = useChatModeStore((s) => s.chatView === 'chat');
  const ring1 = Math.round(px * 0.82);
  const ring2 = Math.round(px * 0.80);
  const outerGlowOffset = Math.round(px * 0.22);
  if (chatOpen) return null;
  return (
    <div
      aria-hidden
      className="absolute inset-0 flex items-center justify-center pointer-events-none"
      style={{ zIndex: 2, opacity: dimmed ? 0.25 : 1, transition: 'opacity 0.35s ease' }}
    >
      <TrackRing
        size={ring1 + outerGlowOffset}
        colour={colours.ring1}
        half="front"
        messengers={1}
        dir={-1}
        seconds={9}
        messengerColour="#22d3ee"
        reduced={reduced}
      />
      <TrackRing
        size={ring2}
        colour={colours.ring2}
        half="front"
        messengers={1}
        dir={1}
        seconds={6}
        messengerColour="#c084fc"
        reduced={reduced}
      />
    </div>
  );
}
