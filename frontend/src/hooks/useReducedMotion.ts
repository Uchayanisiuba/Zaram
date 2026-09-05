import { useReducedMotion } from 'framer-motion';

/**
 * Whether this person has asked their computer for less motion.
 *
 * **A definite boolean, not framer's `boolean | null`.** The null means "not
 * measured yet" — it cannot occur once `matchMedia` has run, which in a browser
 * is synchronous on first render, so every caller was carrying a third case
 * that never arrives. Left as-is it forces `?? false` at each call site, and
 * the one that forgets is the one that silently stops gating.
 *
 * Unknown resolves to *not reduced*, matching framer's own default. The
 * alternative — hold everything still until measured — would make the common
 * case flash from static to animating on first paint to serve a state that does
 * not happen here.
 */
export function useIsReducedMotion(): boolean {
  return useReducedMotion() === true;
}
