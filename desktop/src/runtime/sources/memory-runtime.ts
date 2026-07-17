// desktop/src/runtime/sources/memory-runtime.ts
import { BaseSource } from './base'
import { IRuntimeSource, MemorySnapshot } from './types'
import { clampUnit } from './util'

// Memory Runtime: recall activity and visual memory intensity.
export class MemoryRuntime extends BaseSource<MemorySnapshot> implements IRuntimeSource<MemorySnapshot> {
  private activity = 0
  private recall = 0

  setActivity(activity: number): void {
    this.activity = clampUnit(activity)
    this.emit()
  }

  setRecall(recall: number): void {
    this.recall = clampUnit(recall)
    this.emit()
  }

  getSnapshot(): MemorySnapshot {
    return { activity: this.activity, recall: this.recall }
  }
}
