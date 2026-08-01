# ZARAM Architecture Review
## Post-Sprint 5 Assessment

**Date:** 2026-07-27  
**Reviewer:** Atlas, Chief Software Architect  
**Scope:** Full-stack architecture review of the Zaram Operating System

---

## Executive Summary

The Zaram architecture presents a compelling vision: a full-stack AI operating system with a strict 4-stage pipeline (Semantic → Simulation → Frame → Visual) and a constitutional separation of concerns. The codebase demonstrates significant architectural ambition with a layered runtime model, a React/R3F renderer, and a Python backend with event-bus-driven runtimes.

However, the architecture is **inconsistent in its execution**. Multiple parallel systems exist for the same conceptual purpose (two FrameComposer implementations, two EventBus implementations, two EmbodimentFactory systems), the runtime boundaries are violated in several places, and significant dead code exists. The architecture is **partially realized** — the constitutional documents describe an ideal that the code does not fully match.

---

## 1. Runtime Boundaries

### 1.1 Frontend Runtime Hierarchy

The frontend follows a 5-layer model defined in `ZARAM_FRONTEND_ARCHITECTURE.md`:

| Layer | Directory | Status |
|-------|-----------|--------|
| Layer 1: Kernel & Platform | `src/core/events/`, `src/desktop/` | Partially implemented |
| Layer 2: Intelligence | `src/desktop/src/capabilities/`, `src/pages/ConversationPanel.tsx` | Not clearly delineated |
| Layer 3: Spatial Runtime | `src/core/simulation/`, `src/core/semantic/`, `src/core/layout/` | Partially implemented |
| Layer 4: Embodiment Runtime | `src/embodiments/`, `src/engine/factory/` | Partially implemented |
| Layer 5: Renderers | `src/engine/adapters/`, `src/engine/renderers/`, `src/engine/components/` | Partially implemented |

**Issues:**
- Layer 2 (Intelligence) is not clearly separated. Intelligence components (ConversationPanel, Knowledge, Memory pages) live in `src/components/` and `src/pages/` without a dedicated `src/desktop/src/capabilities/` directory.
- The `src/core/bridge/` directory exists but is only partially used. `FrameStateBridge.ts` implements a Web Worker-based simulation pipeline that is **not used by the main `App.tsx`** — `App.tsx` uses a direct `SimulationRuntime` on the main thread instead.
- `src/core/frame/composer.ts` (FrameComposer) is used by `PresenceContext.tsx` and `App.tsx`, but `src/core/bridge/FrameStateBridge.ts` has its own frame composition logic in the simulation worker, creating a parallel path.

### 1.2 Backend Runtime Hierarchy

The backend follows a runtime model with event-bus-driven runtimes:

```
backend/
├── core/           # Kernel: event_bus, execution_engine, planner, scheduler
├── runtimes/       # Individual runtimes: memory, knowledge, speech, models, etc.
├── runtime/        # Runtime discovery and presence
├── orchestrator/   # Capability orchestration
├── garage/         # Model/provider discovery
├── knowledge/      # Knowledge management
└── services/       # High-level services (conversation, speech, text)
```

**Issues:**
- The `backend/runtime/presence/` directory contains contracts (`contracts.py`) but no implementation. The `tests/` subdirectory has a test file but no runtime implementation.
- The `backend/runtime/discovery/` directory is a large, complex subsystem that duplicates functionality from `backend/runtimes/discovery/`.
- The `backend/knowledge/` directory contains a massive `runtime.py` (695 lines) with 40+ methods, violating the single-responsibility principle.

### 1.3 Runtime Separation Violations

The `CLAUDE.md` states: "Never import one Runtime into another. Use the `EventBus` in `backend/core/event_bus.py`."

**Violations found:**
- `backend/knowledge/runtime.py:257` directly imports and calls `self._memory_runtime.retrieve()` — KnowledgeRuntime directly depends on MemoryRuntime, violating the no-import rule.
- `backend/knowledge/runtime.py:231` directly imports and calls `self._internet_runtime.search()` — KnowledgeRuntime directly depends on InternetRuntime.
- `frontend/src/core/bridge/FrameStateBridge.ts` imports `three` (a renderer library) into `core/`, violating the "Renderer Ignorance" rule stated in `ZARAM_FRONTEND_ARCHITECTURE.md` Section 7.

---

## 2. Module Responsibilities

