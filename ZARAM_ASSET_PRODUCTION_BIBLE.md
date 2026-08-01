# ZARAM ASSET PRODUCTION BIBLE

**Version:** 1.0  
**Status:** Frozen (Production Authority)  
**Target Engine:** Zaram Spatial Engine v1.0 (React Three Fiber / Three.js / WebGL)  
**Audience:** 3D Modelers, Technical Artists, Shader Developers  

---

## I. Global Engine & Export Rules

Before modeling any species, the following global rules must be strictly followed to ensure compatibility with the Zaram Spatial Engine.

*   **Coordinate System:** Y-Up, Right-Handed (Standard Three.js).
*   **Scale:** 1 Unit = 1 Meter. (All dimensions below are in meters).
*   **Pivot Point:** All objects must have their pivot/origin at `(0, 0, 0)` at the base or exact center of the object. No floating pivots.
*   **Transforms:** All transforms (Location, Rotation, Scale) must be applied (Frozen) before export.
*   **GLB Export Settings (Blender):**
    *   **Format:** glTF Binary (.glb)
    *   **Compression:** Draco Mesh Compression (Level 6).
    *   **Textures:** KTX2 / Basis Universal compression for all textures. Max texture size: 2048x2048.
    *   **Animations:** Export only skeletal/shape-key animations. Do *not* export transform animations (translation/rotation) as these are handled procedurally by the Zaram Spatial Runtime.
    *   **Materials:** Use Principled BSDF. Ensure "Emission" is connected to the Emissive slot.

---

## II. Species Production Specifications

### 1. The Living Orb
*   **Purpose:** The central consciousness and anchor of the universe.
*   **Visual Story:** A contained star of cognitive energy.
*   **Silhouette:** Perfect sphere.
*   **Dimensions:** 1.0m diameter.
*   **Pivot:** Exact center (0,0,0).
*   **LOD0:** High-res UV sphere (64 segments). Used for ray-marched volumetric shader.
*   **LOD1:** UV sphere (32 segments). Used for complex PBR with animated normal maps.
*   **LOD2:** UV sphere (8 segments). Simple glowing emissive material.
*   **Animation:** Procedural in-engine (Curl noise). No baked animations.
*   **Material Slots:** `Mat_Core` (Emissive/Volumetric), `Mat_Fresnel` (Edge glow).
*   **Texture Slots:** 1x Normal Map (LOD1), 1x Noise Map (LOD0).
*   **Shader:** Custom R3F ShaderMaterial (Ray-marching for LOD0, Standard PBR for LOD1).
*   **Poly Budget:** LOD0: 8k tris | LOD1: 2k tris | LOD2: 100 tris.
*   **Naming Convention:** `geo_orb_lodX`, `mat_orb_core`, `tex_orb_normal`.
*   **Collision:** Sphere collider, radius 0.5m.
*   **Spawn Animation:** Scale from 0 to 1 with spring bounce.
*   **Hover Animation:** Scale to 1.05, increase emissive intensity.

### 2. Projects
*   **Purpose:** Heavy, anchored foundations of work.
*   **Visual Story:** Monolithic, brutalist obelisks.
*   **Silhouette:** Tall, rectangular block with beveled edges.
*   **Dimensions:** 0.8m wide, 0.8m deep, 2.0m tall.
*   **Pivot:** Bottom center (0,0,0).
*   **LOD0:** High-poly beveled box with interior parallax cavity.
*   **LOD1:** Beveled geometric block with baked texture maps.
*   **LOD2:** Solid dark cube (no bevels).
*   **Animation:** Procedural floating (bobbing).
*   **Material Slots:** `Mat_Obsidian` (Core), `Mat_Glass` (Casing), `Mat_Emissive` (Circuitry).
*   **Texture Slots:** 1x Albedo, 1x Normal, 1x Roughness, 1x Emissive (Circuitry).
*   **Poly Budget:** LOD0: 5k tris | LOD1: 1k tris | LOD2: 12 tris.
*   **Naming Convention:** `geo_project_lodX`, `mat_project_obsidian`.
*   **Collision:** Box collider, 0.8 x 0.8 x 2.0.

### 3. Memories
*   **Purpose:** Captured moments of time. Precious, sharp, clear.
*   **Visual Story:** Asymmetrical, faceted crystals.
*   **Silhouette:** Irregular, sharp prism.
*   **Dimensions:** ~0.3m diameter.
*   **Pivot:** Exact center.
*   **LOD0:** High-poly irregular icosahedron (decimated).
*   **LOD1:** Simplified decimated crystal (20 faces).
*   **LOD2:** Glowing white particle / billboard sprite.
*   **Animation:** Procedural rotation and floating.
*   **Material Slots:** `Mat_Diamond` (High IOR, transmission).
*   **Texture Slots:** None (Procedural glass shader).
*   **Poly Budget:** LOD0: 2k tris | LOD1: 200 tris | LOD2: 4 tris (quad).
*   **Naming Convention:** `geo_memory_lodX`, `mat_memory_diamond`.
*   **Collision:** Sphere collider, radius 0.15m.

