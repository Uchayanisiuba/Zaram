// packages/zaram-engine/runtime/AnimationRuntime.ts
import { FrameState } from '../types/FrameState';
import { StateAdapter } from './StateAdapter';
import { InfluenceEngine } from './InfluenceEngine';
import { EmotionEngine } from './EmotionEngine';
import { RhythmEngine } from './RhythmEngine';
import { FrameComposer } from './FrameComposer';

export class AnimationRuntime {
  private adapter = new StateAdapter();
  private influences = new InfluenceEngine();
  private emotion = new EmotionEngine();
  private rhythm = new RhythmEngine();
  private identitySeed: number;

  constructor(identitySeed: number = 0.5) {
    this.identitySeed = identitySeed;
  }

  public initialize(visualIdentity: number): void {
    this.identitySeed = visualIdentity;
  }

  public update(dt: number, rawState: any): FrameState {
    const targets = this.adapter.mapToTargets(rawState.state);
    const blended = this.influences.blend(targets, dt);
    const emotion = this.emotion.compute(blended, dt);
    const rhythm = this.rhythm.compute(blended, emotion, dt);
    return FrameComposer.compose(blended, emotion, rhythm, rawState, this.identitySeed);
  }
}