### 2.1 FrameComposer — Duplicate Implementations

There are **two** FrameComposer implementations:

1. **`frontend/src/core/frame/composer.ts`** (145 lines) — Used by `PresenceContext.tsx` and `App.tsx`. Composes FrameState from SimulationState + PresenceState + audio input. Has presence transition logic (300-400ms lerp).

2. **`packages/zaram-engine/runtime/FrameComposer.ts`** (44 lines) — Part of the `zaram-engine` package. Composes FrameState from TargetInfluences + EmotionDimensions + RhythmData + RuntimeState. Uses biological rhythm modulation.

**Neither imports the other.** The `zaram-engine` package is not imported by the frontend application. This is dead code or a parallel architecture that was never integrated.

### 2.2 EventBus — Duplicate Implementations

There are **two** EventBus implementations:

1. **`frontend/src/core/events/EventBus.ts`** (452 lines) — Full-featured event bus with history replay, typed events, React hooks. Used by `UniverseView.tsx`, `PresenceContext.tsx`.

2. **`backend/core/event_bus.py`** (43 lines) — Minimal event bus with subscribe/publish. Used by backend runtimes.

3. **`frontend/src/core/bridge/MemorySpatialBridge.ts`** — Contains its own `KnowledgeEventBus` class (30 lines), a third event bus implementation.

**Issues:**
- The frontend EventBus is feature-rich but the backend EventBus is minimal. No shared protocol.
- `MemorySpatialBridge.ts` creates a third event bus instead of using the existing one.

### 2.3 Embodiment System — Multiple Parallel Systems

The embodiment system has **three** parallel implementations:

1. **`frontend/src/engine/factory/EmbodimentFactory.ts`** — React component factory. Maps SemanticNodeType/RuntimeSignature to React components. Used by `R3FRendererAdapter.tsx`.

2. **`frontend/src/engine/embodiments/EmbodimentRegistry.tsx`** — A registry that wraps EmbodimentFactory, adds LOD/animation/particle/material registration. Has `EMBODIMENT_REGISTRATIONS` array with `component: null as any` for all entries — **components are never registered**.

3. **`packages/zaram-engine/registries/EmbodimentRegistry.ts`** — Backend-oriented registry in the zaram-engine package. Not used by the frontend.

**Issues:**
- `EmbodimentRegistry.tsx` has 13 embodiment registrations, all with `component: null as any`. The `initialize()` method calls `this.factory.setDefault(this.createDefaultEmbodiment())` but never registers the actual components. This means all nodes render as default spheres.
- The `bootstrap.ts` file registers components for `orb`, `knowledge`, `project`, `memory` types, but `EmbodimentRegistry.tsx` has registrations for 13 types including `agent`, `document`, `folder`, `code`, `conversation`, `research`, `website`, `task`, `calendar`, `person` — none of which have components registered.

### 2.4 Renderer Architecture — Inconsistent Patterns

The renderer architecture has multiple patterns:

1. **`OrbRenderer.ts`** — 2D Canvas renderer for the Living Orb. Consumes FrameState directly. Has its own animation loop via `requestAnimationFrame`.

2. **`R3FRendererAdapter.tsx`** — React Three Fiber adapter. Creates `<Canvas>` with `SceneContent` that uses `EmbodimentFactory`. Has a no-op `render()` method.

3. **`OuterRimRenderer.ts`** — InstancedMesh renderer for high-density nodes. Uses custom shaders. Integrated into `UniverseView.tsx`.

4. **`packages/zaram-engine/renderer/Renderer.ts`** — 2D canvas renderer in the zaram-engine package. Draws rectangles. Dead code.

5. **`App.tsx`** — Uses `R3FRendererAdapter` but also has its own animation loop that calls `SimulationRuntime.tick()` and `FrameComposer.compose()` directly, then forces React re-renders via `setTick()`.

**Issues:**
- `App.tsx` has a dual-path architecture: it runs its own animation loop (calling simulation + composition) AND uses the R3F renderer (which has its own `useFrame` loop). The `setTick()` call forces React re-renders at the simulation frequency, which conflicts with R3F's own render loop.
- `OrbRenderer.ts` has hardcoded `STATE_HUE`, `STATE_ENERGY`, `STATE_FOCUS`, `STATE_ACTIVITY` lookup tables that duplicate the presence state modifiers in `FrameComposer.ts`.
- The `LivingOrbCenter.tsx` component reads `PRESENCE_COLORS` from `presenceTheme.ts` directly, while `OrbRenderer.ts` uses its own `STATE_HUE` lookup table. These are **duplicate state-to-color mappings**.

