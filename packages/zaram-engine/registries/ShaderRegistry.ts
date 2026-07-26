// packages/zaram-engine/registries/ShaderRegistry.ts
import { ShaderDescriptor } from '../types/ShaderDescriptor';

export class ShaderRegistry {
  private readonly items = new Map<string, ShaderDescriptor>();
  private readonly hashIndex = new Map<string, string>();
  private warnOnDuplicate = true;

  register(descriptor: ShaderDescriptor): void {
    const hash = this.computeHash(descriptor);
    const existingId = this.hashIndex.get(hash);
    if (existingId && existingId !== descriptor.id) {
      if (this.warnOnDuplicate) {
        console.warn(`[ShaderRegistry] Duplicate shader (same vertex+fragment): "${descriptor.id}" matches "${existingId}"`);
      }
      return;
    }
    if (this.warnOnDuplicate && this.items.has(descriptor.id)) {
      console.warn(`[ShaderRegistry] Duplicate shader registration: "${descriptor.id}" — overwriting existing entry`);
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

  get(id: string): ShaderDescriptor | undefined {
    return this.items.get(id);
  }

  getOrError(id: string): ShaderDescriptor {
    const item = this.items.get(id);
    if (!item) {
      throw new Error(`[ShaderRegistry] Shader not found: "${id}"`);
    }
    return item;
  }

  list(): ShaderDescriptor[] {
    return Array.from(this.items.values());
  }

  has(id: string): boolean {
    return this.items.has(id);
  }

  clear(): void {
    this.items.clear();
    this.hashIndex.clear();
  }

  getOrCreate(descriptor: ShaderDescriptor): ShaderDescriptor {
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

  private computeHash(descriptor: ShaderDescriptor): string {
    const parts: string[] = [descriptor.vertex, descriptor.fragment];
    if (descriptor.defines) {
      parts.push(...descriptor.defines);
    }
    return parts.join('\n');
  }
}
