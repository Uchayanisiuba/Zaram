// packages/zaram-engine/registries/EmbodimentRegistry.ts
import { AssetDescriptor } from '../types/AssetDescriptor';
import { MaterialDescriptor } from '../types/MaterialDescriptor';
import { ShaderDescriptor } from '../types/ShaderDescriptor';
import { LODDescriptor } from '../types/LODDescriptor';

export interface Embodiment {
  id: string;
  assetId: string;
  materialId: string;
  shaderId: string;
  lodId: string;
  transform?: {
    position?: [number, number, number];
    rotation?: [number, number, number];
    scale?: [number, number, number];
  };
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export class EmbodimentRegistry {
  private readonly items = new Map<string, Embodiment>();
  private warnOnDuplicate = true;

  register(embodiment: Embodiment): void {
    if (this.warnOnDuplicate && this.items.has(embodiment.id)) {
      console.warn(`[EmbodimentRegistry] Duplicate embodiment registration: "${embodiment.id}" — overwriting existing entry`);
    }
    this.items.set(embodiment.id, embodiment);
  }

  unregister(id: string): boolean {
    return this.items.delete(id);
  }

  get(id: string): Embodiment | undefined {
    return this.items.get(id);
  }

  getOrError(id: string): Embodiment {
    const item = this.items.get(id);
    if (!item) {
      throw new Error(`[EmbodimentRegistry] Embodiment not found: "${id}"`);
    }
    return item;
  }

  list(): Embodiment[] {
    return Array.from(this.items.values());
  }

  has(id: string): boolean {
    return this.items.has(id);
  }

  clear(): void {
    this.items.clear();
  }

  setWarnOnDuplicate(warn: boolean): void {
    this.warnOnDuplicate = warn;
  }

  validate(
    assetRegistry: { has(id: string): boolean },
    materialRegistry: { has(id: string): boolean },
    shaderRegistry: { has(id: string): boolean },
    lodRegistry?: { has(id: string): boolean }
  ): string[] {
    const errors: string[] = [];
    for (const [id, emb] of this.items) {
      if (!assetRegistry.has(emb.assetId)) {
        errors.push(`Embodiment "${id}" references missing asset: "${emb.assetId}"`);
      }
      if (!materialRegistry.has(emb.materialId)) {
        errors.push(`Embodiment "${id}" references missing material: "${emb.materialId}"`);
      }
      if (!shaderRegistry.has(emb.shaderId)) {
        errors.push(`Embodiment "${id}" references missing shader: "${emb.shaderId}"`);
      }
      if (lodRegistry && !lodRegistry.has(emb.lodId)) {
        errors.push(`Embodiment "${id}" references missing LOD: "${emb.lodId}"`);
      }
    }
    return errors;
  }
}
