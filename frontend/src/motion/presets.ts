/**
 * =================================================================================================
 * ZARAM MOTION PRESETS
 *
 * This file contains reusable animation variants for Framer Motion.
 * Centralizing motion logic ensures a consistent feel across the application and simplifies
 * component implementation.
 *
 * Each preset is a standard Framer Motion `variants` object.
 * =================================================================================================
 */

import { Variants } from 'framer-motion';

/**
 * A simple fade-in/out transition.
 */
export const fade: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { duration: 0.3, ease: 'easeInOut' } },
  exit: { opacity: 0, transition: { duration: 0.2, ease: 'easeInOut' } },
};

/**
 * A fade combined with a slight scale-up for emphasis.
 */
export const fadeScale: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.3, ease: 'easeOut' } },
  exit: { opacity: 0, scale: 0.95, transition: { duration: 0.2, ease: 'easeIn' } },
};

/**
 * A "lift" effect for hover interactions, raising and scaling an element.
 */
export const lift: Variants = {
  initial: { scale: 1, y: 0, boxShadow: 'var(--shadow-md)' },
  hover: {
    scale: 1.03,
    y: -4,
    boxShadow: 'var(--shadow-xl)',
    transition: { duration: 0.2, ease: 'easeOut' },
  },
};

/**
 * A slide-in/out from the bottom, often used for panels or docks.
 */
export const slideInBottom: Variants = {
  hidden: { y: '100%', opacity: 0 },
  visible: { y: 0, opacity: 1, transition: { duration: 0.4, ease: [0.25, 1, 0.5, 1] } },
  exit: { y: '100%', opacity: 0, transition: { duration: 0.3, ease: [0.5, 0, 0.75, 0] } },
};

/**
 * A reveal animation for panels, sliding in from the side.
 */
export const panelReveal: Variants = {
  hidden: { x: '-100%', opacity: 0 },
  visible: { x: 0, opacity: 1, transition: { duration: 0.5, ease: [0.25, 1, 0.5, 1] } },
  exit: { x: '-100%', opacity: 0, transition: { duration: 0.4, ease: [0.5, 0, 0.75, 0] } },
};

// =================================================================================================
// ORB-SPECIFIC ANIMATIONS
// These are more complex and tailored to the Living Orb's specification.
// =================================================================================================

/**
 * The Orb's foundational "breathing" animation for the Idle state.
 * A slow, gentle pulse to show the AI is alive.
 */
export const orbBreathe: Variants = {
  animate: {
    scale: [1, 1.02, 1],
    opacity: [0.8, 1, 0.8],
    transition: {
      duration: 6,
      ease: 'easeInOut',
      repeat: Infinity,
    },
  },
};

/**
 * A faster, more pronounced pulse for when the Orb is speaking or active.
 */
export const orbPulse: Variants = {
  animate: (i: number = 0) => ({
    scale: [1, 1.1, 1],
    opacity: [0.7, 1, 0.7],
    transition: {
      duration: 1.5,
      ease: 'easeInOut',
      repeat: Infinity,
      delay: i * 0.2,
    },
  }),
};

/**
 * A ripple effect that radiates outwards from the Orb's core.
 */
export const orbRipple: Variants = {
  initial: { scale: 0, opacity: 1 },
  animate: {
    scale: 4,
    opacity: 0,
    transition: {
      duration: 2,
      ease: 'easeOut',
      repeat: Infinity,
    },
  },
};