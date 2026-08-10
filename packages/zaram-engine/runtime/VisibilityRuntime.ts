// packages/zaram-engine/runtime/VisibilityRuntime.ts
import { UniverseRuntime, UniverseEntity } from '../universe/UniverseRuntime';
import { AssetDescriptor } from '../types/AssetDescriptor';
import { MaterialDescriptor } from '../types/MaterialDescriptor';
import { ShaderDescriptor } from '../types/ShaderDescriptor';
import { LODManager, LODSelection } from '../lod/LODManager';
import { UnifiedRegistry, Embodiment } from '../registries/UnifiedRegistry';

export interface CameraState {
  position: [number, number, number];
  forward: [number, number, number];
  up: [number, number, number];
  fov: number;
  near: number;
  far: number;
  aspect: number;
  visibilityMask?: number;
}

export interface FrustumPlanes {
  left: number[];
  right: number[];
  top: number[];
  bottom: number[];
  near: number[];
  far: number[];
}

export interface VisibilityResult {
  visible: Array<{
    entityId: string;
    asset: AssetDescriptor;
    material: MaterialDescriptor;
    shader: ShaderDescriptor;
    lodOverride?: LODSelection;
    transform?: {
      position: [number, number, number];
      rotation: [number, number, number];
      scale: [number, number, number];
    };
  }>;
  sleeping: string[];
  culled: string[];
}

export class VisibilityRuntime {
  private readonly sleepingMap = new Map<string, number>();
  private readonly sectors = new Map<string, Set<string>>();
  private sleepingTimeout = 5000;

  public computeFrustumPlanes(camera: CameraState): FrustumPlanes {
    const { position, forward, up, fov, near, far, aspect } = camera;
    const h = near * Math.tan((fov * Math.PI) / 360);
    const w = h * aspect;

    const z = normalize(forward);
    const x = normalize(cross(forward, up));
    const y = cross(z, x);

    const nc = [
      position[0] + z[0] * near,
      position[1] + z[1] * near,
      position[2] + z[2] * near
    ];

    const fc = [
      position[0] + z[0] * far,
      position[1] + z[1] * far,
      position[2] + z[2] * far
    ];

    const nearTL = [nc[0] + y[0] * h - x[0] * w, nc[1] + y[1] * h - x[1] * w, nc[2] + y[2] * h - x[2] * w];
    const nearTR = [nc[0] + y[0] * h + x[0] * w, nc[1] + y[1] * h + x[1] * w, nc[2] + y[2] * h + x[2] * w];
    const nearBL = [nc[0] - y[0] * h - x[0] * w, nc[1] - y[1] * h - x[1] * w, nc[2] - y[2] * h - x[2] * w];
    const nearBR = [nc[0] - y[0] * h + x[0] * w, nc[1] - y[1] * h + x[1] * w, nc[2] - y[2] * h + x[2] * w];

    const farTL = [fc[0] + y[0] * h - x[0] * w, fc[1] + y[1] * h - x[1] * w, fc[2] + y[2] * h - x[2] * w];
    const farTR = [fc[0] + y[0] * h + x[0] * w, fc[1] + y[1] * h + x[1] * w, fc[2] + y[2] * h + x[2] * w];
    const farBL = [fc[0] - y[0] * h - x[0] * w, fc[1] - y[1] * h - x[1] * w, fc[2] - y[2] * h - x[2] * w];
    const farBR = [fc[0] - y[0] * h + x[0] * w, fc[1] - y[1] * h + x[1] * w, fc[2] - y[2] * h + x[2] * w];

    return {
      left: planeFromPoints(nc, nearBL, nearTL),
      right: planeFromPoints(nc, nearTR, nearBR),
      top: planeFromPoints(nc, nearTL, nearTR),
      bottom: planeFromPoints(nc, nearBR, nearBL),
      near: planeFromPoints(nc, nearTR, nearTL),
      far: planeFromPoints(fc, farTR, farTL)
    };
  }

  public filter(
    universe: UniverseRuntime,
    registry: UnifiedRegistry,
    lodManager: LODManager,
    camera: CameraState,
    now: number
  ): VisibilityResult {
    const planes = this.computeFrustumPlanes(camera);
    const visible: VisibilityResult['visible'] = [];
    const sleeping: string[] = [];
    const culled: string[] = [];

    lodManager.setCamera(camera);

    for (const entity of universe.getEntities()) {
      if (this.isSleeping(entity.id, now)) {
        sleeping.push(entity.id);
        continue;
      }

      const embodiment = registry.getEmbodiment(entity.embodimentId);
      if (!embodiment) {
        culled.push(entity.id);
        continue;
      }

      const asset = registry.getAsset(embodiment.assetId);
      if (!asset || !isSphereInFrustum(embodiment, planes, camera)) {
        culled.push(entity.id);
        continue;
      }

      const material = registry.getMaterial(embodiment.materialId);
      const shader = registry.getShader(embodiment.shaderId);
      if (!material || !shader) {
        culled.push(entity.id);
        continue;
      }

      const lod = lodManager.select(entity.cameraDistance, entity.id);
      visible.push({
        entityId: entity.id,
        asset,
        material,
        shader,
        lodOverride: lod ?? undefined,
        transform: embodiment.transform ? {
          position: embodiment.transform.position ?? [0, 0, 0],
          rotation: embodiment.transform.rotation ?? [0, 0, 0],
          scale: embodiment.transform.scale ?? [1, 1, 1],
        } : undefined
      });
    }

    return { visible, sleeping, culled };
  }

  public wake(entityId: string): void {
    this.sleepingMap.delete(entityId);
  }

  public setSector(sectorId: string, entityIds: string[]): void {
    this.sectors.set(sectorId, new Set(entityIds));
  }

  public activateSector(sectorId: string): void {
    this.sectors.get(sectorId)?.forEach(id => this.wake(id));
  }

  private isSleeping(entityId: string, now: number): boolean {
    const lastSeen = this.sleepingMap.get(entityId);
    if (lastSeen === undefined) {
      this.sleepingMap.set(entityId, now);
      return false;
    }
    return now - lastSeen > this.sleepingTimeout;
  }
}

function normalize(v: [number, number, number]): [number, number, number] {
  const len = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
  return len > 0 ? [v[0] / len, v[1] / len, v[2] / len] : [0, 0, 0];
}

function cross(a: [number, number, number], b: [number, number, number]): [number, number, number] {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0]
  ];
}

function planeFromPoints(a: number[], b: number[], c: number[]): number[] {
  const ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
  const ac = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
  const n = cross([ab[0], ab[1], ab[2]], [ac[0], ac[1], ac[2]]);
  const d = -(n[0] * a[0] + n[1] * a[1] + n[2] * a[2]);
  return [n[0], n[1], n[2], d];
}

function isSphereInFrustum(
  embodiment: { transform?: { position?: [number, number, number] }; metadata?: Record<string, unknown> },
  planes: FrustumPlanes,
  camera: CameraState
): boolean {
  const center = embodiment.transform?.position ?? [0, 0, 0];
  const radius = (embodiment.metadata?.boundingRadius as number) ?? 1;

  const allPlanes = [planes.left, planes.right, planes.top, planes.bottom, planes.near, planes.far];
  for (const p of allPlanes) {
    const dist = p[0] * center[0] + p[1] * center[1] + p[2] * center[2] + p[3];
    if (dist + radius < 0) return false;
  }

  const d = Math.sqrt(
    Math.pow(center[0] - camera.position[0], 2) +
    Math.pow(center[1] - camera.position[1], 2) +
    Math.pow(center[2] - camera.position[2], 2)
  );
  return d - radius <= camera.far;
}