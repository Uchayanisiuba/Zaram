// src/components/LivingOrb/v2/ColorInterpolator.ts

type RGB = [number, number, number];

/**
 * Smoothly interpolates between hex colors based on AI state changes.
 */
export class ColorInterpolator {
  private currentRGB: RGB;
  private targetRGB: RGB;
  private readonly lerpSpeed: number;

  constructor(initialHex: string, lerpSpeed: number = 0.05) {
    this.currentRGB = this.hexToRgb(initialHex);
    this.targetRGB = [...this.currentRGB];
    this.lerpSpeed = lerpSpeed;
  }

  /**
   * Sets a new target color. The interpolator will smoothly glide toward it.
   */
  setTarget(hex: string) {
    this.targetRGB = this.hexToRgb(hex);
  }

  /**
   * Calculates the next step in the color transition.
   * Returns an RGB string ready for Canvas or CSS.
   */
  update(): string {
    for (let i = 0; i < 3; i++) {
      this.currentRGB[i] += (this.targetRGB[i] - this.currentRGB[i]) * this.lerpSpeed;
    }
    return `rgb(${Math.round(this.currentRGB[0])}, ${Math.round(this.currentRGB[1])}, ${Math.round(this.currentRGB[2])})`;
  }

  private hexToRgb(hex: string): RGB {
    const sanitized = hex.replace('#', '');
    const bigint = parseInt(sanitized, 16);
    return [(bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255];
  }
}