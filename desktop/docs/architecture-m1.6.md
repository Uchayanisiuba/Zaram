# Final Architecture — Milestone 1.6

## Runtime Stack

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Zaram Kernel                                    │
│                   (Orchestrator / Bootstrapper)                         │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ DI (I[Runtime])
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Conversation Runtime                               │
│                   (Speech-to-Intent / NLP)                              │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ events
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       Attention Runtime                                 │
│                   (Focus / Salience / Priority)                         │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ events
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Executive Runtime                                   │
│                   (Decision Engine / Goals / Interrupts)                │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ ICapabilityRuntime (interface only)                              │  │
│  │ • Requests capability metadata                                  │  │
│  │ • NEVER calls capabilities directly                             │  │
│  │ • NEVER executes anything                                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ execute(request)
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Execution Runtime                                   │
│                   (Lifecycle / Timeout / Retry / Cancel)                │
│                                                                         │
│  Responsibilities:                                                      │
│  • ExecutionRequest / ExecutionResult / ExecutionContext                │
│  • Lifecycle state machine (deterministic)                              │
│  • Timeout, retries, cancellation, progress                             │
│  • Audit trail, execution history                                       │
│  • Rollback hooks                                                       │
│  • Permission enforcement                                               │
│  • Execution ids                                                       │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ IExecutionInvoker (handler registry)                             │  │
│  │ • Resolves handlers by capability id                             │  │
│  │ • Resolves optional rollback hooks                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ invoke
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Capabilities                                     │
│                   (Filesystem, Browser, Calculator, ...)                │
│                                                                         │
│  Each capability implements ExecutionHandler:                           │
│    (request, context, controls) => void | Promise<void>                 │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   │ results
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          Results                                        │
│                   (Output / Error / Progress / History)                 │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Executive Runtime
    │
    │ 1. Discovers capability via ICapabilityRuntime
    ▼
Capability Runtime
    │
    │ 2. Receives descriptor (permissions, metadata)
    ▼
Executive Runtime
    │
    │ 3. Calls executionRuntime.execute(request)
    ▼
Execution Runtime
    │
    │ 4. Queues execution
    │ 5. Validates permissions
    │ 6. Invokes handler via IExecutionInvoker
    ▼
Handler (Capability)
    │
    │ 7. Reports progress / succeeds / fails
    ▼
Execution Runtime
    │
    │ 8. Records history, audit, state transition
    ▼
Result (ExecutionResult)
```

## Key Constraints

| Constraint | Enforced By |
|------------|-------------|
| Execution Runtime is the ONLY runtime that invokes capabilities | Architecture + tests |
| Capability Runtime NEVER executes | Metadata-only interface |
| Executive Runtime NEVER executes | No execute() method |
| No timers / polling / RAF | Structural tests |
| No renderer/embodiment imports | Structural tests |
| Reuse existing 30Hz tick | PresenceRuntime.tick() |
| DI-only integration | Container registration |
| Deterministic state machine | execution-state-machine.ts |

## Modified Files

- `src/runtime/execution/execution-runtime.ts` — Core implementation
- `src/runtime/execution/types.ts` — Added `input`, `options`, `elapsedMs`, `retryDelayRemainingMs` to ExecutionResult
- `src/runtime/execution/index.ts` — Updated exports
- `src/runtime/di/container.ts` — Added `executionRuntime` token
- `src/runtime/bootstrap.ts` — Registered ExecutionRuntime singleton
- `src/runtime/presence/presence-runtime.ts` — Wired ExecutionRuntime into 30Hz tick

## New Files

- `src/runtime/execution/execution-runtime.ts` — Core implementation
- `tests/runtime/execution/execution-runtime.test.ts` — Full test suite (57 tests)
- `docs/execution-runtime.md` — Documentation
- `.ai/adr/ADR-015_Execution_Runtime.md` — Architecture Decision Record
