# ZARAM EMBODIMENT CATALOG (Implementation Specification)

**Version:** 1.0 | **Status:** Frozen | **Target:** R3F / WebGL Engine

---

## 1. LIVING ORB (Energy DNA)
*   **Purpose:** Central consciousness anchor.
*   **GLB:** `geo_energy_core_master.glb` | **Shader:** `shader_liquid_energy`
*   **Particles:** `particle_thinking_energy` (internal volumetric motes).
*   **LODs:** L0: Ray-marched fluid (8k tris). L1: PBR sphere w/ animated normals (2k tris). L2: Emissive sphere (100 tris).
*   **Interactions:** Hover: Scale 1.05x, noise freq +20%. Selected: Bloom pulse. Speaking: Audio-reactive vertex displacement.
*   **Context Menu:** Settings, Sleep Mode, Change Embodiment.
*   **Perf Budget:** Max 2ms GPU for L0. Fallback to L1 if < 45 FPS.

## 2. PROJECTS (Monument DNA)
*   **Purpose:** Heavy, anchored foundations of work.
*   **GLB:** `geo_monolith_master.glb` | **Shader:** `shader_obsidian`
*   **Particles:** None.
*   **LODs:** L0: Beveled box w/ parallax (5k tris). L1: Static textured block (1k tris). L2: Solid dark cube (12 tris).
*   **Interactions:** Hover: Circuitry emissive intensity +50%. Double-click: Zoom into Sub-Universe.
*   **Context Menu:** Open Project, View Tasks, Archive.
*   **Sub-Universe:** Yes (Contains Docs, Tasks, Agents).

## 3. MEMORIES (Crystal DNA)
*   **Purpose:** Ephemeral, precious, contextual data.
*   **GLB:** `geo_crystal_master.glb` | **Shader:** `shader_crystal_refraction`
*   **Particles:** `particle_memory_sparks` (slow drift outward).
*   **LODs:** L0: Multi-faceted refractive (2k tris). L1: Basic glass (200 tris). L2: Glowing sprite (4 tris).
*   **Interactions:** Hover: Chromatic aberration +30%. Selected: Flare brightly, drift toward Orb.
*   **Context Menu:** Recall, Pin, Delete, Edit.

## 4. AGENTS (Mechanical DNA)
*   **Purpose:** Autonomous workers.
*   **GLB:** `geo_mech_block_master.glb` | **Shader:** `shader_titanium` + `shader_neon_circuit`
*   **Particles:** `particle_agent_thrusters` (micro-bursts on movement).
*   **LODs:** L0: High-poly rings (4k tris). L1: Merged rings (800 tris). L2: Cyan point light (0 tris).
*   **Interactions:** Hover: Rings lock, status beam projects. Selected: Halts patrol, displays task queue.
*   **Context Menu:** Assign Task, View Status, Terminate.

## 5. DOCUMENTS (Glass DNA)
*   **Purpose:** Static knowledge, text, files.
*   **GLB:** `geo_glass_panel_master.glb` | **Shader:** `shader_frosted_glass`
*   **Particles:** None.
*   **LODs:** L0: Glass w/ text mask (200 tris). L1: Opaque plane (4 tris). L2: Sprite (4 tris).
*   **Interactions:** Hover: Flattens to face camera, edge glow. Selected: Expands to read size.
*   **Context Menu:** Open, Summarize, Share, Delete.

## 6. FOLDERS (Glass DNA)
*   **Purpose:** Containment without walls.
*   **GLB:** `geo_glass_panel_master.glb` (scaled) | **Shader:** `shader_wireframe_glow`
*   **Particles:** Internal volumetric fog.
*   **LODs:** L0: Glowing tubes (500 tris). L1: Line renderer (24 tris). L2: Culled (0 tris).
*   **Interactions:** Hover: Interior fog brightens. Double-click: Expands to reveal children.

## 7. CODE (Mechanical DNA)
*   **Purpose:** Structured, logical, executable data.
*   **GLB:** `geo_mech_block_master.glb` (scaled) | **Shader:** `shader_neon_circuit`
*   **Particles:** None.
*   **LODs:** L0: Layered plates (400 tris). L1: Single plate (100 tris). L2: Green line (20 tris).
*   **Interactions:** Hover: Scroll speed 2x. Selected: Snaps to grid, highlights syntax.

## 8. CONVERSATION (Energy DNA)
*   **Purpose:** Flow of dialogue.
*   **GLB:** `geo_energy_core_master.glb` (torus variant) | **Shader:** `shader_ribbon`
*   **Particles:** None.
*   **LODs:** L0: Vertex-displaced ribbon (3k tris). L1: Alpha-mapped ring (100 tris). L2: Particle ring (200 tris).
*   **Interactions:** Hover: Undulation amplitude +50%. Selected: Freezes time, isolates audio track.

## 9. RESEARCH (Crystal DNA)
*   **Purpose:** Gathering disparate threads.
*   **GLB:** `geo_crystal_master.glb` | **Shader:** `shader_crystal_refraction`
*   **Particles:** Orbiting micro-nodes.
*   **LODs:** L0: Orbital array (2k tris). L1: Wireframe sphere (500 tris). L2: Blue particle (50 tris).
*   **Interactions:** Hover: Orbit speed 2x. Selected: Expands rings to show source nodes.

## 10. WEBSITES (Glass DNA)
*   **Purpose:** Windows to external world.
*   **GLB:** `geo_glass_panel_master.glb` (curved) | **Shader:** `shader_hologram`
*   **Particles:** None.
*   **LODs:** L0: Curved mesh w/ texture (1k tris). L1: Flat plane (4 tris). L2: Colored square (4 tris).
*   **Interactions:** Hover: Scanline speed increases. Selected: Opens full browser overlay.

## 11. TASKS (Mechanical DNA)
*   **Purpose:** Metrics counting down.
*   **GLB:** `geo_mech_block_master.glb` (torus variant) | **Shader:** `shader_matte_emissive`
*   **Particles:** None.
*   **LODs:** L0: 3D torus w/ mask (800 tris). L1: 2D sprite (4 tris). L2: Dot (50 tris).
*   **Interactions:** Hover: Radial fill pulses. Selected: Opens task detail panel.

## 12. CALENDAR (Mechanical DNA)
*   **Purpose:** Time mapped to spatial distance.
*   **GLB:** `geo_mech_block_master.glb` (ring variant) | **Shader:** `shader_subtle_line`
*   **Particles:** None.
*   **LODs:** L0: Thin cylinders (2k tris). L1: Line renderer (200 tris). L2: Culled (0 tris).
*   **Interactions:** Hover: Markers glow. Selected: Expands to show day/week view.

## 13. METAHUMAN (Energy DNA - Future)
*   **Purpose:** Empathy and intelligence.
*   **GLB:** `geo_energy_core_master.glb` (placeholder) | **Shader:** `shader_sss_skin`
*   **Particles:** None.
*   **LODs:** L0: Skeletal mesh (50k tris). L1: Low-poly PBR (10k tris). L2: Reverts to Orb.
*   **Interactions:** Hover: Eye contact. Selected: Full-screen conversation mode.