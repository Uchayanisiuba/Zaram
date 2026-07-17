// desktop/src/runtime/embodiment/metahuman.ts
//
// PART 6 — Future MetaHuman Support (INTERFACES ONLY)
//
// Architecture scaffolding for a future Unreal/MetaHuman embodiment. NO Unreal
// imports. NO LiveLink. No implementation — only the contracts future adapters
// will satisfy so they can plug into the registry/DI without changing the
// runtime.

import { IEmbodiment } from '../interfaces'
import { FrameState } from '../types'
import { CharacterFrame } from './types'

// A MetaHuman embodiment exposes a face rig it can drive via blendshape/ARKit
// weights projected from a CharacterFrame.
export interface IMetaHumanAdapter {
  // Build a MetaHuman-backed IEmbodiment. The adapter owns how the rig is
  // created; the runtime only receives the IEmbodiment contract.
  createEmbodiment(): IEmbodiment
}

// A face rig accepts facial expression weights (ARKit-style) and applies them to
// the underlying head/face. Renderer-agnostic: it operates on numeric weights.
export interface IFaceRig {
  // Apply a full set of ARKit blendshape weights (0..1 each).
  applyExpression(weights: ARKitBlendshapeWeights): void
  // Move the head/eye gaze toward a normalised target.
  applyGaze(target: { eyeX: number; eyeY: number; headX: number; headY: number }): void
  // Drive a blink 0(open)..1(closed).
  applyBlink(closure: number): void
  reset(): void
}

// Provides facial expression weights from a CharacterFrame. Decouples expression
// math from any specific rig/engine.
export interface IFacialExpressionProvider {
  compute(frame: CharacterFrame): ARKitBlendshapeWeights
}

// Drives ARKit blendshape weights. Implementations will translate the
// continuous CharacterFrame into ARKit 52-shape weights (or a subset).
export interface IARKitDriver {
  // Map a CharacterFrame to ARKit blendshape weights.
  drive(frame: CharacterFrame): ARKitBlendshapeWeights
  readonly supportedShapes: readonly string[]
}

// The canonical ARKit 52 blendshape set. We model the full key space so future
// adapters can populate any subset; values are 0..1.
export type ARKitBlendshapeWeights = {
  eyeBlinkLeft: number
  eyeBlinkRight: number
  eyeLookDownLeft: number
  eyeLookDownRight: number
  eyeLookInLeft: number
  eyeLookInRight: number
  eyeLookOutLeft: number
  eyeLookOutRight: number
  eyeLookUpLeft: number
  eyeLookUpRight: number
  eyeSquintLeft: number
  eyeSquintRight: number
  eyeWideLeft: number
  eyeWideRight: number
  jawForward: number
  jawLeft: number
  jawOpen: number
  jawRight: number
  mouthClose: number
  mouthFunnel: number
  mouthLeft: number
  mouthRight: number
  mouthSmileLeft: number
  mouthSmileRight: number
  mouthFrownLeft: number
  mouthFrownRight: number
  mouthPucker: number
  mouthRollLower: number
  mouthRollUpper: number
  mouthShrugLower: number
  mouthShrugUpper: number
  mouthStretchLeft: number
  mouthStretchRight: number
  mouthUpperUpLeft: number
  mouthUpperUpRight: number
  cheekPuff: number
  cheekSquintLeft: number
  cheekSquintRight: number
  noseSneerLeft: number
  noseSneerRight: number
  browDownLeft: number
  browDownRight: number
  browInnerUp: number
  browOuterUpLeft: number
  browOuterUpRight: number
  tongueOut: number
  [key: string]: number
}

// Optional: what a MetaHuman embodiment must do when receiving a FrameState
// from the legacy pipeline (kept for compatibility — the abstraction consumes
// CharacterFrame; this shows the conversion seam).
export type FrameStateSink = (frame: FrameState) => void
