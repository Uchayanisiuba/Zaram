# Presence Runtime Foundation (Milestone 0.9)

The **Presence Runtime** is the permanent abstraction layer responsible for managing Zaram's
visual embodiment. It is the sole intermediary between the Zaram Kernel / functional runtimes
and the physical or virtual embodiment (Living Orb, Unreal Character, XR Avatar, etc.). The rest
of the system remains entirely agnostic to which embodiment is currently active.

---

## 1. Architectural placement

```
Zaram Kernel (Orchestrator)
        │  depends only on IPresenceRuntime (DI)
        ▼
Functional Runtimes ──(expressive params)──┐
  Conversation / Voice / Memory / Garage /  │
  Plugin / Personality / System             │
        │                                    │
        ▼                                    ▼
Animation Runtime ──(animation data)──► FrameState Producer ──(FrameState)──►
        │                                                                   │
        └───────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
                            ┌──────────────────────────┐
                            │     Presence Runtime      │  (this milestone)
                            │  lifecycle + orchestration │
                            │  + health + personality    │
                            └───────────┬───────────────┘
                                        │  setFrameState(FrameState)
                                        ▼
                            ┌──────────────────────────┐
                            │     Active Embodiment     │
                            │  e.g. LivingOrbAdapter    │  implements IEmbodiment
                            └───────────┬───────────────┘
                                        │  IRenderTransport.sendFrameState
                                        ▼
                            ┌──────────────────────────┐
                            │   Renderer (Living Orb)   │  never receives app events
                            └──────────────────────────┘
```

### Where the code lives

The brief specified `backend/runtime/presence/`. In this repository the Python `backend/`
is the LLM/TTS service layer, while the **embodiment stack is a TypeScript/Electron concern**
(the `IEmbodiment` interface is TypeScript, the renderer is the React Living Orb, and the
Electron host owns window/WebGL lifecycle). Per the hard constraint that *no runtime may live in
the renderer* and that the Presence Runtime is wired via DI and tested under `vitest`, the
implementation lives in the Electron host project:

```
desktop/src/runtime/        ← the "backend/runtime" layer behind the renderer
  types.ts                  FrameState, EmbodimentStatus, ExpressiveParams, ...
  interfaces.ts             IEmbodiment, IAnimationSource, IFrameStateProducer,
                            IPresenceRuntime, IPresenceDiagnostics, IZaramKernel, ...
  bootstrap.ts              DI registration (bootstrapPresence)
  di/                       dependency-injection Container + tokens
  presence/                 PresenceRuntime, LivingOrbAdapter, PresenceDiagnostics
  animation/                AnimationRuntime, FrameStateProducer
  personality/              DefaultExpressiveParamsSource (Personality Runtime hook)
  electron/                 EmbodimentHost + render transports
  kernel/                   ZaramKernel (orchestrator)
  index.ts                  public API barrel
```

---

## 2. The embodiment interface (`IEmbodiment`)

Every embodiment (current or future) implements this single, renderer-independent contract.
The Presence Runtime depends only on this interface — never on a concrete embodiment.

```typescript
interface IEmbodiment {
  initialize(): Promise<void>;
  start(): Promise<void>;
  pause(): Promise<void>;
  resume(): Promise<void>;
  shutdown(): Promise<void>;
  setFrameState(frameState: FrameState): void;
  getStatus(): EmbodimentStatus;
}
```

`FrameState` is the only data shape an embodiment ever receives. It is standardized and
renderer-agnostic:

```typescript
interface FrameState {
  timestamp: number;
  sequence: number;                         // monotonic, assigned by the Presence Runtime
  expressive: ExpressiveParams;             // presence, energy, focus, emotion, voiceLevel, processingLoad
  visual: { amplitude; intensity; hue; pulse; scale };  // 0..1 / 0..360
  conversation: { phase: ConversationPhase };
  meta?: Record<string, unknown>;
}
```

The renderer must **never** receive application events directly. It only receives `FrameState`
updates (forwarded by the adapter over the render transport channel `presence:frame`).

---

## 3. Presence Runtime lifecycle

`PresenceRuntime` is the orchestration core. It is constructed with an optional
`IFrameStateProducer`, an `IExpressiveParamsSource` (Personality Runtime), and an `IEmbodiment`.

| Method | Responsibility |
| --- | --- |
| `initialize()` | Initialize the active embodiment; mark animation connection `disconnected`. Idempotent. |
| `start()` | Initialize (if needed), start the embodiment, begin health clock, mark connection `connected`. |
| `pause()` | Pause the embodiment and throttle frame flow (used on window hide). |
| `resume()` | Resume the embodiment and frame flow (used on window show). |
| `shutdown()` | Best-effort shutdown of the embodiment; sets connection `disconnected`. |
| `setEmbodiment(e)` | Swap the active embodiment at runtime without Kernel involvement. |
| `consumeFrameState(fs)` | Forward a `FrameState` to the embodiment, stamp the sequence, record health. |
| `ingestAnimationFrame(frame)` | Convenience: run an `AnimationFrame` through the producer + latest expressive params, then `consumeFrameState`. |
| `getStatus()` / `getHealth()` | Embodiment status and runtime health/diagnostics. |

### Personality integration

Expressive parameters (Presence, Energy, Focus, Emotion, Voice Level, Processing Load) are
consumed from the Personality Runtime via `IExpressiveParamsSource`. The Presence Runtime
subscribes to them and forwards the *latest* snapshot into the `FrameStateProducer`, which maps
them to the visual fields (`hue` from emotion, `amplitude` from energy + voice, `intensity` from
focus, `scale` from presence, etc.). **No visual is hardcoded in the runtime** — the mapping is
data-driven and the embodiment interprets `FrameState` generically.

