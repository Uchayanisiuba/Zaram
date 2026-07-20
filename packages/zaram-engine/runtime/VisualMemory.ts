// packages/zaram-engine/runtime/VisualMemory.ts

export class VisualMemory {
  private readonly signatureSeed: number;

  constructor(installationId: string) {
    this.signatureSeed = this.hashString(installationId);
  }

  /**
   * Returns the persistent visual signature for this specific Zaram instance.
   */
  public getIdentitySeed(): number {
    return this.signatureSeed;
  }

  /**
   * Simple deterministic hash function to generate a stable seed from a UUID.
   */
  private hashString(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    // Normalize to a 0.0 - 1.0 float seed
    return Math.abs(hash) / 2147483647; 
  }
}