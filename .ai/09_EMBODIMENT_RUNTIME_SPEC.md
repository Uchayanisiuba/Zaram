# Embodiment Runtime Specification
**Version:** 1.0 | **Status:** Frozen

## 1. Purpose
Manages the lifecycle, loading, and switching of visual embodiments.

## 2. Renderer Independence
The application never imports renderer code. The Embodiment Runtime handles the mapping between the `IEmbodiment` interface and the specific rendering technology (Canvas, WebGL, Unreal Pixel Streaming).

## 3. Future Character Parity
The Unreal Character consumes the exact same FrameState as the Living Orb. The renderer changes; the application does not. This is an architectural law.