# Runtime_Executive v1.0

Status: Accepted (Milestone 1.4)

## Purpose

The Executive Runtime is the AI's **executive control system** — the single
authority for high-level decision-making. Where Milestones 1.2 (Cognitive) and
1.3 (World) added internal state and perception, Milestone 1.4 adds the
**decider** that coordinates every cognitive subsystem and turns their signals
into one high-level action:

```
reply | wait | listen | continue-thinking | look | remember | ignore
interrupt-self | cancel-task | switch-context | launch-automation
call-tool | ask-clarification | be-proactive
```

It is the "what should the AI do right now" layer, fully separate from how the
AI is expressed (CharacterFrame) and how it is drawn (renderer). Everything else
(Attention, Emotion, Behaviour, World, Memory, Relationship, Conversation,
Vision, Automation, Tool, Plugin) becomes a **subsystem** that feeds into it.

Milestone 1.4 builds directly on the verified M1.0–M1.3 architecture. The
existing runtimes, the renderer, the embodiment framework, `CharacterFrame`,
`AnimationRuntime`, and the renderer pipeline are untouched.

## Dependencies

- `../types` (`clampUnit`) — pure runtime helpers, no drawing-layer/body-layer import.
- The existing 30Hz scheduler owned by `PresenceRuntime.tick()`.
- The existing DI container (`TOKENS.executiveRuntime`).
- The existing `Set`-based pub/sub pattern (same as World/Cognitive runtimes).

It does **not** depend on: the drawing layer, the body layer, concrete avatars,
the character projection, the animation engine, frame snapshots, the orb drawing
code, the desktop shell, any GPU/3D engine, or any polling/timer/RAF primitive.

## Files

- `src/runtime/executive/types.ts` — `ExecutiveGoal`, `ExecutiveIntent`,
  `ExecutiveDecision`, `FocusTarget`, `Priority`, `Interrupt`,
  `InterruptState`, `ReasoningMode`, `ThinkingMode`.
- `src/runtime/executive/executive-state.ts` — `ExecutiveState` (the read model)
  plus `defaultExecutiveState` / `cloneExecutiveState`.
- `src/runtime/executive/goal-manager.ts` — `GoalManager`: goal lifecycle,
  ordering by weight, pinning (context switch), suspension/resume, completion.
- `src/runtime/executive/focus-manager.ts` — `FocusManager`: focus selection
  from conversation/goal/world/interrupt and eased strength transitions.
- `src/runtime/executive/interrupt-manager.ts` — `InterruptManager`: interrupt
  queuing by salience, preemption threshold, handling.
- `src/runtime/executive/priority-manager.ts` — `PriorityManager`: urgency
  scalar and discrete priority band resolution.
- `src/runtime/executive/intent-generator.ts` — `IntentGenerator`: the decision
  core that maps resolved context to a single `ExecutiveDecision` + `Intent`.
- `src/runtime/executive/executive-runtime.ts` — `ExecutiveRuntime`: owns the
  managers, ingests subsystem signals, runs the decision pipeline, and exposes
  `ExecutiveState` + `ExecutiveIntent`. Advanced on the 30Hz tick.
- `src/runtime/executive/index.ts` — barrel.

## Public API

```ts
class ExecutiveRuntime {
  // Subsystem ingestion (push-based, event-driven; the executive never pulls).
  ingestConversation(signal: { phase: string; activity?: number }): void
  ingestMemory(signal: { recall?: number; activity?: number }): void
  ingestWorld(signal: { salience?: number; foreground?: boolean }): void
  ingestAttention(signal: { target?: FocusTarget; confidence?: number; notificationSalience?: number }): void
  ingestRelationship(signal: { familiarity?: number; interactionFrequency?: number }): void
  ingestCognitive(signal: { reasoning?; thinking?; needsClarification?; hasPendingTask?; goalFocus? }): void

  // Goal management — the executive owns goals.
  addGoal(input: { label: string; weight?: number; id?: string }): ExecutiveGoal
  switchGoal(id: string): ExecutiveGoal | null
  suspendCurrentGoal(): void
  resumeGoal(id: string): void
  completeGoal(id: string): void

  // Interrupt handling.
  raiseInterrupt(input: { reason: string; severity?; salience?; source? }): { id: string }
  handleTopInterrupt(): void

  // Time evolution on the reused 30Hz tick. No new timer/loop.
  update(dt: number): ExecutiveSnapshot

  // Read-only consumption.
  getState(): ExecutiveState
  getIntent(): ExecutiveIntent
  getSnapshot(): ExecutiveSnapshot
  subscribe(listener: (s: ExecutiveSnapshot) => void): () => void
}
```

