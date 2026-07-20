# Engine Integration

**Milestone:** 1.2 – Living Orb Engine Integration  
**Status:** Active  
**Package:** `@zaram/engine` (local workspace dependency)

---

## 1. Architecture

The desktop application consumes `@zaram/engine` as a black-box library. The frontend owns the renderer. The `EmbodimentManager` selects embodiments without modifying the runtime.

```
Kernel
  ↓
RuntimeStateProvider (Aggregator)
  ↓
EngineAdapter
  ↓
AnimationRuntime  (@zaram/engine)
  ↓
FrameState (canonical)
  ↓
PresenceRuntime
  ↓
LivingOrbAdapter
  ↓
OrbRenderer (frontend)
```

### Layer Responsibilities

| Layer | Responsibility | Rendering Logic? |
|-------|---------------|-----------------|
| `EngineAdapter` | Owns `AnimationRuntime`, initializes with `visualIdentity`, translates `RuntimeSnapshot` → `RuntimeState`, returns `FrameState` | **No** |
| `PresenceRuntime` | Owns lifecycle, diagnostics, timer, performance metrics; forwards `FrameState` to the active `IEmbodiment` | **No** |
| `EmbodimentManager` | Selects and switches between embodiments; delegates lifecycle calls | **No** |
| `LivingOrbAdapter` | Pushes `FrameState` across the render transport boundary; reflects renderer health | **No** |
| `OrbRenderer` | Frontend canvas renderer; consumes canonical `FrameState` and performs all drawing | Yes |

The engine is never imported by renderer code, and renderer code is never imported by the engine or the integration layer.

---

## 2. Data Flow

```
┌────────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│ Runtime Sources    │     │ PresenceRuntime    │     │ EngineAdapter      │
│ (Aggregator)       │────▶│                    │────▶│                    │
│                    │     │  - timer (~30Hz)   │     │  - initialize(vi)  │
│  Conversation      │     │  - mapSnapshot()   │     │  - update(dt, rs)  │
│  Voice             │     │  - tick()          │     │                    │
│  Memory            │     │  - consumeFrame()  │     │  - delegates to    │
│  System            │     │  - diagnostics     │     │    AnimationRuntime│
│  Personality       │     │  - performance     │     │                    │
└────────────────────┘     └────────────────────┘     └─────────┬──────────┘
                                                              │
                                                              ▼
┌────────────────────┐                             ┌────────────────────┐
│ LivingOrbAdapter    │◀──────────────────────────│ AnimationRuntime    │
│                    │   FrameState (canonical)   │  (@zaram/engine)   │
│  - setFrameState() │                             │                    │
│  - transport.send  │                             │  - update(dt, rs)  │
│                     │                             │  - returns FrameState│
└────────────────────┘                             └────────────────────┘
```

### Step-by-step

1. **Aggregation** — `RuntimeSourceAggregator` merges live snapshots from Conversation, Voice, Memory, System, and Personality runtimes into a single `RuntimeSnapshot`.
2. **Tick** — `PresenceRuntime` runs a `setInterval` at ~30 Hz. On each tick it reads the latest snapshot from the aggregator.
3. **Mapping** — `PresenceRuntime` maps the desktop `RuntimeSnapshot` into the engine's `RuntimeState` contract (e.g. lowercase phase → uppercase state).
4. **Engine Update** — `EngineAdapter.update(dt, runtimeState)` delegates to `AnimationRuntime.update(dt, runtimeState)`.
5. **FrameState** — The engine returns the canonical `FrameState` (visual, audio, emotion, system, metadata).
6. **Forwarding** — `PresenceRuntime.consumeFrameState()` stamps the sequence and forwards the frame to the active `IEmbodiment`.
7. **Transport** — `LivingOrbAdapter` pushes the frame to the render transport; it never imports renderer code.

---

## 3. Embodiment Manager

The `EmbodimentManager` selects embodiments without modifying the runtime.

```ts
// desktop/src/runtime/embodiment/EmbodimentManager.ts
const manager = new EmbodimentManager({ transport })
manager.register('living-orb', new LivingOrbAdapter(transport))
manager.register('xr-avatar', new XRAvatarAdapter(transport))
await manager.switchTo('xr-avatar')
```

Supported today:
- `living-orb` — default

Future:
- `metahuman`
- `unreal-character`
- `xr-avatar`
- custom embodiments

---

## 4. Performance Integration

