import { AssetDescriptor, AssetType } from '../types/AssetDescriptor';
import { MaterialDescriptor } from '../types/MaterialDescriptor';
import { ShaderDescriptor } from '../types/ShaderDescriptor';
import { LODDescriptor, LODLevel } from '../types/LODDescriptor';
import { FrameState } from '../types/FrameState';

export type AssetLoadState = 'registered' | 'loading' | 'ready' | 'error';

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

export interface UnifiedRegistryConfig {
  warnOnDuplicate?: boolean;
  autoDisposeUnused?: boolean;
  maxUnusedAge?: number;
}

export class UnifiedRegistry {
  private assets = new Map<string, AssetDescriptor>();
  private assetLoadStates = new Map<string, AssetLoadState>();
  private materials = new Map<string, MaterialDescriptor>();
  private materialHashIndex = new Map<string, string>();
  private shaders = new Map<string, ShaderDescriptor>();
  private shaderHashIndex = new Map<string, string>();
  private embodiments = new Map<string, Embodiment>();
  private lods = new Map<string, LODDescriptor>();
  private config: Required<UnifiedRegistryConfig>;

  constructor(config: UnifiedRegistryConfig = {}) {
    this.config = {
      warnOnDuplicate: config.warnOnDuplicate ?? true,
      autoDisposeUnused: config.autoDisposeUnused ?? true,
      maxUnusedAge: config.maxUnusedAge ?? 30000,
    };
  }

  registerAsset(descriptor: AssetDescriptor): void {
    if (this.config.warnOnDuplicate && this.assets.has(descriptor.id)) {
      console.warn(`[UnifiedRegistry] Duplicate asset registration: "${descriptor.id}" — overwriting`);
    }
    this.assets.set(descriptor.id, descriptor);
    if (!this.assetLoadStates.has(descriptor.id)) {
      this.assetLoadStates.set(descriptor.id, 'registered');
    }
  }

  unregisterAsset(id: string): boolean {
    this.assetLoadStates.delete(id);
    return this.assets.delete(id);
  }

  getAsset(id: string): AssetDescriptor | undefined {
    return this.assets.get(id);
  }

  getAssetOrError(id: string): AssetDescriptor {
    const item = this.assets.get(id);
    if (!item) throw new Error(`[UnifiedRegistry] Asset not found: "${id}"`);
    return item;
  }

  listAssets(): AssetDescriptor[] {
    return Array.from(this.assets.values());
  }

  hasAsset(id: string): boolean {
    return this.assets.has(id);
  }

  markAssetLoading(id: string): void {
    this.assetLoadStates.set(id, 'loading');
  }

  markAssetReady(id: string): void {
    this.assetLoadStates.set(id, 'ready');
  }

  markAssetError(id: string): void {
    this.assetLoadStates.set(id, 'error');
  }

  getAssetLoadState(id: string): AssetLoadState | undefined {
    return this.assetLoadStates.get(id);
  }

  isAssetReady(id: string): boolean {
    return this.assetLoadStates.get(id) === 'ready';
  }

  registerMaterial(descriptor: MaterialDescriptor): void {
    const hash = this.computeMaterialHash(descriptor);
    const existingId = this.materialHashIndex.get(hash);
    if (existingId && existingId !== descriptor.id) {
      if (this.config.warnOnDuplicate) {
        console.warn(`[UnifiedRegistry] Duplicate material (same shader+uniforms): "${descriptor.id}" matches "${existingId}"`);
      }
      return;
    }
    if (this.config.warnOnDuplicate && this.materials.has(descriptor.id)) {
      console.warn(`[UnifiedRegistry] Duplicate material registration: "${descriptor.id}" — overwriting`);
    }
    this.materials.set(descriptor.id, descriptor);
    this.materialHashIndex.set(hash, descriptor.id);
  }

  unregisterMaterial(id: string): boolean {
    const desc = this.materials.get(id);
    if (desc) {
      this.materialHashIndex.delete(this.computeMaterialHash(desc));
    }
    return this.materials.delete(id);
  }

  getMaterial(id: string): MaterialDescriptor | undefined {
    return this.materials.get(id);
  }

  getMaterialOrError(id: string): MaterialDescriptor {
    const item = this.materials.get(id);
    if (!item) throw new Error(`[UnifiedRegistry] Material not found: "${id}"`);
    return item;
  }

  listMaterials(): MaterialDescriptor[] {
    return Array.from(this.materials.values());
  }

  hasMaterial(id: string): boolean {
    return this.materials.has(id);
  }

  getOrCreateMaterial(descriptor: MaterialDescriptor): MaterialDescriptor {
    const hash = this.computeMaterialHash(descriptor);
    const existingId = this.materialHashIndex.get(hash);
    if (existingId) {
      return this.materials.get(existingId)!;
    }
    this.registerMaterial(descriptor);
    return descriptor;
  }

  private computeMaterialHash(descriptor: MaterialDescriptor): string {
    const parts: string[] = [descriptor.shaderId];
    if (descriptor.uniforms) {
      for (const [key, val] of Object.entries(descriptor.uniforms)) {
        parts.push(`${key}:${JSON.stringify(val)}`);
      }
    }
    return parts.join('|');
  }

