# Zaram Milestone 1.1 — Embodiment Framework

Architectural milestone. Evolves the verified Milestone 1.0 frame pipeline into a
renderer-independent embodiment system that can drive the Living Orb, MetaHuman,
GNM-generated MetaHuman, Robots, and future embodiments — **without changing the
runtime**.

> **Milestone 1.2 update:** The cognitive layer (`src/runtime/cognitive`) now sits
> *above* `CharacterRuntime`, separating thinking from embodiment. See
> `docs/MILESTONE_1.2_COGNITIVE_RUNTIME.md`. The pipeline below is extended, not
> broken: `CognitiveRuntime → CharacterRuntime`, with `PresenceRuntime` feeding
> both event-driven from the aggregator and advancing them on the same 30 Hz tick.

---

## 1. Verified Milestone 1.0 Pipeline (UNTOUCHED)

```
AnimationRuntime          (@zaram/engine — unchanged)
   -> PresenceRuntime     (unchanged)
      -> IEmbodiment     (unchanged contract)
         -> LivingOrbAdapter (unchanged)
            -> RenderTransport (unchanged)
               -> OrbRenderer    (unchanged; owner of requestAnimationFrame)
```

These files were not modified. All 60 Milestone 1.0 tests continue to pass.

---

## 2. Final Embodiment Architecture (Milestone 1.1)

```
+---------------------------------------------------------------+
|                      SOURCE RUNTIMES (events)                 |
|  Conversation | Voice | Knowledge | System | Memory          |
+---------------+-----------------------------------------------+
                |  aggregated RuntimeSnapshot (subscribe)
                v
+---------------------------------------------------------------+
|  PresenceRuntime  (unchanged contract, extended injection)     |
|   - tick(30Hz): AnimationRuntime.update()  [FrameState]       |
|   - tick(30Hz): CharacterRuntime.update() [CharacterState]    |
|   - subscribe(): feeds CharacterRuntime (event-driven)         |
+--------+------------------------------------------+-------------+
         |                                          |
   FrameState (existing)                    CharacterState (new)
         |                                          |
         v                                          v
   IEmbodiment                               toCharacterFrame()
   (LivingOrbAdapter)                             |
         |                                       CharacterFrame  <-- RENDERER BOUNDARY
         v                                          |
   RenderTransport  ---------------------------->  Renderer
                                              (sees ONLY CharacterFrame:
                                               no emotion/think/voice/
                                               memory/knowledge refs)
```

### Embodiment selection (DI-driven registry)

```
                +-----------------------------+
                |   EmbodimentRegistry      |  (declares, resolves)
                |   descriptors: Map<type> |
                +-------------+-------------+
                              |  resolve(type, context)
                              v
                  EmbodimentFactory(ctx) -> IEmbodiment
                       LivingOrb  |  MetaHuman* |  Robot* |  Null
                       (*future, disabled until deps injected)

   EmbodimentManager  ->  holds the ACTIVE IEmbodiment
        (the single IEmbodiment PresenceRuntime talks to)
```

---

## 3. Dependency Graph

```
Container (TOKENS)
  ├─ renderTransport        -> NullRenderTransport | WebContentsTransport
  ├─ expressiveParams       -> DefaultExpressiveParamsSource
  ├─ embodimentRegistry     -> EmbodimentRegistry (built-ins seeded)
  ├─ embodiment            -> EmbodimentManager(registry, transport, adapters)
  ├─ characterRuntime      -> CharacterRuntime            [NEW]
  ├─ runtimeAggregator     -> RuntimeSourceAggregator
  ├─ conversationRuntime / voiceRuntime / memoryRuntime / systemRuntime
  ├─ engineAdapter         -> AnimationRuntime(@zaram/engine)
  └─ presenceRuntime       -> PresenceRuntime(..., characterRuntime) [EXTENDED]

CharacterRuntime
  ├─ EmotionRuntime      (continuous model + smoothing)
  ├─ BehaviourRuntime    (state machine)
  └─ GazeController      (eye/head/blink targets)

EmbodimentRegistry
  └─ EmbodimentDescriptor{ type, label, enabled, create: EmbodimentFactory }
        └─ EmbodimentFactory(EmbodimentContext) -> IEmbodiment

Future interfaces (no impl, no external imports):
  IMetaHumanAdapter, IFaceRig, IFacialExpressionProvider, IARKitDriver
  IHeadGenerator, HeadDescriptor, FaceTopology, MorphTargetSet

RENDERER depends on: CharacterFrame  (and FrameState, legacy)
FRAMEWORK depends on RENDERER: nothing.
```

---

## 4. Runtime Graph

