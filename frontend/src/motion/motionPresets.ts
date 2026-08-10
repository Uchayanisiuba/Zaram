import { Variants } from 'framer-motion';

export const motionPresets: { [key: string]: Variants } = {
  fadeIn: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
  slideIn: {
    initial: { x: '-100%' },
    animate: { x: 0 },
    exit: { x: '-100%' },
  },
  // ... other presets
};