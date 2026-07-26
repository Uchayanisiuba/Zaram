// packages/zaram-engine/registries/AssetRegistry.ts
import { AssetDescriptor } from '../types/AssetDescriptor';

export type AssetLoadState = 'registered' | 'loading' | 'ready' | 'error';

export class AssetRegistry {
  private readonly items = new Map<string, AssetDescriptor>();
  private readonly loadStates = new Map<string, AssetLoadState>();
  private warnOnDuplicate = true;

  register(descriptor: AssetDescriptor): void {
    if (this.warnOnDuplicate && this.items.has(descriptor.id)) {
      console.warn(`[AssetRegistry] Duplicate asset registration: "${descriptor.id}" — overwriting existing entry`);
    }
    this.items.set(descriptor.id, descriptor);
    if (!this.loadStates.has(descriptor.id)) {
      this.loadStates.set(descriptor.id, 'registered');
    }
  }

  unregister(id: string): boolean {
    this.loadStates.delete(id);
    return this.items.delete(id);
  }

  get(id: string): AssetDescriptor | undefined {
    return this.items.get(id);
  }

  getOrError(id: string): AssetDescriptor {
    const item = this.items.get(id);
    if (!item) {
      throw new Error(`[AssetRegistry] Asset not found: "${id}"`);
    }
    return item;
  }

  list(): AssetDescriptor[] {
    return Array.from(this.items.values());
  }

  has(id: string): boolean {
    return this.items.has(id);
  }

  clear(): void {
    this.items.clear();
    this.loadStates.clear();
  }

  markLoading(id: string): void {
    this.loadStates.set(id, 'loading');
  }

  markReady(id: string): void {
    this.loadStates.set(id, 'ready');
  }

  markError(id: string): void {
    this.loadStates.set(id, 'error');
  }

  getLoadState(id: string): AssetLoadState | undefined {
    return this.loadStates.get(id);
  }

  isReady(id: string): boolean {
    return this.loadStates.get(id) === 'ready';
  }

  setWarnOnDuplicate(warn: boolean): void {
    this.warnOnDuplicate = warn;
  }

  validate(): string[] {
    const errors: string[] = [];
    for (const [id, desc] of this.items) {
      if (!desc.source) {
        errors.push(`Asset "${id}" has no source URL`);
      }
      if (desc.boundingSphere && desc.boundingSphere.radius <= 0) {
        errors.push(`Asset "${id}" has invalid bounding sphere radius`);
      }
    }
    return errors;
  }
}
