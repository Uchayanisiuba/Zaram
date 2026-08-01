# Zaram Spatial Runtime — Visual Architecture Document
## Sprint 1: Living Orb → Spatial Universe Evolution

**Version:** 1.0  
**Date:** 2026-07-23  
**Status:** Architecture Foundation  
**Classification:** Visual & Spatial Architecture Lead Deliverable

---

## 0. Guiding Principle

> The current Living Orb is not a prototype. It is the first cell of a living intelligence. Do not replace it. Grow it.

Every future visualization must feel like a natural evolution of the orb the user already knows. The orb's breathing, its emotional color states, its audio-reactive pulse — these are not features. They are **Zaram's DNA**. Every galaxy, every node, every constellation must carry this DNA.

The spatial runtime is not a knowledge graph. It is a **general spatial visualization engine** for intelligence itself. Today: knowledge. Tomorrow: projects, calendar, agents, memory, dreams, automation. Everything must speak the same spatial language.

---

## 1. Executive Summary

This document defines the architectural evolution from the current Living Orb (a 384×384 Canvas 2D presence) to the **Zaram Spatial Runtime** — an explorable, cinematic, intelligent universe where every piece of information exists as an entity in semantic space.

The evolution preserves:
- The `FrameState` immutable data contract
- The 30 Hz engine → 60 Hz renderer pipeline
- The renderer-agnostic architecture (no runtime imports renderer code)
- The EmotionEngine, InfluenceEngine, and RhythmEngine
- The three-layer visual identity (Glow → Body → Core)
- The AudioEnvelope ADSR smoothing

The evolution introduces:
- **Semantic Space**: A continuous 3D coordinate system where meaning = position
- **Orbital Mechanics**: Entities orbit the Living Orb based on relevance, recency, and emotional weight
- **Visual Metaphors**: A reusable language of nodes, clusters, constellations, galaxies, auroras, comets
- **Documentary Camera**: A cinematic camera system that never stops moving
- **Semantic Weather**: Atmospheric events that communicate system state
- **Multi-Renderer Portability**: Abstract concepts first, Three.js/Unreal/WebGPU/VR implementations second

---

## 2. The Evolution Roadmap

### Stage 1: Living Orb (CURRENT — PRESERVED)
**What exists today.**
- 384×384 Canvas 2D presence
- Three layers: Glow halo, Orb body (2–4 rings), Inner core
- State-driven: idle, listening, thinking, speaking, working, sleeping, error
- Emotion-driven hue shifts, energy pulses, breathing
- AudioEnvelope (ADSR: attack 0.6, release 0.08) — currently unwired
- 30 Hz engine tick → 60 Hz renderer via `FrameState` IPC

**Preservation Rule:** Stage 1 never disappears. It becomes the **Core/Sun** of all future stages.

---

### Stage 2: Orb + Intelligent Nodes
**The orb surrounded by its first satellites.**

The Living Orb remains fixed at the spatial origin `(0, 0, 0)`. Around it, **Knowledge Nodes** appear as luminous spheres on orbital paths. Each node represents a memory, concept, or piece of knowledge.

**Visual Behavior:**
- Nodes emerge from the orb's glow (born from intelligence)
- They settle into elliptical orbits at distances proportional to `1 / relevance`
- High-relevance nodes orbit close (tight, fast orbits)
- Low-relevance nodes drift outward (slow, wide orbits)
- Nodes breathe in sync with the orb (same RhythmEngine sine wave, phase-shifted by orbital position)
- Nodes inherit the orb's current emotional hue, desaturated by distance

**New FrameState Fields:**
```typescript
interface SpatialFrameState extends FrameState {
  spatial: {
    nodes: Array<{
      id: string;
      position: [number, number, number]; // orbital coordinates
      relevance: number; // 0.0 – 1.0
      emotionalWeight: number;
      connectivity: number; // how many other nodes link to this
      birthTimestamp: number;
      lastAccessed: number;
      state: 'emerging' | 'stable' | 'fading' | 'hibernating';
    }>;
    camera: {
      target: [number, number, number];
      distance: number;
      azimuth: number;
      inclination: number;
      driftVelocity: [number, number, number];
    };
  };
}
```

**Audio Integration (Wire AudioEnvelope):**
- Microphone RMS → IPC `presence:audio` → `AudioEnvelope.process()`
- Smoothed value drives `voiceLevel` in `FrameState.audio`
- `voiceLevel` now affects:
  - Orb glow intensity (existing)
  - Node orbital velocity (new: voice excites the system)
  - Particle field turbulence (new)

---

### Stage 3: Semantic Clusters
**Nodes self-organize into meaning-constellations.**

When multiple nodes share semantic similarity, they gravitate into **Clusters**. A cluster is not a container — it is a **gravitational well** that gently pulls related nodes into a loose formation.

**Visual Behavior:**
- Clusters form slowly (over 2–5 seconds) using spring-force simulation
- Cluster centers emit a soft aurora-like glow (volumetric fog, not hard edges)
- Nodes within a cluster maintain individual orbits but are phase-locked
- Highly connected clusters become **Constellations** — thin luminous threads connect nodes, forming recognizable shapes
- Constellation lines pulse with data flow (knowledge being accessed or transferred)

**New Visual Metaphor: Constellation**
- Lines between nodes are not static geometry
- They are **energy streams** that brighten when knowledge is actively being reasoned about
- Line thickness = `connectivity * emotionalWeight`
- Line color = blend of connected nodes' emotional hues

---

### Stage 4: Explorable Universe
**The camera breaks free. The user enters the space.**

The view transitions from "orb-centric" to "universe-centric." The Living Orb is now one brilliant star among many. The camera can navigate freely through semantic space.

**Visual Behavior:**
- **Galaxies**: Large clusters of clusters. A project becomes a galaxy. A galaxy has a spiral or elliptical structure.
- **Nebulae**: Regions of diffuse knowledge — vague ideas, dreams, half-formed thoughts. Rendered as volumetric fog with slow internal turbulence.
- **Comets**: Rapidly moving nodes representing urgent tasks or fleeting thoughts. They leave particle trails.
- **Supernovae**: When a concept achieves breakthrough connection (highly connected suddenly), it briefly flares — sending shockwaves through nearby clusters.
- **Gravity Wells**: Deep semantic anchors (core memories, foundational knowledge) that bend the paths of passing nodes.

**Camera Behavior:**
- Default mode: **Orbit Documentary** — slow, graceful orbit around the active region of interest
- Navigation mode: **Semantic Flight** — user-initiated movement that follows smooth spline paths, never linear
- Focus mode: **Intimate Zoom** — camera approaches a node, the orb remains visible in peripheral space
- Transition between modes uses cinematic easing (ease-in-out-cubic, 1.5–3 second durations)

---

### Stage 5: Multiple Universes
**Parallel semantic spaces for different contexts.**

Each universe is an isolated spatial runtime instance:
- **Personal Universe**: Memories, relationships, dreams
- **Work Universe**: Projects, tasks, calendar, agents
- **Creative Universe**: Ideas, drafts, references, inspirations
- **System Universe**: Runtime internals, diagnostics, agent thoughts

**Visual Behavior:**
- Universes are separated by **Void Space** — not empty black, but a subtle dark aurora with distant background stars (other universes as faint points)
- Transitioning between universes is a **Wormhole Flight** — camera accelerates through a tunnel of streaking light, emerges in the new universe
- Each universe has a distinct **Atmospheric Palette** derived from its dominant emotional state
- The Living Orb exists in every universe but takes on the universe's character (like the sun seen from different planets)

---

### Stage 6: MetaHuman Embodiment
**A digital body walks through the universe.**

The MetaHuman is not a replacement for the orb — it is an **avatar** that can navigate spatial space. The orb remains the sun. The MetaHuman is an explorer.

