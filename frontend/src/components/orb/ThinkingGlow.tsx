import { motion } from 'framer-motion';

const ThinkingGlow = () => {
  return (
    <motion.div
      className="absolute w-[320px] h-[320px] rounded-full"
      style={{
        background:
          'conic-gradient(from 0deg, #22d3ee, #a855f7, #4f46e5, #22d3ee)',
      }}
      animate={{
        rotate: 360,
      }}
      transition={{
        duration: 4,
        repeat: Infinity,
        ease: 'linear',
      }}
    />
  );
};

export default ThinkingGlow;