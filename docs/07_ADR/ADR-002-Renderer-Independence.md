# ADR-002: Renderer Independence
**Status:** Accepted
**Context:** Tightly coupling AI to a specific renderer (Three.js/Unreal) prevents future embodiments.
**Decision:** The Presence Runtime outputs abstract `FrameState`. Embodiment Runtimes consume it. No layer above Embodiment may import renderer code.
**Consequences:** We can swap the Living Orb for a MetaHuman without changing a single line of intelligence code.