---

## 3. Dependency Direction

### 3.1 Frontend Dependency Flow

The intended flow is:
```
Semantic (core/semantic) → Simulation (core/simulation) → Frame (core/frame) → Visual (core/visual) → Renderer (engine/)
```

**Violations:**
- `frontend/src/core/bridge/FrameStateBridge.ts:10` imports `three` (renderer library) into `core/`.
- `frontend/src/core/bridge/FrameStateBridge.ts:12` imports `SpatialGraph` from `core/semantic/types` — correct, but also imports `PresenceState` from `theme/` which is a presentation concern.
- `frontend/src/core/visual/mapper.ts:13` imports `PresenceState` and `PRESENCE_COLORS` from `theme/presenceTheme` — visual layer depends on theme layer, which is acceptable but the mapper also imports `ARCHETYPE_METADATA` from `semantic/types`, creating a dependency from visual → semantic.
- `frontend/src/engine/embodiments/EmbodimentRegistry.tsx` imports from `core/visual/types`, `core/frame/types`, `engine/lod/`, `engine/animation/`, `engine/particles/`, `engine/materials/`, `engine/assets/`, `engine/shaders/` — this is a god module with dependencies across all engine subsystems.

### 3.2 Backend Dependency Flow

The intended flow is: runtimes communicate only via EventBus.

**Violations:**
- `backend/knowledge/runtime.py` directly imports and uses `self._memory_runtime` and `self._internet_runtime` (see Section 1.3).
- `backend/runtimes/memory/runtime.py:7` imports `core.event_bus` — correct.
- `backend/knowledge/runtime.py:11` imports `core.event_bus` — correct, but also directly calls other runtimes.

### 3.3 Shared Types

The `shared/` directory contains:
- `shared/types/workspace.ts` — Panel/layout types. Used by frontend.
- `shared/types/artifacts.ts` — Artifact types. Used by frontend.
- `shared/personaVoices.ts` — Persona-to-voice mapping. Used by backend and frontend.

**Issues:**
- `shared/types/workspace.ts` and `shared/types/artifacts.ts` are only used by the frontend. They should be in `frontend/src/types/`.
- `shared/personaVoices.ts` is the only truly shared module, but it's a simple constant map with no complex types.

---

## 4. Future Scalability

### 4.1 Strengths

- The 4-stage pipeline (Semantic → Simulation → Frame → Visual) provides a clean separation that could scale well if properly enforced.
- The Embodiment Factory pattern allows new embodiment types to be added without modifying the renderer.
- The EventBus pattern enables loose coupling between runtimes.
- The zaram-engine package provides a reusable engine abstraction that could be used by multiple frontends.

### 4.2 Bottlenecks

- **FrameComposer duplication**: Two implementations exist, neither is clearly the "production" one. The `zaram-engine` version has more sophisticated features (rhythm modulation, emotion integration) but is unused.
- **EmbodimentRegistry dead components**: All 13 embodiment registrations have `component: null as any`. Adding new embodiment types requires fixing this registry first.
- **App.tsx dual render loop**: The main application has two concurrent animation loops (React state updates + R3F useFrame), which will cause performance issues at scale.
- **Backend KnowledgeRuntime monolith**: 695-line class with 40+ methods handling search, storage, indexing, entity extraction, relationship building, temporal logic, conflict resolution, garbage collection, and continuous learning. This will not scale.
- **Backend KnowledgeRuntime direct runtime imports**: The KnowledgeRuntime directly imports MemoryRuntime and InternetRuntime, creating tight coupling that prevents independent scaling.

### 4.3 Thread Architecture

The `ZARAM_FRONTEND_ARCHITECTURE.md` Section 6 describes a 3-thread architecture:
- Main Thread: Rendering, Input, UI, Interpolation
- Simulation Worker: Physics @ 20Hz
- Asset Loader: Background loading

**Reality:**
- `App.tsx` runs simulation on the main thread (no Web Worker).
- `FrameStateBridge.ts` implements the Web Worker pattern but is only used by `UniverseView.tsx`, not `App.tsx`.
- `UniverseView.tsx` is a separate page that is not the main application entry point.
- No asset loader thread exists.

---

## 5. Renderer Architecture

