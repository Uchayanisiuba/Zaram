// packages/zaram-engine/runtime/RhythmEngine.ts
import { EmotionDimensions } from './EmotionEngine';
import { TargetInfluences } from './StateAdapter';
import { perlinNoise } from '../utils/math';

export interface RhythmData {
  breathingOffset: number;
  microOscillation: number;
  focusDrift: number;
  energyPulse: number;
}

export class RhythmEngine {
  private timeElapsed: number = 0;

  /**
   * Generates non-repeating biological variance driven by time and current emotional state.
   */
  public compute(influences: TargetInfluences, emotions: EmotionDimensions, dt: number): RhythmData {
    this.timeElapsed += dt;

    // Breathing cadence shifts based on calmness and energy
    const breathSpeed = 1.0 + (influences.activity * 1.5) - (emotions.calmness * 0.5);
    const breathingOffset = Math.sin(this.timeElapsed * breathSpeed) * 0.5 + 0.5;

    // Micro oscillations increase with energy and focus, using noise to avoid looping
    const microOscillation = perlinNoise(this.timeElapsed * 3.0) * influences.energy * 0.1;

    // Focus drift wanders slowly, decreasing as absolute focus increases
    const driftSpeed = 0.5 * (1.0 - influences.focus);
    const focusDrift = perlinNoise(this.timeElapsed * driftSpeed) * (1.0 - influences.focus) * 0.2;

    // Energy pulse spikes occasionally based on playfulness and activity
    const pulseTrigger = perlinNoise(this.timeElapsed * 5.0);
    const energyPulse = pulseTrigger > 0.8 ? (pulseTrigger - 0.8) * emotions.playfulness : 0;

    return {
      breathingOffset,
      microOscillation,
      focusDrift,
      energyPulse
    };
  }
}