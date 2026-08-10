// packages/zaram-engine/runtime/GPUResourceManager.ts

export type ResourceKind = 'geometry' | 'texture' | 'material' | 'buffer';

export interface GPUResourceHandle {
  kind: ResourceKind;
  id: string;
  lastUsed: number;
  sizeBytes: number;
}

export interface GPUResourcePool {
  key: string;
  handle: GPUResourceHandle;
}

export interface GPUResourceStats {
  total: number;
  unused: number;
  memoryBytes: number;
  pools: number;
}

export class GPUResourceManager {
  private readonly resources = new Map<string, GPUResourceHandle>();
  private readonly pools = new Map<string, GPUResourcePool>();
  private readonly lru: string[] = [];
  private memoryBudget = 256 * 1024 * 1024;
  private usedMemory = 0;

  setMemoryBudget(bytes: number): void {
    this.memoryBudget = bytes;
  }

  register(handle: GPUResourceHandle): void {
    this.resources.set(handle.id, handle);
    this.touch(handle.id);
  }

  unregister(id: string): boolean {
    const handle = this.resources.get(id);
    if (!handle) return false;
    this.usedMemory -= handle.sizeBytes;
    this.resources.delete(id);
    this.removeFromLru(id);
    return true;
  }

  touch(id: string): void {
    const handle = this.resources.get(id);
    if (!handle) return;
    handle.lastUsed = performance.now();
    this.removeFromLru(id);
    this.lru.push(id);
  }

  reusePool(key: string): GPUResourceHandle | null {
    const pool = this.pools.get(key);
    if (!pool) return null;
    this.touch(pool.handle.id);
    return pool.handle;
  }

  putInPool(key: string, handle: GPUResourceHandle): void {
    if (this.pools.has(key)) {
      this.pools.get(key)!.handle = handle;
    } else {
      this.pools.set(key, { key, handle });
    }
    this.touch(handle.id);
  }

  disposeUnused(maxBytes?: number): string[] {
    const target = maxBytes ?? this.memoryBudget * 0.2;
    const freed: string[] = [];
    let freedBytes = 0;

    while (freedBytes < target && this.lru.length > 0) {
      const id = this.lru.shift()!;
      const handle = this.resources.get(id);
      if (!handle) continue;
      if (performance.now() - handle.lastUsed > 5000) {
        freed.push(id);
        freedBytes += handle.sizeBytes;
        this.resources.delete(id);
      }
    }

    return freed;
  }

  getStats(): GPUResourceStats {
    let unused = 0;
    const now = performance.now();
    for (const h of this.resources.values()) {
      if (now - h.lastUsed > 2000) unused++;
    }
    return {
      total: this.resources.size,
      unused,
      memoryBytes: this.usedMemory,
      pools: this.pools.size
    };
  }

  allocateBindlessSlot(id: string): number {
    return this.resources.size;
  }

  private removeFromLru(id: string): void {
    const idx = this.lru.indexOf(id);
    if (idx !== -1) this.lru.splice(idx, 1);
  }
}