### 5.1 Living Orb Rendering Pipeline

The Living Orb has two rendering paths:

**Path A: 2D Canvas (OrbRenderer.ts)**
```
PresenceContext.tsx
  → FrameComposer.compose()
  → OrbEngine.tsx
  → OrbRenderer.ts (2D Canvas)
```

**Path B: Three.js/R3F (LivingOrbCenter.tsx)**
```
UniverseView.tsx
  → FrameStateBridge (Web Worker)
  → R3FRendererAdapter
  → LivingOrbCenter.tsx (Three.js)
```

**Issues:**
- The two paths use different color mappings: `OrbRenderer.ts` has `STATE_HUE` lookup table, `LivingOrbCenter.tsx` uses `PRESENCE_COLORS` from `presenceTheme.ts`.
- The two paths use different animation timing: `OrbRenderer.ts` uses `requestAnimationFrame` with target FPS throttling, `LivingOrbCenter.tsx` uses R3F's `useFrame` with delta-based interpolation.
- The two paths receive different FrameState shapes: `OrbRenderer.ts` expects `FrameState` from `core/frame/types.ts`, `LivingOrbCenter.tsx` receives a partial FrameState constructed in `UniverseView.tsx:289` with `{ visual: visualState, system: systemState } as any`.

### 5.2 Orb Animation Timing

The orb animation is driven by **multiple competing systems**:

1. **`OrbRenderer.ts`** — Uses `requestAnimationFrame` with a target FPS of 60. Animation is driven by FrameState fields (`visual.energy`, `visual.presence`, `audio.rmsLevel`, `system.state`). Has its own RMS smoothing (`smoothedRms`).

2. **`LivingOrbCenter.tsx`** — Uses R3F's `useFrame` (driven by the browser's refresh rate). Animation is driven by FrameState fields (`visual.energy`, `visual.presence`, `audio.voiceLevel`, `audio.rmsLevel`). Has its own color interpolation (`coreColorRef.lerp()`).

3. **`FrameComposer.ts`** — Produces FrameState with presence transition logic (300-400ms lerp between states). Also has its own RMS smoothing (`smoothRms()` method that returns raw value).

4. **`PresenceContext.tsx`** — Runs its own `requestAnimationFrame` loop at 60fps, composing FrameState every frame.

**Duplicate state mapping exists:**
- `FrameComposer.ts` has `getPresenceModifiers()` which maps PresenceState → VisualFrame (presence, energy, focus, activity).
- `OrbRenderer.ts` has `STATE_HUE`, `STATE_ENERGY`, `STATE_FOCUS`, `STATE_ACTIVITY` lookup tables that map PresenceState → visual parameters.
- `presenceTheme.ts` has `PRESENCE_COLORS` which maps PresenceState → color tokens.
- `UniverseView.tsx` has `getPresenceColor()` function with its own PresenceState → color mapping.

This is **four duplicate state-to-visual mappings** for the same PresenceState enum.

---

## 6. Status Change Propagation

### 6.1 PresenceState Entry Point

PresenceState enters the system from two sources:

1. **Desktop IPC** (`desktop-bridge.ts`): `desktop.presence.onState()` receives PresenceState from the backend Presence Runtime.

2. **Local React state** (`PresenceContext.tsx`): `setPresenceState()` is called by UI components or the local animation loop.

### 6.2 State Transition Decision

The **FrameComposer** (`core/frame/composer.ts`) is the component that decides state transitions. It:
- Tracks `lastPresenceState` and `presenceTransitionProgress`
- When `presenceState !== lastPresenceState`, it resets transition progress to 0
- Progresses the transition over ~400ms via linear interpolation
- Modulates visual parameters (presence, energy, focus, activity) based on the current state and transition progress

### 6.3 OrbEngine Ownership

**OrbEngine does NOT own the state.** It is a passive renderer. It receives FrameState via:
- Props (`frameState` prop) for embedded usage
- IPC (`desktop.presence.onFrame()`) for desktop usage

It instantiates `OrbRenderer` and passes FrameState to it.

### 6.4 OrbRenderer Visual Computation

**OrbRenderer computes visuals itself.** It receives the already-computed FrameState but then applies its own visual mappings:
- `STATE_HUE` lookup for color
- `STATE_ENERGY`, `STATE_FOCUS`, `STATE_ACTIVITY` lookups for defaults
- Emotion-based hue shifts
- Audio-reactive glow and pulsing
- RMS smoothing

