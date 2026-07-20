# Zaram System Architecture Blueprint
**Version:** 1.0
**Status:** Frozen (Requires ADR to modify)
**Dependencies:** `00_AI_ENGINEERING_MANIFEST.md`

> **This document provides the high-level visual blueprint of Zaram. It defines how the pieces fit together, not how they are implemented.**

---

## 1. High-Level System Flow

```text
─────────────────────────────────────────────────────────────────────────
│                         ZARAM OPERATING SYSTEM                          │
│                                                                         │
│  ──────────────┐                                                       │
│  │   Frontend   │ (React, Desktop, Mobile, AR, Voice-Only)              │
│  └──────┬───────┘                                                       │
│         │ (User Input / Events)                                         │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        ZARAM CORE                                │   │
│  │                                                                  │   │
│  │  ┌──────────────┐  ┌───────────────┐  ──────────────────────┐  │   │
│  │  │ Interaction  │  │  Capability   │  │  Runtime Registry    │  │   │
│  │  │ Runtime      │──►  Router       │──► (OS Kernel Manager)  │  │   │
│  │  └──────┬───────┘  └───────┬───────┘  └──────────┬───────────┘  │   │
│  │         │                  │                      │              │   │
│  │         ▼                  ▼                      ▼              │   │
│  │  ┌──────────────┐  ┌──────────────  ┌──────────────────────┐   │   │
│  │  │ Task         │  │  Execution   │  │                      │   │   │
│  │  │ Orchestrator │  │  Planner     │  │      EVENT BUS       │   │   │
│  │  └──────────────┘  └──────────────┘  │ (Prioritized Pub/Sub)│   │   │
│  │                                       └──────────┬───────────┘   │   │
│  └──────────────────────────────────────────────────┼───────────────┘   │
│                                                     │ (Pub/Sub)        │
│  ┌──────────────────────────────────────────────────┼───────────────┐   │
│  │               RUNTIME LAYER                      ▼               │   │
│  │                                                                  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ──────────────┐    │   │
│  │  │ Speech   │  │ Memory   │  │Knowledge │  │    Tool      │    │   │
│  │  │ Runtime  │  │ Runtime  │  │ Runtime  │  │   Runtime    │    │   │
│  │  └────┬─────┘  └────┬─────  └─────────┘  └──────┬───────┘    │   │
│  │       │             │             │               │             │   │
│  │  ┌────┴─────┐  ┌─────────┐  ┌────┴─────┐  ┌─────┴───────┐    │   │
│  │  │ Speech   │  │ Memory   │  │ Vector   │  │  File/Browser│    │   │
│  │  │ Service  │  │ Service  │  │ Service  │  │  /Terminal    │    │   │
│  │  └────┬─────  └────┬─────┘  └─────────┘  └─────┬───────┘    │   │
│  │       │             │             │               │             │   │
│  │  ┌────┴─────┐  ┌─────────  ┌────┴─────┐  ┌─────┴───────┐    │   │
│  │  │ Kokoro   │  │ SQLite/  │  │ ChromaDB │  │  OS APIs    │    │   │
│  │  │ (Engine) │  │ VectorDB │  │ (Engine) │  │  (Engine)   │    │   │
│  │  └──────────┘  ──────────┘  ──────────┘  └─────────────┘    │   │
│  │                                                                  │   │
│  │  ┌──────────────────────────────────────────────────────────┐   │   │
│  │  │                 Reasoning Runtime                        │   │   │
│  │  │  ┌──────────────┐  ┌──────────┐  ┌──────────────────┐   │   │   │
│  │  │  │ Model        │  │ Ollama   │  │ Cloud Engine     │   │   │   │
│  │  │  │ Selector     │──► Engine   │──► (Future)         │   │   │   │
│  │  │  └──────────────┘  └──────────┘  └──────────────────┘   │   │   │
│  │  └──────────────────────────────────────────────────────────   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     EMBODIMENT LAYER                             │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │   │
│  │  │ Living   │  │MetaHuman │  │ Desktop  │  │ Voice Only   │    │   │
│  │  │   Orb    │  │ (Unreal) │  │   UI     │  │ (Headless)   │    │   │
│  │  └──────────┘  ──────────┘  └──────────  └──────────────┘    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘

---

## 2. Canonical Runtime Pipeline (Zaram Core)

This is the authoritative flow for the desktop runtime (`desktop/src/runtime`).
It is the single source of truth for how a user interaction becomes a rendered
living presence. Milestone 1.4 makes the **Executive Runtime** the single
authority for high-level AI decision-making. Milestone 1.5 adds the **Capability
Runtime** as the OS capability discovery and execution interface so the Executive
requests capabilities (never tools) strictly through `ICapabilityRuntime`.

```text
Conversation
Memory
Knowledge
World
Vision (future)
Automation (future)
Tool (future)
Plugin (future)
      │
      ▼
 Executive Runtime            ← Milestone 1.4 (Decision Engine)
      │                          owns: focus, priorities, interrupts,
      │                          task switching, context, goals, intent
      │  requests capabilities ONLY through the interface (never tools)
      ▼
 Capability Runtime           ← Milestone 1.5 (Discovery & Execution Interface)
      │                          single source of truth for every capability;
      │                          exposes ONLY capability metadata
      ▼
 Execution Engine             ← separate layer (not built in M1.5)
      ▼
 Capability                   ← concrete implementation
