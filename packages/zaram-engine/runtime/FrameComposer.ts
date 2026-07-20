// packages/zaram-engine/runtime/FrameComposer.ts
import { FrameState } from '../types/FrameState';
import { TargetInfluences } from './StateAdapter';
import { EmotionDimensions } from './EmotionEngine';
import { RhythmData } from './RhythmEngine';
import { RuntimeState } from '../types/RuntimeState';
import { randomUUID } from '../utils/crypto';

export class FrameComposer {
  public static compose(
    influences: TargetInfluences,
    emotions: EmotionDimensions,
    rhythm: RhythmData,
    rawState: RuntimeState,
    identitySeed: number
  ): FrameState {
    return {
      visual: {
        // Modulate baseline presence with biological rhythm
        presence: Math.max(0, Math.min(1, influences.presence + rhythm.microOscillation)),
        energy: Math.max(0, Math.min(1, influences.energy + rhythm.energyPulse)),
        focus: Math.max(0, Math.min(1, influences.focus + rhythm.focusDrift)),
        activity: Math.max(0, Math.min(1, influences.activity + (rhythm.breathingOffset * 0.1))),
      },
      audio: {
        voiceLevel: rawState.audio?.voiceLevel || 0.0,
        microphoneLevel: rawState.audio?.microphoneLevel || 0.0,
      },
      emotion: {
        ...emotions
      },
      system: {
        state: rawState.state,
        cognitiveLoad: rawState.cognitiveLoad || 0.0,
        visualIdentity: identitySeed
      },
      metadata: {
        timestamp: Date.now(),
        correlationId: rawState.correlationId || randomUUID(),
        version: "1.0.0"
      }
    };
  }
}