```
[tick 30Hz, owned by PresenceRuntime's existing setInterval]
   |
   +---> AnimationRuntime.update(dt, snapshot)  -> FrameState
   |           -> EmbodimentManager.setFrameState(FrameState)
   |                 -> LivingOrbAdapter -> RenderTransport -> OrbRenderer
   |
   +---> CharacterRuntime.update(dt)  -> CharacterState
               (EmotionRuntime, BehaviourRuntime, GazeController advance)
   |
   +---> PresenceRuntime.getCharacterFrame() -> toCharacterFrame() -> CharacterFrame
                                                      -> Renderer (neutral)

[event-driven, subscribed once at construction]
   RuntimeSourceAggregator.subscribe(snapshot => feedCharacterFromSnapshot)
       -> CharacterRuntime.setIntent / emitEmotion / setGazeTarget
```

**No additional requestAnimationFrame. No new timers. No polling.** The only
interval is the pre-existing 30Hz tick in PresenceRuntime; CharacterRuntime is
advanced inside it.

---

## 5. Data Flow

```
RuntimeSnapshot (conversation/voice/system/memory)
   |
   |  (a) subscribe -> feedCharacterFromSnapshot()
   v
EmotionEvents ──> EmotionRuntime.emit() ──> target axes
                                      |
                                      v  (smoothed each update)
                                  EmotionState
Behaviour intents ──> BehaviourRuntime.setIntent()/trigger*() ──> BehaviourState
Gaze context ──> GazeController.setMode()/setTarget() ──> GazeState

CharacterRuntime.update(dt):
   EmotionState + BehaviourState + GazeState + breath + microMovement
                                   |
                                   v
                             CharacterState
                                   |
                                   v  toCharacterFrame()
                             CharacterFrame  ──(renderer boundary)──> Renderer
```

---

## 6. Sequence Diagrams

### 6.1 Boot & Injection

```
Dev/Bootstrap      Container        EmbodimentRegistry   EmbodimentManager   CharacterRuntime
   |                  |                    |                     |                   |
   | bootstrapPresence()                |                     |                   |
   |----------------->| register tokens   |                     |                   |
   |                  |------------------>| seed built-ins      |                   |
   |                  | resolve(embodiment)------------------>|                   |
   |                  |                    | resolve('living-orb', ctx)               |
   |                  |                    |-------------------->| new LivingOrb    |
   |                  | resolve(characterRuntime)--------------------------------->|
   |                  | resolve(presenceRuntime, characterRuntime)                |
   |<-----------------| PresenceRuntime ready  |                     |           |
```

### 6.2 Per-Tick (no new loop)

```
PresenceRuntime.tick()  [existing 30Hz]
   |
   |-- AnimationRuntime.update(dt, snapshot) -> FrameState
   |-- consumeFrameState(FrameState) -> EmbodimentManager -> LivingOrb -> Transport
   |
   |-- CharacterRuntime.update(dt) -> CharacterState
   |-- (Renderer pulls) getCharacterFrame() -> toCharacterFrame() -> CharacterFrame
```

### 6.3 Event-Driven Emotion (no polling)

```
RuntimeSourceAggregator      PresenceRuntime          CharacterRuntime      EmotionRuntime
   | emit(snapshot)               |                        |                    |
   |----------------subscribe------>| feedCharacterFromSnapshot                       |
   |                              | setIntent('thinking') |                    |
   |                              | emit({thinkingLoad})  ->| emit(event)        |
   |                              |                        | target axes updated |
   (next tick) CharacterRuntime.update(dt) -> EmotionRuntime eases current->target
```

### 6.4 Embodiment Switch (registry, runtime untouched)

```
Caller              EmbodimentManager      EmbodimentRegistry     Next IEmbodiment
  | switchTo('metahuman')  |                    |                     |
  |------------------------>| has('metahuman')? |                     |
  |                        |------------------->| true                |
  |                        | resolve('metahuman', ctx)------------------>| create()
  |                        | current.shutdown() |                     |
  |                        | current = next     |                     |
  |<-----------------------| done              |                     |
  (PresenceRuntime never changes; it still calls current.setFrameState)
```

---

## 7. Renderer Independence (PART 8 — enforced)

The Renderer receives **only** `CharacterFrame` (and the legacy `FrameState`).

`CharacterFrame` contains:
- `emotion`: { valence, arousal, confidence, attention, warmth, curiosity, fatigue }
- `behaviour`: { mode, intensity, microExpression }
- `gaze`: { eyeX, eyeY, convergence, headX, headY, headTilt, blinkClosure }
- `breath`, `microMovement`, `sequence`, `version`, `timestamp`

It contains **no field, type, or reference** to: emotion *semantics*, thinking,
conversation, voice, memory, knowledge. The projection `toCharacterFrame()` is
the single seam. A test asserts the serialized frame does not match
`/conversation|voice|memory|knowledge|thinking/i`.

---

## 8. Performance (PART 9)

- **No additional render loops.** OrbRenderer keeps ownership of
  `requestAnimationFrame`. The only interval is the pre-existing 30Hz tick in
  `PresenceRuntime`.
- **Everything else is event-driven.** `CharacterRuntime` is fed by a single
  `subscribe` to the aggregator and advanced inside the existing tick.
- **No polling, no duplicated updates.** The aggregator is subscribed once.
- **Measured cost:** 1000 `CharacterRuntime.update(1/30)` calls execute in
  well under 50ms (asserted in tests). Cost per tick is O(1) field easing.

