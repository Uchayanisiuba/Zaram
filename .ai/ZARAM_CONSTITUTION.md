# ZARAM CONSTITUTION
**Version:** 2.0
**Status:** Frozen (Requires ADR to modify)
**Dependencies:** `ZARAM_BIBLE.md`

> **This document defines the immutable principles of Zaram. Violating these principles is considered an architectural regression.**

---

## 1. Product Principles
1. **Local-First, Cloud-Optional:** Local computation is the default. Cloud services are strictly optional. Users always own their data.
2. **Hardware Agnostic:** Zaram must adapt to the user's hardware, not the other way around.
3. **No Vendor Lock-in:** Every subsystem (Models, Voices, Characters, Runtimes) must be replaceable.
4. **Privacy by Default:** Intelligence should not require sacrificing privacy.

## 2. Architectural Principles
1. **Kernel Orchestrates, Runtimes Specialize:** The Kernel is the central nervous system. Runtimes (Speech, Memory, Models) are independent, isolated subsystems.
2. **Subsystem Independence:** A subsystem must never depend upon another subsystem's implementation. Communication occurs only through Contracts, Events, and Interfaces.
3. **Engine is an Interface:** The Service layer must never know which specific Engine (e.g., Kokoro vs. ElevenLabs) is running underneath.
4. **Strangler Fig Migration:** Never rewrite working systems. Introduce new runtimes beside existing implementations, validate, switch, then remove legacy.

## 3. Business & Monetization Principles
1. **Orchestration is Free:** Model routing, hardware profiling, and hybrid orchestration are core platform features. They will never be locked behind a subscription.
2. **Monetize the Ecosystem:** Revenue comes from Skills, Marketplace, Premium Characters, and Enterprise features, not from limiting base intelligence.
3. **Own the Experience:** We do not compete with model providers. We provide the best environment to use all of them together.

## 4. Engineering Principles
1. **Readable Code Beats Clever Code:** Maintainability is paramount.
2. **Documentation Before Implementation:** AI agents implement contracts. They do not invent architecture.
3. **Small Commits, Feature Flags:** Major migrations must be hidden behind feature flags until validated.
4. **Performance Before Graphics:** The OS must be responsive and stable before visual polish is applied.

---
*End of Zaram Constitution.*