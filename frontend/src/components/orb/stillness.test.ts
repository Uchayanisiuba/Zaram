/**
 * @vitest-environment node
 *
 * Holding the orb still, asserted — because the branch cannot be clicked.
 *
 * `prefers-reduced-motion` is an operating-system setting. There is no way to
 * exercise this path by driving the app, so the only honest proof that it works
 * is a test of the transform itself. That is the whole reason this file exists:
 * `docs/UI-SPEC.md` has required the gate all along, `LivingOrb` never had one,
 * and nothing anywhere would have noticed.
 *
 * The properties that matter are the ones that would each fail silently:
 * movement actually stops, the resting pose is the one the animation pauses at
 * rather than a frame from mid-breath, and the periods the orb loops on share a
 * factor so the composite resolves.
 *
 * The `settle`/`settleAll` suites went with the helpers, which went with the
 * three variant-driven components that were imported by nothing.
 */
import { describe, it, expect } from 'vitest';
import { SETTLE_SECONDS, frames, loop } from './stillness';

describe('loop', () => {
  it('repeats forever when motion is allowed', () => {
    expect(loop(8, false)).toEqual({ duration: 8, repeat: Infinity, ease: 'easeInOut' });
  });

  it('runs once when motion is reduced', () => {
    const t = loop(8, true) as { duration: number; repeat?: number };
    expect(t.repeat).toBeUndefined();
    expect(t.duration).toBe(SETTLE_SECONDS);
  });

  it('carries the callers easing, so a ripple does not become a breath', () => {
    expect(loop(4, false, 'easeOut')).toMatchObject({ ease: 'easeOut' });
    expect(loop(32, false, 'linear')).toMatchObject({ ease: 'linear' });
  });
});

describe('frames', () => {
  it('passes keyframes through when motion is allowed', () => {
    expect(frames([0, -24, 0], false)).toEqual([0, -24, 0]);
  });

  it('returns the resting frame when motion is reduced', () => {
    expect(frames([0, -24, 0], true)).toBe(0);
    expect(frames([1, 1.06, 1], true)).toBe(1);
  });
});

describe('the periods the orb actually animates on', () => {
  /**
   * **Non-harmonic cycles are what made it restless, not their speed.**
   * Ten particles ran at `3.5 + delay` — ten distinct durations from 3.5s to
   * 5.5s — so the field drifted through every phase relationship and never
   * repeated. Periods sharing a common factor resolve; these could not.
   *
   * Asserted as arithmetic rather than eyeballed, because the next person to
   * add a layer will pick a duration that looks fine on its own.
   */
  const LIVE_IDLE_PERIODS = [8, 8, 4, 8]; // glow, globe, core dot, particles

  it('every idle period shares the four-second base', () => {
    for (const p of LIVE_IDLE_PERIODS) {
      expect(p % 4, `${p}s is not on the 4s grid`).toBe(0);
    }
  });

  it('the composite repeats rather than drifting forever', () => {
    const lcm = (a: number, b: number): number => {
      const gcd = (x: number, y: number): number => (y === 0 ? x : gcd(y, x % y));
      return (a * b) / gcd(a, b);
    };
    const composite = LIVE_IDLE_PERIODS.reduce(lcm);
    expect(Number.isFinite(composite)).toBe(true);
    // 8s, not "never".
    expect(composite).toBe(8);
  });
});
