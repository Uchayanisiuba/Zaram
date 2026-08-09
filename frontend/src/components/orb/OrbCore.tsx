import { motion, type Variants } from 'framer-motion';
import { useOrbStore } from '@/stores';
import type { OrbState } from '@/stores/orbStore';

// Total map — see the note in Aura.tsx.
const orbCoreVariants: Record<OrbState, Variants[string]> = {
  idle: {
    scale: [1, 1.02, 1],
    background: 'radial-gradient(circle, rgba(139, 92, 246, 0.8) 0%, rgba(12, 74, 110, 0.8) 100%)',
    transition: {
      duration: 5,
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
      duration: 3.4,
      repeat: Infinity,
      ease: 'easeInOut',
    } as const,
  },
};

const OrbCore = () => {
  const { orbState } = useOrbStore();

  return (
    <motion.div
      className="absolute w-[160px] h-[160px] rounded-full"
      variants={orbCoreVariants}
      animate={orbState}
    />
  );
};

export default OrbCore;