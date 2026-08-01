# ADR-006: Local Model Manager
**Status:** Accepted
**Context:** Non-technical users cannot use terminal commands like `ollama pull`.
**Decision:** Zaram will benchmark hardware on first launch and provide an in-app UI to download, install, and manage models.
**Consequences:** Removes the biggest barrier to entry for local AI. Requires building a robust download and verification pipeline.