### 4. Agents
*   **Purpose:** Autonomous workers. Precise, mechanical.
*   **Visual Story:** Gyroscopic rings around a solid core.
*   **Silhouette:** Spherical drone with intersecting rings.
*   **Dimensions:** 0.4m diameter.
*   **Pivot:** Exact center.
*   **LOD0:** High-poly GLB with separate ring meshes for independent rotation.
*   **LOD1:** Simplified procedural rings (merged geometry).
*   **LOD2:** Cyan point light / small glowing sphere.
*   **Animation:** Skeletal/Transform animation for rings (LOD0 only).
*   **Material Slots:** `Mat_Titanium` (Rings), `Mat_Carbon` (Core), `Mat_Cyan_Emissive` (Ports).
*   **Texture Slots:** 1x Metalness/Roughness, 1x Emissive.
*   **Poly Budget:** LOD0: 4k tris | LOD1: 800 tris | LOD2: 50 tris.
*   **Naming Convention:** `geo_agent_lodX`, `geo_agent_ring_01`.
*   **Collision:** Sphere collider, radius 0.2m.

### 5. Documents
*   **Purpose:** Pages of knowledge floating in zero gravity.
*   **Visual Story:** Thin, rectangular panes.
*   **Silhouette:** Flat rectangle with rounded corners.
*   **Dimensions:** 0.4m wide, 0.5m tall, 0.01m thick.
*   **Pivot:** Bottom center.
*   **LOD0:** Plane with thickness, glass shader.
*   **LOD1:** Opaque white plane with text texture.
*   **LOD2:** Flat sprite / billboard.
*   **Animation:** Procedural floating and slight Y-axis rotation.
*   **Material Slots:** `Mat_FrostedGlass`.
*   **Texture Slots:** 1x Text/Content Mask (LOD1).
*   **Poly Budget:** LOD0: 200 tris | LOD1: 4 tris | LOD2: 4 tris.
*   **Naming Convention:** `geo_doc_lodX`, `mat_doc_glass`.
*   **Collision:** Box collider, 0.4 x 0.5 x 0.01.

### 6. Code
*   **Purpose:** The matrix of logic. Strict, rigid.
*   **Visual Story:** Vertical cascades, geometric pillars.
*   **Silhouette:** Tall, thin rectangular prism.
*   **Dimensions:** 0.2m wide, 0.2m deep, 1.5m tall.
*   **Pivot:** Bottom center.
*   **LOD0:** Layered depth plates with scrolling UVs.
*   **LOD1:** Single plate with scrolling texture.
*   **LOD2:** Green line segment / thin box.
*   **Animation:** UV scrolling (Shader). No mesh animation.
*   **Material Slots:** `Mat_NeonTrace`.
*   **Texture Slots:** 1x Scrolling Data Texture (Tileable).
*   **Poly Budget:** LOD0: 400 tris | LOD1: 100 tris | LOD2: 20 tris.
*   **Naming Convention:** `geo_code_lodX`, `mat_code_neon`.

### 7. Conversation
*   **Purpose:** The echo of a voice in a physical space.
*   **Visual Story:** Open toruses, ribbon-like waveforms.
*   **Silhouette:** Flowing, curved ribbon.
*   **Dimensions:** 1.0m diameter loop, 0.1m thick.
*   **Pivot:** Exact center.
*   **LOD0:** Vertex-displaced ribbon geometry (high segment count).
*   **LOD1:** Flat alpha-mapped ring.
*   **LOD2:** Particle ring / simple torus.
*   **Animation:** Vertex displacement (Shader).
*   **Material Slots:** `Mat_IridescentRibbon`.
*   **Texture Slots:** 1x Alpha/Opacity map, 1x Iridescence map.
*   **Poly Budget:** LOD0: 3k tris | LOD1: 100 tris | LOD2: 200 tris.
*   **Naming Convention:** `geo_conv_lodX`, `mat_conv_ribbon`.

### 8. Research
*   **Purpose:** Gathering disparate threads into a central thesis.
*   **Visual Story:** Intersecting orbital rings holding data-nodes.
*   **Silhouette:** Atom-like structure.
*   **Dimensions:** 0.8m diameter.
*   **Pivot:** Exact center.
*   **LOD0:** Full orbital array (separate meshes for rings and nodes).
*   **LOD1:** Single sphere with wireframe material.
*   **LOD2:** Blue particle.
*   **Animation:** Procedural rotation of rings.
*   **Material Slots:** `Mat_SilverVector`, `Mat_DataNode`.
*   **Texture Slots:** None.
*   **Poly Budget:** LOD0: 2k tris | LOD1: 500 tris | LOD2: 50 tris.
*   **Naming Convention:** `geo_research_lodX`.

