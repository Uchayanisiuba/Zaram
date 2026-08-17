import { useMemo } from 'react';
import { motion, type Variants } from 'framer-motion';
import { useOrbStore } from '@/stores';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import type { OrbState } from '@/stores/orbStore';
import { settleAll } from './stillness';

// Total map — see the note in Aura.tsx.
const orbCoreVariants: Record<OrbState, Variants[string]> = {
  idle: {
    scale: [1, 1.02, 1],
    // **Indigo, and this is the one that mattered most.** It was
    // `rgba(139,92,246)` — `#8b5cf6`, violet — which `docs/UI-SPEC.md` assigns
    // to *cloud*. This is the centre of the orb, the brightest thing on the
    // landing, so at rest the indicator whose whole job is to be trusted was
    // lit in the colour that means data left the device. `LivingOrb` was
    // already painting idle indigo around it, so the two disagreed and the
    // wrong one won the middle.
    //
    // This is the argument UI-SPEC already made about the avatar's face,
    // applied to the orb where it was never applied.
    background: 'radial-gradient(circle, rgba(99, 102, 241, 0.8) 0%, rgba(12, 74, 110, 0.8) 100%)',
    transition: {
      // 8s, was 5. `LivingOrb`'s outer breath is 8s and this inner one was 5,
      // so two nested breaths at non-harmonic periods drifted in and out of
      // phase forever. That beat is the single loudest source of the
      // restlessness. Matched, they read as one breath.
      duration: 8,
      repeat: Infinity,
      ease: 'easeInOut',
    } as const,
  },
  listening: {
    scale: 1.14,
    background: 'radial-gradient(circle, rgba(34, 211, 238, 0.9) 0%, rgba(12, 74, 110, 0.9) 100%)',
  },
  thinking: {
    scale: 1.1,
    background: 'radial-gradient(circle, rgba(168, 85, 247, 0.8) 0%, rgba(12, 74, 110, 0.8) 100%)',
  },
  speaking: {
    scale: 1.05,
    background: 'radial-gradient(circle, rgba(16, 185, 129, 0.9) 0%, rgba(12, 74, 110, 0.9) 100%)',
  },
  swapping: {
    scale: [1, 1.03, 1],
    background: 'radial-gradient(circle, rgba(100, 116, 139, 0.55) 0%, rgba(12, 74, 110, 0.7) 100%)',
    transition: {
      duration: 4, // was 3.4 — onto the four-second grid
      repeat: Infinity,
      ease: 'easeInOut',
    } as const,
  },
};

const OrbCore = () => {
  const { orbState } = useOrbStore();
  const reduced = useIsReducedMotion();
  const variants = useMemo(
    () => (reduced ? settleAll(orbCoreVariants) : orbCoreVariants),
    [reduced],
  );

  return (
    <motion.div
      className="absolute w-[160px] h-[160px] rounded-full"
      variants={variants}
      animate={orbState}
    />
  );
};

export default OrbCore;