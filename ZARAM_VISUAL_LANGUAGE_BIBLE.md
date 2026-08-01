# ZARAM VISUAL LANGUAGE BIBLE

**Version:** 1.0  
**Status:** Frozen (Visual Authority)  
**Authority:** Visual Language Architect  
**Scope:** All Embodiments, Materials, Motion, and UI within the Zaram Ecosystem.

---

## 1. Design Philosophy

**Zaram is not a file system. It is a Living Knowledge Ecosystem.**

We do not build "graphs," "nodes," or "icons." We cultivate a digital habitat. Every piece of data is an organism; every context is an environment. 

*   **Biological over Mechanical:** Nothing in Zaram should feel like a rigid desktop UI. Everything breathes, floats, and reacts organically.
*   **Embodiment as Species:** Every data type is a distinct species with its own silhouette, behavior, and material. A "Memory" should look and behave fundamentally differently than a "Task."
*   **Depth over Flatness:** We reject the 2D desktop paradigm. Zaram exists in a volumetric space where depth indicates context, hierarchy, and focus.
*   **Light as Information:** In a dark universe, light is the primary carrier of meaning. Emissive properties, glow, and shadow dictate importance and state.

---

## 2. Embodiment Taxonomy

Every species in the Zaram ecosystem must be instantly recognizable by its silhouette and motion alone.

### The Living Orb (The Heart)
*   **Purpose:** The central consciousness and anchor of the universe.
*   **Silhouette:** Perfect sphere, but with a volatile, liquid surface.
*   **Material:** Liquid Light / Volumetric Energy.
*   **Emissive Behavior:** Pulses in time with the AI's "breathing" (FrameState). Glows intensely during active speech or deep reasoning.
*   **Idle Animation:** Slow, rhythmic expansion and contraction (breathing). Surface ripples gently.
*   **Hover/Selection:** The surface tension breaks slightly, revealing a brighter core. A subtle gravitational pull affects nearby particles.
*   **Transition:** Expands to fill the screen (zoom in) or shrinks to a distant sun (zoom out).

### Documents (The Leaves)
*   **Purpose:** Static knowledge, text, and files.
*   **Silhouette:** Thin, rectangular planes with slightly rounded, organic corners. Like glass tablets or crystalline leaves.
*   **Material:** Frosted Glass.
*   **Emissive Behavior:** Edges glow faintly. The center remains translucent.
*   **Idle Animation:** Slowly drifts and rotates on its Y-axis, catching the light.
*   **Hover/Selection:** Flattens to face the camera directly. Edges brighten.
*   **Transition:** Shatters into light particles when deleted; materializes from a single point of light when created.

### Folders / Clusters (The Geodes)
*   **Purpose:** Containment and organization of related species.
*   **Silhouette:** Rough, multifaceted polyhedrons (like geodes or hollow crystals).
*   **Material:** Obsidian exterior, crystalline interior.
*   **Emissive Behavior:** The interior glows with the combined color of its contents. The exterior is dark and grounding.
*   **Idle Animation:** Slowly tumbles in 3D space.
*   **Hover/Selection:** The exterior facets crack open slightly, revealing the bright interior.
*   **Transition:** "Pops" open like a seed pod to release its contents into the universe.

### Projects (The Solar Systems)
*   **Purpose:** Complex, multi-faceted initiatives containing tasks, docs, and agents.
*   **Silhouette:** A central dense core surrounded by orbiting micro-nodes.
*   **Material:** Metallic core, energy rings.
*   **Emissive Behavior:** The core pulses steadily. The rings emit a trailing light.
*   **Idle Animation:** The micro-nodes orbit the core at varying speeds and inclinations.
*   **Hover/Selection:** The orbit speed increases. The rings align to face the camera.
*   **Transition:** Zooms into the core, transitioning the camera into the "Project Sub-Universe."

### Memories (The Fireflies)
*   **Purpose:** Ephemeral, contextual, highly personal data.
*   **Silhouette:** Small, soft, glowing orbs without hard edges.
*   **Material:** Pure Energy / Bioluminescence.
*   **Emissive Behavior:** High emissive intensity, soft falloff. They cast actual light on nearby objects.
*   **Idle Animation:** Erratic, floating movement (Brownian motion). They drift toward the Living Orb when "recalled."
*   **Hover/Selection:** Flares brightly, then dims.
*   **Transition:** Fades in and out smoothly, never popping into existence.

