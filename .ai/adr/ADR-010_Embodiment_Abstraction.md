# ADR-010: Embodiment Abstraction
**Status:** Accepted
**Context:** Future MetaHuman and XR avatars must consume the exact same data as the Living Orb.
**Decision:** The FrameState is the universal truth. The renderer changes; the application does not.
**Consequences:** Unreal Engine must be configured to ingest FrameState via Live Link or WebSocket.