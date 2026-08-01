# Rendering & Embodiment Layer

## Presence Runtime
The abstraction between AI and rendering. Produces `FrameState`.
- Presence knows no renderer.
- Embodiments know no cognition.

## Dual Embodiment System
Users switch instantly between embodiments:
- **Mode 1: Living Orb** (Minimal, Fast, Ambient)
- **Mode 2: Avatar** (Fully animated, Facial expressions, Eye contact)
- **Mode 3: Knowledge Universe** (Future: The Orb becomes the Sun in a navigable 3D galaxy of projects, memory, and agents).

## Renderer Independence
No runtime outside Embodiment may know Unreal, MetaHuman, ThreeJS, Electron renderer, or WebGPU. Everything above Embodiment only outputs abstract state.