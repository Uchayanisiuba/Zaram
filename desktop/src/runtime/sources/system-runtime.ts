// desktop/src/runtime/sources/system-runtime.ts
import { BaseSource } from './base'
import { IRuntimeSource, SystemSnapshot, SystemRuntimeState } from './types'
import { clampUnit } from './util'

// System Runtime: discrete OS state, cognitive load, and persistent visual id.
export class SystemRuntime extends BaseSource<SystemSnapshot> implements IRuntimeSource<SystemSnapshot> {
  private state: SystemRuntimeState = 'idle'
  private cognitiveLoad = 0.2
  private visualIdentity = 0.5

  setState(state: SystemRuntimeState): void {
    this.state = state
    this.emit()
  }

  setCognitiveLoad(load: number): void {
    this.cognitiveLoad = clampUnit(load)
    this.emit()
  }

  setVisualIdentity(seed: number): void {
    this.visualIdentity = clampUnit(seed)
    this.emit()
  }

  getSnapshot(): SystemSnapshot {
    return { state: this.state, cognitiveLoad: this.cognitiveLoad, visualIdentity: this.visualIdentity }
  }
}
