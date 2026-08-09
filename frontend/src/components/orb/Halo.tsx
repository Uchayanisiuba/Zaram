import { motion, type Variants } from 'framer-motion';
import { useOrbStore } from '@/stores';
import type { OrbState } from '@/stores/orbStore';

// Total map — see the note in Aura.tsx.
const haloVariants: Record<OrbState, Variants[string]> = {
  idle: {
    rotate: 360,
    borderColor: 'rgba(139, 92, 246, 0.4)', // Indigo
    transition: {
      duration: 30,
      repeat: Infinity,
      ease: 'linear',
    } as const,
  },
  listening: {
    rotate: 360,
    borderColor: 'rgba(34, 211, 238, 0.6)', // Cyan
    transition: {
      duration: 10,
      repeat: Infinity,
      ease: 'linear',
    } as const,
  },
  thinking: {
    rotate: 360,
    borderColor: 'rgba(168, 85, 247, 0.5)', // Purple
    transition: {
      duration: 7.5,
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

  return (
    <motion.div
      className="absolute w-[320px] h-[320px] rounded-full border-2"
      variants={haloVariants}
      animate={orbState}
    />
  );
};

export default Halo;
