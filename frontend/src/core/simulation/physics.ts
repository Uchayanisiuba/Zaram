import { SimulationState, SpatialForces, NodeForce } from './types';
import { SpatialGraph } from '../semantic/types';

/**
 * Semantic Physics Engine.
 * Calculates forces based on Semantic Mass. NEVER mutates state.
 */
export class SemanticPhysicsEngine {
  private readonly GRAVITY_CONSTANT = 0.05;
  private readonly REPULSION_CONSTANT = 0.2;

  calculateForces(graph: SpatialGraph, state: SimulationState, dt: number): SpatialForces {
    const forces: NodeForce[] = [];

    for (const simNode of state.nodes) {
      if (simNode.constraints?.locked) {
        forces.push({ nodeId: simNode.id, vector: { x: 0, y: 0, z: 0 } });
        continue;
      }

      let fx = 0, fy = 0, fz = 0;
      const semanticNode = graph.nodes.find(n => n.id === simNode.id);
      if (!semanticNode) {
        forces.push({ nodeId: simNode.id, vector: { x: 0, y: 0, z: 0 } });
        continue;
      }

      // 1. Semantic Gravity (Pull toward center 0,0,0 based on mass)
      const gravityFactor = simNode.mass * this.GRAVITY_CONSTANT * dt;
      fx -= simNode.position.x * gravityFactor;
      fy -= simNode.position.y * gravityFactor;
      fz -= simNode.position.z * gravityFactor;

      // 2. Semantic Repulsion (Push away from other nodes to prevent overlap)
      for (const otherSim of state.nodes) {
        if (otherSim.id === simNode.id) continue;
        const dx = simNode.position.x - otherSim.position.x;
        const dy = simNode.position.y - otherSim.position.y;
        const dz = simNode.position.z - otherSim.position.z;
        const distSq = dx * dx + dy * dy + dz * dz + 0.01; // Avoid division by zero
        
        const repulsion = this.REPULSION_CONSTANT / distSq;
        fx += dx * repulsion;
        fy += dy * repulsion;
        fz += dz * repulsion;
      }

      // 3. Edge Attraction (Connected nodes attract each other)
      const connectedEdges = graph.edges.filter(e => e.sourceId === simNode.id || e.targetId === simNode.id);
      for (const edge of connectedEdges) {
        const otherId = edge.sourceId === simNode.id ? edge.targetId : edge.sourceId;
        const otherSim = state.nodes.find(n => n.id === otherId);
        if (!otherSim) continue;

        const dx = otherSim.position.x - simNode.position.x;
        const dy = otherSim.position.y - simNode.position.y;
        const dz = otherSim.position.z - simNode.position.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01;

        const attraction = edge.semanticStrength * 0.02 * dt;
        fx += (dx / dist) * attraction;
        fy += (dy / dist) * attraction;
        fz += (dz / dist) * attraction;
      }

      forces.push({ nodeId: simNode.id, vector: { x: fx, y: fy, z: fz } });
    }

    return { forces };
  }
}