// packages/zaram-engine/registries/MaterialRegistry.ts
import { MaterialDescriptor } from '../types/MaterialDescriptor';

export class MaterialRegistry {
  private readonly items = new Map<string, MaterialDescriptor>();
  private readonly hashIndex = new Map<string, string>();
  private warnOnDuplicate = true;

  register(descriptor: MaterialDescriptor): void {
    const hash = this.computeHash(descriptor);
    const existingId = this.hashIndex.get(hash);
    if (existingId && existingId !== descriptor.id) {
      if (this.warnOnDuplicate) {
        console.warn(`[MaterialRegistry] Duplicate material (same shader+uniforms): "${descriptor.id}" matches "${existingId}"`);
      }
      return;
    }
    if (this.warnOnDuplicate && this.items.has(descriptor.id)) {
      console.warn(`[MaterialRegistry] Duplicate material registration: "${descriptor.id}" — overwriting existing entry`);
    }
    this.items.set(descriptor.id, descriptor);
    this.hashIndex.set(hash, descriptor.id);
  }

  unregister(id: string): boolean {
    const desc = this.items.get(id);
    if (desc) {
      this.hashIndex.delete(this.computeHash(desc));
    }
    return this.items.delete(id);
  }

  get(id: string): MaterialDescriptor | undefined {
    return this.items.get(id);
  }

  getOrError(id: string): MaterialDescriptor {
    const item = this.items.get(id);
    if (!item) {
      throw new Error(`[MaterialRegistry] Material not found: "${id}"`);
    }
    return item;
  }

  list(): MaterialDescriptor[] {
    return Array.from(this.items.values());
  }

  has(id: string): boolean {
    return this.items.has(id);
  }

  clear(): void {
    this.items.clear();
    this.hashIndex.clear();
  }

  getOrCreate(descriptor: MaterialDescriptor): MaterialDescriptor {
    const hash = this.computeHash(descriptor);
    const existingId = this.hashIndex.get(hash);
    if (existingId) {
      return this.items.get(existingId)!;
    }
    this.register(descriptor);
    return descriptor;
  }

  setWarnOnDuplicate(warn: boolean): void {
    this.warnOnDuplicate = warn;
  }

  private computeHash(descriptor: MaterialDescriptor): string {
    const parts: string[] = [descriptor.shaderId];
    if (descriptor.uniforms) {
      for (const [key, val] of Object.entries(descriptor.uniforms)) {
        parts.push(`${key}:${JSON.stringify(val)}`);
      }
    }
    return parts.join('|');
  }
}
