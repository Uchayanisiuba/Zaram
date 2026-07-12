// src/components/LivingOrb/v2/AudioEnvelope.ts

/**
 * Converts raw, jittery audio RMS data into a smooth, organic energy value.
 * Uses an ADSR (Attack, Decay, Sustain, Release) envelope follower.
 */
export class AudioEnvelope {
  private smoothedValue: number = 0;
  private readonly attackCoef: number;
  private readonly releaseCoef: number;

  /**
   * @param attack - How quickly the energy spikes (0.0 to 1.0). Higher = faster.
   * @param release - How gracefully the energy settles (0.0 to 1.0). Lower = slower tail.
   */
  constructor(attack: number = 0.6, release: number = 0.08) {
    this.attackCoef = attack;
    this.releaseCoef = release;
  }

  /**
   * Processes the raw audio input and returns the smoothed energy level.
   */
  process(rawInput: number): number {
    // Clamp input between 0 and 1
    const target = Math.max(0, Math.min(1, rawInput));
    
    // Apply different coefficients for attack (spike) vs release (decay)
    const coef = target > this.smoothedValue ? this.attackCoef : this.releaseCoef;
    
    // Exponential smoothing
    this.smoothedValue += (target - this.smoothedValue) * coef;
    
    return this.smoothedValue;
  }

  /**
   * Forcefully resets the envelope (e.g., when the user interrupts the AI).
   */
  reset() {
    this.smoothedValue = 0;
  }
}