// packages/zaram-engine/types/LODDescriptor.ts
import { MaterialDescriptor } from './MaterialDescriptor';

export interface LODLevel {
  distance: number;
  assetId: string;
  materialOverrides?: Partial<MaterialDescriptor>;
  screenSize?: number;
}

export interface LODDescriptor {
  id: string;
  levels: LODLevel[];
  screenSizes?: number[];
}
