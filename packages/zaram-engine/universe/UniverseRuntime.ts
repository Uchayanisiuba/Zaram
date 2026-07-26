// packages/zaram-engine/universe/UniverseRuntime.ts
import { FrameState } from '../types/FrameState';
import { EmbodimentRegistry, Embodiment } from '../registries/EmbodimentRegistry';
import { AssetRegistry } from '../registries/AssetRegistry';
import { MaterialRegistry } from '../registries/MaterialRegistry';
import { ShaderRegistry } from '../registries/ShaderRegistry';
import { LODManager } from '../lod/LODManager';
import { LODDescriptor } from '../types/LODDescriptor';
import { AssetDescriptor } from '../types/AssetDescriptor';
import { MaterialDescriptor } from '../types/MaterialDescriptor';
import { ShaderDescriptor } from '../types/ShaderDescriptor';

export interface UniverseEntity {
  id: string;
  embodimentId: string;
  frameState: FrameState;
  cameraDistance: number;
}

export class UniverseRuntime {
  private entities = new Map<string, UniverseEntity>();
  private assetRegistry: AssetRegistry;
  private materialRegistry: MaterialRegistry;
  private shaderRegistry: ShaderRegistry;
  private embodimentRegistry: EmbodimentRegistry;
  private lodManager: LODManager;

  constructor(
    assetRegistry: AssetRegistry,
    materialRegistry: MaterialRegistry,
    shaderRegistry: ShaderRegistry,
    embodimentRegistry: EmbodimentRegistry,
    lodManager: LODManager
  ) {
    this.assetRegistry = assetRegistry;
    this.materialRegistry = materialRegistry;
    this.shaderRegistry = shaderRegistry;
    this.embodimentRegistry = embodimentRegistry;
    this.lodManager = lodManager;
  }

  addEntity(entity: UniverseEntity): void {
    this.entities.set(entity.id, entity);
  }

  removeEntity(id: string): boolean {
    return this.entities.delete(id);
  }

  getFrameAssets(): Array<{
    entityId: string;
    asset: AssetDescriptor;
    material: MaterialDescriptor;
    shader: ShaderDescriptor;
    lodOverride?: { assetId: string; materialOverrides?: Partial<MaterialDescriptor> };
  }> {
    const output: Array<{
      entityId: string;
      asset: AssetDescriptor;
      material: MaterialDescriptor;
      shader: ShaderDescriptor;
      lodOverride?: { assetId: string; materialOverrides?: Partial<MaterialDescriptor> };
    }> = [];

    for (const entity of this.entities.values()) {
      const embodiment = this.embodimentRegistry.get(entity.embodimentId);
      if (!embodiment) continue;

      const asset = this.assetRegistry.get(embodiment.assetId);
      const material = this.materialRegistry.get(embodiment.materialId);
      const shader = this.shaderRegistry.get(embodiment.shaderId);
      const lod = this.lodManager.select(entity.cameraDistance, entity.id);

      if (!asset || !material || !shader) continue;

      output.push({
        entityId: entity.id,
        asset,
        material,
        shader,
        lodOverride: lod ?? undefined
      });
    }

    return output;
  }

  getEntities(): UniverseEntity[] {
    return Array.from(this.entities.values());
  }

  updateFrameState(id: string, frameState: FrameState): void {
    const entity = this.entities.get(id);
    if (!entity) return;
    entity.frameState = frameState;
  }
}
