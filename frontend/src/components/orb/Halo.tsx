import { motion } from 'framer-motion';
import { useOrbStore } from '@/stores';

const haloVariants = {
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