  registerShader(descriptor: ShaderDescriptor): void {
    const hash = this.computeShaderHash(descriptor);
    const existingId = this.shaderHashIndex.get(hash);
    if (existingId && existingId !== descriptor.id) {
      if (this.config.warnOnDuplicate) {
        console.warn(`[UnifiedRegistry] Duplicate shader (same vertex+fragment): "${descriptor.id}" matches "${existingId}"`);
      }
      return;
    }
    if (this.config.warnOnDuplicate && this.shaders.has(descriptor.id)) {
      console.warn(`[UnifiedRegistry] Duplicate shader registration: "${descriptor.id}" — overwriting`);
    }
    this.shaders.set(descriptor.id, descriptor);
    this.shaderHashIndex.set(hash, descriptor.id);
  }

  unregisterShader(id: string): boolean {
    const desc = this.shaders.get(id);
    if (desc) {
      this.shaderHashIndex.delete(this.computeShaderHash(desc));
    }
    return this.shaders.delete(id);
  }

  getShader(id: string): ShaderDescriptor | undefined {
    return this.shaders.get(id);
  }

  getShaderOrError(id: string): ShaderDescriptor {
    const item = this.shaders.get(id);
    if (!item) throw new Error(`[UnifiedRegistry] Shader not found: "${id}"`);
    return item;
  }

  listShaders(): ShaderDescriptor[] {
    return Array.from(this.shaders.values());
  }

  hasShader(id: string): boolean {
    return this.shaders.has(id);
  }

  getOrCreateShader(descriptor: ShaderDescriptor): ShaderDescriptor {
    const hash = this.computeShaderHash(descriptor);
    const existingId = this.shaderHashIndex.get(hash);
    if (existingId) {
      return this.shaders.get(existingId)!;
    }
    this.registerShader(descriptor);
    return descriptor;
  }

  private computeShaderHash(descriptor: ShaderDescriptor): string {
    const parts: string[] = [descriptor.vertex, descriptor.fragment];
    if (descriptor.defines) {
      parts.push(...descriptor.defines);
    }
    return parts.join('\n');
  }

  registerEmbodiment(embodiment: Embodiment): void {
    if (this.config.warnOnDuplicate && this.embodiments.has(embodiment.id)) {
      console.warn(`[UnifiedRegistry] Duplicate embodiment registration: "${embodiment.id}" — overwriting`);
    }
    this.embodiments.set(embodiment.id, embodiment);
  }

  unregisterEmbodiment(id: string): boolean {
    return this.embodiments.delete(id);
  }

  getEmbodiment(id: string): Embodiment | undefined {
    return this.embodiments.get(id);
  }

  getEmbodimentOrError(id: string): Embodiment {
    const item = this.embodiments.get(id);
    if (!item) throw new Error(`[UnifiedRegistry] Embodiment not found: "${id}"`);
    return item;
  }

  listEmbodiments(): Embodiment[] {
    return Array.from(this.embodiments.values());
  }

  hasEmbodiment(id: string): boolean {
    return this.embodiments.has(id);
  }

  registerLOD(descriptor: LODDescriptor): void {
    if (this.config.warnOnDuplicate && this.lods.has(descriptor.id)) {
      console.warn(`[UnifiedRegistry] Duplicate LOD registration: "${descriptor.id}" — overwriting`);
    }
    this.lods.set(descriptor.id, descriptor);
  }

  unregisterLOD(id: string): boolean {
    return this.lods.delete(id);
  }

  getLOD(id: string): LODDescriptor | undefined {
    return this.lods.get(id);
  }

  getLODOrError(id: string): LODDescriptor {
    const item = this.lods.get(id);
    if (!item) throw new Error(`[UnifiedRegistry] LOD not found: "${id}"`);
    return item;
  }

  listLODs(): LODDescriptor[] {
    return Array.from(this.lods.values());
  }

  hasLOD(id: string): boolean {
    return this.lods.has(id);
  }

  validate(): string[] {
    const errors: string[] = [];

    for (const [id, desc] of this.assets) {
      if (!desc.source) {
        errors.push(`Asset "${id}" has no source URL`);
      }
      if (desc.boundingSphere && desc.boundingSphere.radius <= 0) {
        errors.push(`Asset "${id}" has invalid bounding sphere radius`);
      }
    }

    for (const [id, emb] of this.embodiments) {
      if (!this.assets.has(emb.assetId)) {
        errors.push(`Embodiment "${id}" references missing asset: "${emb.assetId}"`);
      }
      if (!this.materials.has(emb.materialId)) {
        errors.push(`Embodiment "${id}" references missing material: "${emb.materialId}"`);
      }
      if (!this.shaders.has(emb.shaderId)) {
        errors.push(`Embodiment "${id}" references missing shader: "${emb.shaderId}"`);
      }
      if (!this.lods.has(emb.lodId)) {
        errors.push(`Embodiment "${id}" references missing LOD: "${emb.lodId}"`);
      }
    }

    return errors;
  }

  getStats() {
    return {
      assets: this.assets.size,
      materials: this.materials.size,
      shaders: this.shaders.size,
      embodiments: this.embodiments.size,
      lods: this.lods.size,
    };
  }

  clear(): void {
    this.assets.clear();
    this.assetLoadStates.clear();
    this.materials.clear();
    this.materialHashIndex.clear();
    this.shaders.clear();
    this.shaderHashIndex.clear();
    this.embodiments.clear();
    this.lods.clear();
  }

  dispose(): void {
    this.clear();
  }
}

export const unifiedRegistry = new UnifiedRegistry();