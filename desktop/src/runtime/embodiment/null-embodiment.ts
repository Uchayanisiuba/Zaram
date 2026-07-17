// desktop/src/runtime/embodiment/null-embodiment.ts
//
// A no-op embodiment. Used as the safe default when no renderer attachment is
// desired or when an embodiment must be logically present but inert (e.g. head-
// less test runs). It satisfies IEmbodiment without any renderer dependency.

import { EmbodimentStatus, EmbodimentType, FrameState } from '../types'
import { IEmbodiment } from '../interfaces'

export class NullEmbodiment implements IEmbodiment {
  private status: EmbodimentStatus = {
    type: 'none',
    state: 'uninitialized',
    healthy: true,
    lastUpdated: Date.now()
  }

  async initialize(): Promise<void> {
    this.set('ready')
  }

  async start(): Promise<void> {
    this.set('running')
  }

  async pause(): Promise<void> {
    this.set('paused')
  }

  async resume(): Promise<void> {
    this.set('running')
  }

  async shutdown(): Promise<void> {
    this.set('shutdown')
  }

  setFrameState(_frameState: FrameState): void {
    /* intentionally inert */
  }

  getStatus(): EmbodimentStatus {
    return { ...this.status }
  }

  private set(state: EmbodimentStatus['state']): void {
    this.status = {
      type: 'none',
      state,
      healthy: true,
      lastUpdated: Date.now()
    }
  }
}

// MetaHuman descriptors are declared structurally via EmbodimentType, but the
// engine's EmbodimentType union must include the framework's known kinds.
export const KNOWN_EMBODIMENT_TYPES: EmbodimentType[] = [
  'none',
  'living-orb',
  'metahuman',
  'unreal-character',
  'xr-avatar'
]
