import { useMemo } from 'react';
import { motion, type Variants } from 'framer-motion';
import { useOrbStore } from '@/stores';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import type { OrbState } from '@/stores/orbStore';
import { settleAll } from './stillness';

// Total map — see the note in Aura.tsx.
//
// Every duration here is a whole multiple of four seconds. See the note on
// `Aura.swapping` for why: periods sharing no common factor never re-align, so
// the composite never resolves and the orb reads as restless rather than calm.
const haloVariants: Record<OrbState, Variants[string]> = {
  idle: {
    rotate: 360,
    // Indigo. Was `#8b5cf6` — violet, the cloud accent — under a comment
    // saying Indigo. See `Aura.idle`.
    borderColor: 'rgba(99, 102, 241, 0.4)',
    transition: {
      duration: 32, // was 30
      repeat: Infinity,
      ease: 'linear',
    } as const,
  },
  listening: {
    rotate: 360,
    borderColor: 'rgba(34, 211, 238, 0.6)', // Cyan
    transition: {
      duration: 12, // was 10
      repeat: Infinity,
      ease: 'linear',
    } as const,
  },
  thinking: {
    rotate: 360,
    borderColor: 'rgba(168, 85, 247, 0.5)', // Purple
    transition: {
      duration: 8, // was 7.5
      repeat: Infinity,
      ease: 'linear',
    } as const,
  },
  speaking: {
    rotate: 360,
    borderColor: 'rgba(16, 185, 129, 0.7)', // Emerald
    transition: {
      duration: 20,
      repeat: Infinity,
      ease: 'linear',
    } as const,
  },
  // The slowest rotation of any state, and the faintest border. Every other
  // state speeds the halo up to signal work; a swap is waiting, not working.
  swapping: {
    rotate: 360,
    borderColor: 'rgba(148, 163, 184, 0.25)', // Slate
    transition: {
      duration: 40,
      repeat: Infinity,
      ease: 'linear',
    } as const,
  },
};

const Halo = () => {
  const { orbState } = useOrbStore();
  const reduced = useIsReducedMotion();
  const variants = useMemo(
    () => (reduced ? settleAll(haloVariants) : haloVariants),
    [reduced],
  );

  return (
    <motion.div
      className="absolute w-[320px] h-[320px] rounded-full border-2"
      variants={variants}
      animate={orbState}
    />
  );
};

export default Halo;