It does NOT receive pre-computed visual data — it computes visual parameters from FrameState fields.

### 6.5 Complete Propagation Chain

```
1. PresenceState enters system
   → PresenceContext.tsx (React state)
   → desktop.presence.onState() (IPC)

2. FrameComposer.compose() (core/frame/composer.ts)
   → Receives PresenceState + SimulationState + audio input
   → Computes VisualFrame (presence, energy, focus, activity)
   → Applies 400ms transition lerp
   → Produces FrameState

3. PresenceContext.tsx
   → setFrameState(composedFrame) (React state update)
   → applyPresenceTheme() (CSS variables)

4. OrbEngine.tsx (component)
   → Receives FrameState via props or IPC
   → renderer.setFrameState(frameState)

5. OrbRenderer.ts (class)
   → Receives FrameState
   → Computes visual parameters (hue, energy, focus, activity)
   → Applies STATE_HUE/STATE_ENERGY/STATE_FOCUS/STATE_ACTIVITY lookups
   → Draws to 2D Canvas via requestAnimationFrame

6. LivingOrbCenter.tsx (Three.js component)
   → Receives FrameState via props
   → useFrame loop reads FrameState fields
   → Interpolates colors, scales, opacities
   → Updates Three.js mesh materials
```

### 6.6 Single Source of Truth

**There is NO single source of truth.** Multiple sources exist:

1. **PresenceState** — Defined in `theme/presenceTheme.ts` as a TypeScript type. Also defined as a string in `backend/runtime/presence/contracts.py` (`SystemParams.state: str`).

2. **FrameState** — Defined in `core/frame/types.ts` (frontend). Also defined in `packages/zaram-engine/types/FrameState.ts` (zaram-engine). Also defined in `backend/runtime/presence/contracts.py` (backend).

3. **Presence colors** — Defined in `theme/presenceTheme.ts` (`PRESENCE_COLORS`). Also partially in `OrbRenderer.ts` (`STATE_HUE`). Also in `UniverseView.tsx` (`getPresenceColor()`).

### 6.7 Duplicate State Mapping

**Yes, extensive duplication exists:**

| Mapping | Location 1 | Location 2 | Location 3 | Location 4 |
|---------|-----------|-----------|-----------|-----------|
| PresenceState → Visual parameters | `FrameComposer.getPresenceModifiers()` | `OrbRenderer.STATE_HUE/ENERGY/FOCUS/ACTIVITY` | `presenceTheme.PRESENCE_COLORS` | `UniverseView.getPresenceColor()` |
| FrameState type | `core/frame/types.ts` | `packages/zaram-engine/types/FrameState.ts` | `backend/runtime/presence/contracts.py` | — |
| EmbodimentFactory | `engine/factory/EmbodimentFactory.ts` | `engine/embodiments/EmbodimentRegistry.tsx` | `packages/zaram-engine/registries/EmbodimentRegistry.ts` | — |
| EventBus | `core/events/EventBus.ts` | `core/bridge/MemorySpatialBridge.ts` (KnowledgeEventBus) | `backend/core/event_bus.py` | — |

### 6.8 Orb Animation Timing Driver

The orb animation timing is driven by **multiple competing systems**:

1. **PresenceState** — Drives color/theme changes via `FrameComposer.getPresenceModifiers()` and `OrbRenderer.STATE_HUE`.
2. **FrameState.visual** — Drives energy, presence, focus, activity parameters.
3. **OrbEngine** — Uses `requestAnimationFrame` with target FPS throttling (60fps).
4. **OrbRenderer** — Uses `requestAnimationFrame` with its own frame interval calculation.
5. **LivingOrbCenter** — Uses R3F's `useFrame` (browser refresh rate).
6. **PresenceContext** — Uses `requestAnimationFrame` for FrameState composition.
7. **CSS** — `applyPresenceTheme()` sets CSS variables, but OrbRenderer doesn't use them (it has its own color lookups).
8. **Framer Motion** — Not used anywhere in the codebase.
9. **requestAnimationFrame** — Used by OrbRenderer, PresenceContext, and indirectly by R3F's useFrame.

The primary driver is **requestAnimationFrame**, with FrameState fields providing the animation parameters.

---

## 7. Sequence Diagram

