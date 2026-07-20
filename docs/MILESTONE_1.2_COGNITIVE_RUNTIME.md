# Zaram Milestone 1.2 — Cognitive Runtime

Architectural milestone. Introduces the **internal AI cognition layer** that
separates *thinking* from *embodiment*. The AI maintains internal state
independent of rendering.

The verified embodiment pipeline is **preserved**:

```
AnimationRuntime
  -> PresenceRuntime
     -> CharacterRuntime
        -> IEmbodiment
           -> LivingOrbAdapter
              -> RenderTransport
                 -> OrbRenderer
```

---

## 1. New Pipeline (Milestone 1.2)

```
                 SOURCE RUNTIMES (events)
   Conversation | Voice | Knowledge | System | Memory
                          |
                          |  aggregated RuntimeSnapshot (subscribe, once)
                          v
                  +--------------------------+
                  |   PresenceRuntime        |  (extended, pipeline intact)
                  |  - 30 Hz tick (existing) |
                  |  - aggregator.subscribe  |  (existing, event-driven)
                  +-----+-----------+--------+
                        |           |
        feedCognitive   |           |  feedCharacter (emotion)
        (event-driven)  |           |
                        v           v
              +------------------+  +------------------+
              | CognitiveBundle  |  | CharacterRuntime |  (M1.1, unchanged role)
              |  - Cognitive     |  |  Emotion/Behaviour|
              |  - Attention     |  |  /Gaze            |
              |  - Relationship  |  +------------------+
              +--------+---------+
                       |
                       | CharacterRuntime.setIntent(reasoning)  (cognitive -> embodiment bridge)
                       v
                  CharacterRuntime (unchanged ownership)
                       |
                       v  toCharacterFrame()
                  CharacterFrame  <-- RENDERER BOUNDARY (no cognition fields)
                       |
                       v
                  IEmbodiment -> LivingOrbAdapter -> RenderTransport -> OrbRenderer
```

Key point: the renderer receives **only** `CharacterFrame` (and legacy
`FrameState`). It never sees reasoning, planning, relationship, attention, or
knowledge state.

---

## 2. PART 1 — CognitiveRuntime

Responsibilities (all internal, independent of rendering):

| Concern | Field / API |
|---|---|
| Reasoning State | `reasoning: 'idle'|'perceiving'|'reasoning'|'planning'|'reflecting'|'deciding'` |
| Conversation Intent | `intent: ConversationIntent` |
| Internal Goals | `goals: {id,label,weight}[]` (weighted, sorted) |
| Planning State | `planning: {active,progress,steps[]}` |
| Task Queue | `taskQueue: CognitiveTask[]` (priority sorted) |
| Attention Priority | `attentionPriority: 0..1` |
| Thinking Status | `thinking: boolean` |
| Knowledge Requests | `knowledgeRequests[]` (open/resolved) |
| Memory Requests | `memoryRequests[]` (open/resolved) |

Driven exclusively by `CognitiveEvent`s emitted by runtimes — never set by the
user. Each event bumps a monotonic `revision` so consumers can detect change.

## 3. PART 2 — AttentionRuntime

Tracks `current` target, `speaker`, `conversationTarget`, normalized
`cursor`/`camera`, `focusConfidence`, `notificationSalience`, `memoryRelevance`,
derived `priority`. Cursor/camera ease toward event-driven **targets** so
transitions are smooth (no instant jumps). Notification salience decays over
time. Purely event-driven + advanced on the existing tick.

`attentionTargetFromCognitive(state)` maps reasoning → attention target
(`perceiving→speaker`, `reasoning/planning→internal`, `deciding→conversation`,
`reflecting→memory`).

## 4. PART 3 — RelationshipRuntime

Continuous metrics evolving **gradually** (each event capped to `maxStep`,
default 0.05 of the full range — no instant jumps). Tracks trust, familiarity,
conversation history weight, preference confidence, interaction frequency
(decays when idle), respect, humor compatibility, interaction count.

## 5. PART 4 — MemoryProjection (interfaces only)

The Memory Runtime is **not modified**. Projection interfaces read its snapshot:
- `MemoryProjection` — `project`, `buildContext`, `rankRelevant`
- `RelevantMemory` — `{id, summary, relevance, recency, tags}`
- `MemorySummary` — `{count, recall, activity, relevant[]}`
- `ConversationContext` — `{summary, participants[], topics[], turnCount}`

## 6. PART 5 — ConversationProjection

`projectConversation(phase, cognitive)` → `ConversationProjection`:
- `ThinkingState` (active, depth, reasoning)
- `SpeakingState` (active, assertiveness, intent)
- `ListeningState` (active, attentiveness)
- `InterruptibleState` (interruptible, openness)
- `ConversationIntent`

Pure function, no side effects, no renderer logic.

## 7. PART 6 — Presence Integration

`PresenceRuntime` (Milestone 1.0/1.1 contract preserved):
- accepts optional `cognitiveRuntime: CognitiveBundle`
- on the **existing** aggregator subscription, calls `feedCognitiveFromSnapshot`
  (event-driven) in addition to `feedCharacterFromSnapshot`
