# Zaram Runtime Model

## ⚠️ ARCHITECTURE FREEZE POLICY
The architectural boundaries defined in this document are considered **STABLE AND FROZEN**. 
1. **Extension over Invention:** New work must extend existing runtimes and pipelines rather than introducing new layers.
2. **High Bar for Change:** Architectural changes require an Architecture Decision Record (ADR) and must demonstrate that the existing design fundamentally cannot satisfy the requirement without violating separation of concerns.
3. **Governance:** All implementations must be reviewed for constitutional compliance (4-Stage Pipeline, Layer boundaries, Embodiment Factory usage) before merging.

---

**Status:** Frozen (Constitutional Authority)  
**Version:** 1.0 (Architecture 1.0)  
**Authority:** Chief Architect & System Architect  
**Scope:** All Zaram Runtimes, SDKs, and Engine Implementations  

---

## 1. Supreme Directives

The Zaram Operating System is governed by three unbreakable rules. No implementation, optimization, or feature may violate these directives.

1. **Strict Downward Flow:** Data and control flow strictly downward through the architectural layers. No layer may bypass the layer immediately above it. No layer may import or directly call a layer below it.
2. **Absolute Separation of Concerns:** Meaning (Semantics), Math (Simulation), Aesthetics (Visuals), and Pixels (Rendering) are strictly isolated. They communicate only through immutable contracts and the Event Bus.
3. **Renderer Ignorance:** The AI intelligence and the spatial simulation must remain 100% agnostic to the rendering technology. The system must be able to swap Three.js for Unreal Engine, WebGPU, or a physical robot without altering a single line of intelligence or simulation code.

---

## 2. The 5-Layer OS Architecture

The Zaram OS is structured into five distinct layers. 

### Layer 1: The Kernel & Platform Services
The foundational infrastructure. It provides the services that all other layers consume.
* **Components:** Event Bus, Runtime Registry, Capability Registry, Permission Manager, Configuration, Storage, Scheduler, Logging, Diagnostics.
* **Responsibility:** Lifecycle management, secure inter-runtime communication, and resource allocation.

### Layer 2: The Intelligence Layer
The cognitive core of the OS. These runtimes operate independently and communicate exclusively via the Event Bus.
* **Adaptive Runtime:** The executive optimization engine. Learns user preferences and dynamically routes tasks.
* **Core Runtimes:** Memory, Knowledge, Speech, Vision, Executive, Emotion, Behaviour, Identity, Relationship, World.
* **Utility Runtimes:** Automation, Tools, Plugins, Internet.
* **Responsibility:** Processing user intent, managing state, retrieving context, and generating `FrameState`.

### Layer 3: The Spatial Runtime
The agnostic spatial engine. It knows nothing of "memories," "projects," or "knowledge." It only understands abstract nodes, edges, and physics.
* **Components:** Semantic Graph, Simulation Engine (Physics), Spatial Query Engine, Animation Engine.
* **Responsibility:** Calculating semantic gravity, managing spatial relationships, and outputting abstract `SpatialState`.

### Layer 4: The Embodiment Runtime
The bridge between abstract state and physical/digital presence. 
* **Components:** Orb Embodiment, Avatar Embodiment, Robot Embodiment, etc.
* **Responsibility:** Consuming `FrameState` and `VisualState` to determine *how* the AI expresses itself (e.g., "pulse red" vs "furrow brow"). **Embodiments are NOT renderers.**

### Layer 5: The Renderers
The strictly isolated visualization adapters.
* **Components:** Three.js Adapter, Unreal Engine Adapter, Unity Adapter, WebGPU Adapter.
* **Responsibility:** Consuming `VisualState` and translating it into GPU commands. They know nothing of AI, memory, or physics.

---

## 3. The Knowledge Hierarchy (Graph vs. Universe)

A critical architectural distinction must be maintained between the underlying data and its visualization. The Living Knowledge Universe is **not** the graph. It is merely one embodiment (visualization) of the graph.

