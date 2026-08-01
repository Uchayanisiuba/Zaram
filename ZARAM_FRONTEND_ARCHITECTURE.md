# ZARAM FRONTEND ARCHITECTURE

## ⚠️ ARCHITECTURE FREEZE POLICY
The architectural boundaries defined in this document are considered **STABLE AND FROZEN**. 
1. **Extension over Invention:** New work must extend existing runtimes and pipelines rather than introducing new layers.
2. **High Bar for Change:** Architectural changes require an Architecture Decision Record (ADR) and must demonstrate that the existing design fundamentally cannot satisfy the requirement without violating separation of concerns.
3. **Governance:** All implementations must be reviewed for constitutional compliance (4-Stage Pipeline, Layer boundaries, Embodiment Factory usage) before merging.

---

## 1. Runtime Hierarchy (React/R3F Mapping)

| Constitution Layer | Frontend Implementation | Directory |
|---|---|---|
| **Layer 1: Kernel & Platform** | Event Bus, Runtime Registry, Desktop Bridge (IPC) | `src/core/events/`, `src/desktop/` |
| **Layer 2: Intelligence** | Capabilities (Memory, Knowledge, Speech, Executive), Conversation Panel | `src/desktop/src/capabilities/`, `src/pages/ConversationPanel.tsx` |
| **Layer 3: Spatial Runtime** | Semantic Graph, Simulation Engine, Spatial Query, Layout Engine | `src/core/simulation/`, `src/core/semantic/`, `src/core/layout/` |
| **Layer 4: Embodiment Runtime** | Orb Embodiment, Knowledge Universe, Factory | `src/embodiments/`, `src/engine/factory/` |
| **Layer 5: Renderers** | R3F Adapter, InstancedMesh Renderer, Camera System | `src/engine/adapters/`, `src/engine/renderers/`, `src/engine/components/` |

---

## 2. The 4-Stage Pipeline (Data Flow)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: SEMANTIC (Pure Meaning)                                            │
│ Contract: SpatialNode, SpatialEdge, SpatialGraph                            │
│ Properties: id, type, label, semanticMass, metadata, relationships         │
│ Rule: ZERO position, velocity, color, size                                 │
│ Location: src/core/semantic/types.ts                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: SIMULATION (Pure Math)                                             │
│ Contract: SimulationNode, SimulationState, SpatialForces                   │
│ Properties: position, velocity, acceleration, physical mass                │
│ Rule: Physics Engine outputs forces only. NEVER mutates Semantic Graph.    │
│ Location: src/core/simulation/                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: FRAME (The Sacred Contract)                                        │
│ Contract: FrameState                                                        │
│ Properties: visual (presence, energy), audio, emotion, system state        │
│ Rule: Single producer (FrameComposer). Consumed by Embodiment Layer.       │
│ Location: src/core/frame/                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: VISUAL (Pure Aesthetics)                                           │
│ Contract: VisualNode, VisualEdge, VisualState                              │
│ Properties: position, radius, color, scale, opacity, meshProfile           │
│ Rule: Stateless generation via VisualMapper. Combines Sim + Frame + Theme. │
│ Location: src/core/visual/                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: RENDERER (Pixels)                                                  │
│ Contract: VisualState → GPU Commands                                        │
│ Rule: Knows nothing of AI, memory, or physics. Pure translation.           │
│ Location: src/engine/adapters/, src/engine/renderers/                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Render Pipeline (VisualState → R3F)

```
VisualState (Stage 4 output)
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ R3FRendererAdapter.createReactElement()                                     │
│   Returns: <Canvas><SceneContent /></Canvas>                                │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ SceneContent (inside Canvas)                                                │
│   • CameraRig (useFrame, useThree)                                         │
│   • Lights                                                                  │
│   • Embodiment Factory → creates embodiment components                     │
│   • NodeMesh / EdgeLine for generic nodes                                  │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Embodiment Components (inside Canvas)                                       │
│   • OrbEmbodiment (useFrame for breathing animation)                       │
│   • KnowledgeUniverse nodes via InstancedMesh (OuterRimRenderer)           │
│   • Future: AvatarEmbodiment, RobotEmbodiment                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key Rule:** All R3F hooks (`useFrame`, `useThree`, `useLoader`) **must** be called inside components rendered within `<Canvas>`. The `R3FRendererAdapter` creates the `<Canvas>` boundary; `SceneContent` and all embodiment components are children of that boundary.

---

## 4. Embodiment Factory Contract

**File:** `src/engine/factory/EmbodimentFactory.ts`

### Interface
```typescript
interface IEmbodiment {
  readonly type: string;                    // Matches SemanticNodeType or RuntimeSignature
  readonly component: React.ComponentType<EmbodimentProps>;
  readonly priority?: number;               // For fallback resolution
}

interface EmbodimentProps {
  visualNode: VisualNode;
  frameState: FrameState;
  visualState: VisualState;
}
```

### Responsibilities
| MUST | MUST NOT |
|---|---|
| Select embodiment by `SemanticNodeType` / `RuntimeSignature` | Perform rendering |
| Instantiate embodiment React components | Execute simulation |
| Register/deregister embodiments at runtime | Own semantic logic |
| Provide default fallback embodiment | Own shaders or renderer state |

### Registration
```typescript
// At app bootstrap (once)
EmbodimentFactory.register('orb', OrbEmbodiment);
EmbodimentFactory.register('knowledge', KnowledgeNodeEmbodiment);
EmbodimentFactory.register('project', ProjectNodeEmbodiment);
EmbodimentFactory.register('memory', MemoryNodeEmbodiment);
// ... etc.

