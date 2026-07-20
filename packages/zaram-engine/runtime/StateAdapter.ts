// packages/zaram-engine/runtime/StateAdapter.ts
import { RuntimeState } from '../types/RuntimeState';

export interface TargetInfluences {
  presence: number;
  energy: number;
  focus: number;
  activity: number;
}

export class StateAdapter {
  /**
   * Maps discrete application state to target continuous visual parameters.
   * These are target states; the InfluenceEngine will handle the interpolation.
   */
  public mapToTargets(state: RuntimeState['state']): TargetInfluences {
    switch (state) {
      case 'Thinking':
        return { presence: 0.85, energy: 0.60, focus: 0.95, activity: 0.50 };
      case 'Speaking':
        return { presence: 0.90, energy: 0.80, focus: 0.70, activity: 0.85 };
      case 'Listening':
        return { presence: 0.75, energy: 0.40, focus: 0.85, activity: 0.30 };
      case 'Working':
        return { presence: 0.60, energy: 0.90, focus: 1.00, activity: 0.95 };
      case 'Sleeping':
        return { presence: 0.15, energy: 0.10, focus: 0.05, activity: 0.05 };
      case 'Error':
        return { presence: 1.00, energy: 0.95, focus: 0.30, activity: 0.90 };
      case 'Idle':
      default:
        return { presence: 0.40, energy: 0.30, focus: 0.20, activity: 0.20 };
    }
  }
}