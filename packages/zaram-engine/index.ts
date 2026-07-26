// Public API Surface
export { AnimationRuntime } from './runtime/AnimationRuntime';
export { VisibilityRuntime } from './runtime/VisibilityRuntime';
export { StreamingRuntime } from './runtime/StreamingRuntime';
export { FrameGraph } from './runtime/FrameGraph';
export { GPUResourceManager } from './runtime/GPUResourceManager';
export { UniverseRuntime } from './universe/UniverseRuntime';
export { LODManager } from './lod/LODManager';
export type { LODSelection, LODState, LODConfig, LODCamera, EntityLODInfo } from './lod/LODManager';
export { Renderer } from './renderer/Renderer';
export { AssetRegistry } from './registries/AssetRegistry';
export type { AssetLoadState } from './registries/AssetRegistry';
export { MaterialRegistry } from './registries/MaterialRegistry';
export { ShaderRegistry } from './registries/ShaderRegistry';
export { EmbodimentRegistry } from './registries/EmbodimentRegistry';
export { ParticleRuntime } from './particle/ParticleRuntime';
export type { Particle, ParticleEmitterDesc, GPUParticleData, ParticleStats } from './particle/ParticleRuntime';
export { PerformanceOverlay } from './renderer/PerformanceOverlay';
export type { FrameState } from './types/FrameState';
export type { RuntimeState } from './types/RuntimeState';
export type { CameraState, FrustumPlanes, VisibilityResult } from './runtime/VisibilityRuntime';
export type {
  AssetDescriptor,
  AssetType
} from './types/AssetDescriptor';
export type { ShaderDescriptor } from './types/ShaderDescriptor';
export type { MaterialDescriptor } from './types/MaterialDescriptor';
export type { LODDescriptor, LODLevel } from './types/LODDescriptor';
export type { Embodiment } from './registries/EmbodimentRegistry';
export type { StreamingTask, StreamingQueueConfig } from './runtime/StreamingRuntime';
export type { StreamingPriority, StreamingBudget } from './types/StreamingBudget';
export type { StreamingBudget as StreamingBudgetType, StreamingPriority as StreamingPriorityType, BudgetParams } from './types/StreamingBudget';
export type { GPUResourceHandle, GPUResourceStats, ResourceKind } from './runtime/GPUResourceManager';
export type { FrameGraphInput, FrameGraphResult } from './runtime/FrameGraph';
