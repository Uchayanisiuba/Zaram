// desktop/src/runtime/cognitive/conversation-projection.ts
//
// PART 5 — Conversation Projection
//
// Projects the conversation phase + cognitive reasoning into the precise states
// the embodiment/behaviour layer consumes. This is the cognitive layer's view
// of conversation — separate from raw source events. No renderer logic.

import type { ConversationPhase } from '../sources/types'
import type { CognitiveState, ConversationIntent, ReasoningState } from './types'

export interface ThinkingState {
  active: boolean
  // 0..1 depth of reasoning
  depth: number
  reasoning: ReasoningState
}

export interface SpeakingState {
  active: boolean
  // 0..1 how much the AI is currently driving the conversation
  assertiveness: number
  intent: ConversationIntent
}

export interface ListeningState {
  active: boolean
  // 0..1 attention given to the speaker
  attentiveness: number
}

export interface InterruptibleState {
  // whether the AI can be interrupted right now
  interruptible: boolean
  // 0..1 window openness
  openness: number
}

export interface ConversationProjection {
  thinking: ThinkingState
  speaking: SpeakingState
  listening: ListeningState
  interruptible: InterruptibleState
  intent: ConversationIntent
}

// Builds the projection from a conversation phase + the cognitive state. Pure
// function, no side effects, no runtime source imports.
export function projectConversation(
  phase: ConversationPhase,
  cognitive: CognitiveState
): ConversationProjection {
  const thinking = phase === 'thinking' || phase === 'generating' || phase === 'working'
  const speaking = phase === 'speaking'
  const listening = phase === 'listening'
  const interrupted = phase === 'interrupted'

  return {
    thinking: {
      active: thinking || cognitive.thinking,
      depth: thinking ? 0.7 : cognitive.thinking ? 0.4 : 0,
      reasoning: cognitive.reasoning
    },
    speaking: {
      active: speaking,
      assertiveness: speaking ? 0.8 : 0.1,
      intent: cognitive.intent
    },
    listening: {
      active: listening,
      attentiveness: listening ? 0.8 : 0.2
    },
    interruptible: {
      interruptible: !speaking && !thinking,
      openness: interrupted ? 0.9 : speaking ? 0.1 : thinking ? 0.3 : 0.7
    },
    intent: cognitive.intent
  }
}
