// packages/zaram-engine/runtime/FrameGraph.ts
import { FrameState } from '../types/FrameState';
import { CameraState } from './VisibilityRuntime';
import { VisibilityResult } from './VisibilityRuntime';
import { AnimationRuntime } from './AnimationRuntime';
import { UniverseRuntime } from '../universe/UniverseRuntime';
import { LODManager } from '../lod/LODManager';
import { VisibilityRuntime } from './VisibilityRuntime';
import { ParticleRuntime } from '../particle/ParticleRuntime';
import { StreamingRuntime } from './StreamingRuntime';
import { ThreeRenderer, RenderPayload } from '../renderer/ThreeRenderer';
import { PerformanceOverlay } from '../renderer/PerformanceOverlay';
import { GPUResourceManager } from './GPUResourceManager';
import { UnifiedRegistry } from '../registries/UnifiedRegistry';

export interface FrameGraphInput {
  dt: number;
  camera: CameraState;
  rawState: any;
  time: number;
}

export interface FrameGraphResult {
  rendered: number;
  particles: number;
  streamed: string[];
  stats: ReturnType<PerformanceOverlay['getStats']>;
  gpuStats: ReturnType<GPUResourceManager['getStats']>;
  rendererStats: ReturnType<ThreeRenderer['getStats']>;
}

export class FrameGraph {
  constructor(
    private animation: AnimationRuntime,
    private universe: UniverseRuntime,
    private lod: LODManager,
    private visibility: VisibilityRuntime,
    private particles: ParticleRuntime,
    private streaming: StreamingRuntime,
    private renderer: ThreeRenderer,
    private overlay: PerformanceOverlay,
    private gpu: GPUResourceManager,
    private registry: UnifiedRegistry
  ) {}

  public execute(input: FrameGraphInput): FrameGraphResult {
    const { dt, camera, rawState, time } = input;

    const frameState = this.animation.update(dt, rawState);

    this.lod.setCamera(camera);
    const entities = this.universe.getEntities().map(e => ({
      id: e.id,
      cameraDistance: e.cameraDistance,
    }));
    this.lod.update(dt * 1000, entities);

    const visibility = this.visibility.filter(
      this.universe,
      this.registry,
      this.lod,
      camera,
      time
    );

    const particles = this.particles.update(dt);

    const { loaded } = this.streaming.update(dt);

    const payloads: RenderPayload[] = visibility.visible.map(v => ({
      asset: v.asset,
      material: v.material,
      shader: v.shader,
      lod: v.lodOverride,
      frameState,
      transform: v.transform,
    }));
    this.renderer.render(payloads, frameState);

    const stats = this.renderer.getStats();
    const gpuStats = this.gpu.getStats();
    const rendererStats = this.renderer.getStats();

    this.overlay.recordActiveParticles(particles.length);
    this.overlay.recordLOD(this.lod.getGlobalLODBias());
    this.overlay.recordRegistries(
      (this.registry.listAssets().length > 0 ? 1 : 0) +
      (this.registry.listMaterials().length > 0 ? 1 : 0) +
      (this.registry.listShaders().length > 0 ? 1 : 0) +
      (this.registry.listEmbodiments().length > 0 ? 1 : 0)
    );
    this.overlay.recordMemory(
      this.registry.listAssets().length * 1024 +
      this.registry.listMaterials().length * 256 +
      this.registry.listShaders().length * 512 +
      this.registry.listEmbodiments().length * 128
    );

    this.gpu.disposeUnused();

    return {
      rendered: visibility.visible.length,
      particles: particles.length,
      streamed: loaded,
      stats,
      gpuStats,
      rendererStats,
    };
  }
}