```

The cognitive/emotive/embodiment chain beneath the Executive remains unchanged:

```text
 Executive Runtime
      ▼
 Attention
      ▼
 Emotion
      ▼
 Behaviour
      ▼
 Presence
      ▼
 Character
      ▼
 Embodiment
      ▼
 Renderer
```

### Verified renderer-independent pipeline (M1.0–M1.4)

```text
AnimationRuntime
        ↓
PresenceRuntime
        ↓
CharacterRuntime
        ↓
IEmbodiment
        ↓
LivingOrbAdapter
        ↓
RenderTransport
        ↓
OrbRenderer
```

`CharacterRuntime` receives ONLY the high-level `Intent` from the Executive
Runtime. It never receives goals, planning, confidence, reasoning, memory, or
relationship internals. The Executive Runtime is advanced on the existing 30Hz
tick (`PresenceRuntime.tick`) and never touches the renderer, the embodiment
framework, or `CharacterFrame`. The Capability Runtime is injected into the
Executive Runtime strictly through `ICapabilityRuntime` and exposes only
capability metadata — no behaviour, no execution, no drawing-layer/body-layer
dependency.

### Capability Runtime (Milestone 1.5)

The Capability Runtime is the OS capability discovery and execution interface.
It is the single source of truth for every capability available to the OS and
exposes ONLY capability metadata (descriptors). The Executive Runtime depends on
it strictly through `ICapabilityRuntime` and requests capabilities — it never
calls tools directly and never imports a concrete capability implementation.

```text
Executive Runtime          (decides WHAT to do)
      │  requestCapability(query)  — interface only, never tools
      ▼
Capability Runtime        (discovers CAN Zaram do X?)
      │  CapabilityDescriptor (metadata)
      ▼
Execution Engine          (separate layer, not built in M1.5)
      ▼
Capability                (concrete implementation)
```

Capability categories: `system`, `workspace`, `filesystem`, `communication`,
`ai`, `automation`, `developer`, `media`, `vision`, `speech`, `plugins`,
`security`. Each descriptor carries `id`, `name`, `description`, `category`,
`permissions`, `inputSchema`, `outputSchema`, `availability`, `latencyEstimateMs`,
`location` (`local`/`cloud`), `cost`, and `enabled`.

### Runtime Map (Zaram Core)

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Subsystem Sources                                                     │
│  Conversation · Memory · Knowledge · World · Voice · System          │
└───────────────────────────────────┬──────────────────────────────────┘
                                     │ aggregated snapshot
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Cognitive Layer (M1.2)                                                │
│  Cognitive · Attention · Relationship                                 │
└───────────────────────────────────┬──────────────────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Executive Runtime (M1.4)            Decision Engine                    │
│  focus · priorities · interrupts · goals · intent                     │
└───────────────┬───────────────────────────────────┬──────────────────┘
                │ requests capabilities (interface)   │ high-level Intent
                ▼                                      ▼
┌──────────────────────────┐            ┌──────────────────────────────────┐
│ Capability Runtime (M1.5) │            │ Embodiment Chain                  │
│ Discovery & metadata only │            │  Attention → Emotion → Behaviour  │
└───────────────┬────────────┘            │   → Presence → Character → Body  │
                │                          │   → Renderer                      │
                ▼                          └──────────────────────────────────┘
┌──────────────────────────┐
│ Execution Engine (future)│
└──────────────────────────┘
```

The Capability Runtime is injected into the Executive Runtime via DI
(`TOKENS.capabilityRuntime`, singleton) and consumes no renderer, embodiment, or
character-pipeline code. It introduces no timers, polling, or
`requestAnimationFrame`.
