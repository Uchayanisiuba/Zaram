// packages/zaram-engine/renderer/Renderer.ts
import { AssetDescriptor } from '../types/AssetDescriptor';
import { MaterialDescriptor } from '../types/MaterialDescriptor';
import { ShaderDescriptor } from '../types/ShaderDescriptor';
import { LODDescriptor } from '../types/LODDescriptor';
import { FrameState } from '../types/FrameState';
import { PerformanceOverlay } from './PerformanceOverlay';

export interface RenderPayload {
  asset: AssetDescriptor;
  material: MaterialDescriptor;
  shader: ShaderDescriptor;
  lod?: {
    assetId: string;
    materialOverrides?: Partial<MaterialDescriptor>;
  };
  frameState: FrameState;
}

export interface RenderContext {
  canvas: { getContext: (t: string) => unknown; width: number; height: number };
}

export class Renderer {
  private ctx: RenderContext | null = null;
  private readonly overlay = new PerformanceOverlay();
  private internalThree: unknown = {};

  initialize(ctx: RenderContext): void {
    this.ctx = ctx;
  }

  render(payloads: RenderPayload[], frameState: FrameState): void {
    if (!this.ctx) return;

    const t0 = performance.now();
    let triangleCount = 0;

    for (const payload of payloads) {
      this.draw(payload, frameState);
      triangleCount += 2;
    }

    const t1 = performance.now();
    this.overlay.record(t1 - t0, payloads.length, triangleCount);
    this.overlay.recordVisibleEmbodiments(payloads.length);
  }

  private draw(
    payload: RenderPayload,
    frameState: FrameState
  ): void {
    if (!this.ctx) return;
    const ctx2d = this.ctx.canvas.getContext('2d') as any;
    if (!ctx2d) return;

    const width = this.ctx.canvas.width;
    const height = this.ctx.canvas.height;

    const { asset, material, shader, lod, frameState: fs } = payload;
    const x = Math.abs((frameState.visual.presence * 100) % width);
    const y = Math.abs((frameState.visual.energy * 100) % height);
    const w = 80;
    const h = 80;

    ctx2d.save();
    ctx2d.globalAlpha = material.transparent ? 0.6 : 1.0;
    ctx2d.fillStyle = `rgba(${Math.floor(frameState.visual.presence * 255)},${Math.floor(frameState.visual.energy * 255)},${Math.floor(frameState.visual.focus * 255)},1)`;
    ctx2d.fillRect(x - w / 2, y - h / 2, w, h);
    ctx2d.strokeStyle = `rgba(255,255,255,0.8)`;
    ctx2d.strokeRect(x - w / 2, y - h / 2, w, h);
    ctx2d.restore();
  }

  getStats() {
    return this.overlay.getStats();
  }
}