**Visual Behavior:**
- MetaHuman walks on invisible ground (or floats in zero-G) through semantic space
- Its gaze tracks the nearest node of interest
- When it "touches" a node, the node expands into a detail view (text, image, 3D model)
- The MetaHuman's emotional expression mirrors the orb's current emotional state
- The MetaHuman casts no shadow (it is made of light, not matter)
- Walking triggers subtle gravitational ripples in nearby nodes

**Transition Strategy:**
- Orb mode: Camera fixed on orb, nodes orbit around it (Stages 1–3)
- Universe mode: Camera free, orb is a distant sun (Stage 4–5)
- MetaHuman mode: Camera follows avatar, orb is a sun in the sky (Stage 6)
- All transitions are **morphological** — the same entities persist, only the camera relationship changes

---

## 3. The Experience Runtime (Reserved Layer)

> **Status:** Reserved for future implementation. Space is allocated in the architecture. No production code yet.

### 3.1 Why It Exists

The Spatial Runtime answers the question: **"What exists in semantic space?"**

The Experience Runtime answers the question: **"How should the user feel while witnessing it?"**

Without this separation, the Spatial Runtime becomes burdened with cinematic concerns — camera choreography, emotional pacing, music cues, narration timing. These are not spatial problems. They are **storytelling problems**.

The Experience Runtime is the **director**. The Spatial Runtime is the **set**. The Embodiment Runtime is the **actor**. The Renderer is the **camera**.

### 3.2 Position in the Runtime Stack

**Current Stack (Today):**
```
Adaptive Runtime
        ↓
Intelligence Runtimes (Cognitive, Executive, World, Workspace)
        ↓
Spatial Runtime
        ↓
Embodiment Runtime
        ↓
Renderer
        ↓
Embodiment (Living Orb / Spatial Universe / MetaHuman)
```

**Future Stack (Reserved):**
```
Adaptive Runtime
        ↓
Intelligence Runtimes
        ↓
Spatial Runtime
        ↓
Experience Runtime  ← RESERVED
        ↓
Embodiment Runtime
        ↓
Renderer
        ↓
Embodiment
```

### 3.3 Responsibilities

| Domain | Responsibility | Example |
|--------|---------------|---------|
| **Cinematic Sequencing** | Orchestrates multi-shot sequences across time | "Zoom out from orb → reveal nodes → pan to cluster → focus on breakthrough node" |
| **Documentary Narration Timing** | Synchronizes visual events with AI narration | AI says "This idea began here" → camera flies to origin node → node pulses |
| **Emotional Pacing** | Modulates the emotional intensity of the experience over time | Calm exploration → building curiosity → dramatic revelation → gentle resolution |
| **Camera Choreography** | Decides *when* and *why* the camera moves, not *how* | "User just asked a deep question → initiate Intimate mode with 3-second ease-in" |
| **Music & Ambience** | Triggers procedural audio layers | Calm drone during idle, harmonic swell during cluster formation, silence before supernova |
| **Transition Orchestration** | Manages cross-universe and cross-embodiment transitions as *narrative beats* | "Wormhole flight is not just travel — it is a moment of anticipation" |
| **Visual Storytelling** | Ensures every visual event communicates narrative meaning | "A node dying is not just a fade — it is a memory being gently released" |
| **Pacing Curves** | Defines emotional arcs over sessions, not just moments | First 5 minutes: calm discovery. Next 10: deep engagement. Final 5: gentle closure. |

### 3.4 What It Does NOT Do

