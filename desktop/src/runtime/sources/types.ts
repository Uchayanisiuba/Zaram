// desktop/src/runtime/sources/types.ts
//
// Runtime source contracts. These are the live data feeds that the Animation
// Runtime consumes to produce FrameState. Each source is an independent runtime
// (Conversation, Voice, Personality, Memory, System) that the Animation Runtime
// observes. The Animation Runtime never talks to those runtimes directly about
// rendering — it only reads the aggregated RuntimeSnapshot.

import { ExpressiveParams } from '../types'

export type ConversationPhase =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'generating'
  | 'speaking'
  | 'interrupted'
  | 'error'
  | 'working'
  | 'sleeping'

export type SystemRuntimeState =
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'working'
  | 'speaking'
  | 'sleeping'
  | 'error'

export interface ConversationSnapshot {
  phase: ConversationPhase
  activity: number
}

export interface VoiceSnapshot {
  voiceLevel: number
  microphoneLevel: number
}

export interface MemorySnapshot {
  activity: number
  recall: number
}

export interface SystemSnapshot {
  state: SystemRuntimeState
  cognitiveLoad: number
  visualIdentity: number
}

export interface RuntimeSnapshot {
  conversation: ConversationSnapshot
  voice: VoiceSnapshot
  personality: ExpressiveParams
  memory: MemorySnapshot
  system: SystemSnapshot
}

export interface IRuntimeSource<T> {
  getSnapshot(): T
  subscribe(listener: (snapshot: T) => void): () => void
  start(): void
  stop(): void
}

export interface IRuntimeStateProvider {
  getSnapshot(): RuntimeSnapshot
  subscribe(listener: (snapshot: RuntimeSnapshot) => void): () => void
  start(): void
  stop(): void
}
