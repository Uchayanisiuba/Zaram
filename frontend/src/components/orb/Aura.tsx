import { motion } from 'framer-motion';
import { useOrbStore } from '@/stores';

const auraVariants = {
  idle: {
    scale: [1, 1.05, 1],
    backgroundColor: 'rgba(139, 92, 246, 0.2)', // Indigo
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
};

const Aura = () => {
  const { orbState } = useOrbStore();

  return (
    <motion.div
      className="absolute w-[320px] h-[320px] rounded-full blur-2xl"
      variants={auraVariants}
      animate={orbState}
    />
  );
};

export default Aura;