# Presence Runtime Specification
**Version:** 1.0 | **Status:** Frozen

## 1. Purpose
The Presence Runtime is the permanent abstraction layer between the OS and any visual embodiment.

## 2. Architecture Flow
```mermaid
graph TD
    A[Application Core] -->|FrameState| B(Presence Runtime)
    B -->|IEmbodiment Interface| C{Active Embodiment}
    C -->|Living Orb| D[Orb Renderer]
    C -->|MetaHuman| E[Unreal Engine]
    C -->|XR Avatar| F[WebXR]