```
title Zaram Orb Status Change Propagation

participant "UI/Backend" as Source
participant "PresenceContext" as PC
participant "FrameComposer" as FC
participant "OrbEngine" as OE
participant "OrbRenderer" as OR
participant "LivingOrbCenter" as LOC

== PresenceState Entry ==
Source->PC: desktop.presence.onState({state})
PC->PC: setPresenceState(state)
PC->PC: applyPresenceTheme(document, state)

== FrameState Composition ==
PC->FC: compose({simulation, presenceState, audioInput})
FC->FC: Detect state change
FC->FC: Reset transition progress (0)
FC->FC: Compute base visual from simulation
FC->FC: Get presence modifiers (getPresenceModifiers)
FC->FC: Lerp base → modifiers over 400ms
FC->FC: Return FrameState

== React State Update ==
PC->PC: setFrameState(frameState)
PC->PC: requestAnimationFrame(tick)

== OrbEngine Rendering (2D Canvas) ==
PC->OE: frameState (via props or IPC)
OE->OR: renderer.setFrameState(frameState)
OR->OR: requestAnimationFrame(tick)
OR->OR: Read FrameState.visual, .audio, .system, .emotion
OR->OR: Apply STATE_HUE/ENERGY/FOCUS/ACTIVITY lookups
OR->OR: Compute hue shift from emotion
OR->OR: Apply RMS smoothing
OR->OR: drawGlow(), drawOrb(), drawInnerCore()

== LivingOrbCenter Rendering (Three.js) ==
PC->LOC: frameState (via props)
LOC->LOC: useFrame(delta)
LOC->LOC: Read FrameState fields
LOC->LOC: Lerp colors (coreColorRef, glowColorRef)
LOC->LOC: Update mesh materials, scales, rotations
LOC->LOC: Audio reactive scaling

== Alternative: UniverseView Path ==
participant "FrameStateBridge" as FSB
participant "SimulationWorker" as SW
participant "OuterRimRenderer" as ORR

PC->FSB: updatePresenceState(state)
FSB->SW: postMessage({type: 'updatePresence', state})
SW->SW: Run physics simulation (20Hz)
SW->FSB: postMessage({type: 'frameState', buffer})
FSB->FSB: Interpolate (120fps / 20Hz = 6x)
FSB->ORR: updateFromFrameState(nodes)
ORR->ORR: cullAndUpdate() (frustum + distance)
```

---

## 8. Architectural Smells, Duplicated Logic, and Dead Code

### 8.1 Architectural Smells

#### 8.1.1 God Modules
- **`backend/knowledge/runtime.py`** (695 lines, 40+ methods) — Handles search, storage, indexing, entity extraction, relationship building, temporal logic, conflict resolution, garbage collection, continuous learning, reindexing, cross-document linking, authority scoring, and telemetry.
- **`frontend/src/engine/embodiments/EmbodimentRegistry.tsx`** (403 lines) — Wraps EmbodimentFactory, manages LOD/animation/particle/material/asset registration, handles node lifecycle, and provides stats.
- **`frontend/src/core/events/EventBus.ts`** (452 lines) — Event bus with history, replay, typed events, React hooks, and convenience actions.

#### 8.1.2 Tight Coupling
- **`backend/knowledge/runtime.py`** directly imports and calls `MemoryRuntime` and `InternetRuntime` (violates the no-import rule).
- **`frontend/src/core/bridge/FrameStateBridge.ts`** imports `three` into `core/` (violates renderer ignorance rule).
- **`frontend/src/engine/embodiments/EmbodimentRegistry.tsx`** imports from 8 different engine subsystems.

#### 8.1.3 Inconsistent Layering
- `frontend/src/components/LivingOrb/LivingOrb.tsx` imports `OrbEngine` from `../OrbEngine/OrbEngine` — components importing from components, bypassing the layer structure.
- `frontend/src/embodiments/LivingOrb/LivingOrb.tsx` imports `OrbEngine` from `@/components/OrbEngine/OrbEngine` — embodiments importing from components.
- `frontend/src/pages/UniverseView.tsx` directly imports `OuterRimRenderer`, `CullingSystem`, `LivingOrbCenter`, `CinematicCameraController`, `UniverseInteraction` — pages importing engine internals.

