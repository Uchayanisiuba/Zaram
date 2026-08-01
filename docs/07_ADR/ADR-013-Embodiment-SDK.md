# ADR-013: Embodiment SDK & Package Standard
**Status:** Accepted (RC2)

## Context
The Marketplace will not just sell human characters. It will sell robots, anime avatars, holograms, floating AI companions, drones, custom orbs, and Knowledge Universe themes. The SDK must support every possible embodiment.

## Decision
Define the **Zaram Embodiment Package (`.zaram-embodiment`)** standard. A package must contain:

### Package Contents
- `manifest.json` (Metadata, Author, Version, Embodiment Type)
- `identity.json` (Personality, Values, Boundaries)
- `appearance/` (Textures, 3D models, orb shader presets, universe themes)
- `animations/` (Frame presets, blendshape maps, motion packs, orbital paths)
- `voices/` (TTS config, voice clones, samples)
- `behaviour/` (Micro-actions, idle reactions, gaze patterns)
- `emotion/` (Affective baselines, expression maps)
- `knowledge/` (Optional bundled knowledge/memory pack)
- `workspace/` (Default UI layouts, shortcuts, universe configurations)
- `skills/` (Bundled capabilities)
- `plugins/` (Third-party extensions)
- `training/` (Conversation examples, personality tuning, few-shot prompts)
- `license/` (EULA, commercial rights, attribution)

### Supported Embodiment Types
The Embodiment SDK supports the following types via the Universal Character Framework:

| Type | Examples |
|---|---|
| **Photorealistic Human** | MetaHuman, Character Creator, RealityCapture |
| **Stylized Character** | Ready Player Me, VRM, Anime rigs, Cartoon styles |
| **Facial Animation** | ARKit, Audio2Face, MediaPipe |
| **Robot** | Physical robots, mechanical rigs, drone avatars |
| **Floating AI** | Holograms, orbs, geometric shapes, particle systems |
| **Knowledge Universe** | Galaxy themes, orbital configurations, spatial layouts |
| **Custom Rig** | Blender rigs, Unity avatars, Unreal skeletons |
| **VTuber** | Live2D, 3D VTuber rigs, motion capture avatars |

### Key Principles
1. **One Package, Any Embodiment:** A single `.zaram-embodiment` package can contain assets for multiple embodiment types (e.g., an Orb preset + an Avatar model + a Universe theme).
2. **FrameState Driven:** All embodiments consume the same `FrameState`. The package defines how that state is visually interpreted.
3. **Marketplace Ready:** Packages are signed, versioned, and publishable to the Zaram Marketplace.

## Consequences
An Embodiment Package becomes an entire "digital person" or "digital entity." Developers can sell fully realized AI companions on the Marketplace that work instantly across the Orb, Avatar, and Knowledge Universe.