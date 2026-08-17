import { useMemo } from 'react';
import { motion, type Variants } from 'framer-motion';
import { useOrbStore } from '@/stores';
import { useIsReducedMotion } from '@/hooks/useReducedMotion';
import type { OrbState } from '@/stores/orbStore';
import { settleAll } from './stillness';

// `Record<OrbState, …>`, so a new orb state fails the build here rather than
// animating to nothing at runtime. framer-motion resolves an unknown variant
// name to no animation and reports nothing.
const auraVariants: Record<OrbState, Variants[string]> = {
  idle: {
    scale: [1, 1.05, 1],
    // Indigo, and it now is. The comment said Indigo and the value was
    // `#8b5cf6` — violet, which `docs/UI-SPEC.md` assigns to **cloud**. Three
    // components carried that same mislabelled pair, so at rest the orb was
    // tinted with the one colour that means "data left the device". Idle is
    // the state where nothing has.
    backgroundColor: 'rgba(99, 102, 241, 0.2)',
    transition: {
      duration: 4,
      repeat: Infinity,
      ease: 'easeInOut',
    } as const,
  },
  listening: {
    scale: 1.14,
    backgroundColor: 'rgba(34, 211, 238, 0.3)', // Cyan
  },
  thinking: {
    scale: 1.1,
    backgroundColor: 'rgba(168, 85, 247, 0.25)', // Purple
  },
  speaking: {
    scale: 1.2,
    backgroundColor: 'rgba(16, 185, 129, 0.3)', // Emerald
  },
  swapping: {
    scale: [1, 1.03, 1],
    backgroundColor: 'rgba(100, 116, 139, 0.18)', // Slate — resident to neither
    transition: {
      // 4s, was 3.4. Every looping period in the orb is now a whole multiple of
      // four seconds. Cycles that share no common factor never re-align, so the
      // composite of ten of them never repeats and the eye keeps finding fresh
      // change — which is what reads as restless even when each animation is
      // individually slow.
      duration: 4,
      repeat: Infinity,
      ease: 'easeInOut',
    } as const,
  },
};

const Aura = () => {
  const { orbState } = useOrbStore();
  const reduced = useIsReducedMotion();
  const variants = useMemo(
    () => (reduced ? settleAll(auraVariants) : auraVariants),
    [reduced],
  );

  return (
    <motion.div
      className="absolute w-[320px] h-[320px] rounded-full blur-2xl"
      variants={variants}
      animate={orbState}
    />
  );
};

export default Aura;