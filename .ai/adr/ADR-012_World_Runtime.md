# ADR-012: World Runtime (System Perception Intelligence Runtime)
**Status:** Accepted
**Milestone:** 1.3
**Context:** The AI needs a coherent, read-only model of the environment it lives in (desktop, applications, OS, notifications) that is separate from how it is expressed (CharacterFrame) and how it is drawn (renderer). Milestone 1.2 verified the Cognitive Runtime separation; Milestone 1.3 adds the "World" layer without touching the verified architecture.
**Decision:** Introduce `WorldRuntime` as a new Intelligence Runtime under `src/runtime/world/`. It aggregates system perception into an immutable `WorldState`, publishes typed world events, and is consumed by the Attention Runtime through the `IWorldState`/`IWorldStateProvider` interfaces only. It reuses the existing 30Hz scheduler (`PresenceRuntime.tick()`) for time evolution — no new timers, polling loops, or `requestAnimationFrame`. It is wired via the existing DI container as a singleton and never imports renderer, embodiment, or `CharacterFrame` code.
**Consequences:**
- The Attention Runtime depends on an interface, not the concrete runtime; direction of coupling is correct (world → attention adapter depends only on `IWorldState`).
- 100% drawing-layer independence is preserved; the World Runtime emits no `FrameState`.
- `CharacterFrame` and all Milestone 1.0–1.2 runtimes remain byte-for-byte unchanged except for the additive DI registration and the single `update(dt)` call in the reused tick.
**Compliance:**
- No `setInterval`/`setTimeout`/`requestAnimationFrame`/`while` in `src/runtime/world/*`.
- Immutable snapshots via `deepFreeze`; verified by unit tests.
- DI verified by `tests/runtime/world/world-runtime.test.ts` and `bootstrapPresence()`.
