import { motion } from 'framer-motion';
import { useOrbStore } from '@/stores';

const orbCoreVariants = {
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