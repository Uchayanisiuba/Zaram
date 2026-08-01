# ZARAM PARTICLE LIBRARY (Implementation Specification)

**Version:** 1.0 | **Status:** Frozen | **Target:** Three.js Points / InstancedMesh

---

## 1. Memory Sparks (`particle_memory_sparks`)
*   **Purpose:** Emitted by Memories on spawn/recall.
*   **Spawn Rate:** Burst of 20-30 on event.
*   **Lifetime:** 1.5s - 3.0s.
*   **Velocity:** Low outward radial (0.2 - 0.5 m/s).
*   **Noise:** High turbulence (Brownian motion).
*   **Blend Mode:** `AdditiveBlending`.
*   **GPU/CPU:** CPU (low count).
*   **LOD Rules:** Disabled at LOD2.

## 2. Search Dust (`particle_search_dust`)
*   **Purpose:** Ambient universe atmosphere, highlights search paths.
*   **Spawn Rate:** Continuous, 5000 total pool.
*   **Lifetime:** Infinite (recycled).
*   **Velocity:** Near zero (0.01 m/s drift).
*   **Noise:** Perlin noise flow field.
*   **Blend Mode:** `AdditiveBlending`, low opacity (0.1).
*   **GPU/CPU:** GPU (InstancedMesh or Points).
*   **LOD Rules:** Density reduced by 50% at LOD1, 90% at LOD2.

## 3. Portal Fragments (`particle_portal_fragments`)
*   **Purpose:** Emitted when opening/closing Sub-Universes.
*   **Spawn Rate:** Burst of 100.
*   **Lifetime:** 0.5s - 1.0s.
*   **Velocity:** High inward/outward radial (2.0 - 5.0 m/s).
*   **Noise:** None (linear trajectories).
*   **Blend Mode:** `NormalBlending`.
*   **GPU/CPU:** CPU.
*   **LOD Rules:** Disabled at LOD1 and LOD2.

## 4. Thinking Energy (`particle_thinking_energy`)
*   **Purpose:** Internal Living Orb activity.
*   **Spawn Rate:** Continuous, 50 total pool (internal to Orb mesh).
*   **Lifetime:** 0.5s.
*   **Velocity:** Orbital around center.
*   **Noise:** Curl noise.
*   **Blend Mode:** `AdditiveBlending`.
*   **GPU/CPU:** GPU (Shader-based, not actual particles).
*   **LOD Rules:** Replaced by texture animation at LOD1.

## 5. Learning Streams (`particle_learning_streams`)
*   **Purpose:** Visualizing data ingestion.
*   **Spawn Rate:** Continuous flow along edge paths.
*   **Lifetime:** 2.0s.
*   **Velocity:** Follows edge curve (1.0 m/s).
*   **Noise:** None.
*   **Blend Mode:** `AdditiveBlending`.
*   **GPU/CPU:** GPU (Shader UV scroll on edge geometry).
*   **LOD Rules:** Disabled at LOD2.

## 6. Conversation Ripples (`particle_conversation_ripples`)
*   **Purpose:** Audio visualization from Orb.
*   **Spawn Rate:** Triggered by audio amplitude.
*   **Lifetime:** 1.0s.
*   **Velocity:** Expanding sphere (3.0 m/s).
*   **Noise:** None.
*   **Blend Mode:** `AdditiveBlending`.
*   **GPU/CPU:** CPU (Ring geometry scaling).
*   **LOD Rules:** Disabled at LOD2.

## 7. Agent Thrusters (`particle_agent_thrusters`)
*   **Purpose:** Agent movement feedback.
*   **Spawn Rate:** Continuous while moving.
*   **Lifetime:** 0.2s.
*   **Velocity:** Opposite to movement direction.
*   **Noise:** Low.
*   **Blend Mode:** `AdditiveBlending`.
*   **GPU/CPU:** CPU.
*   **LOD Rules:** Disabled at LOD1 and LOD2.