### 9. Websites
*   **Purpose:** Windows into the external world.
*   **Visual Story:** Curved, ultra-wide cinematic screens.
*   **Silhouette:** Curved rectangle.
*   **Dimensions:** 1.5m wide, 0.8m tall, curved depth 0.2m.
*   **Pivot:** Bottom center.
*   **LOD0:** Curved mesh with high-res texture.
*   **LOD1:** Flat plane.
*   **LOD2:** Flat colored square.
*   **Animation:** None.
*   **Material Slots:** `Mat_EmissiveScreen`.
*   **Texture Slots:** 1x Screenshot/Content Texture.
*   **Poly Budget:** LOD0: 1k tris | LOD1: 4 tris | LOD2: 4 tris.
*   **Naming Convention:** `geo_web_lodX`.

### 10. Tasks
*   **Purpose:** Metrics counting down to completion.
*   **Visual Story:** Segmented, glowing circular rings.
*   **Silhouette:** Flat torus / donut.
*   **Dimensions:** 0.4m diameter, 0.05m thick.
*   **Pivot:** Exact center.
*   **LOD0:** 3D torus with dynamic masking.
*   **LOD1:** 2D sprite ring.
*   **LOD2:** Dot / small sphere.
*   **Animation:** Shader-based radial fill.
*   **Material Slots:** `Mat_MatteEmissive`.
*   **Texture Slots:** 1x Gradient Mask (for fill).
*   **Poly Budget:** LOD0: 800 tris | LOD1: 4 tris | LOD2: 50 tris.
*   **Naming Convention:** `geo_task_lodX`.

### 11. Calendar
*   **Purpose:** Time mapped to spatial distance.
*   **Visual Story:** Concentric, massive orbital rings.
*   **Silhouette:** Saturn-like rings on the horizontal plane.
*   **Dimensions:** 3.0m diameter, 0.1m thick.
*   **Pivot:** Exact center.
*   **LOD0:** Thin cylinders with bloom.
*   **LOD1:** Standard line renderer / flat ring.
*   **LOD2:** Not rendered (culled).
*   **Animation:** Slow procedural rotation on Y-axis.
*   **Material Slots:** `Mat_SubtleLine`.
*   **Texture Slots:** None.
*   **Poly Budget:** LOD0: 2k tris | LOD1: 200 tris | LOD2: 0 tris.
*   **Naming Convention:** `geo_cal_lodX`.

### 12. Folders
*   **Purpose:** Containment without walls.
*   **Visual Story:** Open, 3D wireframe bounding boxes.
*   **Silhouette:** Cube wireframe.
*   **Dimensions:** 1.0m x 1.0m x 1.0m.
*   **Pivot:** Exact center.
*   **LOD0:** Glowing tubes with corner joints.
*   **LOD1:** Basic line renderer.
*   **LOD2:** Not rendered.
*   **Animation:** Pulsing emissive intensity.
*   **Material Slots:** `Mat_GlowingTube`.
*   **Texture Slots:** None.
*   **Poly Budget:** LOD0: 500 tris | LOD1: 24 tris | LOD2: 0 tris.
*   **Naming Convention:** `geo_folder_lodX`.

### 13. Future MetaHuman (Placeholder)
*   **Purpose:** The ghost in the machine becomes flesh.
*   **Visual Story:** Anatomically correct human bust emerging from geometry.
*   **Silhouette:** Human head and shoulders.
*   **Dimensions:** 0.5m wide, 0.8m tall.
*   **Pivot:** Bottom center (base of neck).
*   **LOD0:** Full skeletal mesh, facial morph targets.
*   **LOD1:** Lower poly count, standard PBR skin.
*   **LOD2:** Reverts to the Living Orb.
*   **Animation:** Skeletal idle (breathing, eye darts).
*   **Material Slots:** `Mat_Skin_SSS`, `Mat_Eye`, `Mat_Hair`.
*   **Texture Slots:** Albedo, Normal, Roughness, SSS Map, Specular.
*   **Poly Budget:** LOD0: 50k tris | LOD1: 10k tris | LOD2: N/A.
*   **Naming Convention:** `geo_metahuman_lodX`, `skel_metahuman`.
*   **Collision:** Capsule collider.

---

## III. UI & Glass HUDs (2D/3D Hybrid)

*   **Context Panels:** Do not model in Blender. These are built procedurally in React using `@react-three/drei` `<Html>` or `<Glass>` components with CSS `backdrop-filter: blur()`.
*   **Typography:** Inter or SF Pro. White (#FFFFFF). No 3D text meshes in the spatial environment.

---
*End of Asset Production Bible.*