- drives `CharacterRuntime.setIntent` from the cognitive `reasoning` state
- on the **existing** 30 Hz tick, calls `cognitiveRuntime.update(dt)`

Accessors (`getCognitiveState`, `getAttentionState`, `getRelationshipState`)
expose internal AI state for the application layer — **not** for the renderer.

## 8. PART 7 — Performance

- **Event-driven.** One aggregator subscription feeds both character and
  cognitive layers. No polling.
- **No additional render loops.** `CognitiveBundle.update()` runs inside the
  same 30 Hz tick already owned by `PresenceRuntime`.
- **No duplicated state.** Cognitive state is the single source; the
  embodiment reads it via the projection/bridge.
- Measured (see §10): 5000 `update` ticks < 100 ms; 10000 event emits < 100 ms;
  the cognitive layer contains no `requestAnimationFrame`/`setInterval`/
  `setTimeout`.

---

## 9. Dependency Graph

```
Container (TOKENS)
  ├─ cognitiveRuntime  -> CognitiveBundle (singleton)        [NEW]
  │     ├─ CognitiveRuntime
  │     ├─ AttentionRuntime
  │     └─ RelationshipRuntime
  ├─ characterRuntime  -> CharacterRuntime        (M1.1)
  ├─ embodiment        -> EmbodimentManager       (M1.1)
  ├─ runtimeAggregator -> RuntimeSourceAggregator (feeds both layers)
  └─ presenceRuntime   -> PresenceRuntime (feeds + ticks both) [EXTENDED]

Cognitive layer imports: only types + ../types(clampUnit) + sources/types
Cognitive layer imports from renderer/embodiment: NOTHING (one-way: Presence
bridge writes CharacterRuntime intent; cognition never reads renderer).
```

## 10. Performance Analysis (benchmarks)

| Operation | Volume | Budget | Measured |
|---|---|---|---|
| `CognitiveBundle.update(dt)` | 5000 ticks | < 100 ms | < 100 ms ✅ |
| `CognitiveRuntime.emit(event)` | 10000 emits | < 100 ms | < 100 ms ✅ |
| New timers in `cognitive/` | — | 0 | 0 ✅ (grep-verified) |
| Added tick work | per frame | O(1) easing | negligible ✅ |

All cognition work reuses the existing 30 Hz tick; no frame is added.

## 11. Files

### New files
- `src/runtime/cognitive/types.ts` — CognitiveRuntime + CognitiveState/Event
- `src/runtime/cognitive/attention-runtime.ts` — AttentionRuntime + attentionTargetFromCognitive
- `src/runtime/cognitive/relationship-runtime.ts` — RelationshipRuntime
- `src/runtime/cognitive/memory-projection.ts` — MemoryProjection interfaces
- `src/runtime/cognitive/conversation-projection.ts` — ConversationProjection + projectConversation
- `src/runtime/cognitive/bundle.ts` — CognitiveBundle (DI unit)
- `src/runtime/cognitive/index.ts` — barrel
- `tests/runtime/cognitive-runtime.test.ts` — 30 new tests

### Modified files
- `src/runtime/di/container.ts` — `TOKENS.cognitiveRuntime`
- `src/runtime/bootstrap.ts` — register + inject `CognitiveBundle`
- `src/runtime/presence/presence-runtime.ts` — accept/feed/tick cognitive bundle; accessors
- `src/runtime/index.ts` — `export * from './cognitive'`
- `docs/MILESTONE_1.1_EMBODIMENT_FRAMEWORK.md` — M1.2 note
- `.ai/13_ADR_INDEX.md`, `.ai/adr/ADR-011_Cognitive_Runtime_Separation.md`

### Deleted files
- None. The Milestone 1.0/1.1 pipelines are preserved.

## 12. Test Results

- **Prior tests:** 88/88 still pass (Milestone 1.0 + 1.1).
- **New tests:** 30/30 pass (cognitive-runtime.test.ts).
- **Total:** **118/118 pass.** `tsc -p .` exits 0.

## 13. Final Cognitive Architecture

```
                 ┌─────────────────────────────────────────┐
   sources ──────▶│  RuntimeSourceAggregator (subscribe once) │
                 └───────────────┬───────────────┬──────────┘
                                 │               │
                    feedCharacter │               │ feedCognitive (event-driven)
                                 ▼               ▼
                       CharacterRuntime    CognitiveBundle
                       (embodiment state)   ├─ CognitiveRuntime
                                            ├─ AttentionRuntime
                                            └─ RelationshipRuntime
                                 │               │
                                 │  setIntent(    │
                                 │   reasoning)   │
                                 ▼               │
                       CharacterState ───────────┘
                                 │
                                 ▼ toCharacterFrame()
                          CharacterFrame  ──▶ Renderer (only this; no cognition)
```

The AI now thinks in `CognitiveRuntime` (and Attention/Relationship), entirely
decoupled from how the Living Orb (or any future embodiment) expresses it.
