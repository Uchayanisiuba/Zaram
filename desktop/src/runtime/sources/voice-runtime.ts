// desktop/src/runtime/sources/voice-runtime.ts
import { BaseSource } from './base'
import { IRuntimeSource, VoiceSnapshot } from './types'
import { clampUnit } from './util'

// Voice Runtime: AI speech amplitude and user microphone amplitude.
export class VoiceRuntime extends BaseSource<VoiceSnapshot> implements IRuntimeSource<VoiceSnapshot> {
  private voiceLevel = 0
  private microphoneLevel = 0

  setVoiceLevel(level: number): void {
    this.voiceLevel = clampUnit(level)
    this.emit()
  }

  setMicrophoneLevel(level: number): void {
    this.microphoneLevel = clampUnit(level)
    this.emit()
  }

  getSnapshot(): VoiceSnapshot {
    return { voiceLevel: this.voiceLevel, microphoneLevel: this.microphoneLevel }
  }
}
