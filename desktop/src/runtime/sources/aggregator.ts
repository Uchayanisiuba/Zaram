// desktop/src/runtime/sources/aggregator.ts
//
// Aggregates the independent runtime sources (Conversation, Voice, Personality,
// Memory, System) into a single RuntimeSnapshot that the Animation Runtime
// reads. This is the ONLY point where the Animation Runtime observes those
// runtimes; it never imports or calls them directly.

import { DEFAULT_EXPRESSIVE_PARAMS } from '../types'
import {
  ConversationSnapshot,
  IRuntimeSource,
  IRuntimeStateProvider,
  MemorySnapshot,
  RuntimeSnapshot,
  SystemSnapshot,
  VoiceSnapshot
} from './types'

export interface AggregatorSources {
  conversation?: IRuntimeSource<ConversationSnapshot>
  voice?: IRuntimeSource<VoiceSnapshot>
  personality?: IRuntimeSource<import('../types').ExpressiveParams>
  memory?: IRuntimeSource<MemorySnapshot>
  system?: IRuntimeSource<SystemSnapshot>
}

export class RuntimeSourceAggregator implements IRuntimeStateProvider {
  private readonly sources: AggregatorSources
  private readonly listeners = new Set<(snapshot: RuntimeSnapshot) => void>()
  private readonly detach: Array<() => void> = []

  constructor(sources: AggregatorSources) {
    this.sources = sources
  }

  start(): void {
    Object.values(this.sources).forEach((source) => source?.start?.())
    this.detach.length = 0
    Object.values(this.sources).forEach((source) => {
      if (!source) return
      const off = source.subscribe(() => this.emit())
      this.detach.push(off)
    })
    this.emit()
  }

  stop(): void {
    this.detach.forEach((off) => off())
    this.detach.length = 0
    Object.values(this.sources).forEach((source) => source?.stop?.())
  }

  getSnapshot(): RuntimeSnapshot {
    return {
      conversation: this.sources.conversation?.getSnapshot() ?? { phase: 'idle', activity: 0 },
      voice: this.sources.voice?.getSnapshot() ?? { voiceLevel: 0, microphoneLevel: 0 },
      personality: this.sources.personality?.getSnapshot() ?? { ...DEFAULT_EXPRESSIVE_PARAMS },
      memory: this.sources.memory?.getSnapshot() ?? { activity: 0, recall: 0 },
      system: this.sources.system?.getSnapshot() ?? {
        state: 'idle',
        cognitiveLoad: 0.2,
        visualIdentity: 0.5
      }
    }
  }

  subscribe(listener: (snapshot: RuntimeSnapshot) => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  private emit(): void {
    const snapshot = this.getSnapshot()
    this.listeners.forEach((listener) => listener(snapshot))
  }
}