// Default fallback
EmbodimentFactory.register('default', DefaultNodeEmbodiment);
```

### Usage in Renderer
```tsx
// Inside SceneContent (inside Canvas)
{visualState.nodes.map(node => {
  const EmbodimentComponent = EmbodimentFactory.get(node.type, node.signature);
  return <EmbodimentComponent key={node.id} visualNode={node} frameState={frameState} visualState={visualState} />;
})}
```

**Result:** Renderer contains **zero** `if (node.type === '...')` logic. All type→component mapping lives in the Factory.

---

## 5. Camera System & Event Flow

### Camera System
- **Source of Truth:** `SpatialCameraState` (interface in `src/core/contracts/ICameraController.ts`)
- **Controller:** `CinematicCameraController` (in `src/engine/camera/`) — pure math, no Three.js
- **R3F Binding:** `CameraRig` component uses `useFrame` + `useThree` to lerp Three.js camera to `SpatialCameraState`
- **Modes:** `orbit` | `focus` | `firstPerson` | `cinematic`

### Event Flow (Event Bus)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│ UI Layer (React Components)                                                 │
│   • Spotlight Search → EventBus.emit('SEARCH_INTENT_UPDATED')              │
│   • Node Click → EventBus.emit('NODE_SELECTED')                            │
│   • Camera Move → EventBus.emit('CAMERA_MOVED')                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ EventBus (src/core/events/EventBus.ts)                                      │
│   • Typed events, wildcard subscriptions, history replay                   │
│   • Decouples UI from Spatial Runtime                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Spatial Runtime (Simulation Worker / Main Thread)                          │
│   • Receives SEARCH_INTENT_UPDATED → recalculates gravity                  │
│   • Emits FRAME_STATE_READY @ 20Hz (Web Worker → Main Thread)             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ FrameStateBridge (Main Thread)                                              │
│   • Receives flat Float32Array buffers                                     │
│   • GPU interpolation to 120fps                                            │
│   • Calls onFrame callback with interpolated nodes                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ Renderer (R3F)                                                              │
│   • useFrame loop advances interpolation                                   │
│   • OuterRimRenderer (InstancedMesh) culls & updates                       │
│   • Embodiment components animate via FrameState                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Thread Architecture (EDS-001)

| Thread | Responsibility | Implementation |
|---|---|---|
| **Main Thread** | Rendering, Input, UI, Interpolation | `UniverseView.tsx`, `FrameStateBridge`, `OuterRimRenderer` |
| **Simulation Worker** | Physics @ 20Hz fixed timestep | `src/worker/simulationWorker.ts` |
| **Asset Loader** | Background GLTF/KTX2/Texture loading | `src/core/assets/AssetPreloadQueue.ts` |

**Data Transfer:** Simulation Worker → Main Thread via `postMessage` with `transferable` `ArrayBuffer` (zero-copy). Main thread interpolates 6 frames per sim tick (120fps / 20Hz).

---

## 7. Architectural Prohibitions (Enforced)

| Prohibition | Enforcement |
|---|---|
| Semantics ↔ Visuals mixing | `core/visual/types.ts` imports `Vector3` from `simulation/types`, NOT semantic types directly |
| Physics mutating state | `SemanticPhysicsEngine.calculateForces()` returns `SpatialForces` only |
| Polling between runtimes | All cross-runtime via `IEventBus` (EventBus.ts) |
| Renderer imports in core/ | `core/` has **zero** `three`, `@react-three/fiber`, `unreal` imports |
| Embodiments in engine/ | Embodiments live in `src/embodiments/` only |

---

## 8. File Structure Reference

```
src/
├── core/
│   ├── simulation/          # Stage 2: Math only
│   ├── semantic/            # Stage 1: Meaning only
│   ├── frame/               # Stage 3: FrameState contract
│   ├── visual/              # Stage 4: VisualState + Mapper
│   ├── events/              # EventBus (Layer 1)
│   ├── bridge/              # FrameStateBridge (Worker ↔ Main)
│   ├── assets/              # AssetPreloadQueue
│   └── contracts/           # Interfaces (IRenderer, ICameraController)
├── engine/
│   ├── factory/             # EmbodimentFactory (NEW)
│   ├── adapters/            # R3FRendererAdapter (Layer 5)
│   ├── renderers/           # OuterRimRenderer, InstancedMesh
│   ├── components/          # NodeMesh, EdgeLine, CameraRig
│   ├── camera/              # CinematicCameraController
│   ├── culling/             # Frustum/Distance culling
│   └── assets/              # AssetPipeline (React components)
├── embodiments/             # Layer 4: Orb, KnowledgeUniverse, etc.
├── pages/                   # App entry points (App.tsx, UniverseView.tsx)
├── mock/                    # Test data (MOCK_SEMANTIC_GRAPH)
└── desktop/                 # Tauri/Electron IPC bridge
```

---

## 9. Constitutional Compliance Checklist

Before any PR merge, verify:

- [ ] **Strict Downward Flow:** No upward imports (e.g., `core/simulation` does not import `core/visual`)
- [ ] **4-Stage Pipeline:** Data passes through all 4 stages with correct contracts
- [ ] **Renderer Ignorance:** `core/` and `platform/` have zero renderer imports
- [ ] **Embodiment Factory:** No `if (node.type)` in renderer; all via Factory
- [ ] **Event Bus Only:** Cross-runtime communication via `EventBus.emit/subscribe`
- [ ] **Thread Isolation:** Physics in Worker, rendering on Main Thread
- [ ] **Asset Pipeline:** Async loading with instant proxy fallbacks

---

*Generated from `00_ZARAM_CONSTITUTION/RuntimeModel.md` and codebase analysis. This document is the authoritative frontend architecture reference.*