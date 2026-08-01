// packages/zaram-engine/types/MaterialDescriptor.ts
export interface MaterialDescriptor {
  id: string;
  shaderId: string;
  uniforms?: Record<string, { value: unknown; type?: string }>;
  transparent?: boolean;
  depthWrite?: boolean;
  depthTest?: boolean;
  blending?: 'normal' | 'additive' | 'multiply';
  side?: 'front' | 'back' | 'double';
  metadata?: Record<string, unknown>;
}
