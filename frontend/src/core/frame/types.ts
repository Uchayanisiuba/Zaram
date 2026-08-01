// frontend/src/core/frame/types.ts
//
// ZARAM CONSTITUTIONAL COMPLIANCE:
// This file operates strictly in Stage 3 (Frame) of the 4-Stage Pipeline.
// PROHIBITED: Importing React, Three.js, or Simulation/Visual types.
// RULE: This file defines the sacred FrameState contract consumed by ALL renderers.
// See: 00_ZARAM_CONSTITUTION/RuntimeModel.md

import { PresenceState } from '../../theme/presenceTheme';

export interface VisualFrame {
  presence: number;    // 0.0 - 1.0, overall presence intensity
  energy: number;      // 0.0 - 1.0, energy/animation intensity
  focus: number;       // 0.0 - 1.0, focus/attention level
  activity: number;    // 0.0 - 1.0, activity/busyness level
}

export interface AudioFrame {
  voiceLevel: number;        // 0.0 - 1.0, current speech output level
  microphoneLevel: number;   // 0.0 - 1.0, current mic input level
  rmsLevel?: number;         // 0.0 - 1.0, real-time audio RMS (for reactive visuals)
  smoothedRms?: number;      // 0.0 - 1.0, smoothed RMS for fluid animation
}

export interface EmotionFrame {
  calmness: number;
  confidence: number;
  curiosity: number;
  warmth: number;
  empathy: number;
  playfulness: number;
}

export interface SystemFrame {
  state: PresenceState;      // Current presence state (drives color/theme)
  cognitiveLoad: number;     // 0.0 - 1.0, mental workload
  adaptiveQuality: number;   // 0.0 - 1.0, rendering quality setting
  visualIdentity: string;    // e.g., 'orb-v2', 'orb-v1'
}

export interface MetadataFrame {
  timestamp: number;
  correlationId: string;
  version: string;
}

/**
 * Sacred FrameState Contract
 * 
 * This is the SINGLE source of truth for all renderers:
 * - OrbEngine (2D Canvas)
 * - LivingOrbCenter (Three.js/R3F)
 * - Any future renderer
 * 
 * Produced by FrameComposer (Stage 3) from SimulationState (Stage 2) + Environment.
 * Consumed by renderers (Stage 4) with zero transformation.
 */
export interface FrameState {
  visual: VisualFrame;
  audio: AudioFrame;
  emotion: EmotionFrame;
  system: SystemFrame;
  metadata: MetadataFrame;
  sequence: number;  // Monotonically increasing frame counter
}

// Default/Idle frame for initialization
export const IDLE_FRAME: FrameState = {
  visual: { presence: 0.5, energy: 0.4, focus: 0.6, activity: 0.3 },
  audio: { voiceLevel: 0, microphoneLevel: 0, rmsLevel: 0, smoothedRms: 0 },
  emotion: { calmness: 0.5, confidence: 0.5, curiosity: 0.5, warmth: 0.5, empathy: 0.5, playfulness: 0.5 },
  system: { state: 'Idle', cognitiveLoad: 0.2, adaptiveQuality: 1.0, visualIdentity: 'orb-v2' },
  metadata: { timestamp: 0, correlationId: 'idle', version: '1.0.0' },
  sequence: 0,
};