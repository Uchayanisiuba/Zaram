# ZARAM CONCEPT DESIGN GUIDE

**Document Type:** Art Direction & Visual Concept Specification  
**Target Engine:** Zaram Spatial Engine v1.0 (R3F / WebGL)

---

## I. Emotional Design & Art Direction

Zaram is not a tool; it is a cognitive space. The visual language must strip away the clinical feeling of standard software and replace it with the awe of exploring a living intelligence.

*   **Exploration:** Should feel like the Destiny Director map combined with the frictionless movement of Journey. The user is gliding through a vast, frictionless cosmos of their own mind.
*   **Discovery:** Should feel like illuminating a dark room. When searching, the universe bends to the user's will, bringing answers forward with the tactile satisfaction of a physical mechanism locking into place.
*   **Memory:** Fragile, precious, and intimate. Memories should look like holding a physical, crystalline photograph that refracts the light around it.
*   **Projects:** Grounded, monumental, and structural. They are the architectural foundations of the user's work, exuding weight and permanence.
*   **Conversation:** Fluid, biological, and synchronous. It should feel like sitting across from a living entity, where the light in the room shifts with the cadence of their voice.

---

## II. Environment & Atmosphere

The canvas is a high-contrast, volumetric void.

*   **Atmosphere:** 90% absolute black (#050508). We rely on an exponential height fog driven by the depth buffer. Objects further away don't just scale down; they fade into the atmospheric scattering.
*   **Particles:** Not static stars. We use ambient data-dust—a Niagara-style particle field of microscopic, low-emissive motes that drift slowly, mimicking underwater snow. They provide a sense of parallax and scale when the camera moves.
*   **Depth & Scale:** The universe operates on a massive scale. The Living Orb is a star; Projects are planets; Documents are satellites. We use aggressive depth-of-field (DOF) to guide the eye. If the focus distance is 10m, objects at 50m blur into beautiful, cinematic bokeh.

---

## III. Camera Experience

The camera is a physical lens, not a mathematical coordinate.

*   **Movement Feel:** All translations and rotations are bound by cubic bezier easing. No linear movement. The camera possesses mass and inertial damping.
*   **Entering a Sub-Universe:** When zooming into a Semantic Neighborhood, the focal length dynamically shifts from a wide-angle macro view (24mm) to a flatter, more intimate portrait view (50mm). The background objects fade into heavy blur.
*   **Returning:** A double-click on the Orb triggers a sweeping, banking arc back to (0,0,0), re-widening the focal length to reveal the macro structure.
*   **Searching (The Spotlight):** Triggers a "Vertigo" dolly-zoom effect. The field of view narrows slightly while the camera physically pulls back. Non-relevant objects instantly drop to alpha = 0.05, and relevant objects glide to the foreground along glowing procedural splines.

---

## IV. Lighting Experience (Presence States)

Lighting is entirely dynamic and driven by the Presence Runtime. There is no static sun.

*   **Day (Work Mode):** Crisp, high-key lighting. Neutral azures and sharp specular highlights on glass edges. High visibility for dense production work.
*   **Night (Deep Focus):** Low-key, moody. The ambient environment drops to near-black. Objects are lit only by their own internal emissivity and warm, amber rim lights.
*   **Thinking:** The global illumination pulses gently. Bioluminescent ripples travel through the micro-fog.
*   **Searching:** A sharp, volumetric spotlight casts from the camera's origin, slicing through the fog and illuminating dust particles in its path.
*   **Speaking:** Audio-reactive point lights inside the Living Orb drive the scene's global illumination, casting dynamic, shifting shadows across nearby Projects and Memories.
*   **Learning:** Directional energy flows. High-intensity emissive ribbons travel from the periphery into the center, lighting up nearby glass surfaces as they pass.
*   **Idle:** A slow, breathing sine-wave oscillation in the ambient occlusion and base lighting.

---

## V. Embodiment Concept Sheets

### 1. The Living Orb
*   **Visual Story:** The heart of Zaram. A contained star of cognitive energy.
*   **Shape Language:** Perfect sphere, broken by internal fluid dynamics.
*   **Material:** Ray-marched volumetric fluid. High IOR (Index of Refraction), extreme fresnel edges.
*   **Internal Animation:** Constant, roiling procedural noise (Curl Noise) mimicking plasma.
*   **Interaction:** Hover: Expands slightly, noise frequency increases. Selected: Emits a soft, localized bloom pulse.
*   **LODs:** LOD0: Full volumetric ray-marching. LOD1: Complex PBR sphere with animated normal maps. LOD2: Simple glowing emissive sphere.

### 2. Projects
*   **Visual Story:** The heavy, anchored foundations of work.
*   **Shape Language:** Monolithic blocks, brutalist but refined. Obelisks.
*   **Material:** Obsidian core with thick, frosted glass outer casing. Deeply etched luminous paths.
*   **Internal Animation:** Slow, pulsing light tracks running along the etched circuitry.
*   **LODs:** LOD0: Full GLB with interior parallax mapping. LOD1: Beveled geometric block with static textures. LOD2: Solid dark cube.

### 3. Memories
*   **Visual Story:** Captured moments of time. Precious, sharp, and clear.
*   **Shape Language:** Asymmetrical, faceted crystals. Prisms.
*   **Material:** Diamond/Glass hybrid. High chromatic aberration, intense specular reflections.
*   **Internal Animation:** Light refracts and dances inside as the camera orbits.
*   **LODs:** LOD0: Ray-traced refraction (or screen-space equivalent), multi-faceted. LOD1: Simplified decimation, basic glass shader. LOD2: Glowing white particle.

### 4. Agents
*   **Visual Story:** Autonomous workers. Precise, mechanical, purposeful.
*   **Shape Language:** Gyroscopic rings around a solid core. Spherical drones.
*   **Material:** Brushed titanium, matte black carbon fiber, glowing cyan data ports. Anisotropic metal highlights.
*   **Internal Animation:** Rings spin independently on different axes, locking into place when processing.
*   **LODs:** LOD0: High-poly GLB with spinning mechanical parts. LOD1: Simplified procedural rings. LOD2: Cyan point light.

### 5. Future MetaHuman Presence
*   **Visual Story:** The ghost in the machine becomes flesh. Empathy and intelligence.
*   **Shape Language:** Anatomically correct human bust/torso emerging from the Orb's geometry.
*   **Material:** Subsurface scattering (SSS) for skin, realistic micro-facet roughness, dynamic rim lighting to separate from the dark background.
*   **Internal Animation:** Micro-expressions, eye-darts, respiratory idle animations.
*   **LODs:** LOD0: Full skeletal mesh, facial morph targets, SSS. LOD1: Lower poly count, standard PBR skin material. LOD2: Reverts to the Living Orb.

### 6. Documents
*   **Visual Story:** Pages of knowledge floating in zero gravity.
*   **Shape Language:** Thin, rectangular panes with slightly rounded corners.
*   **Material:** Vision Pro-style frosted glass. Highly transparent, back-plate blurring. Text is etched with slight emissivity.
*   **LODs:** LOD0: Glass shader with text masking. LOD1: Opaque white plane. LOD2: Flat sprite.

### 7. Folders
*   **Visual Story:** Containment without walls.
*   **Shape Language:** Open, 3D wireframe bounding boxes.
*   **Material:** Thin, glowing structural vectors. Soft volumetric light filling the interior volume.
*   **LODs:** LOD0: Glowing tubes with corner joints. LOD1: Basic line renderer. LOD2: Not rendered.

### 8. Code
*   **Visual Story:** The matrix of logic. Strict, rigid, executing.
*   **Shape Language:** Vertical cascades. Geometric pillars.
*   **Material:** Neon traces on dark, semi-transparent plates.
*   **Internal Animation:** Data "raindrops" sliding down the vertical traces.
*   **LODs:** LOD0: Layered depth plates with scrolling UVs. LOD1: Single plate, scrolling texture. LOD2: Green line segment.

### 9. Conversation
*   **Visual Story:** The echo of a voice in a physical space.
*   **Shape Language:** Open toruses, ribbon-like waveforms.
*   **Material:** Translucent, iridescent ribbons.
*   **Internal Animation:** Ripples and expands based on historical audio frequency.
*   **LODs:** LOD0: Vertex-displaced ribbon geometry. LOD1: Flat alpha-mapped ring. LOD2: Particle ring.

### 10. Research
*   **Visual Story:** Gathering disparate threads into a central thesis.
*   **Shape Language:** Intersecting orbital rings holding smaller data-nodes. An atom.
*   **Material:** Thin silver vectors, micro-emissive connection points.
*   **LODs:** LOD0: Full orbital array. LOD1: Single sphere with wireframe material. LOD2: Blue particle.

### 11. Websites
*   **Visual Story:** Windows into the external world.
*   **Shape Language:** Curved, ultra-wide cinematic screens.
*   **Material:** Emissive front face (website screenshot), soft drop-shadow projecting backward into the fog.
*   **LODs:** LOD0: Curved mesh with high-res texture. LOD1: Flat plane. LOD2: Flat colored square.

### 12. Tasks
*   **Visual Story:** Metrics counting down to completion.
*   **Shape Language:** Segmented, glowing circular rings.
*   **Material:** Matte emissive. Colors shift from amber (pending) to mint green (completed).
*   **Internal Animation:** Ring fills up radially.
*   **LODs:** LOD0: 3D torus with dynamic masking. LOD1: 2D sprite ring. LOD2: Dot.

### 13. Calendar
*   **Visual Story:** Time mapped to spatial distance.
*   **Shape Language:** Concentric, massive orbital rings on the horizontal plane (like Saturn's rings).
*   **Material:** Extremely subtle, low-opacity white lines with glowing markers for events.
*   **LODs:** LOD0: Thin cylinders with bloom. LOD1: Standard line renderer. LOD2: Not rendered.

---

## VI. UI & Glass HUDs

The UI does not exist in a vacuum; it is anchored in the 3D space.

*   **Context Panels & Glass Cards:** Modeled explicitly after Apple Vision Pro mechanics. They use a heavy background blur (backdrop filter) to distort the 3D universe behind them. Edges have a 1px specular highlight (fresnel) that catches the scene's global illumination.
*   **Typography:** Absolute crispness is required. Text is bright white, high-contrast, utilizing a variable sans-serif font.
*   **Transitions:** Panels do not "slide in." They materialize. They scale from 0.95 -> 1.0 while fading their alpha from 0 -> 1 over a sharp, fast 150ms cubic bezier curve. When dismissed, they dissolve into the ambient fog.
*   **Context Actions:** Floating, pill-shaped buttons attached to the bottom edge of Glass Cards. They react to hover with a physical depth push (Z-axis negative translation) rather than just a color change.