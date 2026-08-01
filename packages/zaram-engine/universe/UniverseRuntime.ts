// packages/zaram-engine/universe/UniverseRuntime.ts
import { FrameState } from '../types/FrameState';
import { UnifiedRegistry, Embodiment } from '../registries/UnifiedRegistry';
import { LODManager, LODSelection } from '../lod/LODManager';
import { AssetDescriptor } from '../types/AssetDescriptor';
import { MaterialDescriptor } from '../types/MaterialDescriptor';
import { ShaderDescriptor } from '../types/ShaderDescriptor';

export interface UniverseEntity {
  id: string;
  embodimentId: string;
  frameState: FrameState;
  cameraDistance: number;
}

export interface UniverseEntityInput {
  id: string;
  embodimentId: string;
  cameraDistance: number;
  transform?: {
    position?: [number, number, number];
    rotation?: [number, number, number];
    scale?: [number, number, number];
  };
}

export class UniverseRuntime {
  private entities = new Map<string, UniverseEntity>();
  private registry: UnifiedRegistry;
  private lodManager: LODManager;

  constructor(registry: UnifiedRegistry, lodManager: LODManager) {
    this.registry = registry;
    this.lodManager = lodManager;
  }

  addEntity(entity: UniverseEntityInput): void {
    const frameState: FrameState = {
      visual: { presence: 0.5, energy: 0.5, focus: 0.5, activity: 0.5 },
      audio: { voiceLevel: 0, microphoneLevel: 0 },
      emotion: { calmness: 0.5, confidence: 0.5, curiosity: 0.5, warmth: 0.5, empathy: 0.5, playfulness: 0.5 },
      system: { state: 'Idle', cognitiveLoad: 0, visualIdentity: 0 },
      metadata: { timestamp: Date.now(), correlationId: '', version: '1.0.0' },
    };

    this.entities.set(entity.id, {
      id: entity.id,
      embodimentId: entity.embodimentId,
      frameState,
      cameraDistance: entity.cameraDistance,
    });
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
    transform?: {
      position: [number, number, number];
      rotation: [number, number, number];
      scale: [number, number, number];
    };
  }> {
    const output: Array<{
      entityId: string;
      asset: AssetDescriptor;
      material: MaterialDescriptor;
      shader: ShaderDescriptor;
      lodOverride?: { assetId: string; materialOverrides?: Partial<MaterialDescriptor> };
      transform?: {
        position: [number, number, number];
        rotation: [number, number, number];
        scale: [number, number, number];
      };
    }> = [];

    for (const entity of this.entities.values()) {
      const embodiment = this.registry.getEmbodiment(entity.embodimentId);
      if (!embodiment) continue;

      const asset = this.registry.getAsset(embodiment.assetId);
      const material = this.registry.getMaterial(embodiment.materialId);
      const shader = this.registry.getShader(embodiment.shaderId);
      const lod = this.lodManager.select(entity.cameraDistance, entity.id);

      if (!asset || !material || !shader) continue;

      const transform = embodiment.transform;
      const hasTransform = transform && transform.position && transform.rotation && transform.scale;

      output.push({
        entityId: entity.id,
        asset,
        material,
        shader,
        lodOverride: lod ?? undefined,
        transform: hasTransform ? {
          position: transform.position!,
          rotation: transform.rotation!,
          scale: transform.scale!,
        } : undefined,
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

  updateCameraDistance(id: string, distance: number): void {
    const entity = this.entities.get(id);
    if (!entity) return;
    entity.cameraDistance = distance;
  }

  getRegistry(): UnifiedRegistry {
    return this.registry;
  }

  getLODManager(): LODManager {
    return this.lodManager;
  }
}