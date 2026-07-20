# ADR-004: Presence Runtime
**Status:** Accepted
**Context:** The application needs to support multiple visual embodiments (Orb, MetaHuman, XR) without rewriting core logic.
**Decision:** Introduce the Presence Runtime as the mandatory gateway. Application emits FrameState; Presence Runtime routes to IEmbodiment.
**Consequences:** Adds a layer of indirection. Requires strict FrameState contract.