# ADR-005: FrameState Contract
**Status:** Accepted
**Context:** Renderers were receiving ad-hoc application events, causing desynchronization.
**Decision:** Freeze FrameState with nested namespaces (visual, audio, emotion, system, metadata). Renderers only consume FrameState.
**Consequences:** Application logic cannot directly trigger renderer animations.