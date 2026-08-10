import type { Vector3 } from '../simulation/types';

export type SemanticNodeType = 'concept' | 'entity' | 'relation' | 'memory' | 'action' | 'agent';

export type KnowledgeArchetype = 'entity' | 'relationship' | 'process' | 'concept' | 'agent' | 'memory' | 'task';

export type EdgeType = 'semantic' | 'temporal' | 'hierarchical' | 'associative';

export interface SpatialNodeMetadata {
  runtimeSignature?: string;
  lastAccessed?: number;
  confidence?: number;
}

export interface SpatialNode {
  id: string;
  type: SemanticNodeType;
  label: string;
  archetype?: KnowledgeArchetype;
  semanticMass: number;
  clusterId?: string;
  neighborhoodId?: string;
  presenceReactivity?: number;
  metadata?: SpatialNodeMetadata;
}

export interface SpatialEdge {
  id: string;
  sourceId: string;
  targetId: string;
  semanticStrength: number;
  edgeType?: EdgeType;
}

export interface SpatialGraph {
  nodes: SpatialNode[];
  edges: SpatialEdge[];
}

export interface Neighborhood {
  id: string;
  label: string;
  position: Vector3;
  color: string;
  icon: string;
}

export const ARCHETYPE_METADATA: Record<KnowledgeArchetype, { meshProfile: string; defaultRadius: number; color: string }> = {
  entity: { meshProfile: 'sphere', defaultRadius: 0.5, color: '#ffffff' },
  relationship: { meshProfile: 'ring', defaultRadius: 0.4, color: '#fbbf24' },
  process: { meshProfile: 'cylinder', defaultRadius: 0.3, color: '#34d399' },
  concept: { meshProfile: 'sphere', defaultRadius: 0.6, color: '#c084fc' },
  agent: { meshProfile: 'capsule', defaultRadius: 0.7, color: '#22d3ee' },
  memory: { meshProfile: 'octahedron', defaultRadius: 0.45, color: '#f59e0b' },
  task: { meshProfile: 'box', defaultRadius: 0.5, color: '#ef4444' },
};

export const SEMANTIC_NODE_TYPES: SemanticNodeType[] = ['concept', 'entity', 'relation', 'memory', 'action', 'agent'];

export const NEIGHBORHOODS: Neighborhood[] = [
  { id: 'memory', label: 'Memory', position: { x: -3, y: 2, z: 0 }, color: '#c084fc', icon: 'brain' },
  { id: 'knowledge', label: 'Knowledge', position: { x: 3, y: 2, z: 0 }, color: '#22d3ee', icon: 'book' },
  { id: 'canvas', label: 'Canvas', position: { x: 3, y: -2, z: 0 }, color: '#34d399', icon: 'palette' },
  { id: 'projects', label: 'Projects', position: { x: -3, y: -2, z: 0 }, color: '#fbbf24', icon: 'code' },
];