#### 8.1.4 Parallel Architectures
- **Frontend App**: `App.tsx` uses direct simulation + R3F renderer. `UniverseView.tsx` uses Web Worker + FrameStateBridge + OuterRimRenderer. These are two completely different rendering architectures in the same codebase.
- **Embodiment Factory**: `EmbodimentFactory.ts` (simple factory) vs `EmbodimentRegistry.tsx` (complex registry with null components).
- **Frame Composer**: `core/frame/composer.ts` vs `packages/zaram-engine/runtime/FrameComposer.ts`.

### 8.2 Duplicated Logic

#### 8.2.1 PresenceState → Visual Mapping (4 copies)
1. `FrameComposer.getPresenceModifiers()` — Maps PresenceState → {presence, energy, focus, activity}
2. `OrbRenderer.STATE_HUE/ENERGY/FOCUS/ACTIVITY` — Maps PresenceState → {hue, energy, focus, activity}
3. `presenceTheme.PRESENCE_COLORS` — Maps PresenceState → {primary, secondary, glow, backgroundAccent, orbCore, ringColor, particleColor}
4. `UniverseView.getPresenceColor()` — Maps PresenceState → hex color string

#### 8.2.2 FrameState Type (3 copies)
1. `frontend/src/core/frame/types.ts` — Full FrameState with VisualFrame, AudioFrame, EmotionFrame, SystemFrame, MetadataFrame
2. `packages/zaram-engine/types/FrameState.ts` — Simplified FrameState (no smoothedRms, different system state enum)
3. `backend/runtime/presence/contracts.py` — Python dataclass FrameState with VisualParams, AudioParams, EmotionParams, SystemParams

#### 8.2.3 EventBus (3 copies)
1. `frontend/src/core/events/EventBus.ts` — Full-featured with history, replay, typed events
2. `frontend/src/core/bridge/MemorySpatialBridge.ts` — Minimal KnowledgeEventBus (30 lines)
3. `backend/core/event_bus.py` — Minimal event bus (43 lines)

#### 8.2.4 Embodiment Factory (3 copies)
1. `frontend/src/engine/factory/EmbodimentFactory.ts` — Simple type/signature → component mapping
2. `frontend/src/engine/embodiments/EmbodimentRegistry.tsx` — Complex registry with null components
3. `packages/zaram-engine/registries/EmbodimentRegistry.ts` — Backend-oriented registry

#### 8.2.5 Animation Systems (2 copies)
1. `frontend/src/engine/animation/AnimationRuntime.ts` — Full animation system with 12 animation types, spring physics, easing functions, LOD awareness
2. `OrbRenderer.ts` — Inline animation (breathing, pulsing, RMS smoothing)

#### 8.2.6 Particle Systems (2 copies)
1. `frontend/src/engine/particles/ParticleRuntime.ts` — Full particle system with GPU/CPU emitters, 8 particle types
2. `packages/zaram-engine/particle/ParticleRuntime.ts` — Backend-oriented particle runtime

### 8.3 Dead Code

#### 8.3.1 Unused Packages
- **`packages/zaram-engine/`** — Entire package is not imported by the frontend application. Contains:
  - `runtime/FrameComposer.ts` — Unused duplicate
  - `runtime/FrameGraph.ts` — Unused frame graph
  - `renderer/Renderer.ts` — Unused 2D renderer (draws rectangles)
  - `universe/UniverseRuntime.ts` — Unused universe runtime
  - `registries/` — Unused registries
  - `types/FrameState.ts` — Unused duplicate
  - `types/RuntimeState.ts` — Unused
  - All other modules in the package

#### 8.3.2 Null Component Registrations
- **`EmbodimentRegistry.tsx`** — All 13 embodiment registrations have `component: null as any`. The `initialize()` method sets a default fallback but never registers the actual components from `bootstrap.ts`.

#### 8.3.3 Unused Imports and Functions
- `frontend/src/engine/factory/EmbodimentFactory.ts:164` — `registerDefaultEmbodiments()` is an empty function (comment says "Actual registration happens in App bootstrap").
- `frontend/src/engine/adapters/R3FFactory.ts` — Implements `IRendererFactory` but is never imported or used.
- `frontend/src/components/OrbSandbox/` directory is referenced in imports but the file doesn't exist.
- `frontend/src/core/contracts/IRendererFactory.ts` — Interface for `R3FFactory` which is unused.
- `frontend/src/core/contracts/IRenderer.ts` — Interface implemented by `R3FRendererAdapter` but the `render()` method is a no-op.

