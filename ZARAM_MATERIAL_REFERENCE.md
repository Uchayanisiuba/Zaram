# ZARAM MATERIAL REFERENCE

**Version:** 1.0  
**Status:** Frozen (Production Authority)  
**Target Audience:** 3D Modelers, Material Artists, Shader Programmers  

---

## Core Philosophy
Every material in Zaram must feel physically plausible, even if the object is abstract. We rely heavily on PBR (Physically Based Rendering) principles, utilizing precise Index of Refraction (IOR) and surface roughness values.

---

## 1. The Living Orb (Volumetric Plasma)
*   **Surface Properties:** A ray-marched volume, not a hollow shell.
*   **Material:** High IOR (1.5 - 1.8), mimicking dense liquid or contained plasma.
*   **Emission:** Driven by internal curl noise. The core is blindingly hot (white/cyan), fading to deep azure at the fresnel edges.
*   **Emotional Feel:** Alive, breathing, infinite.

## 2. Projects (Obsidian & Glass)
*   **Surface Properties:** Dense, heavy, monolithic.
*   **Material:** The core is an anisotropic metal or polished obsidian (Roughness 0.1, Metalness 1.0). The outer casing is a thick, frosted glass (Roughness 0.4, high transmission).
*   **Emission:** Deeply etched glowing circuitry (lumens pushed high enough to trigger the anamorphic bloom).
*   **Emotional Feel:** Permanent, structural, grounded.

## 3. Memories (Crystalline)
*   **Surface Properties:** Asymmetrical, faceted prisms.
*   **Material:** Diamond/Crystal hybrid (IOR 2.4). High chromatic aberration at the edges. Perfect specular reflections (Roughness 0.0).
*   **Environment Reflection:** Must deeply reflect the surrounding data-dust and the Living Orb.
*   **Emotional Feel:** Fragile, precious, clear.

## 4. Documents & UI (Vision Pro Glass)
*   **Surface Properties:** Thin, weightless panes.
*   **Material:** Highly transparent with a strong backdrop blur (acrylic/frosted glass). Edge-lit with a 1px fresnel highlight to separate it from the dark fog.
*   **Emotional Feel:** Clean, frictionless, legible.