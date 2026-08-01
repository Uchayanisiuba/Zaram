
---

# 6. ARCHITECTURE_DECISION_RECORDS.md

```markdown
# Architecture Decision Records (ADRs)

**Document Type:** Architectural History  
**Version:** 2.0.0  
**Status:** Canonical  

---

## ADR-001: Event-Driven RuntimeBus over Direct Method Calls
**Status:** Accepted  
**Context:** Early prototypes used direct function calls between surfaces and the Orb. This led to tight coupling and circular dependencies.  
**Decision:** Implement a central, typed Pub/Sub `RuntimeBus`.  
**Consequences:** 
- *Positive:* Complete decoupling. New modules can be added without modifying existing code. Enables event replay for Undo/Redo.
- *Negative:* Slight overhead in event routing. Requires strict typing to prevent "magic string" bugs.

---

## ADR-002: Context Graph as the Single Source of Truth
**Status:** Accepted  
**Context:** Traditional apps use component-local state or a global Redux store. This fails for an AI OS that needs to "remember" what the user was doing across different, unrelated surfaces.  
**Decision:** Implement a temporal `Context Graph` that aggregates ephemeral packets into an `Active Working Set`.  
**Consequences:** 
- *Positive:* AI engines have grounded, real-time context. Surfaces are truly independent.
- *Negative:* Requires careful management of TTL and eviction to prevent memory leaks.

---

## ADR-003: Renderer-Independent Orb Runtime
**Status:** Accepted  
**Context:** The initial Orb was built with DOM/CSS. The long-term vision includes WebGPU, Unreal Engine, and MetaHuman embodiments.  
**Decision:** Abstract the Orb's state machine (`IOrbRuntime`) from its visual implementation. The runtime only manages `OrbState` and emits events; the renderer listens and draws.  
**Consequences:** 
- *Positive:* Future-proof. We can swap the DOM Orb for a 3D canvas Orb without changing a single line of business logic.
- *Negative:* Requires maintaining a strict contract between state and renderer.

---

## ADR-004: Canvas Intelligence via Ephemeral Context Objects
**Status:** Accepted  
**Context:** Proactive AI insights were initially designed as modal pop-ups or toast notifications. These are disruptive and block the user's workflow.  
**Decision:** Implement `ContextObjects` as lightweight, draggable, auto-fading elements on the infinite background canvas (`z-5`).  
**Consequences:** 
- *Positive:* Creates a "calm," non-blocking, spatial UI. The AI feels like a helpful assistant leaving notes, not an interrupting boss.
- *Negative:* Requires careful z-index management to ensure they don't get lost behind windows.

---

## ADR-005: Local-First Event Logging
**Status:** Accepted  
**Context:** Cloud-based telemetry is the industry standard, but violates Zaram's core privacy and offline-first principles.  
**Decision:** All events are logged to a local, rotating SQLite database. Cloud telemetry is strictly opt-in and heavily anonymized.  
**Consequences:** 
- *Positive:* 100% privacy by default. Works flawlessly offline. Enables powerful local debugging and session replay.
- *Negative:* We cannot aggregate global usage metrics without explicit user consent.