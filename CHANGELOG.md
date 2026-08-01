# Zaram Changelog

## [1.0.0-Alpha] - Documentation Freeze & Architecture Lock
### Added
- **Business Model Finalized:** Zaram Core ($49 one-time), Marketplace, and Cloud Credits documented.
- **5-Layer OS Architecture:** Kernel, Intelligence, Projection, Embodiment, Platform layers formally defined.
- **Dual Embodiment System:** Living Orb, Avatar, and future Knowledge Universe modes documented.
- **Knowledge Runtime Spec:** Provider-agnostic architecture approved.
- **Local Model Manager:** Hardware benchmarking and in-app installation workflow approved.
- **Architecture Decision Records (ADRs):** 12 core ADRs created to govern future development.

### Changed
- **Strangler Fig Migration:** FastAPI `main.py` successfully integrated with the new Execution Engine behind the `USE_NEW_KERNEL` feature flag.
- **Runtime Naming:** Standardized all runtime names (e.g., `Runtime_Models`, `Execution Engine`).

### Status
- **Implemented:** Kernel, Registry, Event Bus, Execution Engine, Models Runtime, FastAPI Integration.
- **In Progress:** Memory Runtime, Speech Runtime.
- **Planned:** Knowledge Runtime, Presence Runtime, Embodiment Runtime, Electron Platform, Marketplace.