### Websites / Internet (The Portals)
*   **Purpose:** External, live, dynamic data.
*   **Silhouette:** Circular or hexagonal frames with a shimmering center.
*   **Material:** Holographic / Shimmering Forcefield.
*   **Emissive Behavior:** The center is a swirling vortex of light.
*   **Idle Animation:** The frame rotates slowly. The center vortex spins rapidly.
*   **Hover/Selection:** The frame expands, and the vortex stabilizes into a clear window.

### Code (The Grids)
*   **Purpose:** Structured, logical, executable data.
*   **Silhouette:** Sharp, rigid cubes or rectangular prisms.
*   **Material:** Matte Metal with emissive circuitry lines.
*   **Emissive Behavior:** The circuitry lines pulse in a rhythmic, binary pattern.
*   **Idle Animation:** Snaps to a grid. Moves with precise, linear interpolation (no organic floating).
*   **Hover/Selection:** The circuitry lines light up fully.

### Agents (The Familiars)
*   **Purpose:** Autonomous, active entities performing tasks.
*   **Silhouette:** Small, distinct geometric shapes (tetrahedrons, octahedrons) that dart around.
*   **Material:** Polished Chrome / Reflective Metal.
*   **Emissive Behavior:** A single "eye" or focal point that tracks the Living Orb.
*   **Idle Animation:** Darts quickly from node to node, "inspecting" them.
*   **Hover/Selection:** Stops moving and hovers in place, projecting a small status beam.

### Conversation (The Ribbons)
*   **Purpose:** The flow of dialogue between user and AI.
*   **Silhouette:** Flowing, ribbon-like trails of light connecting the User presence to the Living Orb.
*   **Material:** Liquid Light.
*   **Emissive Behavior:** Pulses travel down the ribbon during speech.
*   **Idle Animation:** The ribbon undulates like a snake in water.

---

## 3. Material Language

All materials must be defined using Physically Based Rendering (PBR) principles, but stylized for a dark, volumetric UI.

### Glass (Documents, UI Panels)
*   **Appearance:** Clean, translucent, slightly refractive.
*   **Lighting:** Catches environment reflections sharply.
*   **Roughness:** 0.1 (Very smooth).
*   **Transparency:** 0.8 (Highly transparent).
*   **Fresnel:** Strong edge glow when viewed at grazing angles.

### Crystal (Folders, Clusters)
*   **Appearance:** Faceted, internal refraction, sharp edges.
*   **Lighting:** Scatters light internally (subsurface scattering).
*   **Roughness:** 0.0 (Perfectly smooth).
*   **Transparency:** 0.9.
*   **Fresnel:** Extreme. Edges should glow brightly.

### Liquid Light / Energy (Orb, Memories, Trails)
*   **Appearance:** No solid surface. Pure volumetric emission.
*   **Lighting:** *Is* the light source. Casts dynamic light on surrounding geometry.
*   **Roughness:** N/A (Emissive only).
*   **Transparency:** 1.0 (Additive blending).
*   **Shader Notes:** Use noise functions to create internal turbulence.

### Obsidian (Backgrounds, Heavy Containers)
*   **Appearance:** Deep black, highly reflective, grounding.
*   **Lighting:** Sharp, mirror-like reflections.
*   **Roughness:** 0.05.
*   **Transparency:** 0.0.
*   **Fresnel:** Subtle. Used to anchor the scene and provide contrast for emissive elements.

### Holographic (Internet, AR elements)
*   **Appearance:** Iridescent, scanlines, digital noise.
*   **Lighting:** Unlit or emissive. Ignores scene lighting.
*   **Roughness:** N/A.
*   **Transparency:** 0.5.
*   **Shader Notes:** Apply a scrolling UV noise texture and a subtle RGB split (chromatic aberration) at the edges.

---

## 4. Motion Language

Motion in Zaram must feel **biological, fluid, and intentional**. Mechanical, linear, or abrupt movements are forbidden.

*   **Breathing:** Everything alive has a subtle, continuous scale pulse (1.0 to 1.02).
*   **Floating:** Objects do not sit still. They drift using Perlin noise on their position vectors.
*   **Responding:** When interacted with, objects should "squash and stretch" slightly, or recoil like jelly.
*   **Merging:** When two nodes combine, they should magnetically pull toward each other, deform upon contact, and snap into the new shape.
*   **Splitting:** A node should bulge, stretch, and pinch off into two separate entities.
*   **Spawning:** Never pop into existence. Materialize from a point of light, expanding rapidly then settling with a slight bounce (spring physics).
*   **Disappearing:** Dissolve into particles or fade into light. Never just vanish.
*   **Easing:** All camera and object movements must use `Ease-In-Out` or `Spring` damping. Linear interpolation is only for rigid objects (Code).

