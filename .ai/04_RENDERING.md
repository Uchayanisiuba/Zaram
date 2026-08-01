# Rendering & Embodiment Layer

## 1. Presence Runtime
The Presence Runtime is the **abstraction layer** between the AI Intelligence and the visual rendering. It translates abstract cognitive states into the `FrameState` contract.

### Key Responsibilities
- Consumes state from Cognitive, Emotion, and Behaviour Runtimes.
- Produces `FrameState` (see `09_SPECIFICATIONS.md`).
- **Knows no renderer:** It does not know if the output is a 2D Orb, a 3D MetaHuman, or a Robot.

## 2. Embodiment System
Zaram supports multiple embodiments that consume the same `FrameState`.

### Mode 1: Living Orb (Current Alpha)
- **Type:** 2D Procedural Visualization
- **Characteristics:** Minimal, fast, ambient, conversational.
- **Status:** ✅ Implemented

### Mode 2: Avatar (Future)
- **Type:** 3D Character (MetaHuman/Unreal)
- **Characteristics:** Fully animated, facial expressions, eye contact, emotion.
- **Status:** 🔮 Planned

### Mode 3: Knowledge Universe (Future)
- **Type:** 3D Navigable Galaxy
- **Characteristics:** The Living Orb becomes the "Sun". Projects, documents, memory, files, agents, skills, and knowledge orbit dynamically.
- **Purpose:** Not decoration. It is the user's navigable second brain.
- **Status:** 🔮 Planned

## 3. Renderer Independence
**Rule:** No runtime outside the Embodiment Layer may know about:
- Unreal Engine
- MetaHuman
- Three.js
- Electron Renderer
- WebGPU

Everything above the Embodiment Layer only outputs **abstract state** (`FrameState`). This ensures that swapping the Living Orb for a MetaHuman requires **zero changes** to the Intelligence Layer.

## 4. Dual Embodiment UX
Users can switch between embodiments instantly. The Presence Runtime ensures that the visual representation changes, but the AI's intelligence, memory, and personality remain constant.