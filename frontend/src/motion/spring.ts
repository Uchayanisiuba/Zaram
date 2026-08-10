import type { SpringOptions } from 'framer-motion';

export const springPreset: SpringOptions = {
  stiffness: 300,
  damping: 30,
};

export const customSpring = (stiffness: number, damping: number): SpringOptions =>
  ({ stiffness, damping });