// frontend/src/core/simulation/types.ts

/**
 * ZARAM CONSTITUTIONAL COMPLIANCE:
 * This file operates strictly in Stage 2 (Simulation) of the 4-Stage Pipeline.
 * PROHIBITED: Importing React, Three.js, Visual types, or Semantic/Memory logic.
 * RULE: This file defines pure mathematical state and forces.
 * See: 00_ZARAM_CONSTITUTION/RuntimeModel.md
 */

export interface Vector3 { 
  x: number; 
  y: number; 
  z: number; 
}

export interface SimulationNode {
  id: string;
  position: Vector3;
  velocity: Vector3;
  acceleration: Vector3;
  mass: number; // Derived from semanticMass, purely mathematical here
  constraints?: { locked?: boolean; orbitTargetId?: string };
}

export interface SimulationState {
  nodes: SimulationNode[];
  timestamp: number;
}

export interface NodeForce {
  nodeId: string;
  vector: Vector3;
}

export interface SpatialForces {
  forces: NodeForce[];
}