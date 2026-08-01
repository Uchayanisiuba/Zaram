# Zaram Runtime Architecture

**Document Type:** System Architecture  
**Version:** 2.0.0 (Milestone 2)  
**Status:** Canonical  
**Owner:** Chief Software Architect  

---

## 1. Runtime Philosophy
The Zaram Runtime is not a traditional application framework; it is an **event-driven, spatial operating environment**. It is designed around four immutable principles:
1. **Decoupling:** No module directly calls another module's methods. All communication flows through the `RuntimeBus`.
2. **Renderer Independence:** The runtime logic (state, events, context) is completely agnostic to how it is rendered (DOM, Canvas, WebGPU, Unreal Engine).
3. **Local-First Sovereignty:** All runtime state, events, and context graphs reside on the user's device. Cloud sync is an optional, encrypted overlay.
4. **Calm Intelligence:** The runtime prioritizes user focus. Background AI processing must not block the main thread or cause UI jank.

---

## 2. The RuntimeBus
The `RuntimeBus` is the central nervous system of Zaram. It is a typed, asynchronous Publish/Subscribe (Pub/Sub) message broker.

```text
[Surface/Module] --(Emits Event)--> [RuntimeBus] --(Routes)--> [Subscribers (Orb, Memory, Canvas)]