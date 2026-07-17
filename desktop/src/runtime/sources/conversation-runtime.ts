// desktop/src/runtime/sources/conversation-runtime.ts
import { ConversationPhase } from './types'
import { BaseSource } from './base'
import { ConversationSnapshot, IRuntimeSource } from './types'
import { clampUnit } from './util'

// Conversation Runtime: live dialogue phase and activity.
export class ConversationRuntime extends BaseSource<ConversationSnapshot> implements IRuntimeSource<ConversationSnapshot> {
  private phase: ConversationPhase = 'idle'
  private activity = 0

  setPhase(phase: ConversationPhase): void {
    this.phase = phase
    this.emit()
  }

  setActivity(activity: number): void {
    this.activity = clampUnit(activity)
    this.emit()
  }

  getSnapshot(): ConversationSnapshot {
    return { phase: this.phase, activity: this.activity }
  }
}
