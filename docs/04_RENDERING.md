# Rendering & Embodiment Layer

## 1. Presence Runtime

The Presence Runtime is the **abstraction layer** between the AI Intelligence and all visual embodiments. It translates abstract cognitive state into the `FrameState` contract.

### Key Responsibilities
- Consumes state from Cognitive, Emotion, Behaviour, and Relationship Runtimes.
- Produces `FrameState` (see `.ai/06_FRAMESTATE_SPEC.md`).
- **Knows no renderer:** It does not know if the output is a 2D Orb, a 3D MetaHuman, or the Knowledge Universe.

### FrameState Projection
The Presence Runtime projects `FrameState` to three first-class embodiments:

1. **Living Orb:** Procedural 2D/3D visualization. Consumes `visual`, `audio`, `emotion` namespaces for particle effects, glow, and rhythm.
2. **Avatar:** High-fidelity 3D character. Consumes full `FrameState` mapped to blendshapes, gaze, gestures, and lip-sync.
3. **Knowledge Universe:** Spatial intelligence workspace. Consumes full `FrameState` to modulate the entire cosmic environment (lighting, orbital speed, node highlighting).

All three embodiments consume the **exact same abstract state**. The Presence Runtime simply routes `FrameState` to the active Embodiment Adapter.

---

## 2. Triple Embodiment System

Zaram supports three first-class embodiments. Users can switch between them instantly. All three maintain identical conversation state, memory, and intelligence.

### Mode 1: Living Orb
- **Type:** Procedural 2D/3D Visualization
- **Characteristics:** Minimal, fast, ambient, conversational. Always available.
- **Role:** The central intelligence. In Universe Mode, the Orb becomes the Sun.
- **Status:** ✅ Implemented

### Mode 2: Avatar
- **Type:** 3D Character (MetaHuman, RPM, VRM, ARKit, Custom)
- **Characteristics:** Fully animated, facial expressions, eye contact, emotion, speech.
- **Role:** High-fidelity conversational partner.
- **Status:** 🔮 Planned

### Mode 3: Knowledge Universe
- **Type:** Spatial Intelligence Workspace
- **Characteristics:** The Living Orb becomes the Sun. Projects, documents, memory, files, agents, skills, and knowledge orbit dynamically as a navigable 3D galaxy.
- **Role:** Operational workspace for deep work, project management, and knowledge exploration. **Not decoration.** It is the user's second brain.
- **Status:** 🔮 Planned

---

## 3. Renderer Independence

**Rule:** No runtime outside the Embodiment Layer may know about:
- Unreal Engine
- MetaHuman
- Three.js
- Electron Renderer
- WebGPU
- Unity
- Custom renderers

Everything above the Embodiment Layer only outputs **abstract state** (`FrameState`). This ensures that swapping the Living Orb for a MetaHuman or entering the Knowledge Universe requires **zero changes** to the Intelligence Layer.

---

## 4. Orb-Centric Intelligence

The Living Orb is **always** the central intelligence of Zaram, regardless of the active embodiment mode.

- In **Orb Mode**, the Orb is the sole focus.
- In **Avatar Mode**, the Orb's intelligence drives the Avatar's behaviour.
- In **Universe Mode**, the Orb is the Sun at the center of the Knowledge Universe.

All cognitive processes (speech, thinking, attention, knowledge retrieval, reasoning, memory activation) originate from the Orb. The Universe responds. **Never the reverse.**

---

## 5. Interaction Modes

Users can instantly switch between embodiments:

| Mode | View | Use Case |
|---|---|---|
| **Orb Mode** | Living Orb fills screen | Ambient monitoring, quick chat, low distraction |
| **Avatar Mode** | 3D character fills screen | Deep conversation, emotional connection, presentation |
| **Universe Mode** | Orb at center, Universe navigable | Deep work, project management, knowledge exploration |

Switching is instant. No data is lost. Conversation state, memory, and context persist across all modes.