### ExecutiveState (the only read model)

```ts
interface ExecutiveState {
  currentGoal: ExecutiveGoal | null
  goalStack: ExecutiveGoal[]
  focus: FocusTarget
  focusStrength: number            // 0 (diffuse) .. 1 (locked in)
  currentIntent: ExecutiveDecision
  priority: Priority               // 'critical' | 'high' | 'normal' | 'low' | 'background'
  interruptState: InterruptState   // 'clear' | 'pending' | 'handling' | 'preempted'
  pendingInterrupts: Array<{ id; reason; severity; salience }>
  reasoningMode: ReasoningMode
  confidence: number               // 0 .. 1
  urgency: number                  // 0 .. 1
  thinkingMode: ThinkingMode
  revision: number
  updatedAt: number
}
```

### ExecutiveIntent (the ONLY signal the body layer consumes)

```ts
interface ExecutiveIntent {
  decision: ExecutiveDecision      // what to do now
  focus: FocusTarget
  focusStrength: number
  confidence: number
  urgency: number
  proactivity: number
  shouldInterrupt: boolean
  note: string
  revision: number
  updatedAt: number
}
```

`CharacterRuntime` receives **only** the `ExecutiveIntent`. It never receives
goals, planning, confidence internals, reasoning, memory, or relationship state.

## Architectural Invariants

1. **Single authority.** No other runtime decides `reply | wait | listen |
   continue-thinking | look | remember | ignore | interrupt-self | cancel-task |
   switch-context | launch-automation | call-tool | ask-clarification |
   be-proactive`. Only the Executive Runtime does.
2. **Event-driven ingestion.** Subsystems push via `ingest*`; the executive
   never pulls or polls them.
3. **Reused 30Hz scheduler.** `ExecutiveRuntime.update(dt)` is called inside
   `PresenceRuntime.tick()` — the same `setInterval(() => this.tick(), 1000/30)`
   that already drives Animation/Character/Cognitive/World. No `setInterval`,
   `setTimeout`, or `requestAnimationFrame` is introduced by the Executive
   Runtime.
4. **Full drawing-layer independence.** Zero imports of the drawing layer, the
   body layer, concrete avatars, the character projection, the animation engine,
   frame snapshots, the orb drawing code, the desktop shell, or any GPU/3D
   engine. The Executive Runtime produces no `FrameState` and no
   `CharacterFrame`.
5. **Dependency injection only.** Registered as a singleton token
   `executiveRuntime`. `PresenceRuntime` consumes it *optionally* via DI and
   advances it on the existing tick; no singleton globals.
6. **Private internals.** Goals, planning, confidence, reasoning, memory, and
   relationship internals remain private to the executive; only `ExecutiveState`
   and `ExecutiveIntent` escape.

## Decision Pipeline

```
Subsystems ──ingest*──► ExecutiveRuntime
                                │
                                ├─ GoalManager      (goal management)
                                ├─ FocusManager      (focus selection + easing)
                                ├─ InterruptManager  (interrupt handling)
                                ├─ PriorityManager   (urgency + priority band)
                                └─ IntentGenerator   (decision core)
                                │
                                ▼
                        ExecutiveState + ExecutiveIntent
                                │
                                ▼
                  CharacterRuntime receives only the Intent
```

`update(dt)` eases focus strength and re-resolves the decision so the AI's
behaviour evolves smoothly with time, framerate-independent and timer-free.

## Scheduler Reuse Detail

`PresenceRuntime.tick()` (the existing 30Hz loop) now also advances the
executive:

```ts
if (this.executiveRuntime) {
  this.executiveRuntime.update(dt)   // ease focus, re-resolve decision
}
```

The executive is also fed from the **same** aggregated runtime snapshot that
already drives `CharacterRuntime` and `CognitiveBundle` (single subscription, no
polling). It observes conversation, memory, world, attention, relationship, and
cognitive signals.

## Performance

Benchmarks (`tests/runtime/executive/benchmarks.test.ts`) assert:

- 10,000 `update()` calls in < 100ms.
- `update()` avg < 1ms/frame at 30Hz over one simulated second.
- 10,000 interrupt raise+handle cycles in < 100ms.
- No `setInterval`/`setTimeout`/`requestAnimationFrame`/`while` in the executive module.

Unit tests (`tests/runtime/executive/*.test.ts`) verify goal switching,
interrupt handling, focus transitions, priority calculation, intent generation,
context switching, DI, the 30Hz tick, and renderer/embodiment independence.