The application measures performance metrics and exposes them through diagnostics. The engine receives `dt` (delta time) per frame and decides how to adapt.

| Metric | Measured By | Reported Via |
|--------|-------------|--------------|
| GPU frame time | `OrbRenderer` (frontend) | `presence:renderer-health` IPC |
| CPU frame time | `PresenceRuntime.tick()` | `PresenceDiagnostics` |
| Frame budget | Configuration | `PresenceDiagnostics` |
| Refresh rate | `OrbRenderer` FPS counter | `PresenceDiagnostics` |
| Quality level | Application policy | `PresenceDiagnostics` |

---

## 5. Development Diagnostics

A dev-only diagnostics panel is mounted in the frontend when `import.meta.env.DEV` is true. It shows:

- RuntimeState
- FrameState
- FPS
- GPU frame time
- CPU frame time
- Quality level
- Current embodiment
- Engine status

Access via the `Diagnostics` button in the bottom-right corner of the application.

The desktop exposes a `presence:diagnostics` IPC handler that returns `PresenceHealth` on demand.

---

## 6. Placeholder Removal

The following placeholder logic has been eliminated from the production pipeline:

- Desktop `AnimationRuntime` (fake breathing, dummy energy, simulated thinking states)
- `CosmicCore` framer-motion placeholder
- `LivingOrbV1` framer-motion placeholder
- Duplicated interpolation and smoothing

The engine's `AnimationRuntime` is now the sole source of visual state. The frontend `OrbRenderer` consumes `FrameState` directly with no additional runtime calculations.

---

## 3. Dependency Graph

```
desktop/
  ├── src/runtime/
  │   ├── engine/
  │   │   └── EngineAdapter.ts
  │   │       ├── imports AnimationRuntime, FrameState, RuntimeState from @zaram/engine
  │   │       └── NO renderer imports
  │   ├── presence/
  │   │   ├── presence-runtime.ts
  │   │   │   └── imports IEngineAdapter (interface)
  │   │   └── living-orb-adapter.ts
  │   │       └── imports IRenderTransport (interface)
  │   ├── interfaces.ts
  │   │   └── defines IEngineAdapter
  │   └── bootstrap.ts
  │       └── registers EngineAdapter via DI token TOKENS.engineAdapter
  │
  └── tests/
      └── runtime/
          ├── engine-integration.test.ts
          ├── presence-runtime.test.ts
          └── living-orb-adapter.test.ts

packages/zaram-engine/
  ├── index.ts               ← public API surface
  ├── runtime/
  │   └── AnimationRuntime.ts ← black-box library
  └── types/
      └── FrameState.ts       ← canonical FrameState spec
```

### Monorepo Resolution

The root `package.json` declares:

```json
{
  "private": true,
  "workspaces": ["packages/*"]
}
```

This makes `@zaram/engine` resolvable from `desktop/` via the workspace symlink in `node_modules/@zaram/engine`.

---

## 4. Sequence Diagram

```
User            Kernel        PresenceRuntime   EngineAdapter   AnimationRuntime   LivingOrbAdapter   Renderer
 │                │                │                │                │                   │               │
 │                │                │                │                │                   │               │
 │   boot()       │                │                │                │                   │               │
 │───────────────▶│                │                │                │                   │               │
 │                │  boot()        │                │                │                   │               │
 │                │───────────────▶│                │                │                   │               │
 │                │                │                │                │                   │               │
 │                │                │  start()       │                │                   │               │
 │                │                │───────────────▶│                │                   │               │
 │                │                │                │                │                   │               │
 │                │                │  tick()        │                │                   │               │
 │                │                │  (30 Hz)       │                │                   │               │
 │                │                │───────────────▶│                │                   │               │
 │                │                │                │                │                   │               │
 │                │                │                │  update(dt,    │                   │               │
 │                │                │                │  runtimeState) │                   │               │
 │                │                │                │───────────────▶│                   │               │
 │                │                │                │                │                   │               │
 │                │                │                │                │  FrameState        │               │
 │                │                │                │                │───────────────────▶│               │
 │                │                │                │                │                   │               │
 │                │                │                │◀───────────────│                   │               │
 │                │                │◀───────────────│                │                   │               │
 │                │                │                │                │                   │               │
 │                │                │  consumeFrame()│                │                   │               │
 │                │                │──────────────────────────────────▶                   │               │
 │                │                │                │                │                   │  setFrame()   │
 │                │                │                │                │                   │──────────────▶│
 │                │                │                │                │                   │               │
```

