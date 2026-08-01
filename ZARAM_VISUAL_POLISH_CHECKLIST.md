# ZARAM VISUAL POLISH CHECKLIST

**Version:** 1.0  
**Status:** Frozen (Production Authority)  
**Target Audience:** QA Engineers, Technical Artists, Engine Programmers  

---

This is the final AAA Quality Assurance pass. Before any build is considered "Alpha," the rendering team must verify the following:

## 1. Motion & Animation Quality
- [ ] **No Linear Curves:** Ensure all camera movements, UI panel summons, and object translations use cubic bezier easing (ease-out dominant).
- [ ] **Inertial Damping Check:** Verify the camera drifts naturally when input ceases, with no hard stops.
- [ ] **Hover States:** Ensure objects react physically (scale up 2%, emit soft bloom) within 50ms of a pointer hover.

## 2. Shaders & Rendering
- [ ] **Stutter Avoidance:** Are all heavy shaders pre-compiled? There must be zero frame drops when a Tier 3 (Production) asset loads onto the screen.
- [ ] **PBR Consistency:** Do the Memories refract light accurately? Does the Obsidian material on Projects reflect the environment properly?
- [ ] **Anti-Aliasing:** Verify TAA (Temporal Anti-Aliasing) is tuned to prevent ghosting on the ambient particles while moving the camera.

## 3. Composition & Readability
- [ ] **Depth of Field:** Is the background bokeh engaging correctly? Ensure it does not blur the Glass HUD UI layers.
- [ ] **Contrast & Legibility:** Can text on the Glass Cards be read easily regardless of what emissive object is behind it? (Verify the backdrop blur opacity).
- [ ] **Framing:** Does the camera auto-pan to keep the primary subject in the rule-of-thirds when a UI panel opens?

## 4. Particles & Lighting
- [ ] **Volumetric Banding:** Check the fog and bloom for color banding. Ensure dithering is applied to smooth out the gradients in the dark areas of the scene.
- [ ] **Particle Density:** Does the scene feel appropriately scaled? Ensure the ambient dust particles are small enough not to distract, but present enough to provide parallax.

## 5. GPU Performance
- [ ] **Frame Pacing:** Is the engine holding a locked 120 FPS (or target framerate)?
- [ ] **Draw Calls:** Verify that the Outer Rim proxy objects are successfully instanced, keeping draw calls to an absolute minimum.
- [ ] **LOD Transitions:** Ensure the crossfade between Tier 1 (Proxy), Tier 2 (Procedural), and Tier 3 (Production) assets is seamless and invisible to the user.