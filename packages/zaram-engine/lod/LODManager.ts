// packages/zaram-engine/lod/LODManager.ts
import { LODDescriptor, LODLevel } from '../types/LODDescriptor';
import { MaterialDescriptor } from '../types/MaterialDescriptor';

export interface LODSelection {
  assetId: string;
  materialOverrides?: Partial<MaterialDescriptor>;
  fromAssetId?: string;
  transitionProgress?: number;
}

export interface LODState {
  entityId: string;
  currentLevel: number;
  previousLevel: number;
  distance: number;
  screenSize: number;
  transitionProgress: number;
  isTransitioning: boolean;
}

export interface LODConfig {
  distances: number[];
  screenSizes: number[];
  hysteresis: number;
  maxDistance: number;
}

export interface LODCamera {
  position: [number, number, number];
  fov: number;
  aspect: number;
}

export interface EntityLODInfo {
  id: string;
  cameraDistance: number;
  screenSize?: number;
}

const DEFAULT_CONFIG: LODConfig = {
  distances: [10, 30, 80, 200],
  screenSizes: [0.15, 0.08, 0.03, 0.01],
  hysteresis: 0.15,
  maxDistance: 500,
};

const PERFORMANCE_BUDGETS = {
  high: { targetFrameTime: 8.33, maxLODBias: -0.5 },
  medium: { targetFrameTime: 16.67, maxLODBias: 0.0 },
  low: { targetFrameTime: 33.33, maxLODBias: 1.0 },
};

const TRANSITION_SPEED = 0.05;
const FRAME_TIME_HISTORY = 60;

export class LODManager {
  private descriptor?: LODDescriptor;
  private config: LODConfig = { ...DEFAULT_CONFIG };
  private states: Map<string, LODState> = new Map();
  private camera: LODCamera | null = null;
  private qualityMode: 'high' | 'medium' | 'low' = 'high';
  private frameTimeHistory: number[] = [];
  private globalLODBias = 0;
  private onLODChangeCallbacks: Map<string, (state: LODState) => void> = new Map();
  private defaultRadius = 1.0;

  configure(descriptor: LODDescriptor): void {
    this.descriptor = descriptor;
    if (descriptor.screenSizes) {
      this.config.screenSizes = descriptor.screenSizes;
    }
  }

  setCamera(camera: LODCamera): void {
    this.camera = camera;
  }

  setConfig(config: Partial<LODConfig>): void {
    this.config = { ...this.config, ...config };
  }

  setQualityMode(mode: 'high' | 'medium' | 'low'): void {
    this.qualityMode = mode;
  }

  update(frameTimeMs: number, entities: EntityLODInfo[]): void {
    this.frameTimeHistory.push(frameTimeMs);
    if (this.frameTimeHistory.length > FRAME_TIME_HISTORY) {
      this.frameTimeHistory.shift();
    }

    this.updateQualityMode();

    for (const entity of entities) {
      this.updateEntity(entity.id, entity.cameraDistance, entity.screenSize);
    }
  }

  private updateQualityMode(): void {
    if (this.frameTimeHistory.length < 30) return;

    const avgFrameTime = this.frameTimeHistory.reduce((a, b) => a + b, 0) / this.frameTimeHistory.length;

    if (avgFrameTime > PERFORMANCE_BUDGETS.medium.targetFrameTime * 1.2) {
      if (this.qualityMode !== 'low') {
        this.qualityMode = 'low';
        this.globalLODBias = Math.min(this.globalLODBias + 0.02, PERFORMANCE_BUDGETS.low.maxLODBias);
      }
    } else if (avgFrameTime > PERFORMANCE_BUDGETS.high.targetFrameTime * 1.2) {
      if (this.qualityMode !== 'medium') {
        this.qualityMode = 'medium';
        this.globalLODBias = Math.max(-0.5, Math.min(0, this.globalLODBias + 0.01));
      }
    } else if (this.qualityMode !== 'high') {
      this.qualityMode = 'high';
      this.globalLODBias = Math.max(PERFORMANCE_BUDGETS.high.maxLODBias, this.globalLODBias - 0.01);
    }
  }

