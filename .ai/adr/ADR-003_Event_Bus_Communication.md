# ADR-003: Event Bus Communication
**Status:** Accepted
**Context:** Direct method calls create tight coupling.
**Decision:** Implement an asynchronous Pub/Sub Event Bus with strict payload immutability and versioning.
**Consequences:** Debugging requires trace IDs. Event ordering must be managed via correlation IDs.