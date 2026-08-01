// packages/zaram-engine/types/AssetDescriptor.ts
export type AssetType = 'mesh' | 'sprite' | 'volume' | 'skinnedMesh' | 'particleEmitter';

export interface AssetDescriptor {
  id: string;
  type: AssetType;
  source: string;
  boundingSphere?: {
    center: [number, number, number];
    radius: number;
  };
  metadata?: Record<string, unknown>;
}