---

## 4. Living Orb adapter

`LivingOrbAdapter` satisfies `IEmbodiment` and acts purely as a **bridge**: it receives
`FrameState` and forwards it to a renderer via an `IRenderTransport`. It contains **no rendering
logic** and imports **no renderer code**.

```typescript
const transport = new WebContentsTransport(() => mainWindow);
const adapter = new LivingOrbAdapter(transport);
// adapter.setTransport(...) can swap the transport (used by the Electron host).
```

Two transports implement `IRenderTransport`:

- `NullRenderTransport` — in-memory, used as the DI default and in tests.
- `WebContentsTransport` — sends `FrameState` to the renderer process over IPC
  (`webContents.send('presence:frame', frameState)`). This is the only place the host talks to
  the renderer, and it only ever sends `FrameState`.

---

## 5. Electron integration layer (`EmbodimentHost`)

`EmbodimentHost` prepares the Electron host to support embodiment lifecycles. It is constructed
with a `getWindow()` accessor and the `IPresenceRuntime`, then `mount()`ed against the main
window. It manages:

- **Renderer host mounting / WebGL lifecycle** — creates the `WebContentsTransport` bound to the
  window and swaps it into the active embodiment via `attachToEmbodiment()`.
- **Resize handling + DPI awareness** — on `resize` and `screen:'display-metrics-changed'` it
  publishes a `ViewportInfo { width, height, scaleFactor }` (channel `presence:viewport`) so the
  renderer can adjust its WebGL viewport.
- **GPU context recovery** — on `webContents:'crashed'` / `'did-fail-load'` it re-initializes the
  Presence Runtime (`shutdown → initialize → start`).
- **Window visibility / background throttling** — `hide` pauses the Presence Runtime; `show`
  resumes it (configurable via `throttleOnHidden`).

All listeners are attached defensively (`safeOn`) and torn down in `unmount()`, so a missing or
partially-mocked window never throws.

`AppLifecycle` (`desktop/src/main/lifecycle.ts`) bootstraps the Presence Runtime via DI and,
once the main window exists, mounts the `EmbodimentHost` and boots the runtime.

---

## 6. Dependency injection

Registration uses a small, explicit `Container` (no global singletons, no hidden dependencies):

```typescript
const { container, presenceRuntime, buildKernel } = bootstrapPresence();
const kernel = buildKernel();   // ZaramKernel depends only on IPresenceRuntime
await kernel.boot();
```

Tokens (`di/container.ts` → `TOKENS`): `frameStateProducer`, `expressiveParams`,
`renderTransport`, `embodiment`, `presenceRuntime`, `kernel`. The Kernel resolves
`IPresenceRuntime` and is therefore **agnostic to the embodiment implementation** — swapping
`living-orb` for `unreal-character` is a DI registration change only.

---

## 7. Diagnostics

`IPresenceDiagnostics` exposes runtime health, current embodiment type, `FrameState` update
frequency, and the Animation↔Presence connection state:

- `getHealth(): PresenceHealth` — `{ status, currentEmbodiment, embodimentHealthy, frameRateHz,
  animationConnection, uptimeMs, lastFrameAt }`.
- `getEmbodimentType()` — currently active `EmbodimentType`.
- `getFrameRate()` — frames/sec over a rolling 1s window.
- `getAnimationConnection()` — `connected | disconnected | reconnecting`.

`PresenceRuntime` implements `IPresenceDiagnostics` directly, and `ZaramKernel.getDiagnostics()`
returns it.

---

## 8. Adding a future embodiment

1. Create `desktop/src/runtime/presence/<name>-adapter.ts` implementing `IEmbodiment`.
   - Never import renderer code.
   - Receive `FrameState` in `setFrameState` and forward it through an `IRenderTransport`.
2. (Optional) Provide a renderer-side consumer that listens on `presence:frame` and maps
   `FrameState` → your renderer. The renderer still only ever receives `FrameState`.
3. Register it in `bootstrapPresence` (or pass a custom `renderTransport` / override the
   `embodiment` token) — the Kernel and Presence Runtime require **no** code changes.

No changes are needed to Conversation, Voice, Memory, Garage, Plugin, Personality, or System
runtimes; they remain unaware of the embodiment.

---

## 9. Scope notes

Per the milestone scope, this foundation does **not** yet:

- integrate the GPU renderer or a real WebGL context (the host publishes viewport info and
  recovers from GPU crashes, but does not create a GL context);
- implement Unreal Engine / XR support (the `IEmbodiment` interface already allows them);
- modify the existing Living Orb renderer or graphics engine (the adapter only forwards
  `FrameState`).

---

## 10. Tests

Run from `desktop/`:

```bash
npm test          # vitest run
npm run build     # tsc -p .  (typecheck)
```

Coverage:

- `tests/runtime/frame-state-producer.test.ts` — FrameState mapping + clamping + emotion→hue.
- `tests/runtime/living-orb-adapter.test.ts` — lifecycle, frame forwarding, transport readiness.
- `tests/runtime/presence-runtime.test.ts` — Animation → Producer → Presence → Adapter data flow,
  health, embodiment switching.
- `tests/runtime/di.test.ts` — DI container + Presence Runtime registration + embodiment swap.
- `tests/runtime/kernel.test.ts` — ZaramKernel boot/dispose via DI, interface-only dependency.
- `tests/runtime/diagnostics.test.ts` — health/frame-rate/connection reporting.
- `tests/runtime/embodiment-host.test.ts` — Electron host: listeners, viewport/DPI, visibility
  throttling, GPU recovery.
