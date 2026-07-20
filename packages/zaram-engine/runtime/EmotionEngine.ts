// packages/zaram-engine/runtime/EmotionEngine.ts
import { TargetInfluences } from './StateAdapter';
import { lerp } from '../utils/interpolation';

export interface EmotionDimensions {
  calmness: number;
  confidence: number;
  curiosity: number;
  warmth: number;
  empathy: number;
  playfulness: number;
}

export class EmotionEngine {
  private currentDimensions: EmotionDimensions = {
    calmness: 0.8,
    confidence: 0.6,
    curiosity: 0.5,
    warmth: 0.7,
    empathy: 0.6,
    playfulness: 0.2
  };

  /**
   * Derives and smooths emotional dimensions based on current active influences.
   */
  public compute(influences: TargetInfluences, dt: number): EmotionDimensions {
    const smoothing = 1.0 - Math.exp(-2.5 * dt); // Slower, more deliberate transitions

    // Derive target emotional states from physical influences
    const targetCalmness = 1.0 - influences.activity * 0.8;
    const targetConfidence = influences.presence * 0.9;
    const targetCuriosity = influences.focus * 0.85;
    
    // Warmth, empathy, and playfulness are modulated subtly by energy and presence
    const targetWarmth = 0.5 + (influences.presence * 0.4);
    const targetEmpathy = 0.6 + (influences.focus * 0.3);
    const targetPlayfulness = Math.max(0, influences.energy - 0.5) * 0.8;

    this.currentDimensions.calmness = lerp(this.currentDimensions.calmness, targetCalmness, smoothing);
    this.currentDimensions.confidence = lerp(this.currentDimensions.confidence, targetConfidence, smoothing);
    this.currentDimensions.curiosity = lerp(this.currentDimensions.curiosity, targetCuriosity, smoothing);
    this.currentDimensions.warmth = lerp(this.currentDimensions.warmth, targetWarmth, smoothing);
    this.currentDimensions.empathy = lerp(this.currentDimensions.empathy, targetEmpathy, smoothing);
    this.currentDimensions.playfulness = lerp(this.currentDimensions.playfulness, targetPlayfulness, smoothing);

    return { ...this.currentDimensions };
  }
}