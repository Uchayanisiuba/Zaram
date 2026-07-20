# Runtime_World v1.0

Status: Accepted (Milestone 1.3)

## Purpose

The World Runtime is an **Intelligence Runtime** that aggregates system
perception — the discrete, observable state of the environment the AI inhabits
(desktop shell, applications, OS, notifications) — into a single immutable
`WorldState`. It is the "what is around the AI right now" layer, fully separate
from how the AI is expressed (CharacterFrame) and how it is drawn (renderer).

Milestone 1.3 builds directly on the verified Milestone 1.2 architecture. The
existing runtimes, the renderer, the embodiment framework, and `CharacterFrame`
are untouched.

## Dependencies

- `../types` (`clampUnit`) — pure runtime helpers, no renderer/embodiment import.
- `../cognitive` (type-only `AttentionEvent`) — for the World→Attention adapter.
- The existing 30Hz scheduler owned by `PresenceRuntime.tick()`.

It does **not** depend on: renderer code, embodiment code, `CharacterFrame`,
`@zaram/engine`, or any polling/timer/RAF primitive.

## Files

- `src/runtime/world/types.ts` — immutable `WorldState` and sub-snapshots
  (`EnvironmentSnapshot`, `DesktopState`, `ApplicationState`, `SystemState`,
  `NotificationState`), the `IWorldState` / `IWorldStateProvider` interfaces, and
  `deepFreeze`.
- `src/runtime/world/world-runtime.ts` — `WorldRuntime`: perception aggregation,
  immutable snapshot production, world-event publishing, and tick-driven
  notification salience decay.
- `src/runtime/world/world-attention-adapter.ts` — `attentionEventFromWorld`
  (interface-only World → Attention mapping).
- `src/runtime/world/index.ts` — barrel.

## Public API

```ts
class WorldRuntime implements IWorldStateProvider {
  // Perception ingestion (called by injected sources; push-based, no timers).
  setEnvironment(next: Partial<EnvironmentSnapshot>): void
  setDesktop(next: Partial<DesktopState>): void
  setApplication(next: Partial<ApplicationState>): void
  setSystem(next: Partial<SystemState>): void
  deliverNotification(input: { id; title; category?; severity?; correlationId? }): void
  clearNotification(id: string): void

  // Time evolution on the reused 30Hz tick. No new timer/loop.
  update(dt: number): void

  // Read-only, frozen snapshots (IWorldState).
  getWorldState(): Readonly<WorldState>
  getEnvironment(): Readonly<EnvironmentSnapshot>
  getDesktop(): Readonly<DesktopState>
  getApplication(): Readonly<ApplicationState>
  getSystem(): Readonly<SystemState>
  getNotification(): Readonly<NotificationState>

  // World-event pub/sub.
  subscribe(listener: WorldEventListener): () => void
}
```

### IWorldState (consumed by the Attention Runtime)

```ts
interface IWorldState {
  getWorldState(): Readonly<WorldState>
  getEnvironment(): Readonly<EnvironmentSnapshot>
  getDesktop(): Readonly<DesktopState>
  getApplication(): Readonly<ApplicationState>
  getSystem(): Readonly<SystemState>
  getNotification(): Readonly<NotificationState>
}

interface IWorldStateProvider extends IWorldState {
  subscribe(listener: WorldEventListener): () => void
  update(dt: number): void
}
```

The Attention Runtime depends only on `IWorldState`/`IWorldStateProvider`. It
never imports `WorldRuntime`. `attentionEventFromWorld(world: IWorldState)`
derives an `AttentionEvent` from the immutable snapshot.

## Architectural Invariants

1. **Immutable snapshots.** Every read returns a `deepFreeze`d deep copy. Consumers
   cannot mutate world state. `revision` increments on every change.
2. **Event-driven perception.** Sources push via `set*`; each produces a typed
   `WorldEvent`. No polling.
3. **Reused 30Hz scheduler.** `WorldRuntime.update(dt)` is called inside
   `PresenceRuntime.tick()` — the same `setInterval(() => this.tick(), 1000/30)`
   that already drives Animation/Character/Cognitive. No `setInterval`,
   `setTimeout`, or `requestAnimationFrame` is introduced by the World Runtime.
4. **Full drawing-layer independence.** Zero imports of renderer, embodiment, or
   `CharacterFrame`. The World Runtime produces no `FrameState`.
5. **Dependency injection.** Registered as a singleton token `worldRuntime` and
   resolved (never `new`ed inline) by `PresenceRuntime` via the container.

## Scheduler Reuse Detail

`PresenceRuntime.tick()` (the existing 30Hz loop) now also advances the world:

```ts
if (this.worldRuntime) {
  this.worldRuntime.update(dt)   // decay notification salience, time-evolved
}
```

This keeps notification salience decay framerate-independent and timer-free,
consistent with how `CognitiveBundle.update(dt)` is advanced.

## Performance

Benchmarks (`tests/runtime/world/world-bench.ts`) assert:

- `getWorldState()` p50 < 1ms, p99 < 5ms (1000 reads).
- `update()` avg < 1ms/frame at 30Hz over one simulated second.
- 10,000 perception writes in < 50ms.
- No `setInterval`/`setTimeout`/`requestAnimationFrame`/`while` in the world module.
