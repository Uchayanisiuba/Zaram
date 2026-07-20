# ADR-008: Renderer Independence
**Status:** Accepted
**Context:** The application should not know if it is rendering to Canvas or Unreal Engine.
**Decision:** Enforce strict renderer independence via the IEmbodiment interface.
**Consequences:** Renderers must implement the full IEmbodiment lifecycle.