#### 8.3.4 Unused Backend Modules
- `backend/runtime/presence/contracts.py` — Defines contracts but no runtime implementation exists.
- `backend/runtime/discovery/` — Large subsystem (15+ files) that duplicates `backend/runtimes/discovery/`.
- `backend/test_kernel.py`, `backend/test_models_runtime.py`, `backend/test_execution_engine.py` — Test files in the root backend directory.
- `backend/capability_audit.py`, `backend/runtime_completion_report.py` — Standalone scripts.

#### 8.3.5 Unused Frontend Components
- `frontend/src/components/DebugAdminLayer.tsx` — Debug component, may not be wired into the app.
- `frontend/src/components/DiagnosticsPanel.tsx` — Diagnostics component, may not be wired in.
- `frontend/src/components/R3FErrorBoundary.tsx` — Error boundary, may not be used.
- `frontend/src/components/performance/PerformanceMonitor.tsx` — Performance monitor, may not be used.

#### 8.3.6 Incomplete Implementations
- `backend/runtime/presence/contracts.py` — `IEmbodiment` protocol defines `set_frame_state()` but no implementation exists.
- `packages/zaram-engine/runtime/FrameGraph.ts` — Imports 12 dependencies but the `execute()` method is never called.
- `frontend/src/engine/embodiments/EmbodimentRegistry.tsx:234` — `registerDefaultShaders()` is an empty placeholder.

---

## 9. Recommendations

### 9.1 Critical (Must Address)

1. **Choose one FrameComposer implementation** and delete the other. The `core/frame/composer.ts` is actively used; the `zaram-engine` version should be either integrated or deleted.

2. **Fix EmbodimentRegistry null components** — Either register actual components for all 13 types or remove the unused registrations.

3. **Remove `three` import from `core/`** — `FrameStateBridge.ts` must not import renderer libraries. Move interpolation logic to the renderer layer.

4. **Fix backend runtime coupling** — `KnowledgeRuntime` must not directly import `MemoryRuntime` or `InternetRuntime`. Use the EventBus for communication.

5. **Delete the `packages/zaram-engine/` package** if it's not being used, or integrate it properly into the frontend.

### 9.2 High Priority

6. **Consolidate PresenceState → Visual mapping** — Choose one location (`presenceTheme.ts`) and have all renderers read from it. Delete `STATE_HUE` from `OrbRenderer.ts` and `getPresenceColor()` from `UniverseView.tsx`.

7. **Unify the two frontend rendering paths** — `App.tsx` and `UniverseView.tsx` use completely different architectures. Choose one and migrate.

8. **Split `KnowledgeRuntime`** — Extract search, storage, indexing, entity extraction, and garbage collection into separate services.

9. **Remove duplicate EventBus** — Delete `KnowledgeEventBus` from `MemorySpatialBridge.ts` and use the existing `EventBus.ts`.

### 9.3 Medium Priority

10. **Delete dead code** — `R3FFactory.ts`, `IRendererFactory.ts`, `OrbSandbox` references, unused test files.

11. **Fix `App.tsx` dual render loop** — Either use R3F's `useFrame` exclusively or the React state update loop, not both.

12. **Move shared types** — `shared/types/workspace.ts` and `shared/types/artifacts.ts` should be in `frontend/src/types/`.

13. **Complete the Web Worker architecture** — Either use `FrameStateBridge.ts` in `App.tsx` or remove it.

### 9.4 Low Priority

14. **Remove `Framer Motion`** — Not used anywhere, remove from dependencies if listed.

15. **Consolidate particle systems** — Choose one particle runtime implementation.

16. **Fix `bootstrap.ts` empty function** — `registerDefaultEmbodiments()` is empty; move registration logic there or delete it.

---

## 10. Conclusion

The Zaram architecture has a strong theoretical foundation with its 4-stage pipeline and constitutional separation of concerns. However, the implementation is **inconsistent and incomplete**. Multiple parallel systems exist for the same purpose, runtime boundaries are violated, and significant dead code exists.

The most critical issues are:
1. Duplicate FrameComposer and EventBus implementations
2. Null component registrations in EmbodimentRegistry
3. Backend runtime coupling (KnowledgeRuntime → MemoryRuntime/InternetRuntime)
4. Renderer library imports in core/
5. An entire unused `packages/zaram-engine/` package

Addressing these issues would significantly improve the architecture's clarity, maintainability, and scalability. The constitutional documents describe an ideal that the code does not yet match — closing this gap should be the primary focus.