  private updateEntity(entityId: string, cameraDistance: number, screenSize?: number): void {
    const state = this.getOrCreateState(entityId);
    state.distance = cameraDistance;

    if (screenSize !== undefined) {
      state.screenSize = screenSize;
    } else {
      state.screenSize = this.calculateScreenSize(cameraDistance);
    }

    const targetLevel = this.determineTargetLevel(cameraDistance, state.screenSize);

    if (targetLevel !== state.currentLevel) {
      const shouldTransition = this.shouldTransition(state, targetLevel, cameraDistance);
      if (shouldTransition) {
        state.previousLevel = state.currentLevel;
        state.currentLevel = targetLevel;
        state.isTransitioning = true;
        state.transitionProgress = 0;
        this.notifyLODChange(entityId, state);
      }
    }

    if (state.isTransitioning) {
      state.transitionProgress += TRANSITION_SPEED;
      if (state.transitionProgress >= 1) {
        state.isTransitioning = false;
        state.transitionProgress = 1;
      }
    }
  }

  private determineTargetLevel(distance: number, screenSize: number): number {
    if (!this.descriptor || this.descriptor.levels.length === 0) {
      return 0;
    }

    const levels = this.descriptor.levels;
    const biasFactor = 1 + this.globalLODBias * 0.2;
    let selected = 0;

    for (let i = 0; i < levels.length; i++) {
      const level = levels[i];
      const distThreshold = level.distance * biasFactor;
      const sizeThreshold = (level.screenSize ?? this.config.screenSizes[i] ?? 0) * biasFactor;

      const distMatch = distance >= distThreshold;
      const sizeMatch = level.screenSize !== undefined && screenSize < sizeThreshold;

      if (distMatch || sizeMatch) {
        selected = i;
      } else {
        break;
      }
    }

    return Math.min(selected, levels.length - 1);
  }

  private shouldTransition(state: LODState, targetLevel: number, distance: number): boolean {
    if (state.currentLevel === targetLevel) return false;

    const levels = this.descriptor?.levels ?? [];
    const hysteresis = this.config.hysteresis;

    if (targetLevel > state.currentLevel) {
      const currentDistThreshold = levels[state.currentLevel]?.distance ?? Infinity;
      return distance > currentDistThreshold * (1 + hysteresis);
    } else {
      const targetDistThreshold = levels[targetLevel]?.distance ?? 0;
      return distance < targetDistThreshold * (1 - hysteresis);
    }
  }

  private calculateScreenSize(distance: number): number {
    if (distance <= 0) return Infinity;
    return this.defaultRadius / distance;
  }

  select(cameraDistance: number, entityId?: string): LODSelection | null {
    if (!this.descriptor || this.descriptor.levels.length === 0) {
      return null;
    }

    const levels = this.descriptor.levels;
    const biasFactor = 1 + this.globalLODBias * 0.2;
    let selected: LODLevel | undefined;

    for (const level of levels) {
      const distThreshold = level.distance * biasFactor;
      const sizeThreshold = (level.screenSize ?? 0) * biasFactor;

      const distMatch = cameraDistance >= distThreshold;
      const sizeMatch = level.screenSize !== undefined && this.calculateScreenSize(cameraDistance) < sizeThreshold;

      if (distMatch || sizeMatch) {
        selected = level;
      } else {
        break;
      }
    }

    if (!selected) {
      selected = levels[levels.length - 1];
    }

    const selection: LODSelection = {
      assetId: selected.assetId,
      materialOverrides: selected.materialOverrides,
    };

    if (entityId) {
      const state = this.states.get(entityId);
      if (state && state.isTransitioning) {
        selection.transitionProgress = state.transitionProgress;
        const prevLevel = levels[state.previousLevel];
        if (prevLevel) {
          selection.fromAssetId = prevLevel.assetId;
        }
      }
    }

    return selection;
  }

  private getOrCreateState(entityId: string): LODState {
    let state = this.states.get(entityId);
    if (!state) {
      state = {
        entityId,
        currentLevel: 0,
        previousLevel: 0,
        distance: 0,
        screenSize: 0,
        transitionProgress: 0,
        isTransitioning: false,
      };
      this.states.set(entityId, state);
    }
    return state;
  }

  getState(entityId: string): LODState | undefined {
    return this.states.get(entityId);
  }

  getAllStates(): Map<string, LODState> {
    return this.states;
  }

  getQualityMode(): 'high' | 'medium' | 'low' {
    return this.qualityMode;
  }

  getGlobalLODBias(): number {
    return this.globalLODBias;
  }

  onLODChange(entityId: string, callback: (state: LODState) => void): () => void {
    this.onLODChangeCallbacks.set(entityId, callback);
    return () => this.onLODChangeCallbacks.delete(entityId);
  }

  private notifyLODChange(entityId: string, state: LODState): void {
    const callback = this.onLODChangeCallbacks.get(entityId);
    if (callback) callback(state);
  }

  dispose(): void {
    this.states.clear();
    this.onLODChangeCallbacks.clear();
    this.frameTimeHistory = [];
    this.camera = null;
  }
}
