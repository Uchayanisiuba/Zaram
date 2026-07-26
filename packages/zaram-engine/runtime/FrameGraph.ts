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
import { Renderer, RenderPayload } from '../renderer/Renderer';
import { PerformanceOverlay } from '../renderer/PerformanceOverlay';
import { GPUResourceManager } from './GPUResourceManager';
import { AssetRegistry } from '../registries/AssetRegistry';
import { MaterialRegistry } from '../registries/MaterialRegistry';
import { ShaderRegistry } from '../registries/ShaderRegistry';
import { EmbodimentRegistry } from '../registries/EmbodimentRegistry';

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
}

export class FrameGraph {
  constructor(
    private animation: AnimationRuntime,
    private universe: UniverseRuntime,
    private lod: LODManager,
    private visibility: VisibilityRuntime,
    private particles: ParticleRuntime,
    private streaming: StreamingRuntime,
    private renderer: Renderer,
    private overlay: PerformanceOverlay,
    private gpu: GPUResourceManager,
    private assetRegistry: AssetRegistry,
    private materialRegistry: MaterialRegistry,
    private shaderRegistry: ShaderRegistry,
    private embodimentRegistry: EmbodimentRegistry
  ) {}

  public execute(input: FrameGraphInput): FrameGraphResult {
    const t0 = performance.now();
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
      this.assetRegistry,
      this.materialRegistry,
      this.shaderRegistry,
      this.lod,
      this.embodimentRegistry,
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
    }));
    this.renderer.render(payloads, frameState);

    const stats = this.renderer.getStats();

    this.overlay.recordActiveParticles(particles.length);
    this.overlay.recordLOD(this.lod.getGlobalLODBias());
    this.overlay.recordRegistries(
      (this.assetRegistry.list().length > 0 ? 1 : 0) +
      (this.materialRegistry.list().length > 0 ? 1 : 0) +
      (this.shaderRegistry.list().length > 0 ? 1 : 0) +
      (this.embodimentRegistry.list().length > 0 ? 1 : 0)
    );
    this.overlay.recordMemory(
      this.assetRegistry.list().length * 1024 +
      this.materialRegistry.list().length * 256 +
      this.shaderRegistry.list().length * 512 +
      this.embodimentRegistry.list().length * 128
    );

    this.gpu.disposeUnused();

    return {
      rendered: visibility.visible.length,
      particles: particles.length,
      streamed: loaded,
      stats
    };
  }
}
