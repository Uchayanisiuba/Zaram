/**
 * ZARAM CONSTITUTIONAL COMPLIANCE:
 * This file operates strictly in Stage 2 (Simulation) of the 4-Stage Pipeline.
 * PROHIBITED: Importing React, Three.js, or Semantic/Memory logic.
 * RULE: This engine only calculates and outputs SpatialForces. It never mutates the Semantic Graph.
 * See: 00_ZARAM_CONSTITUTION/RuntimeModel.md
 */
import { SimulationState, SimulationNode } from './types';
import { SemanticPhysicsEngine } from './physics';
import { SpatialGraph } from '../semantic/types';

/**
 * Simulation Runtime.
 * Applies forces to update SimulationState.
 */
export class SimulationRuntime {
  private physicsEngine: SemanticPhysicsEngine;
  private state: SimulationState;

  constructor(initialState: SimulationState) {
    this.physicsEngine = new SemanticPhysicsEngine();
    this.state = initialState;
  }

  tick(graph: SpatialGraph, deltaTime: number): SimulationState {
    const forces = this.physicsEngine.calculateForces(graph, this.state, deltaTime);
    
    const DAMPING = 0.98;
    const updatedNodes: SimulationNode[] = this.state.nodes.map(node => {
      const force = forces.forces.find(f => f.nodeId === node.id);
      if (!force) return node;

      // Apply forces to acceleration
      const ax = force.vector.x;
      const ay = force.vector.y;
      const az = force.vector.z;

      // Update velocity and apply damping
      let vx = (node.velocity.x + ax * deltaTime) * DAMPING;
      let vy = (node.velocity.y + ay * deltaTime) * DAMPING;
      let vz = (node.velocity.z + az * deltaTime) * DAMPING;

      // Update position
      const px = node.position.x + vx * deltaTime;
      const py = node.position.y + vy * deltaTime;
      const pz = node.position.z + vz * deltaTime;

      return {
        ...node,
        position: { x: px, y: py, z: pz },
        velocity: { x: vx, y: vy, z: vz },
        acceleration: { x: ax, y: ay, z: az },
      };
    });

    this.state = {
      nodes: updatedNodes,
      timestamp: Date.now(),
    };

    return this.state;
  }

  getState(): SimulationState {
    return this.state;
  }

  addNode(node: SimulationNode): void {
    const exists = this.state.nodes.find(n => n.id === node.id);
    if (!exists) {
      this.state = {
        ...this.state,
        nodes: [...this.state.nodes, node],
      };
    }
  }

  removeNode(nodeId: string): void {
    this.state = {
      ...this.state,
      nodes: this.state.nodes.filter(n => n.id !== nodeId),
    };
  }
}