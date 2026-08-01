// frontend/src/core/visual/types.ts

/**
 * ZARAM CONSTITUTIONAL COMPLIANCE:
 * This file operates strictly in Stage 4 (Visual) of the 4-Stage Pipeline.
 * PROHIBITED: Importing React, Three.js, or Semantic/Memory logic.
 * RULE: This file defines pure aesthetic properties derived statelessly from Stage 2 & 3.
 * See: 00_ZARAM_CONSTITUTION/RuntimeModel.md
 */

import { SemanticNodeType, KnowledgeArchetype, ARCHETYPE_METADATA } from '../semantic/types';
import { Vector3 } from '../simulation/types';
import { PresenceState } from '../../theme/presenceTheme';

export type { PresenceState } from '../../theme/presenceTheme';
export type RuntimeSignature = 'memory' | 'knowledge' | 'reasoning' | 'planning' | 'plugin' | 'voice' | 'default';

export interface NodeStyle {
  color: string;
  radius: number;
  meshProfile: string;
  emissiveIntensity: number;
}

export interface VisualTheme {
  id: string;
  name: string;
  nodeStyles: Record<SemanticNodeType, NodeStyle>;
  edgeStyle: { color: string; thickness: number; opacity: number };
  signatureColors: Record<RuntimeSignature, string>;
  // Presence-driven theme overrides
  presenceColors?: Record<PresenceState, { primary: string; glow: string; ambient: string }>;
}

export interface VisualNode {
  id: string;
  position: Vector3;
  velocity: Vector3;
  radius: number;
  color: string;
  scale: number;
  opacity: number;
  meshProfile: string;
  emissiveIntensity: number;
  heat: number;            // 0.0 (cold) to 1.0 (hot)
  confidence: number;      // 0.0 to 1.0
  isIlluminated: boolean;  
  signature: RuntimeSignature;
  // Semantic identity
  type: SemanticNodeType;
  archetype?: KnowledgeArchetype;
  label: string;
  neighborhoodId?: string;
  clusterId?: string;
  // Presence reactivity
  presenceReactivity: number; // 0.0 to 1.0
}

export interface VisualEdge {
  id: string;
  sourcePos: Vector3;
  targetPos: Vector3;
  thickness: number;
  color: string;
  opacity: number;
  isIlluminated: boolean;
  // Energy animation
  energyFlow?: number;      // 0.0 to 1.0 for animated energy
  edgeType?: 'semantic' | 'temporal' | 'hierarchical' | 'associative';
}

export interface VisualState {
  nodes: VisualNode[];
  edges: VisualEdge[];
  // Universe-level state
  activeNeighborhoodId?: string;
  presenceState?: PresenceState;
  cameraPivot?: Vector3;
  zoomLevel: 'universe' | 'neighborhood' | 'cluster' | 'object' | 'detail';
  neighborhoods: NeighborhoodVisualState[];
}

export interface NeighborhoodVisualState {
  id: string;
  label: string;
  position: Vector3;
  color: string;
  icon: string;
  isActive: boolean;
  isHovered: boolean;
  nodeCount: number;
}

// Archetype-specific visual defaults (used by mapper)
export const ARCHETYPE_VISUAL_DEFAULTS: Record<KnowledgeArchetype, {
  meshProfile: string;
  defaultRadius: number;
  baseColor: string;
  emissiveIntensity: number;
}> = Object.fromEntries(
  Object.entries(ARCHETYPE_METADATA).map(([key, meta]) => [
    key as KnowledgeArchetype,
    {
      meshProfile: meta.meshProfile,
      defaultRadius: meta.defaultRadius,
      baseColor: meta.color,
      emissiveIntensity: 0.8,
    }
  ])
) as Record<KnowledgeArchetype, any>;