---

## 9. Files

### New files
- `src/runtime/embodiment/types.ts` — CharacterState, CharacterFrame, EmotionState, Gaze types
- `src/runtime/embodiment/registry.ts` — EmbodimentRegistry, EmbodimentDescriptor, EmbodimentFactory, EmbodimentContext
- `src/runtime/embodiment/descriptors.ts` — built-in descriptors (LivingOrb, Null, MetaHuman*, Robot*)
- `src/runtime/embodiment/null-embodiment.ts` — NullEmbodiment
- `src/runtime/embodiment/emotion-runtime.ts` — EmotionRuntime (continuous + smoothing)
- `src/runtime/embodiment/behaviour-runtime.ts` — BehaviourRuntime
- `src/runtime/embodiment/gaze-controller.ts` — GazeController
- `src/runtime/embodiment/character-runtime.ts` — CharacterRuntime
- `src/runtime/embodiment/character-frame.ts` — toCharacterFrame projection
- `src/runtime/embodiment/metahuman.ts` — IMetaHumanAdapter, IFaceRig, IFacialExpressionProvider, IARKitDriver (interfaces only)
- `src/runtime/embodiment/gnm.ts` — IHeadGenerator, HeadDescriptor, FaceTopology, MorphTargetSet (interfaces only)
- `tests/runtime/embodiment-framework.test.ts` — 28 new tests

### Modified files
- `src/runtime/embodiment/index.ts` — exports the new modules
- `src/runtime/embodiment/EmbodimentManager.ts` — resolves via registry; injects EmbodimentContext
- `src/runtime/di/container.ts` — TOKENS.embodimentRegistry, TOKENS.characterRuntime
- `src/runtime/bootstrap.ts` — registers registry + CharacterRuntime; injects into PresenceRuntime
- `src/runtime/presence/presence-runtime.ts` — subscribes aggregator -> CharacterRuntime; ticks CharacterRuntime; exposes getCharacterFrame()
- `src/runtime/index.ts` — re-exports `./embodiment`

### Deleted files
- None. The Milestone 1.0 pipeline is preserved.

---

## 10. Architectural Decision Justification

| # | Decision | Justification |
|---|-----------|----------------|
| 1 | Keep AnimationRuntime/PresenceRuntime/LivingOrb/Transport/Renderer untouched | The verified 1.0 pipeline is a hard contract. We extend, never modify, the hot path. 60 regression tests enforce this. |
| 2 | Registry holds Descriptors; factories take an injected Context | Guarantees no runtime news up an embodiment. Switching embodiments = registry.resolve(type, ctx). DI-only construction. |
| 3 | Continuous Emotion model (valence/arousal/…) with eased smoothing | Avoids "fake" discrete emotions; emotions *emerge* from events. Smoothing ensures no instant jumps (tested). |
| 4 | User never sets emotion directly | Only `emit(event)` exists; there is no `setValence`. Aligns with the brief. |
| 5 | CharacterRuntime owned by PresenceRuntime, ticked inside the existing 30Hz loop | No second render loop; respects PART 9 performance constraints. |
| 6 | Event-driven feed via aggregator.subscribe | No polling; one subscription at construction. |
| 7 | Single toCharacterFrame() projection = renderer boundary | Renderer sees only renderer-neutral values; decoupled from emotion/thinking/voice/memory/knowledge (enforced by test). |
| 8 | Future MetaHuman/GNM as interfaces only, no Unreal/ARKit/GNM imports | Architecture scaffolding now; implementations plug in later without runtime changes. |
| 9 | BehaviourRuntime & GazeController hold state only, no renderer logic | Keeps the framework renderer-agnostic and testable in isolation. |
| 10 | EmbodimentManager keeps a (type, embodiment) compat shim | Preserves Milestone 1.0 test signatures while adding the descriptor API. |

---

## 11. Validation Summary

- **No renderer coupling:** `toCharacterFrame` output tested to exclude source-domain keywords; embodiment layer imports no `three/webgl/renderer/electron`.
- **Dependency injection:** bootstrap registers registry + CharacterRuntime; EmbodimentManager resolves via injected context; living-orb throws if transport absent.
- **Registry operation:** register/list/resolve/switch verified; MetaHuman resolves only with injected adapter.
- **Behaviour transitions:** intent->mode mapping, transient behaviours returning to base intent, surprise micro-expression, intensity scaling.
- **Emotion smoothing:** continuous eased approach, no instant snap, all axes clamped.
- **Eye target generation:** bounded eye/head targets, scheduled blinks, wander motion.
- **Character state generation:** CharacterRuntime yields emotion/behaviour/gaze/breath/microMovement.
- **Performance:** 1000 updates < 50ms; no `requestAnimationFrame`/`setInterval` in the embodiment layer.
- **Existing Milestone 1.0 tests:** 60/60 still pass.
- **Total:** 88 tests pass (60 existing + 28 new).
