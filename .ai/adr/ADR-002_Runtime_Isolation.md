# ADR-002: Runtime Isolation
**Status:** Accepted
**Context:** Monolithic architectures cause cascading failures.
**Decision:** Implement the 3-tier Runtime/Service/Engine hierarchy. Runtimes may never import each other.
**Consequences:** Requires Event Bus for all communication. Increases boilerplate for simple features.