# ADR-001: Local First Architecture
**Status:** Accepted
**Context:** Zaram requires absolute user privacy and zero-latency local inference.
**Decision:** All core runtimes (Models, Memory, Speech) must default to local execution. Cloud is strictly optional.
**Consequences:** Requires robust hardware detection and VRAM budgeting. Increases initial setup complexity.