// packages/zaram-engine/particle/ParticleRuntime.ts

export interface Particle {
  position: [number, number, number];
  velocity: [number, number, number];
  life: number;
  maxLife: number;
  size: number;
  color: [number, number, number];
}

export interface ParticleEmitterDesc {
  id: string;
  position: [number, number, number];
  rate: number;
  lifetime: [number, number];
  speed: [number, number];
  size: [number, number];
  color: [number, number, number];
  gpu?: boolean;
  capacity?: number;
  gravity?: number;
  drag?: number;
}

export interface GPUParticleData {
  positions: Float32Array;
  velocities: Float32Array;
  lifetimes: Float32Array;
  sizes: Float32Array;
  colors: Float32Array;
  count: number;
  capacity: number;
}

export interface ParticleStats {
  total: number;
  active: number;
  emitters: number;
  gpuParticles: number;
  cpuParticles: number;
  memoryBytes: number;
}

const DEFAULT_MAX_PARTICLES = 10000;
const DEFAULT_MAX_SPAWNS_PER_FRAME = 500;
const POOL_GROWTH_FACTOR = 1.5;

export class ParticleRuntime {
  private pool: Particle[] = [];
  private freeList: number[] = [];
  private active: Set<number> = new Set();
  private particleEmitterMap: Map<number, string> = new Map();

  private gpuBuffer: GPUParticleData | null = null;
  private gpuCapacity = 0;

  private emitters: Map<string, ParticleEmitterDesc> = new Map();
  private accumulator = 0;

  private stats: ParticleStats = {
    total: 0,
    active: 0,
    emitters: 0,
    gpuParticles: 0,
    cpuParticles: 0,
    memoryBytes: 0,
  };

  private maxParticles: number = DEFAULT_MAX_PARTICLES;
  private maxSpawnsPerFrame: number = DEFAULT_MAX_SPAWNS_PER_FRAME;
  private gpuEnabled: boolean = true;
  private gpuParticleCount = 0;

  registerEmitter(emitter: ParticleEmitterDesc): void {
    this.emitters.set(emitter.id, emitter);
    this.stats.emitters = this.emitters.size;
  }

  unregisterEmitter(id: string): boolean {
    const removed = this.emitters.delete(id);
    if (removed) {
      for (const [idx, eid] of this.particleEmitterMap) {
        if (eid === id) {
          this.freeParticle(idx);
        }
      }
      this.stats.emitters = this.emitters.size;
    }
    return removed;
  }

  setMaxParticles(max: number): void {
    this.maxParticles = max;
    this.ensurePoolCapacity(max);
  }

  setMaxSpawnsPerFrame(max: number): void {
    this.maxSpawnsPerFrame = max;
  }

  setGPUEnabled(enabled: boolean): void {
    this.gpuEnabled = enabled;
    if (enabled && !this.gpuBuffer) {
      this.initGPUBuffer(this.maxParticles);
    }
  }

  update(dt: number): Particle[] {
    this.accumulator += dt;

    const spawnCount = Math.min(
      Math.floor(this.accumulator * this.getTotalRate()),
      this.maxSpawnsPerFrame
    );
    this.accumulator -= spawnCount / this.getTotalRate();

    let spawnsThisFrame = 0;
    for (const emitter of this.emitters.values()) {
      if (spawnsThisFrame >= spawnCount) break;

      const emitterSpawns = Math.min(
        Math.floor(dt * emitter.rate),
        spawnCount - spawnsThisFrame
      );
      spawnsThisFrame += emitterSpawns;

      for (let i = 0; i < emitterSpawns; i++) {
        if (this.active.size >= this.maxParticles) break;
        this.spawnParticle(emitter);
      }
    }

    const activeParticles: Particle[] = [];
    for (const idx of this.active) {
      const p = this.pool[idx];
      p.life -= dt;

      if (p.life <= 0) {
        this.freeParticle(idx);
        continue;
      }

      p.position[0] += p.velocity[0] * dt;
      p.position[1] += p.velocity[1] * dt;
      p.position[2] += p.velocity[2] * dt;

      const emitter = this.emitters.get(this.particleEmitterMap.get(idx) ?? '');
      if (emitter) {
        if (emitter.drag !== undefined) {
          p.velocity[0] *= emitter.drag;
          p.velocity[1] *= emitter.drag;
          p.velocity[2] *= emitter.drag;
        }
        if (emitter.gravity !== undefined) {
          p.velocity[1] += emitter.gravity * dt;
        }
      }

      activeParticles.push(p);
    }

    this.updateGPUBuffer(activeParticles);
    this.updateStats();

    return activeParticles;
  }

  getParticles(): Particle[] {
    const result: Particle[] = [];
    for (const idx of this.active) {
      result.push(this.pool[idx]);
    }
    return result;
  }

  getGPUData(): GPUParticleData | null {
    if (!this.gpuEnabled || !this.gpuBuffer) return null;
    return this.gpuBuffer;
  }