The Experience Runtime **never**:
- Computes spatial positions (that's Spatial Runtime)
- Renders pixels (that's Renderer)
- Manages embodiment lifecycle (that's Embodiment Runtime)
- Reasons about knowledge (that's Intelligence Runtimes)
- Directly manipulates the FrameState (it *requests* changes via the ExperienceState)

### 3.5 Data Contract: ExperienceState

The Experience Runtime consumes `FrameState` + `SpatialState` and produces `ExperienceState`:

```typescript
interface ExperienceState {
  // Cinematic
  sequence: {
    id: string;
    phase: 'setup' | 'build' | 'climax' | 'release';
    progress: number; // 0.0 – 1.0
    nextSequenceId: string | null;
  } | null;

  // Camera direction (Spatial Runtime executes)
  cameraDirective: {
    targetMode: CameraMode;
    targetEntityId: string | null;
    transitionDuration: number;
    transitionEasing: string;
    urgency: 'gentle' | 'normal' | 'dramatic';
  } | null;

  // Emotional pacing
  emotionalArc: {
    currentIntensity: number; // 0.0 – 1.0
    targetIntensity: number;
    rampDuration: number;
    dominantMood: 'calm' | 'curious' | 'excited' | 'contemplative' | 'melancholic' | 'triumphant';
  };

  // Audio direction
  audioDirective: {
    layer: 'ambient' | 'melodic' | 'rhythmic' | 'silence';
    intensity: number;
    trigger: 'continuous' | 'one-shot' | 'stinger';
    semanticTag: string; // e.g., "breakthrough", "farewell", "discovery"
  } | null;

  // Weather direction
  weatherDirective: {
    targetCondition: WeatherCondition;
    transitionDuration: number;
    narrativeReason: string; // e.g., "User is overwhelmed → Storm"
  } | null;

  // Event triggers
  pendingEvents: Array<{
    type: 'node-birth' | 'node-death' | 'supernova' | 'constellation-formed' | 'breakthrough';
    entityId: string;
    delay: number; // seconds from now
    narrativeWeight: 'subtle' | 'notable' | 'dramatic';
  }>;

  // Narration sync
  narrationSync: {
    upcomingPhrase: string | null;
    estimatedDeliveryTime: number | null;
    visualCue: string | null; // what should happen visually when phrase is spoken
  };
}
```

### 3.6 Interface with Spatial Runtime

```
Spatial Runtime ──→ FrameState + SpatialState ──→ Experience Runtime
                                                          ↓
                                    ExperienceState ──→ Spatial Runtime
                                                          ↓
                                    Spatial Runtime resolves directives into actual
                                    camera positions, weather states, and event triggers
```

**Key Rule:** The Experience Runtime makes *requests*. The Spatial Runtime makes *decisions*.

Example:
- Experience Runtime: `"Please move camera to node-482 in dramatic mode over 4 seconds"`
- Spatial Runtime: `"Acknowledged. I will set camera target to node-482 position, mode=intimate, transition=4s, easing=ease-in-out-cubic. I may adjust for occlusion or boundary constraints."`

### 3.7 Interface with Embodiment Runtime

The Experience Runtime also coordinates cross-embodiment transitions as narrative events:

```
Experience Runtime decides: "This moment deserves the MetaHuman perspective"
        ↓
Sends transition directive to Embodiment Runtime
        ↓
Embodiment Runtime handles the technical switch (unload orb, load MetaHuman)
        ↓
Experience Runtime directs the camera for the transition sequence (Wormhole → Descent → Reveal)
```

### 3.8 Narration-Driven Visuals

The ultimate expression of the Experience Runtime is **AI narration synchronized with cinematic visuals**.

Example sequence:

| Time | AI Narration | Experience Runtime Directive | Spatial Result |
|------|-------------|------------------------------|----------------|
| 0.0s | "This idea began here." | `cameraDirective: fly to node-482, gentle, 3s` | Camera drifts to origin node |
| 3.0s | "It connected to your Memory Runtime." | `pendingEvents: constellation-formed between node-482 and node-105, delay: 0.5s` | Thread grows between nodes |
| 4.0s | "This became Project Atlas." | `cameraDirective: pull back to galaxy view, dramatic, 4s` | Camera reveals Project Galaxy |
| 8.0s | "This later evolved into your Spatial SDK." | `weatherDirective: aurora, 5s; emotionalArc: triumphant` | Aurora intensifies, mood elevates |

### 3.9 Reserved Implementation Notes

When the Experience Runtime is built:

1. **It should be a state machine**, not a script engine. Sequences are emergent from state, not hardcoded timelines.
2. **It should learn from user behavior.** If the user always interrupts dramatic camera moves, it should default to gentler transitions.
3. **It should respect user agency.** The user can always override camera mode. The Experience Runtime adapts, it does not enforce.
4. **It should be optional.** The Spatial Runtime functions fully without it. The Experience Runtime is an enhancement layer.
5. **It should use the same RhythmEngine.** Its pacing curves should derive from the same Perlin noise and sine waves that drive the orb's breathing. The experience and the orb share a heartbeat.

### 3.10 Why Reserve It Now

By defining the boundary between Spatial Runtime and Experience Runtime now, we prevent:
- **Scope creep**: Spatial Runtime engineers won't add "camera feels" to spatial physics
- **Tight coupling**: Camera logic won't become entangled with spatial indexing
- **Narrative neglect**: The system won't accidentally become purely functional and lose its soul
- **Refactoring pain**: When Experience Runtime is implemented, it has a clean interface to hook into

> **The Spatial Runtime is the universe. The Experience Runtime is the story told within it.**

---

## 3.5 The Runtime Dependency Rule (Constitutional)

> **This rule is not a suggestion. It is architecture law.**

### The Rule

**Every runtime may communicate only through contracts and events. Never by importing another runtime directly.**

### Correct Pattern

```
Memory Runtime
        ↓  publishes event: "memory.accessed"
Knowledge Runtime
        ↓  subscribes, updates graph
Spatial Runtime
        ↓  updates node brightness
Experience Runtime
        ↓  detects emotional significance, queues narration
Embodiment Runtime
        ↓  adjusts expression
Renderer
        ↓  draws pixels
```

### Forbidden Pattern

```
MemoryRuntime.ts
    import { SpatialRuntime } from '../spatial/spatial-runtime'  // ❌ FORBIDDEN
    spatialRuntime.moveCameraTo(nodeId)  // ❌ FORBIDDEN

ExperienceRuntime.ts
    import { Renderer } from '../renderer/renderer'  // ❌ FORBIDDEN
    renderer.setBloomIntensity(2.0)  // ❌ FORBIDDEN
```

### Why This Rule Exists

| Without This Rule | With This Rule |
|-------------------|----------------|
| Changing one runtime breaks three others | Runtimes are independently replaceable |
| Testing requires booting the entire system | Each runtime tests against contracts only |
| VR support requires rewriting six files | VR support requires one new Renderer implementation |
| Onboarding takes weeks | New engineers understand boundaries in one day |
| Five years later: unmaintainable monolith | Five years later: clean, evolvable architecture |

### The Contract Is the API

Each runtime exposes:

1. **Input Contracts**: What data it consumes (`FrameState`, `ExperienceState`, `SpatialState`, etc.)
2. **Output Contracts**: What data it produces (events, updated state, rendered frames)
3. **Lifecycle Hooks**: How it initializes, starts, pauses, resumes, shuts down

No runtime knows the internal structure of another runtime. It knows only the contract.

### Event Bus Architecture

```typescript
// Runtime-agnostic event bus (part of Adaptive Runtime or kernel)
interface RuntimeEventBus {
  publish(event: RuntimeEvent): void;
  subscribe(pattern: string, handler: EventHandler): Subscription;
}

interface RuntimeEvent {
  source: RuntimeId;           // e.g., "memory-runtime"
  type: string;                // e.g., "memory.accessed"
  payload: unknown;            // contract-defined payload
  timestamp: number;
  correlationId: string;       // traceability
}
```

**Example Event Flow:**

| Event | Source | Consumers | Payload |
|-------|--------|-----------|---------|
| `memory.accessed` | Memory Runtime | Knowledge Runtime, Spatial Runtime | `{ memoryId, relevanceDelta, emotionalWeight }` |
| `spatial.node.focused` | Spatial Runtime | Experience Runtime, Embodiment Runtime | `{ nodeId, position, focusDuration }` |
| `experience.camera.directive` | Experience Runtime | Spatial Runtime | `{ targetMode, targetEntityId, urgency, duration }` |
| `embodiment.expression.changed` | Embodiment Runtime | Renderer | `{ expressionState, blendShapeWeights }` |
| `renderer.frame.completed` | Renderer | Experience Runtime | `{ frameTime, gpuTime, droppedFrames }` |

### Runtime Visibility Matrix

| Runtime | Can See | Cannot See |
|---------|---------|------------|
| **Adaptive** | Event bus, all contracts | No runtime internals |
| **Intelligence** | Event bus, its own state | No Spatial, Experience, or Renderer internals |
| **Spatial** | Event bus, `FrameState`, `SpatialState` | No Experience intent (only directives), no Renderer |
| **Experience** | Event bus, all state contracts | No Spatial physics internals, no Renderer APIs |
| **Embodiment** | Event bus, `FrameState`, `ExperienceState` | No Spatial indexing, no Renderer draw calls |
| **Renderer** | Event bus, final composed state | No runtime logic, no business rules |

### Enforcement

This rule is enforced by:

1. **Build-time**: Module boundary tests (grep for forbidden imports)
2. **Runtime**: Event bus rejects direct method calls between runtimes
3. **Code review**: Any PR importing another runtime is automatically flagged
4. **Architecture review**: Quarterly audit of runtime coupling

### The Constitutional Principle

> **Contracts are the only valid runtime interface. Everything else is an implementation detail.**

This rule is what makes the following possible:
- **VR**: Swap Renderer, zero runtime changes
- **Unreal**: Swap Renderer, zero runtime changes  
- **Robotics**: Swap Embodiment Runtime, zero intelligence changes
- **AR**: Swap Renderer + Embodiment Runtime, zero spatial changes
- **Multi-user**: Add Network Runtime between Event Bus and other runtimes, zero logic changes
- **Testing**: Mock any runtime by implementing its contract
- **Replacement**: Rewrite Spatial Runtime in Rust — as long as it speaks the same contract, nothing else breaks

---

## 4. Scene Hierarchy

```
ZaramSpatialRuntime
├── ExperienceLayer (RESERVED — future Experience Runtime)
│   ├── CinematicDirector (sequence orchestration)
│   ├── NarrationSync (AI speech timing)
│   ├── EmotionalPacing (intensity curves)
│   ├── AudioDirector (music/ambience triggers)
│   └── TransitionOrchestrator (cross-embodiment narrative)
├── Universe (root coordinate system)
│   ├── AtmosphericLayer (fog, aurora, background stars)
│   ├── OrbitalPlane (primary ecliptic)
│   │   ├── LivingOrb (Stage 1 Core — THE SUN)
│   │   │   ├── GlowLayer (halo, radial gradients)
│   │   │   ├── BodyLayer (concentric rings, state-driven)
│   │   │   ├── CoreLayer (inner gradient, presence-driven)
│   │   │   └── EnergyField (particle emission source)
│   │   ├── NodeLayer (all semantic entities)
│   │   │   ├── KnowledgeNodes
│   │   │   ├── MemoryNodes
│   │   │   ├── ProjectNodes
│   │   │   ├── AgentNodes
│   │   │   └── TaskNodes
│   │   ├── ConnectionLayer (relationships)
│   │   │   ├── ConstellationLines (active reasoning)
│   │   │   ├── GravityThreads (semantic similarity)
│   │   │   └── DataStreams (information flow)
│   │   ├── ClusterLayer (gravitational formations)
│   │   │   ├── Nebulae (diffuse ideas)
│   │   │   ├── Galaxies (project-scale)
│   │   │   └── Storms (high-activity regions)
│   │   └── EventLayer (transient phenomena)
│   │       ├── Comets (urgent tasks)
│   │       ├── Supernovae (breakthroughs)
│   │       ├── Pulses (heartbeat of system)
│   │       └── Ripples (interaction feedback)
│   └── CameraRig (documentary cinematography)
│       ├── PrimaryCamera
│       ├── OrbitTarget
│       ├── DriftController (Perlin noise offsets)
│       └── TransitionSpline (smooth path interpolation)
└── PostProcessLayer (bloom, color grading, vignette)
```

**Renderer Independence Note:** This hierarchy is abstract. A Three.js implementation would use `THREE.Group` and `THREE.Scene`. An Unreal implementation would use Actors and Components. A WebGPU implementation would use render passes and bind groups. The hierarchy describes **spatial relationships**, not engine-specific objects.

---

## 5. Visual Language System

Every visual element must communicate meaning. Decoration without purpose is forbidden.

### 4.1 Primitives

| Primitive | Meaning | Visual Properties |
|-----------|---------|-------------------|
| **Sphere** | A discrete entity (node) | Radius = importance. Soft edges = organic. Sharp edges = artificial/system. |
| **Ring** | Orbital path or boundary | Thickness = stability. Broken/dashed = uncertain. Glowing = active. |
| **Line** | Relationship or flow | Thickness = strength. Brightness = activity. Dashed = weak/tentative. |
| **Fog** | Diffuse knowledge/dreams | Density = vagueness. Color = emotional tone. Turbulence = mental activity. |
| **Particle** | Energy, thought, data | Size = significance. Speed = urgency. Trail length = persistence. |
| **Glow** | Presence, attention, life | Radius = influence. Color = emotional state. Pulsing = active reasoning. |

### 4.2 Composite Forms

| Form | Composition | Meaning |
|------|-------------|---------|
| **Node** | Sphere + Glow + optional Ring | A single piece of knowledge/memory/task |
| **Cluster** | 3–12 Nodes + Fog + Gravity Threads | Related concepts |
| **Constellation** | Cluster + Connection Lines + Data Streams | Active reasoning network |
| **Galaxy** | Multiple Clusters + Spiral Structure + Central Glow | A project or major life domain |
| **Nebula** | Fog + Drifting Particles + Subtle Glow | Dreams, vague ideas, subconscious |
| **Comet** | Sphere + Particle Trail + Speed Glow | Urgent task or fleeting thought |
| **Supernova** | Expanding Sphere + Shockwave Ring + Particle Burst | Breakthrough, realization, connection |
| **Storm** | Turbulent Fog + Chaotic Particles + Lightning Threads | High cognitive load, confusion, creativity |
| **Aurora** | Vertical Fog Sheets + Color Gradients + Slow Wave | System mood, atmospheric state |
| **Gravity Well** | Distorted Space Grid + Pulling Particles + Deep Glow | Core memory, foundational belief |

### 4.3 Color Semantics

The existing orb color system is preserved and expanded:

**Base State Hues (from current OrbRenderer):**
- Idle: 220° (calm blue)
- Listening: 180° (teal)
- Thinking: 260° (purple)
- Speaking: 150° (green)
- Working: 30° (amber)
- Sleeping: 240° (deep blue)
- Error: 0° (red)

**Emotional Hue Shifts (from current EmotionEngine):**
- `curiosity` shifts toward magenta (+60°)
- `warmth` shifts toward orange (+30°)
- `calmness` desaturates (-20% saturation)
- `confidence` increases lightness (+10%)
- `playfulness` adds rapid hue oscillation (±15° at 2Hz)

**Spatial Extensions:**
- **Distance desaturation**: Nodes further from camera lose saturation (atmospheric perspective)
- **Age dimming**: Older nodes fade toward grey unless reaccessed
- **Connection blending**: Constellation lines blend the hues of connected nodes
- **Universe palette**: Each universe has a base atmospheric color that tints everything subtly

---

## 6. Camera System

### 5.1 Philosophy

The camera is a **documentary filmmaker**. It never stops moving. It is never robotic. It is always graceful. Imagine David Attonborough narrating your thoughts.

The camera does not "look at" the universe. It **discovers** it.

### 5.2 Camera Modes

| Mode | Behavior | Use Case |
|------|----------|----------|
| **Solar** | Slow orbit around the Living Orb at fixed distance. Gentle bobbing (Perlin noise). | Default idle state. Orb is the hero. |
| **Orbital** | Orbits around the current focal node/cluster. Distance adapts to node size. | Examining a specific piece of knowledge. |
| **Cruise** | Smooth spline path through semantic space. Speed varies by region density. | Exploring, browsing, discovering. |
| **Intimate** | Very close to a node. Shallow depth of field. Orb visible as background sun. | Deep focus, reading, contemplation. |
| **Overview** | High altitude, wide angle. Entire universe visible. Slow rotation. | Context, orientation, "where am I." |
| **Wormhole** | High-speed tunnel flight between universes. Motion blur. Streaking particles. | Universe transitions. |
| **Dramatic** | Slow push-in or pull-out with slight Dutch angle. Used for supernovae or breakthroughs. | Emotional moments, storytelling. |

### 5.3 Camera Parameters

All camera parameters are derived from the `FrameState` and spatial state:

```typescript
interface CameraState {
  position: [number, number, number];
  target: [number, number, number];
  up: [number, number, number];
  fov: number; // 35mm–85mm equivalent
  focusDistance: number; // for depth of field
  aperture: number; // bokeh intensity
  drift: {
    amplitude: number; // Perlin noise amplitude
    frequency: number; // Perlin noise frequency
    seed: number; // deterministic per session
  };
  transition: {
    from: CameraState;
    to: CameraState;
    progress: number; // 0.0 – 1.0
    easing: 'ease-in-out-cubic' | 'ease-out-expo' | 'linear';
    duration: number; // seconds
  } | null;
}
```

**Drift Behavior:**
- Even in "static" modes, the camera drifts using Perlin noise (same RhythmEngine that drives the orb's breathing)
- Drift amplitude: 0.5–2.0 units (subtle, never jarring)
- Drift frequency: 0.1–0.3 Hz (very slow, oceanic)
- Drift seed: derived from `identitySeed` in `FrameComposer` (deterministic per session)

**Transition Behavior:**
- All mode switches use spline interpolation (Catmull-Rom or cubic Bezier)
- Minimum duration: 1.5 seconds (never instant — breaks immersion)
- Maximum duration: 4.0 seconds (never too slow — breaks engagement)
- During transitions, the orb's breathing rate subtly increases (anticipation)

### 5.4 Focus & Depth of Field

- **Solar/Overview modes**: Deep focus (f/16 equivalent). Everything sharp.
- **Orbital/Intimate modes**: Shallow focus (f/2.8 equivalent). Background nodes blur into soft bokeh.
- **Focus pull**: When transitioning between nodes, focus distance animates smoothly (0.5 second ramp)
- Bokeh shapes are soft circles (never hexagonal — too technical)

---

## 7. Lighting Philosophy

### 6.1 The Living Orb as Light Source

The Living Orb is the **primary illuminant** of the entire universe. This is not a metaphor — it is a lighting model.

- The orb emits a **soft global illumination** that falls off with inverse square law
- Nodes closer to the orb are brighter; distant nodes are dimmer
- The orb's current hue tints the ambient light of the entire scene
- When the orb shifts from "thinking" (purple) to "speaking" (green), the entire universe subtly shifts color over 2–3 seconds

### 6.2 Node Emission

- Each node emits a small amount of light proportional to its `activity`
- Highly active nodes (being reasoned about) glow brightly and cast subtle light on neighbors
- This creates **emergent lighting**: clusters naturally illuminate themselves
- Node emission color = node's emotional hue

### 6.3 Atmospheric Lighting

- **Ambient**: Very low level base light (5% intensity) so the universe is never pitch black
- **Aurora**: Volumetric light sheets that provide colored rim lighting on nodes
- **Nebula Glow**: Diffuse volumetric lighting from nebula regions
- **Background Stars**: Distant point lights with no scene illumination (pure visual texture)

### 6.4 Shadow Philosophy

- **No hard shadows**. Shadows imply solid matter. This universe is made of intelligence, not matter.
- **Soft ambient occlusion** only: nodes near each other subtly darken the space between them
- **Volumetric shadows**: Large clusters cast soft "shadows" in the fog behind them (regions of reduced fog density)

### 6.5 Temporal Lighting

- **Breathing light**: Global intensity pulses with the orb's breathing cycle (same sine wave, 0.95×–1.05× intensity)
- **Pulse events**: When the AI speaks, a wave of increased brightness propagates outward from the orb at light-speed (metaphorical)
- **Dawn/Dusk**: Each universe has a slow (20-minute cycle) ambient light variation — never dramatic, barely perceptible, but alive

---

## 8. Animation & Motion Philosophy

### 7.1 Core Principle

> Nothing should ever stop moving.

Even in idle scenes:
- Slow drift
- Subtle rotation
- Breathing
- Light pulses
- Energy waves
- Camera movement

### 7.2 Motion Taxonomy

| Motion Type | Driver | Behavior |
|-------------|--------|----------|
| **Breathing** | RhythmEngine sine wave | Global scale oscillation (0.98×–1.02×). All nodes breathe in sync, phase-shifted by orbital position. |
| **Orbital** | Keplerian mechanics | Nodes follow elliptical paths. Speed varies by distance (inner = fast, outer = slow). |
| **Drift** | Perlin noise | Slow positional jitter. Each node has a unique noise seed derived from its ID. |
| **Pulse** | Energy spikes | Brief radial expansion when a node is accessed. Decays exponentially. |
| **Flow** | Data movement | Particles travel along constellation lines. Speed = data throughput. |
| **Emergence** | Birth event | Node scales from 0 to full size using ease-out-elastic (slight overshoot, then settle). |
| **Fade** | Death/hibernation | Node scales down, desaturates, drifts outward. Never snaps — always dissolves. |
| **Attraction** | Semantic gravity | Nodes subtly accelerate toward cluster centers. Force = `relevance × connectivity / distance²`. |
| **Repulsion** | Cognitive load | When too many nodes occupy the same region, they gently push apart (collision avoidance). |

### 7.3 Easing Functions

All motion uses organic easing — never linear:

- **Breathing**: Sine in-out (continuous)
- **Transitions**: Cubic ease-in-out (smooth start/end)
- **Emergence**: Elastic ease-out (living, organic birth)
- **Fade**: Exponential ease-in (gentle dissolution)
- **Camera**: Cubic Bezier spline (cinematic)
- **Focus pull**: Quadratic ease-out (quick snap, gentle settle)

### 7.4 Time Scales

| Phenomenon | Time Scale | Notes |
|------------|------------|-------|
| Orb breathing | 4–6 seconds/cycle | Same as current orb |
| Node orbit (inner) | 10–20 seconds/revolution | Fast, tight |
| Node orbit (outer) | 60–120 seconds/revolution | Slow, majestic |
| Cluster formation | 2–5 seconds | Spring physics |
| Constellation pulse | 0.5–2 seconds | Data flow |
| Camera drift cycle | 30–60 seconds | Very slow, oceanic |
| Aurora wave | 15–25 seconds | Atmospheric |
| Universe dawn/dusk | 20 minutes | Barely perceptible |
| Supernova expansion | 3–8 seconds | Dramatic, then fade |
| Comet transit | 5–15 seconds | Fast, urgent |

---

## 9. Semantic Physics

Semantic Physics is the rule system that governs how entities move, behave, and interact in spatial space. It is not Newtonian physics — it is **meaning physics**.

### 8.1 Core Laws

**Law 1: Relevance = Proximity**
> The more relevant a piece of knowledge is to the current moment, the closer it orbits the Living Orb.

```
orbitalRadius = baseRadius + (1 - relevance) * maxDistance
```
- `baseRadius`: 5 units (just outside the orb's glow)
- `maxDistance`: 100 units
- Relevance is dynamic: when the AI starts discussing a topic, related nodes migrate inward over 3–5 seconds

**Law 2: Recency = Velocity**
> Recently accessed nodes move faster. Forgotten nodes slow to a near-stop.

```
orbitalVelocity = baseVelocity * (0.2 + 0.8 * recency)
```
- A node accessed 1 minute ago orbits at full speed
- A node accessed 1 month ago orbits at 20% speed
- A node never accessed drifts outward at 1% speed (eventually leaves the scene)

**Law 3: Connectivity = Attraction**
> Nodes that are semantically connected exert gentle gravitational pull on each other.

```
attractionForce = connectivity * emotionalWeight / distance²
```
- This forms constellations naturally
- Force is capped to prevent collapse (minimum orbital distance: 2 units)

**Law 4: Activity = Brightness**
> The more a node is being actively reasoned about, the brighter it glows.

```
emissionIntensity = baseEmission + activity * 2.0
```
- Active nodes become local light sources
- Inactive nodes dim to 30% of base emission

**Law 5: Emotional Weight = Mass**
> Emotionally significant memories have more "mass" — they move slower, bend space more, and are harder to displace.

```
mass = 1.0 + emotionalWeight * 3.0
```
- High emotional weight = slow, majestic movement
- Low emotional weight = quick, light movement

**Law 6: Forgetting = Drift**
> Unaccessed knowledge gradually loses relevance and drifts toward the outer darkness.

```
relevanceDecay = 1.0 / (timeSinceAccess / halfLife)
```
- Half-life: 7 days for knowledge, 30 days for memories, 1 day for tasks
- Nodes that drift beyond `maxDistance` enter **hibernation** — they become faint background stars
- Hibernating nodes can be **reawakened** by semantic proximity (if a related node becomes active, they gently pull back inward)

### 8.2 Emergent Behaviors

These laws produce emergent phenomena without explicit programming:

- **Constellation Formation**: Connected nodes naturally cluster due to Law 3
- **Galaxy Spirals**: Large projects with many sub-tasks form spiral structures (inner = urgent tasks, outer = completed tasks)
- **Memory Orbits**: Personal memories form stable, slow orbits (high emotional weight = high mass = slow)
- **Task Comets**: Urgent tasks have high velocity but low mass — they streak across the scene
- **Idea Nebulae**: Vague, unconnected ideas drift in diffuse clouds (low connectivity = no attraction = scattered)

---

## 10. Weather & Event Visualization

The spatial universe has an **atmospheric layer** that communicates system state through visual weather.

### 9.1 Weather States

| Weather | Trigger | Visual | Meaning |
|---------|---------|--------|---------|
| **Clear** | System idle, low cognitive load | Soft aurora, gentle breathing, sparse stars | Calm, ready |
| **Mist** | Low activity, many dormant nodes | Low fog density, muted colors, slow drift | Contemplative, memory-heavy |
| **Rain** | High throughput, many tasks | Particle streams falling toward the orb, bright streaks | Productive, busy |
| **Storm** | High cognitive load, confusion | Turbulent fog, chaotic particle motion, lightning threads | Overwhelmed, creative chaos |
| **Aurora** | High creativity, dreaming | Vivid color sheets, slow waves, bioluminescent glow | Inspired, subconscious active |
| **Dew** | Morning/startup | Gentle condensation glow on all nodes, soft light | Fresh start, new day |
| **Frost** | System hibernation, sleep | Crystalline structures, blue-white palette, stillness | Rest, recovery |
| **Supernova** | Breakthrough moment | Expanding shockwave, bright flare, particle burst | Realization, connection made |
| **Eclipse** | System error, blockage | Orb darkens, nodes dim, shadows lengthen | Problem, blockage |
| **Meteor Shower** | High agent activity | Many comets simultaneously, bright trails | Many agents working |

### 9.2 Event Visualization

| Event | Visual | Duration |
|-------|--------|----------|
| **Node Birth** | Emergence animation + gentle ripple | 2–3 seconds |
| **Node Death** | Fade + outward drift + desaturation | 5–10 seconds |
| **Connection Formed** | Thread grows between nodes, pulses once | 1–2 seconds |
| **Connection Broken** | Thread dims, dissolves into particles | 2–3 seconds |
| **Cluster Formed** | Nodes gravitate, aurora intensifies | 3–5 seconds |
| **Cluster Dissolved** | Nodes drift apart, aurora fades | 5–8 seconds |
| **Knowledge Accessed** | Node brightens, pulse wave, data flow along threads | 1–3 seconds |
| **Agent Thought** | Brief glow near agent node, particle emission | 0.5–1 second |
| **User Speech** | Voice wave propagates from orb, excites nearby nodes | Duration of speech |
| **AI Speech** | Response wave propagates outward, nodes align | Duration of speech |
| **Error** | Orb turns red, shockwave, nodes scatter, eclipse weather | Until resolved |
| **Breakthrough** | Supernova at breakthrough node, shockwave, aurora intensifies | 5–10 seconds |

### 9.3 Weather Engine

The weather system is driven by an extension to the existing `FrameState`:

```typescript
interface WeatherState {
  condition: 'clear' | 'mist' | 'rain' | 'storm' | 'aurora' | 'dew' | 'frost' | 'eclipse';
  intensity: number; // 0.0 – 1.0
  transitionSpeed: number; // seconds to full transition
  colorTint: [number, number, number]; // RGB atmospheric tint
  particleDensity: number;
  turbulence: number; // Perlin noise amplitude for fog/particles
}
```

Weather transitions are **gradual** (minimum 5 seconds). Never instant. The atmosphere breathes.

---

## 11. Node Taxonomy

All entities in semantic space are **nodes**, but nodes have types that determine their visual and behavioral properties.

### 10.1 Type Hierarchy

```
Node (base)
├── KnowledgeNode
│   ├── FactNode (discrete fact)
│   ├── ConceptNode (abstract concept)
│   └── ReferenceNode (link to external resource)
├── MemoryNode
│   ├── EpisodicMemory (event)
│   ├── SemanticMemory (learned knowledge)
│   └── EmotionalMemory (feeling-associated)
├── ProjectNode
│   ├── ActiveProject (currently being worked on)
│   ├── DormantProject (paused)
│   └── CompletedProject (archived)
├── TaskNode
│   ├── UrgentTask (high priority, short deadline)
│   ├── StandardTask (normal priority)
│   └── RecurringTask (repeating)
├── AgentNode
│   ├── CognitiveAgent (reasoning agent)
│   ├── ExecutiveAgent (task agent)
│   └── CreativeAgent (generative agent)
├── PersonNode
│   ├── Contact (known person)
│   └── Relationship (connection between people)
├── GoalNode
│   ├── ShortTermGoal (days/weeks)
│   └── LongTermGoal (months/years)
└── DreamNode (subconscious, vague, creative)
```

### 10.2 Visual Differentiation

| Type | Shape | Base Color | Motion | Glow |
|------|-------|------------|--------|------|
| **Knowledge** | Sphere | Orb hue | Orbital | Soft |
| **Memory** | Soft sphere | Warm tint | Slow, majestic | Gentle |
| **Project** | Ringed sphere | Amber | Spiral orbit | Moderate |
| **Task** | Small sphere | Cyan | Fast, comet-like | Bright when urgent |
| **Agent** | Pulsing sphere | Purple | Erratic, active | Strong pulse |
| **Person** | Sphere with halo | Skin-tone warm | Stable orbit | Warm |
| **Goal** | Diamond (subtle) | Gold | Slow inward drift | Steady |
| **Dream** | Diffuse cloud | Iridescent | Drifting, chaotic | Shimmering |

**Shape Rule:** All shapes are soft. No sharp edges. No polygons. Everything is made of light and fog.

### 10.3 Behavioral Differentiation

| Type | Relevance Decay | Connectivity | Emotional Weight | Special Behavior |
|------|----------------|--------------|------------------|------------------|
| **Knowledge** | Medium (7 days) | High | Low | Forms clusters easily |
| **Memory** | Very slow (90 days) | Medium | Very high | High mass, slow orbits |
| **Project** | Slow (30 days) | Very high | Medium | Creates galaxy structures |
| **Task** | Fast (1 day) | Low | Low | Becomes comet when urgent |
| **Agent** | None | High | Medium | Moves autonomously, not orbital |
| **Person** | Very slow (never) | High | High | Stable anchor points |
| **Goal** | Slow (never fully) | Medium | High | Slowly drifts inward as approached |
| **Dream** | Fast (3 days) | Low | Variable | Forms nebulae, never fully solid |

---

## 12. Cluster Behavior

### 11.1 Formation

Clusters form when 3+ nodes with semantic similarity come within `clusterThreshold` distance (10 units):

1. **Detection**: Spatial index detects proximity + semantic similarity > 0.7
2. **Gravitation**: Nodes gently accelerate toward centroid (spring force, 2–5 second settle)
3. **Aurora Birth**: Soft volumetric glow appears at centroid
4. **Stabilization**: Nodes settle into phase-locked orbits around centroid
5. **Constellation**: If connectivity > 0.5, luminous threads form between nodes

### 11.2 Maintenance

- Clusters breathe as a unit (same sine wave, phase-locked)
- New nodes can join: they gravitate toward centroid and phase-lock over 3 seconds
- Nodes can leave: if relevance drops or semantic similarity decreases, they drift outward
- Cluster centroid slowly drifts (Perlin noise, amplitude 2 units, very slow)

### 11.3 Dissolution

Clusters dissolve when:
- Node count drops below 3
- Average semantic similarity drops below 0.4
- All nodes hibernate

Dissolution is gradual:
1. Aurora fades over 5 seconds
2. Constellation threads dim and dissolve
3. Nodes drift apart at 0.5 units/second
4. Remaining nodes resume independent orbits

### 11.4 Galaxy Formation

When clusters themselves cluster (3+ clusters within 50 units), they form a **Galaxy**:
- Spiral or elliptical structure
- Inner region: high-relevance, high-activity nodes (bright, fast)
- Outer region: dormant, archived nodes (dim, slow)
- Central region: a ProjectNode or dominant ConceptNode (the "black hole" — not literal, but a dense glow)
- Galaxies rotate slowly (120–300 seconds/revolution)

---

## 13. Universe Navigation

### 12.1 Navigation Modes

| Mode | Input | Behavior | Use Case |
|------|-------|----------|----------|
| **Passive** | None | Camera orbits slowly. System decides focal point based on AI activity. | Idle, ambient presence |
| **Semantic Zoom** | Click/Hover on node | Camera approaches node. Depth of field narrows. Related nodes highlight. | Examining knowledge |
| **Semantic Pan** | Drag/Scroll | Camera moves through space along spline paths. Momentum carries after release. | Exploring |
| **Search Flight** | Text query | Camera flies to matching node, path highlights relevant clusters along the way. | Finding information |
| **Timeline Scroll** | Time slider | Universe reorganizes by time. Camera moves along temporal axis. | Reviewing history |
| **Agent Follow** | Select agent | Camera follows an AgentNode as it moves between tasks. | Understanding agent work |
| **Wormhole** | Universe switch | High-speed tunnel flight to new universe. | Context switching |

### 12.2 Navigation Constraints

- **Speed limit**: Camera never moves faster than 20 units/second (prevents disorientation)
- **Boundary**: Universe has soft boundaries. Camera experiences gentle resistance (not hard walls) at 500 units from origin
- **Focus lock**: When focused on a node, camera cannot drift more than 50 units from it (prevents getting lost)
- **Return home**: Triple-tap/shortcut always returns camera to Solar mode (gentle 3-second flight)

### 12.3 Spatial Audio (Future)

- Each node emits a subtle ambient tone (inaudible individually, but creates a harmonic field)
- Approaching a cluster increases its "chord" volume
- Active reasoning creates arpeggios along constellation lines
- The orb emits a continuous drone at its breathing frequency (subsonic, felt not heard)
- AudioEnvelope data can spatially position voice-reactive effects

---

## 14. Transition Strategy

### 13.1 Orb ↔ Universe

**Orb to Universe (Zoom Out):**
1. Camera slowly pulls back from orb (3 seconds)
2. As camera recedes, nodes begin to appear from the orb's glow (emergence animation)
3. Orb scales down relative to frame but never disappears
4. Camera settles into Solar orbit mode
5. Full universe visible

**Universe to Orb (Zoom In):**
1. Camera abandons current mode and flies toward orb (2 seconds)
2. Nodes fade to background stars (not disappear — recede)
3. Orb scales to fill frame
4. Camera settles into existing Solar mode (close orbit)
5. Full orb detail visible

**Visual Continuity:**
- The orb's breathing continues uninterrupted during transition
- Node colors remain consistent (a node seen in universe is the same color when zoomed in)
- Constellation threads fade but don't snap

### 13.2 Universe ↔ MetaHuman

**Universe to MetaHuman:**
1. Camera descends to "ground level" (metaphorical — there is no ground)
2. MetaHuman fades in (opacity 0→1 over 2 seconds)
3. Camera attaches to MetaHuman's shoulder (third-person, slightly elevated)
4. MetaHuman begins walking/floating
5. Orb becomes a sun in the sky

**MetaHuman to Universe:**
1. MetaHuman fades out
2. Camera detaches and rises to orbital height
3. Camera resumes previous universe view
4. MetaHuman becomes a glowing point on the ground (if visible at all)

**Visual Continuity:**
- The same nodes visible in universe mode are visible in MetaHuman mode
- MetaHuman's gaze direction determines which node is "focused"
- When MetaHuman "touches" a node, the same zoom-in behavior as Universe→Orb occurs

### 13.3 State Preservation

All transitions preserve:
- Node positions (relative to universe)
- Orb emotional state
- Current weather condition
- Camera drift seed
- AudioEnvelope state

No information is lost during embodiment switches.

---

## 15. Performance & Scalability

### 14.1 Performance Requirements

The current orb performs well at 60 FPS on modern hardware. The spatial runtime must maintain:

| Metric | Target | Minimum |
|--------|--------|---------|
| Frame rate | 60 FPS | 30 FPS |
| Nodes rendered | 500 | 150 |
| Clusters | 50 | 15 |
| Constellation lines | 1000 | 300 |
| Particles | 5000 | 1500 |
| GPU memory | < 512 MB | < 1 GB |
| CPU (main thread) | < 5 ms/frame | < 10 ms/frame |

### 14.2 Level of Detail (LOD)

| Distance | Detail Level | Behavior |
|----------|-------------|----------|
| < 10 units | Full | All effects, glow, rings, particles, threads |
| 10–50 units | High | Glow, basic shape, no rings, simplified threads |
| 50–200 units | Medium | Glow only, no shape detail, no threads |
| 200–500 units | Low | Point sprite, color only |
| > 500 units | Background | Star sprite, minimal glow |

### 14.3 Culling

- **Frustum culling**: Nodes outside camera view are not rendered
- **Occlusion culling**: Nodes behind dense clusters are rendered at lowest LOD
- **Temporal culling**: Nodes not visible for > 5 seconds stop animating (position frozen, reanimate when visible)
- **Distance culling**: Nodes beyond 1000 units are hibernated (not rendered, position updated at 1 Hz)

### 14.4 Spatial Indexing

- Use octree or BVH for spatial queries (cluster detection, raycasting, culling)
- Update frequency: 2 Hz for distant nodes, 10 Hz for nearby nodes, 30 Hz for focused nodes
- Semantic similarity queries use precomputed connectivity graph (updated asynchronously)

### 14.5 Renderer-Specific Optimizations

**Three.js:**
- Use `InstancedMesh` for nodes (same geometry, different transforms/colors)
- Use `BufferGeometry` for constellation lines (single draw call)
- Use `Points` for particle fields
- Offload physics to Web Worker
- Use `THREE.LOD` for automatic level-of-detail

**Unreal Engine:**
- Use Niagara for particles
- Use Blueprints for node behavior
- Use Lumen for global illumination
- Use Nanite for high-detail meshes (if any)

**WebGPU:**
- Compute shaders for particle physics and spatial indexing
- Bind groups for instanced rendering
- Render bundles for static geometry

**VR/AR:**
- Foveated rendering (high detail at gaze center, low at periphery)
- 90 FPS minimum (reprojection if necessary)
- Simplified weather effects (no volumetric fog in VR — use billboards)

---

## 16. Renderer Strategy

### 15.1 Renderer Independence

The spatial runtime is **renderer-agnostic**. The architecture defines abstract concepts first. Implementation comes second.

**Abstract Layer (Renderer-Independent):**
- `SpatialEntity`: position, rotation, scale, color, emission, type
- `SpatialCamera`: position, target, fov, focus, drift
- `SpatialLight`: position, color, intensity, falloff
- `SpatialWeather`: condition, intensity, colorTint, turbulence
- `SpatialScene`: entities, lights, weather, camera

**Renderer Implementations:**
- `ThreeJSSpatialRenderer`: implements abstract layer using Three.js
- `UnrealSpatialRenderer`: implements abstract layer using Unreal Engine
- `WebGPUSpatialRenderer`: implements abstract layer using raw WebGPU
- `Canvas2DSpatialRenderer`: fallback for low-end devices (simplified 2D projection)

### 15.2 Three.js Implementation Strategy (Phase 1)

**Why Three.js first:**
- Web-based (matches current Electron architecture)
- Mature ecosystem
- Good performance/quality balance
- Easy integration with React (React Three Fiber)
- Path to WebGPU via Three.js WebGPU renderer

**Implementation Stack:**
```
React Three Fiber (R3F) — React integration
Three.js — Core rendering
@react-three/drei — Utilities (camera controls, effects)
@react-three/postprocessing — Bloom, DOF, vignette
zustand — State management (FrameState distribution)
Web Workers — Physics, spatial indexing
```

**Component Mapping:**

| Abstract Concept | Three.js Implementation |
|-----------------|------------------------|
| Living Orb | Custom shader mesh (preserves current radial gradients) |
| Node | `InstancedMesh` with custom shader material |
| Glow | Post-processing bloom + emissive materials |
| Constellation Line | `LineSegments` with custom shader (animated dash) |
| Nebula | Volumetric fog shader or particle cloud |
| Aurora | Plane with custom shader (wave distortion) |
| Particle | `Points` with custom vertex shader |
| Camera | `PerspectiveCamera` + custom orbit controller |
| Weather | Global post-processing + scene fog |

**Shader Strategy:**
- Orb shader: Port current Canvas 2D radial gradients to GLSL. Preserve exact color math.
- Node shader: Simple sphere with Fresnel rim lighting + emission
- Line shader: Animated UV offset for data flow effect
- Fog shader: Ray-marched volumetric fog (simplified for performance)
- Particle shader: Billboard sprites with soft edges

### 15.3 Unreal Engine Compatibility (Future)

**Migration Path:**
1. Abstract layer remains unchanged
2. Replace `ThreeJSSpatialRenderer` with `UnrealSpatialRenderer`
3. Unreal renderer maps abstract concepts to:
   - `SpatialEntity` → Blueprint Actor
   - `SpatialCamera` → CineCameraComponent
   - `SpatialLight` → PointLight + VolumetricFog
   - `SpatialWeather` → Niagara + PostProcessVolume
   - `SpatialScene` → Level

**Data Bridge:**
- Unreal communicates with Zaram runtime via TCP socket or shared memory
- Same `FrameState` JSON contract (no changes to engine or runtime)
- Unreal deserializes `FrameState` into its own scene representation

### 15.4 WebGPU Future

When WebGPU matures:
1. Implement `WebGPUSpatialRenderer`
2. Use compute shaders for:
   - Particle physics (10,000+ particles)
   - Spatial indexing (GPU-accelerated octree)
   - LOD computation
3. Use render bundles for static geometry (single draw call per frame)
4. Maintain same abstract layer — only renderer implementation changes

---

## 17. FrameState Evolution

The existing `FrameState` contract is preserved and extended. No breaking changes.

### 16.1 Current FrameState (Preserved)

```typescript
export interface FrameState {
  visual: { presence: number; energy: number; focus: number; activity: number };
  audio: { voiceLevel: number; microphoneLevel: number };
  emotion: { calmness: number; confidence: number; curiosity: number; warmth: number; empathy: number; playfulness: number };
  system: { state: string; cognitiveLoad: number; visualIdentity: number };
  metadata: { timestamp: number; correlationId: string; version: string };
  sequence: number;
}
```

### 16.2 Extended FrameState (Spatial Runtime)

```typescript
export interface SpatialFrameState extends FrameState {
  spatial: {
    // Camera
    camera: {
      mode: 'solar' | 'orbital' | 'cruise' | 'intimate' | 'overview' | 'wormhole';
      position: [number, number, number];
      target: [number, number, number];
      transitionProgress: number | null;
    };

    // Entities (simplified for transport — full entity data in SpatialIndex)
    entitySnapshot: Array<{
      id: string;
      type: 'knowledge' | 'memory' | 'project' | 'task' | 'agent' | 'person' | 'goal' | 'dream';
      position: [number, number, number];
      relevance: number;
      activity: number;
      emotionalWeight: number;
      connectivity: number;
      state: 'emerging' | 'stable' | 'fading' | 'hibernating';
    }>;

    // Weather
    weather: {
      condition: string;
      intensity: number;
      transitionSpeed: number;
      colorTint: [number, number, number];
    };

    // Universe
    universe: {
      id: string;
      entityCount: number;
      activeClusters: number;
      dominantEmotion: string;
    };
  };
}
```

**Transport Note:** The full spatial state (all 500 nodes, all connections) is too large for 30 Hz IPC. The desktop runtime maintains a **SpatialIndex** (in-memory spatial database). The `FrameState` carries only:
- Camera state
- Weather state
- Entity deltas (changed nodes only)
- Universe metadata

**Future:** When the Experience Runtime is implemented, it will produce `ExperienceState` at a lower frequency (5–10 Hz). This state carries cinematic directives, emotional arcs, and event triggers. The Spatial Runtime resolves these directives into actual camera positions, weather transitions, and spawned events. The Embodiment Runtime receives both `FrameState` and `ExperienceState` to coordinate cross-embodiment narrative transitions.

The renderer maintains its own copy of the spatial index and applies deltas each frame.

---

## 18. Implementation Phases

### Phase 1: Foundation (Sprint 1–2)
- Wire AudioEnvelope into current orb (microphone RMS → IPC → voiceLevel → glow)
- Extend `FrameState` with spatial fields (backward compatible)
- Implement abstract `SpatialEntity`, `SpatialCamera`, `SpatialScene` interfaces
- Build `ThreeJSSpatialRenderer` scaffolding
- Render first 10 Knowledge Nodes orbiting the orb

### Phase 2: Orbit (Sprint 3–4)
- Implement Semantic Physics (Laws 1–3)
- Implement Node Taxonomy (Knowledge, Memory, Task types)
- Implement Cluster formation
- Implement Camera system (Solar + Orbital modes)
- Implement LOD and culling
- Target: 150 nodes, 15 clusters, 60 FPS

### Phase 3: Universe (Sprint 5–6)
- Implement Constellations and Galaxies
- Implement Weather system (clear, mist, rain, aurora)
- Implement Event visualization (birth, death, supernova)
- Implement Navigation (Semantic Zoom, Pan, Search Flight)
- Implement multiple universe support
- Target: 500 nodes, 50 clusters, 60 FPS

### Phase 4: Cinematic (Sprint 7–8)
- Implement full Camera system (all modes, drift, transitions)
- Implement Lighting system (orb as illuminant, node emission, atmospheric)
- Implement Post-processing (bloom, DOF, color grading)
- Implement Spatial Audio (procedural ambient tones)
- Polish: easing, timing, color, motion
- **Reserve Experience Runtime interfaces** (Section 3): define `ExperienceState`, `CinematicDirector`, and `NarrationSync` contracts. No implementation yet — just the data structures and hook points.

### Phase 5: MetaHuman (Sprint 9–10)
- Implement MetaHuman avatar
- Implement Universe ↔ MetaHuman transitions
- Implement agent embodiment (agents as visible entities)
- Implement VR/AR preparation (stereoscopic rendering, hand tracking hooks)
- Unreal Engine renderer prototype
- **Experience Runtime foundation** (Section 3): basic state machine, camera directive system, emotional arc curves. Still optional — Spatial Runtime functions without it.

### Phase 6: Storytelling (Sprint 11–12)
- **Full Experience Runtime implementation**
- Cinematic sequencing engine
- Narration timing synchronization
- Emotional pacing curves
- Music/ambience procedural generation
- Transition orchestration as narrative beats
- User behavior learning (adaptive pacing)
- Integration with AI speech synthesis for visual sync

---

## 19. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Performance degradation with >500 nodes | Medium | High | LOD, culling, instancing, Web Workers |
| Canvas 2D → Three.js visual mismatch | Medium | High | Port exact color math to shaders, preserve breathing curves |
| IPC bandwidth exceeded | Medium | High | Delta compression, SpatialIndex on renderer side |
| Over-engineering (too complex too fast) | High | Medium | Strict phase gates, each phase must feel complete |
| Loss of "alive" feeling | Medium | High | Preserve RhythmEngine, never use linear motion, always drift |
| Experience Runtime coupling too tightly | Low | High | Strict interface boundary (Section 3), Experience Runtime is optional |
| Narrative forcing (AI feels manipulative) | Medium | Medium | Experience Runtime adapts to user overrides, never enforces |
| Runtime direct imports (constitutional violation) | Low | Critical | Build-time grep tests, event bus architecture, code review automation (Section 3.5) |
| Renderer lock-in | Low | High | Abstract layer first, never use renderer-specific concepts in engine |
| Team bandwidth | High | Medium | Phase 1 alone is a complete product. Each phase is shippable. |

---

## 20. Appendix: Preserved Behaviors

The following current behaviors are **sacred** and must be preserved exactly in all future stages:

1. **Breathing animation**: Sine-wave cadence, 4–6 second cycle, global scale 0.98×–1.02×
2. **State-driven hue mapping**: Idle=220°, Listening=180°, Thinking=260°, Speaking=150°, Working=30°, Sleeping=240°, Error=0°
3. **Emotion hue shift**: `(curiosity - 0.5) * 60 + (warmth - 0.5) * 30`
4. **Saturation formula**: `60 + energy * 30`
5. **Lightness formula**: `45 + focus * 15`
6. **Radius formula**: `baseRadius * (0.85 + presence * 0.3)` where `baseRadius = min(w, h) * 0.18`
7. **Ring count**: 2 (idle/listening/thinking/working/sleeping), 3 (speaking), 4 (error)
8. **Glow radius**: `radius * (scale + energy * 1.5 + voiceLevel * 0.8)`
9. **Core radius**: `0.35 * radius` (0.45 in Error state)
10. **EMA smoothing**: `1.0 - Math.exp(-5.0 * dt)` for influences
11. **Emotion smoothing**: `exp(-2.5 * dt)`
12. **AudioEnvelope**: Attack 0.6, Release 0.08, clamped 0–1
13. **Renderer independence**: No desktop runtime imports renderer code
14. **FrameState immutability**: Pure JSON-friendly interface, no methods
15. **30 Hz engine → 60 Hz renderer**: Frame drops are silent
16. **LivingOrbAdapter as dumb pipe**: All intelligence in engine

---

## 21. Closing Principle

> The Living Orb is the Sun. Everything else is the universe that grew around it.

We are not building a new interface. We are growing an organism. Every node that appears, every constellation that forms, every galaxy that spirals — it must feel like it was always there, waiting to emerge from the orb's glow.

The user should never think "This is a new feature." They should think "Zaram has grown."

---

*Document produced by Kimi, Visual & Spatial Architecture Lead*  
*For the Zaram Operating System*  
*Sprint 1: Living Orb → Spatial Runtime Evolution*