---

## 5. Scale Language

Hierarchy is communicated through scale, depth, and camera focus.

1.  **The Living Orb (Macro):** Dominates the center. Scale: 100%.
2.  **Species (Meso):** Documents, Memories, Projects. Scale: 10% - 30%. Orbit the Orb.
3.  **Sub-Universe (Micro):** Zooming into a "Project" reveals a new, smaller universe inside it. Scale resets to 100% for the new context.
4.  **Individual Knowledge (Detail):** Hovering over a node brings it to the foreground. Scale: 150%.
5.  **Context Panel (UI):** 2D overlays that appear *over* the 3D space. Scale: Fixed to screen space.
6.  **Actions (Micro-UI):** Small icons or buttons attached to the Context Panel.

---

## 6. Color Language

Color is semantic. It must be consistent across all embodiments.

*   **Memory:** Bioluminescent Blue (`#0077ff`). Calm, deep, trustworthy.
*   **Knowledge / Internet:** Emerald Green (`#00ff77`). Fresh, growing, external.
*   **Projects / Tasks:** Amber / Orange (`#ff7700`). Active, urgent, structured.
*   **People / Social:** Warm Pink / Magenta (`#ff0077`). Human, empathetic.
*   **Execution / Reasoning:** Deep Purple (`#aa00ff`). Complex, computational, deep.
*   **Learning / Thinking:** Cyan (`#00ffff`). Bright, processing, active.
*   **Searching:** White / Silver (`#ffffff`). Neutral, scanning, illuminating.
*   **Speaking:** Gold (`#ffcc00`). Vocal, expressive, broadcasting.
*   **Errors / Warnings:** Crimson Red (`#ff0033`). Urgent, broken, critical.

---

## 7. Audio Language (Conceptual)

Audio reinforces the visual state. It should be ambient, spatial, and non-intrusive.

*   **Living Orb:** Deep, resonant hum. Pitch shifts slightly with emotional state.
*   **Documents:** Soft, crystalline chimes when hovered. A soft "paper" rustle when opened.
*   **Memories:** Ethereal, echoing whispers or soft wind chimes.
*   **Code:** Crisp, digital clicks and high-frequency hums.
*   **Agents:** Small, mechanical whirrs or digital "blips" as they move.
*   **Transitions:** A low-frequency "whoosh" or bass drop when entering a Sub-Universe.

---

## 8. Accessibility

The visual language must be usable by everyone.

*   **Contrast:** Emissive elements must maintain a minimum 4.5:1 contrast ratio against the dark background.
*   **Motion Reduction:** If the user enables "Reduced Motion," all floating, breathing, and drifting animations must cease. Objects remain static. Transitions become simple fades (opacity) instead of spatial movements.
*   **Color Blindness:** Color must *never* be the sole carrier of meaning. Every species must have a distinct **silhouette** and **material** (e.g., Memory is blue AND spherical; Code is cyan AND cubic).
*   **Readability:** 2D UI text must use system fonts, high contrast, and scalable sizing. No 3D text in the spatial environment.

---

## 9. Design Rules (Immutable)

These rules are absolute. Violating them breaks the Zaram experience.

1.  **No Desktop Icons:** Nothing in Zaram should look like a standard OS file icon. We are building a universe, not a folder.
2.  **Silhouette First:** If you turn off all lights and materials, you must still be able to identify the species by its shape alone.
3.  **Animation Communicates State:** An object's motion must reflect its data state. A "decaying" memory moves slower and dims. An "active" task pulses faster.
4.  **Color Never Carries Meaning Alone:** Always pair color with shape, material, or motion.
5.  **Light is Information:** If something is important, it emits light. If it is background, it absorbs light.
6.  **Biological over Mechanical:** When in doubt, make it float, breathe, and ease. Never make it snap, slide linearly, or tick.
7.  **The Orb is Sacred:** The Living Orb is the only object that breaks the rules of the universe. It is the anchor. Everything else orbits it.

---
*End of Visual Language Bible.*