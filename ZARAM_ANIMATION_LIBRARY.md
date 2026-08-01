# ZARAM ANIMATION LIBRARY (Implementation Specification)

**Version:** 1.0 | **Status:** Frozen | **Target:** R3F `useFrame` / Spring Physics

---

## 1. Breathing (`anim_breathing`)
*   **Purpose:** Universal idle state for all living species.
*   **Inputs:** `time` (float), `baseScale` (float).
*   **Outputs:** `scale` (vec3).
*   **Duration:** Continuous (4s cycle).
*   **Curves:** Sine wave: `1.0 + sin(time * 1.5) * 0.02`.
*   **FrameState Hook:** Multiplier increases with `frameState.visual.energy`.

## 2. Floating (`anim_floating`)
*   **Purpose:** Idle drift for Documents, Memories.
*   **Inputs:** `time`, `seed` (float), `basePos` (vec3).
*   **Outputs:** `position` (vec3).
*   **Duration:** Continuous.
*   **Curves:** Perlin noise on X/Y axes.
*   **FrameState Hook:** Amplitude increases in "Night" presence state.

## 3. Orbit (`anim_orbit`)
*   **Purpose:** Agents, Research nodes, Project satellites.
*   **Inputs:** `time`, `radius`, `speed`, `inclination`.
*   **Outputs:** `position`, `rotation`.
*   **Duration:** Continuous.
*   **Curves:** Circular math: `x = cos(t*s)*r`, `z = sin(t*s)*r`.
*   **FrameState Hook:** Speed increases on Hover.

## 4. Snap (`anim_snap`)
*   **Purpose:** Code, Tasks (rigid objects).
*   **Inputs:** `currentPos`, `targetPos`.
*   **Outputs:** `position`.
*   **Duration:** 0.1s.
*   **Curves:** Linear or sharp ease-out. No spring.
*   **FrameState Hook:** None.

## 5. Bloom / Pulse (`anim_bloom`)
*   **Purpose:** Selection, Speaking, Alerts.
*   **Inputs:** `triggerTime`, `intensity`.
*   **Outputs:** `emissiveIntensity`, `scale`.
*   **Duration:** 0.5s.
*   **Curves:** Sharp attack, exponential decay.
*   **FrameState Hook:** Triggered by `frameState.audio.voiceLevel`.

## 6. Crystal Expansion (`anim_crystal_expand`)
*   **Purpose:** Memory recall, Research focus.
*   **Inputs:** `isExpanded` (bool).
*   **Outputs:** `scale`, `rotation`.
*   **Duration:** 0.8s.
*   **Curves:** Spring physics (Stiffness: 150, Damping: 15).
*   **FrameState Hook:** Triggered by Search Focus.

## 7. Ribbon Flow (`anim_ribbon_flow`)
*   **Purpose:** Conversation trails.
*   **Inputs:** `time`, `audioLevel`.
*   **Outputs:** Vertex displacement (Y-axis).
*   **Duration:** Continuous.
*   **Curves:** Sine wave modulated by audio amplitude.
*   **FrameState Hook:** Directly mapped to `frameState.audio.voiceLevel`.

## 8. Portal Spin (`anim_portal_spin`)
*   **Purpose:** Websites, Folders opening.
*   **Inputs:** `isOpen` (bool).
*   **Outputs:** `rotation.z`.
*   **Duration:** 1.0s.
*   **Curves:** Ease-in-out cubic.
*   **FrameState Hook:** Triggered by Double-click.

## 9. Agent Patrol (`anim_agent_patrol`)
*   **Purpose:** Agent idle movement.
*   **Inputs:** `waypoints` (vec3[]).
*   **Outputs:** `position`, `lookAt`.
*   **Duration:** Variable.
*   **Curves:** Linear interpolation between waypoints, smooth turn at nodes.
*   **FrameState Hook:** Pauses when `frameState.system.state === 'thinking'`.

## 10. Hover (`anim_hover`)
*   **Purpose:** Universal interaction feedback.
*   **Inputs:** `isHovered` (bool).
*   **Outputs:** `scale`, `emissiveIntensity`.
*   **Duration:** 0.2s.
*   **Curves:** Spring physics (Stiffness: 300, Damping: 20).
*   **FrameState Hook:** Triggered by Raycaster intersection.

## 11. Selection (`anim_selection`)
*   **Purpose:** Locking focus.
*   **Inputs:** `isSelected` (bool).
*   **Outputs:** `scale`, `emissiveIntensity`, `outlineThickness`.
*   **Duration:** 0.3s.
*   **Curves:** Spring physics (Stiffness: 200, Damping: 15).
*   **FrameState Hook:** Triggered by Click.

## 12. Search Focus (`anim_search_focus`)
*   **Purpose:** Camera and node reaction to search.
*   **Inputs:** `isTarget` (bool), `distanceToTarget` (float).
*   **Outputs:** Node `opacity`, Camera `position/fov`.
*   **Duration:** 1.5s.
*   **Curves:** Cubic bezier for camera; exponential fade for non-targets.
*   **FrameState Hook:** Triggered by Search Event.