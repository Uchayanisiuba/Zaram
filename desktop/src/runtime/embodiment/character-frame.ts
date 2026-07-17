// desktop/src/runtime/embodiment/character-frame.ts
//
// PART 8 — Renderer Independence Boundary
//
// The single projection point from internal CharacterState into the renderer-
// neutral CharacterFrame. The Renderer receives ONLY a CharacterFrame. It knows
// nothing about emotion semantics, thinking, conversation, voice, memory, or
// knowledge — only the values required to render a living presence.

import { CharacterFrame, CharacterState } from './types'

export const CHARACTER_FRAME_VERSION = '1.1.0'

export function toCharacterFrame(
  state: CharacterState,
  sequence: number,
  now: number = Date.now()
): CharacterFrame {
  const { emotion, behaviour, gaze, breath, microMovement } = state
  return {
    version: CHARACTER_FRAME_VERSION,
    timestamp: now,
    emotion: {
      valence: emotion.valence,
      arousal: emotion.arousal,
      confidence: emotion.confidence,
      attention: emotion.attention,
      warmth: emotion.empathy,
      curiosity: emotion.curiosity,
      fatigue: emotion.fatigue
    },
    behaviour: {
      mode: behaviour.mode,
      intensity: behaviour.intensity,
      microExpression: behaviour.microExpression
    },
    gaze: {
      eyeX: gaze.eye.x,
      eyeY: gaze.eye.y,
      convergence: gaze.eye.convergence,
      headX: gaze.head.x,
      headY: gaze.head.y,
      headTilt: gaze.head.tilt,
      blinkClosure: gaze.blink.closure
    },
    breath,
    microMovement,
    sequence
  }
}