  getStats(): ParticleStats {
    return { ...this.stats };
  }

  private getTotalRate(): number {
    let total = 0;
    for (const e of this.emitters.values()) {
      total += e.rate;
    }
    return total;
  }

  private spawnParticle(emitter: ParticleEmitterDesc): void {
    const idx = this.acquireParticle();
    if (idx === -1) return;

    const p = this.pool[idx];
    p.position[0] = emitter.position[0];
    p.position[1] = emitter.position[1];
    p.position[2] = emitter.position[2];

    const speed = emitter.speed[0] + Math.random() * (emitter.speed[1] - emitter.speed[0]);
    p.velocity[0] = (Math.random() - 0.5) * speed;
    p.velocity[1] = Math.random() * speed;
    p.velocity[2] = (Math.random() - 0.5) * speed;

    p.maxLife = emitter.lifetime[0] + Math.random() * (emitter.lifetime[1] - emitter.lifetime[0]);
    p.life = p.maxLife;
    p.size = emitter.size[0] + Math.random() * (emitter.size[1] - emitter.size[0]);
    p.color[0] = emitter.color[0];
    p.color[1] = emitter.color[1];
    p.color[2] = emitter.color[2];

    this.active.add(idx);
    this.particleEmitterMap.set(idx, emitter.id);
  }

  private acquireParticle(): number {
    if (this.freeList.length > 0) {
      return this.freeList.pop()!;
    }

    if (this.pool.length < this.maxParticles) {
      const idx = this.pool.length;
      this.pool.push({
        position: [0, 0, 0],
        velocity: [0, 0, 0],
        life: 0,
        maxLife: 0,
        size: 0,
        color: [0, 0, 0],
      });
      return idx;
    }

    return -1;
  }

  private freeParticle(idx: number): void {
    this.active.delete(idx);
    this.particleEmitterMap.delete(idx);
    this.freeList.push(idx);
  }

  private ensurePoolCapacity(capacity: number): void {
    while (this.pool.length < capacity) {
      this.pool.push({
        position: [0, 0, 0],
        velocity: [0, 0, 0],
        life: 0,
        maxLife: 0,
        size: 0,
        color: [0, 0, 0],
      });
    }
  }

  private initGPUBuffer(capacity: number): void {
    this.gpuCapacity = capacity;
    this.gpuBuffer = {
      positions: new Float32Array(capacity * 3),
      velocities: new Float32Array(capacity * 3),
      lifetimes: new Float32Array(capacity * 2),
      sizes: new Float32Array(capacity),
      colors: new Float32Array(capacity * 3),
      count: 0,
      capacity,
    };
  }

  private updateGPUBuffer(activeParticles: Particle[]): void {
    if (!this.gpuEnabled || !this.gpuBuffer) {
      this.gpuParticleCount = 0;
      return;
    }

    const count = Math.min(activeParticles.length, this.gpuCapacity);
    this.gpuParticleCount = count;

    for (let i = 0; i < count; i++) {
      const p = activeParticles[i];
      const i3 = i * 3;
      const i2 = i * 2;

      this.gpuBuffer.positions[i3] = p.position[0];
      this.gpuBuffer.positions[i3 + 1] = p.position[1];
      this.gpuBuffer.positions[i3 + 2] = p.position[2];

      this.gpuBuffer.velocities[i3] = p.velocity[0];
      this.gpuBuffer.velocities[i3 + 1] = p.velocity[1];
      this.gpuBuffer.velocities[i3 + 2] = p.velocity[2];

      this.gpuBuffer.lifetimes[i2] = p.life;
      this.gpuBuffer.lifetimes[i2 + 1] = p.maxLife;

      this.gpuBuffer.sizes[i] = p.size;

      this.gpuBuffer.colors[i3] = p.color[0];
      this.gpuBuffer.colors[i3 + 1] = p.color[1];
      this.gpuBuffer.colors[i3 + 2] = p.color[2];
    }

    this.gpuBuffer.count = count;
  }

  private updateStats(): void {
    this.stats.total = this.pool.length;
    this.stats.active = this.active.size;
    this.stats.emitters = this.emitters.size;
    this.stats.cpuParticles = this.gpuEnabled ? 0 : this.active.size;
    this.stats.gpuParticles = this.gpuEnabled ? this.gpuParticleCount : 0;
    this.stats.memoryBytes = this.pool.length * 44 + (this.gpuBuffer ? this.gpuCapacity * 44 : 0);
  }

  dispose(): void {
    this.pool = [];
    this.freeList = [];
    this.active.clear();
    this.particleEmitterMap.clear();
    this.emitters.clear();
    this.gpuBuffer = null;
    this.accumulator = 0;
    this.stats = {
      total: 0,
      active: 0,
      emitters: 0,
      gpuParticles: 0,
      cpuParticles: 0,
      memoryBytes: 0,
    };
  }
}