---

## 5. Integration Boundaries

### What EngineAdapter Owns

- A single `AnimationRuntime` instance from `@zaram/engine`.
- The `visualIdentity` seed, initialized from the desktop `SystemRuntime`.
- Translation from desktop `RuntimeSnapshot` → engine `RuntimeState`.
- Calling `AnimationRuntime.update(dt, runtimeState)` and returning the resulting `FrameState`.

### What EngineAdapter Must NOT Contain

- Any renderer imports (`three`, `webgl`, `electron` renderer modules, shaders).
- Any drawing, compilation, or GPU logic.
- Any coupling to `LivingOrbAdapter` or the render transport.

### What PresenceRuntime Changed

- Added `IEngineAdapter` and `IRuntimeStateProvider` dependencies.
- Owns a `setInterval` timer (~30 Hz) that drives the engine.
- Maps `RuntimeSnapshot.system.state` (lowercase) to the engine's `RuntimeState.state` (uppercase).
- Forwards the returned `FrameState` to the active `IEmbodiment`.
- Tracks performance metrics (GPU frame time, CPU frame time, FPS).
- Exposes diagnostics through `IPresenceDiagnostics`.

### What EmbodimentManager Changed

- Manages a registry of `IEmbodiment` implementations.
- Supports switching embodiments without modifying the runtime.
- Delegates lifecycle calls (`initialize`, `start`, `pause`, `resume`, `shutdown`) to the active embodiment.

### What LivingOrbAdapter Changed

- Nothing, except that `setFrameState` now receives the canonical `FrameState` produced by the engine.
- No renderer imports were added.
- No Three.js, React, or Electron renderer code was introduced.

### What the Renderer Owns

- `OrbRenderer` (frontend canvas renderer)
- IPC bridge for `presence:frame`, `presence:viewport`, `presence:renderer-health`
- `DiagnosticsPanel` (dev-only)
- All drawing, canvas, and presentation logic

The desktop integration layer does not touch any of these.

---

## 6. DI Registrations

```ts
// desktop/src/runtime/di/container.ts
TOKENS.engineAdapter: 'EngineAdapter'
TOKENS.embodiment: 'EmbodimentManager'
```

### Registration Flow

```ts
container.register(TOKENS.engineAdapter, (c) => {
  const engineAnimation = new EngineAnimationRuntime(0.5)
  const adapter = new EngineAdapter({
    animationRuntime: engineAnimation,
    visualIdentity: 0.5
  })
  const system = c.resolve<SystemRuntime>(TOKENS.systemRuntime)
  adapter.initialize(system.getSnapshot().visualIdentity)
  return adapter
}, { singleton: true })

container.register(TOKENS.embodiment, (c) => {
  return new EmbodimentManager({
    transport: c.resolve<IRenderTransport>(TOKENS.renderTransport)
  })
}, { singleton: true })
```

- The engine is resolved via the `IEngineAdapter` interface.
- The embodiment is resolved via the `IEmbodiment` interface.
- No globals are used.
- No singletons exist outside the DI container.

---

## 7. TypeScript & Build

- Root `package.json` declares `"workspaces": ["packages/*"]`.
- `@zaram/engine` is linked into `desktop/node_modules/@zaram/engine` by npm workspaces.
- Desktop `tsconfig.json` compiles cleanly against the engine's public API.
- Engine `tsconfig.json` produces `dist/` with declarations.
- Frontend `vite.config.js` no longer aliases `zaram-engine` (renderer is frontend-local).

---

## 8. Tests

| Test File | Coverage |
|-----------|----------|
| `tests/runtime/engine-integration.test.ts` | Engine initializes, receives `RuntimeState`, returns `FrameState`, owns `AnimationRuntime`, no renderer dependency |
| `tests/runtime/presence-runtime.test.ts` | Presence Runtime forwards `FrameState`, switches embodiment, diagnostics |
| `tests/runtime/living-orb-adapter.test.ts` | Adapter lifecycle, forwards `FrameState` to transport, no renderer code |
| `tests/runtime/presence-integration.test.ts` | End-to-end aggregation and frame flow, performance metrics |
| `tests/runtime/embodiment-manager.test.ts` | Embodiment switching, registry, lifecycle delegation |
| `tests/runtime/di.test.ts` | DI registration and singleton behavior |

All tests pass. `npx vitest run` → 64 passed.
