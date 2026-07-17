// desktop/src/runtime/embodiment/gnm.ts
//
// PART 7 — GNM Preparation (INTERFACES ONLY)
//
// Scaffolding for a future GNM (Generative Neural Mesh) head generator. GNM will
// eventually implement these. NO GNM dependency today. The interfaces describe
// how a generated head + its morph targets + face topology plug into the
// embodiment framework as a head source.

import { CharacterFrame } from './types'
import { ARKitBlendshapeWeights } from './metahuman'

// Describes a generated head: identity signature, resolution, seed, etc.
export interface HeadDescriptor {
  id: string
  // Persistent visual-identity seed (0..1) aligning with FrameState visualIdentity.
  visualIdentity: number
  // Generator/model version that produced the head.
  generatorVersion: string
  // Topology reference this head was built against.
  topologyId: string
  // Morph target set this head exposes.
  morphTargetSetId: string
  // Optional metadata (quality tiers, LODs).
  metadata?: Record<string, unknown>
}

// The connectivity/vertex layout of a generated face. Pure data description.
export interface FaceTopology {
  id: string
  // Vertex count; enough for a renderer/rig to bind morph targets.
  vertexCount: number
  // Named regions used to bind expressions to anatomy (brows, lips, lids...).
  regions: ReadonlyArray<{ name: string; vertexRange: [number, number] }>
  // UV / seam hints for future texture projection (optional).
  uvChannels?: number
}

// A named set of morph targets (blendshapes) a generated head can pose with.
export interface MorphTargetSet {
  id: string
  // Canonical shape names this set exposes (may align with ARKit semantics).
  shapes: ReadonlyArray<string>
  // Default pose weights.
  neutral: Readonly<Record<string, number>>
  // Optional remap from ARKit blendshape names to this set's shape names.
  arkitRemap?: Readonly<Record<string, string>>
}

// The generator contract GNM will implement: produce a head descriptor, its
// topology and morph target set from a visual-identity seed.
export interface IHeadGenerator {
  readonly id: string
  // Generate (or retrieve cached) head assets for a visual identity.
  generate(visualIdentity: number): Promise<HeadDescriptor>
  // Return the topology bound to a head descriptor.
  getTopology(descriptor: HeadDescriptor): FaceTopology
  // Return the morph target set bound to a head descriptor.
  getMorphTargets(descriptor: HeadDescriptor): MorphTargetSet
  // Translate a CharacterFrame into this set's morph weights.
  pose(descriptor: HeadDescriptor, frame: CharacterFrame): Record<string, number>
  // Convenience: map a frame to ARKit weights via this generator's remap.
  toARKit(descriptor: HeadDescriptor, frame: CharacterFrame): ARKitBlendshapeWeights
}
