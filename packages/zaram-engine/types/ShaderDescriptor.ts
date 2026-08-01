// packages/zaram-engine/types/ShaderDescriptor.ts
export type ShaderStage = 'vertex' | 'fragment' | 'compute';

export interface ShaderDescriptor {
  id: string;
  vertex: string;
  fragment: string;
  uniforms?: Record<string, { value: unknown; type?: string }>;
  defines?: string[];
  metadata?: Record<string, unknown>;
}
