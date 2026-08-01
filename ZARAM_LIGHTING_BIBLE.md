# ZARAM LIGHTING BIBLE

**Version:** 1.0  
**Status:** Frozen (Production Authority)  
**Target Audience:** Lighting Artists, Shader Developers, Engine Programmers  

---

## Core Philosophy
Zaram has no static sun. Lighting is emotional, volumetric, and entirely driven by the Presence Runtime. We operate in an **ACES (Academy Color Encoding System)** color space to ensure cinematic highlight roll-off and deep, rich blacks.

---

## 1. Environment & Volumetrics

### The Void
*   The base environment is not empty space; it is a dense, volumetric fluid.

### Height Fog
*   Exponential fog drives the depth buffer. Objects further than 100 units don't just get smaller; they desaturate and vanish into the atmospheric scattering.

### Bloom
*   Cinematic, anamorphic bloom. Highlights should streak slightly on the horizontal axis, giving the space a high-end, optical feel.

---

## 2. Presence Lighting States

Lighting is entirely dynamic and driven by the Presence Runtime.

### Thinking
*   The global ambient occlusion softens. A slow, bioluminescent ripple propagates through the fog from the Living Orb outward.

### Searching
*   A sharp, volumetric spotlight emits from the camera's origin. It acts as a flashlight in the dark, illuminating the data-dust particles in its path as it hunts for the target.

### Conversation (Speaking/Listening)
*   Audio-reactive point lights inside the Living Orb drive the scene's global illumination. The intensity and color temperature shift dynamically with the cadence and tone of the voice.

### Learning
*   High-intensity emissive ribbons (directional energy flows) travel from the periphery into the central Orb, casting dynamic rim lights on nearby glass surfaces as they pass.

### Memory Lighting
*   When a Memory is accessed, the global color grading shifts. The contrast lowers, blacks become slightly lifted (milky), and the scene takes on a warmer, nostalgic color temperature (golden hour).

### Error / System Alert
*   Subtle. No flashing red alarms. The ambient fog shifts to a deep, bruised violet, and the Living Orb's internal noise tightens and speeds up.