1. **Memory Runtime:** Stores episodic and semantic facts.
2. **Knowledge Runtime:** Aggregates data from providers (files, web, git, APIs).
3. **Knowledge Graph Runtime:** The abstract, renderer-agnostic graph of all semantic nodes and edges. **(The Source of Truth)**.
4. **Knowledge Universe Runtime:** A specific *visualization* of the Knowledge Graph using the Spatial SDK. **(An Embodiment)**.
5. **Renderer:** Three.js, Unreal, etc. **(The Pixels)**.

*Rule:* Future embodiments (e.g., a 2D Graph View, an Unreal Engine VR Universe, an Analytics Dashboard) will all consume the exact same Knowledge Graph Runtime without modifying it.

---

## 4. The Core Data Pipeline (The 4-Stage Transformation)

Data moving from the Intelligence Layer to the Renderer must pass through four strictly typed, immutable stages.

### Stage 1: Semantic (Pure Meaning)
* **Contract:** `SpatialNode`, `SpatialEdge`, `SpatialGraph`
* **Properties:** ID, type, label, semanticMass, metadata, relationships.
* **Rule:** Contains **ZERO** position, velocity, color, or size data.

### Stage 2: Simulation (Pure Math)
* **Contract:** `SimulationNode`, `SimulationState`, `SpatialForces`
* **Properties:** position, velocity, acceleration, physical mass.
* **Rule:** The Physics Engine calculates `SpatialForces`. It **NEVER** mutates the Semantic Graph directly. The Simulation Runtime applies the forces.

### Stage 3: Frame (The Sacred Contract)
* **Contract:** `FrameState`
* **Properties:** visual (presence, energy), audio, emotion, system state.
* **Rule:** The central hub. Generated by the Intelligence Layer. Consumed by the Embodiment Layer.

### Stage 4: Visual (Pure Aesthetics)
* **Contract:** `VisualNode`, `VisualEdge`, `VisualState`
* **Properties:** position, radius, color, scale, opacity, meshProfile.
* **Rule:** Generated statelessly by the `VisualMapper`. It combines the Simulation State, the FrameState, and the active `ITheme`. It contains no AI logic.

---

## 5. Strict Architectural Prohibitions

To maintain system integrity, the following actions are strictly forbidden:

1. **Thou shalt not mix Semantics and Visuals:** The Memory Runtime must never assign a color, radius, or position to a node. Those are derived statelessly by the Visual Mapper.
2. **Thou shalt not mutate state in Physics:** The Physics Engine must only output forces. It must not alter node positions directly.
3. **Thou shalt not poll:** Runtimes must never poll each other for data. All cross-runtime communication must occur asynchronously via the `IEventBus`.
4. **Thou shalt not hardcode Renderers:** The `core/` and `platform/` directories must never contain imports for `three`, `@react-three/fiber`, `unreal`, or `unity`.
5. **Thou shalt not treat Embodiments as Renderers:** The Orb is a persona/body, not a rendering technology. It must be housed in the `embodiments/` directory, not the `engine/` directory.

---

## 6. Future Expansion: The Experience Runtime

*Status: Reserved for Future Implementation*

As the OS matures, an **Experience Runtime** will be introduced between the Spatial Runtime and the Embodiment Runtime. 
* **Responsibility:** It will own cinematic sequences, emotional pacing, transitions, soundtracks, ambient behavior, and AI narration. 
* **Purpose:** It determines *how* the user experiences the intelligence (the "directing" layer), independently of *where* or *what* is being rendered.

---

## 7. AI Collaboration Roles

The development of Zaram is divided among specialized AI agents to prevent architectural drift:

* **Chief Architect (Human):** Vision, roadmap, final architectural approval, product evaluation.
* **Qwen (System Architect & Documentation Lead):** Constitutional docs, SDK specs, ADRs, interfaces, contracts, platform engineering.
* **Kilo (Implementation Engineer):** Runtime implementations, backend services, frontend modules, IPC, integration, testing, wiring.
* **Kimi (Visual & Spatial Lead):** Three.js renderer, Spatial Runtime implementation, physics visualization, shaders, camera, UI.

*All agents must read this document before generating code. If implementation conflicts with this document, the implementation must be adapted, not the architecture.*