import { motion } from '../theme';

export const transitions = {
  default: {
    duration: motion.duration.normal,
    ease: motion.easing.inOut,
  },
  fast: {
    duration: motion.duration.fast,
    ease: motion.easing.out,
  },
  slow: {
    duration: motion.duration.slow,
    ease: motion.easing.inOut,
  },
};