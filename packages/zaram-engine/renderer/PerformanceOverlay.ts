// packages/zaram-engine/renderer/PerformanceOverlay.ts

export interface PerformanceStats {
  fps: number;
  frameTimeMs: number;
  gpuTimeMs: number;
  cpuTimeMs: number;
  drawCalls: number;
  triangles: number;
  textures: number;
  programs: number;
  memoryBytes: number;
  visibleEmbodiments: number;
  activeParticles: number;
  currentLOD: number;
  activeRegistries: number;
}

export class PerformanceOverlay {
  private frames: number[] = [];
  private gpuTimes: number[] = [];
  private readonly windowSize = 60;
  private lastTime = performance.now();
  private lastFrameTime = 0;
  private lastGPUTime = 0;
  private lastDrawCalls = 0;
  private lastTriangles = 0;
  private lastTextures = 0;
  private lastPrograms = 0;
  private lastMemoryBytes = 0;
  private lastVisibleEmbodiments = 0;
  private lastActiveParticles = 0;
  private lastLOD = 0;
  private lastRegistries = 0;

  public record(frameTimeMs: number, drawCalls: number, triangles: number): void {
    this.frames.push(frameTimeMs);
    if (this.frames.length > this.windowSize) {
      this.frames.shift();
    }
    this.lastFrameTime = frameTimeMs;
    this.lastDrawCalls = drawCalls;
    this.lastTriangles = triangles;
  }

  public recordGPUTime(ms: number): void {
    this.gpuTimes.push(ms);
    if (this.gpuTimes.length > this.windowSize) {
      this.gpuTimes.shift();
    }
    this.lastGPUTime = ms;
  }

  public recordTextures(count: number): void {
    this.lastTextures = count;
  }

  public recordPrograms(count: number): void {
    this.lastPrograms = count;
  }

  public recordMemory(bytes: number): void {
    this.lastMemoryBytes = bytes;
  }

  public recordVisibleEmbodiments(count: number): void {
    this.lastVisibleEmbodiments = count;
  }

  public recordActiveParticles(count: number): void {
    this.lastActiveParticles = count;
  }

  public recordLOD(level: number): void {
    this.lastLOD = level;
  }

  public recordRegistries(count: number): void {
    this.lastRegistries = count;
  }

  public getStats(): PerformanceStats {
    const now = performance.now();
    const elapsed = now - this.lastTime;
    const avgFrame = this.frames.length > 0
      ? this.frames.reduce((a, b) => a + b, 0) / this.frames.length
      : elapsed;
    const avgGPU = this.gpuTimes.length > 0
      ? this.gpuTimes.reduce((a, b) => a + b, 0) / this.gpuTimes.length
      : 0;
    const fps = elapsed > 0 ? 1000 / avgFrame : 0;

    return {
      fps: Math.round(fps),
      frameTimeMs: Math.round(avgFrame * 100) / 100,
      gpuTimeMs: Math.round(avgGPU * 100) / 100,
      cpuTimeMs: Math.round(this.lastFrameTime * 100) / 100,
      drawCalls: this.lastDrawCalls,
      triangles: this.lastTriangles,
      textures: this.lastTextures,
      programs: this.lastPrograms,
      memoryBytes: this.lastMemoryBytes,
      visibleEmbodiments: this.lastVisibleEmbodiments,
      activeParticles: this.lastActiveParticles,
      currentLOD: this.lastLOD,
      activeRegistries: this.lastRegistries,
    };
  }

  public reset(): void {
    this.frames = [];
    this.gpuTimes = [];
    this.lastTime = performance.now();
    this.lastFrameTime = 0;
    this.lastGPUTime = 0;
    this.lastDrawCalls = 0;
    this.lastTriangles = 0;
    this.lastTextures = 0;
    this.lastPrograms = 0;
    this.lastMemoryBytes = 0;
    this.lastVisibleEmbodiments = 0;
    this.lastActiveParticles = 0;
    this.lastLOD = 0;
    this.lastRegistries = 0;
  }
}
