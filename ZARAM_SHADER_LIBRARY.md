# ZARAM SHADER LIBRARY (Implementation Specification)

**Version:** 1.0 | **Status:** Frozen | **Target:** Three.js / R3F ShaderMaterial

---

## 1. Liquid Energy (`shader_liquid_energy`)
*   **Purpose:** Living Orb core, volatile cognitive energy.
*   **Material Inputs:** `u_emissiveColor` (vec3), `u_pulseIntensity` (float), `u_noiseScale` (float).
*   **Texture Inputs:** `u_normalMap` (for L1 fallback), `u_noiseTex` (3D noise for raymarching).
*   **Animation:** Curl noise displacement in vertex shader; fresnel pulse in fragment.
*   **Perf Cost:** High (Raymarching). Fallback to L1 PBR if FPS < 45.
*   **Renderer Notes:** Requires `toneMapped={false}` for HDR bloom.

## 2. Frosted Glass (`shader_frosted_glass`)
*   **Purpose:** Documents, UI panels.
*   **Material Inputs:** `u_blurStrength` (float), `u_transmission` (float), `u_ior` (float, default 1.5).
*   **Texture Inputs:** None (uses screen-space backdrop blur).
*   **Animation:** Static. Edge fresnel reacts to camera angle.
*   **Perf Cost:** Medium (Post-processing pass).
*   **Renderer Notes:** Use `@react-three/postprocessing` or Three.js `MeshPhysicalMaterial` transmission.

## 3. Crystal Refraction (`shader_crystal_refraction`)
*   **Purpose:** Memories, Research.
*   **Material Inputs:** `u_chromaticAberration` (float), `u_internalGlow` (vec3).
*   **Texture Inputs:** `u_envMap` (for reflections).
*   **Animation:** Refraction angle shifts slightly based on camera position.
*   **Perf Cost:** Medium-High.
*   **Renderer Notes:** Requires environment map for specular highlights.

## 4. Portal / Hologram (`shader_hologram`)
*   **Purpose:** Websites, external data.
*   **Material Inputs:** `u_scanlineSpeed` (float), `u_rgbSplit` (float).
*   **Texture Inputs:** `u_diffuseMap` (content), `u_noiseMap` (for glitch effect).
*   **Animation:** UV scroll for scanlines; time-based RGB channel offset.
*   **Perf Cost:** Low.
*   **Renderer Notes:** Use `AdditiveBlending` for the glow, `NormalBlending` for the core.

## 5. Obsidian (`shader_obsidian`)
*   **Purpose:** Projects, Monuments.
*   **Material Inputs:** `u_roughness` (0.05), `u_metalness` (0.9), `u_circuitEmissive` (vec3).
*   **Texture Inputs:** `u_albedoMap`, `u_normalMap`, `u_circuitMaskMap`.
*   **Animation:** `u_circuitMaskMap` UV scroll for pulsing light tracks.
*   **Perf Cost:** Low (Standard PBR).
*   **Renderer Notes:** High contrast between dark base and bright emissive circuits.

## 6. Titanium (`shader_titanium`)
*   **Purpose:** Agents, mechanical parts.
*   **Material Inputs:** `u_anisotropy` (float), `u_anisotropyRotation` (float).
*   **Texture Inputs:** `u_metalnessMap`, `u_roughnessMap`.
*   **Animation:** Static material, relies on geometry rotation for highlights.
*   **Perf Cost:** Low.
*   **Renderer Notes:** Use `MeshStandardMaterial` with anisotropy enabled.

## 7. Neon Circuit (`shader_neon_circuit`)
*   **Purpose:** Code, Tasks.
*   **Material Inputs:** `u_traceColor` (vec3), `u_scrollSpeed` (float).
*   **Texture Inputs:** `u_traceMaskMap` (tileable).
*   **Animation:** UV Y-axis scroll based on `u_time * u_scrollSpeed`.
*   **Perf Cost:** Low.
*   **Renderer Notes:** Emissive channel only; base color is near-black.

## 8. Ribbon (`shader_ribbon`)
*   **Purpose:** Conversation, search trails.
*   **Material Inputs:** `u_fresnelPower` (float), `u_colorA` (vec3), `u_colorB` (vec3).
*   **Texture Inputs:** `u_alphaMap` (for ribbon shape).
*   **Animation:** Vertex displacement via sine waves; color interpolation based on view angle.
*   **Perf Cost:** Medium.
*   **Renderer Notes:** Requires high segment count on geometry for smooth vertex displacement.

## 9. Living Plasma (`shader_living_plasma`)
*   **Purpose:** Internal Orb details, high-energy states.
*   **Material Inputs:** `u_plasmaSpeed` (float), `u_plasmaScale` (float).
*   **Texture Inputs:** `u_plasmaNoise` (3D texture).
*   **Animation:** 3D noise sampling in fragment shader over time.
*   **Perf Cost:** High.
*   **Renderer Notes:** Strictly for LOD0 of the Living Orb.