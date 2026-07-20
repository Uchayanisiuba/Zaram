// packages/zaram-engine/runtime/InfluenceEngine.ts
import { TargetInfluences } from './StateAdapter';
import { lerp } from '../utils/interpolation';

export class InfluenceEngine {
  private current: TargetInfluences = {
    presence: 0.4,
    energy: 0.3,
    focus: 0.2,
    activity: 0.2,
  };

  /**
   * Blends current influences towards target influences over delta time.
   * Uses an Exponential Moving Average (EMA) approach for organic easing.
   */
  public blend(targets: TargetInfluences, dt: number): TargetInfluences {
    // Smoothing factor scales with delta time to ensure framerate independence
    const smoothing = 1.0 - Math.exp(-5.0 * dt);

    this.current.presence = lerp(this.current.presence, targets.presence, smoothing);
    this.current.energy = lerp(this.current.energy, targets.energy, smoothing);
    this.current.focus = lerp(this.current.focus, targets.focus, smoothing);
    this.current.activity = lerp(this.current.activity, targets.activity, smoothing);

    return { ...this.current };
  }
}