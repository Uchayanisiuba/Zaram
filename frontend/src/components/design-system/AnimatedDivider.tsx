import { motion } from 'framer-motion';

const AnimatedDivider = () => {
  return (
    <motion.hr
      initial={{ width: 0 }}
      animate={{ width: '100%' }}
      transition={{ duration: 0.5, ease: 'easeInOut' }}
      className="border-white/10"
    />
  );
};

export default AnimatedDivider;