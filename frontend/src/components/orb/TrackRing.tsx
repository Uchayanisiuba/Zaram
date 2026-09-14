/**
 * One ring in the landing's plane, with lights running along it.
 *
 * Every ring on the landing — the three tracks the nodes ride, and the two
 * energy rings each embodiment keeps around itself into the conversation —
 * is the same object seen from the same tilt. They were three separate
 * drawings, and the two around the embodiment stayed flat circles when the
 * tracks became a wheel, which is what the maintainer saw on 14 September
 * 2026: two rings on the conversation page facing the wrong way. One
 * component, one tilt constant, so a ring cannot face a different way from
 * the others again.
 *
 * The ring itself never rotates — `LivingOrb` settled that a ring that
 * spins is performing, and the orb does not perform. What moves are the
 * messengers: a few points of light on the ring, turning in the ring's own
 * frame so the tilt makes their path the ellipse without their knowing.
 * Composited transforms only; reduced motion stills them and keeps the ring.
 */
import { motion } from 'framer-motion';

/** Cosine of the viewing tilt: depth on the ring lands on screen at this
 *  fraction below centre. Shared with the landing's node wheel. */
export const RING_TILT = 0.58;

export interface TrackRingProps {
  /** Diameter of the ring's long axis, in px. */
  size: number;
  /** Line colour; animated when it changes, since colour is the state channel. */
  colour: string;
  /** How many lights run the ring, which way, and how long one lap takes. */
  messengers?: number;
  dir?: 1 | -1;
  seconds?: number;
  messengerColour?: string;
  reduced?: boolean;
  /** Class for the line element — the landing uses it for the proximity opacity. */
  lineClassName?: string;
  lineOpacity?: number;
}

export default function TrackRing({
  size,
  colour,
  messengers = 0,
  dir = 1,
  seconds = 12,
  messengerColour = '#22d3ee',
  reduced = false,
  lineClassName = '',
  lineOpacity,
}: TrackRingProps) {
  return (
    <div
      className="absolute rounded-full pointer-events-none"
      style={{ width: size, height: size, transform: `scaleY(${RING_TILT})` }}
      aria-hidden
    >
      <motion.div
        className={`absolute inset-0 rounded-full ${lineClassName}`}
        style={{ border: `1px solid ${colour}`, opacity: lineOpacity }}
        animate={{ borderColor: colour }}
        transition={{ duration: reduced ? 0 : 0.45 }}
      />
      {messengers > 0 && (
        <motion.div
          className="absolute inset-0"
          animate={reduced ? undefined : { rotate: 360 * dir }}
          transition={{ duration: seconds, ease: 'linear', repeat: Infinity }}
        >
          {Array.from({ length: messengers }, (_, k) => (
            <span
              key={k}
              className="absolute rounded-full"
              style={{
                width: 4,
                height: 4,
                left: '50%',
                top: 0,
                transform: `translate(-50%, -50%) rotate(${(360 / messengers) * k}deg)`,
                transformOrigin: `50% ${size / 2}px`,
                background: messengerColour,
                boxShadow: `0 0 8px ${messengerColour}, 0 0 2px #fff`,
              }}
            />
          ))}
        </motion.div>
      )}
    </div>
  );
}
