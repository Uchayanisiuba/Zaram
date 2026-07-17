# Execution Runtime (Milestone 1.6)

## Overview

The Execution Runtime is the ONLY runtime allowed to invoke capabilities. The Capability Runtime exposes metadata only; the Executive Runtime decides but never executes. This runtime is fully display-independent and advanced on the existing 30Hz tick.

## Architecture

```
Executive
   │
   ▼
Capability Runtime (metadata only)
   │
   ▼
Execution Runtime ← THIS
   │
   ▼
Capabilities
   │
   ▼
Results
```

## Lifecycle

| Status | Description |
|--------|-------------|
| `queued` | Execution request accepted, waiting for tick |
| `preparing` | Validating permissions and capability availability |
| `running` | Handler is executing |
| `waiting` | Handler is awaiting input |
| `retrying` | Waiting for retry delay to elapse |
| `completed` | Handler succeeded |
| `cancelled` | Caller requested cancellation |
| `failed` | Handler failed, timed out, or permission denied |
| `rolledback` | Rollback hook completed after failure/cancel |

## State Machine

Legal transitions are defined in `execution-state-machine.ts`:

- `queued` → `preparing`, `cancelled`, `failed`
- `preparing` → `running`, `waiting`, `cancelled`, `failed`
- `running` → `waiting`, `completed`, `cancelled`, `failed`, `retrying`
- `waiting` → `running`, `completed`, `cancelled`, `failed`, `retrying`
- `retrying` → `preparing`, `cancelled`, `failed`
- `completed` → (terminal)
- `cancelled` → `rolledback`
- `failed` → `rolledback`, `retrying`
- `rolledback` → (terminal)

## API

### `execute(request: ExecutionRequest): string`

Queues an execution request and returns a stable execution id.

### `cancel(id: string): boolean`

Requests cancellation. Returns false if the execution cannot be cancelled (terminal, already cancelled, or `cancellable: false`).

### `retry(id: string): boolean`

Retries a failed execution. Returns false if the execution is not failed or max retries exceeded.

### `rollback(id: string): boolean`

Manually triggers the rollback hook. Returns false if no rollback hook is registered.

### `getExecution(id: string): ExecutionResult | null`

Returns a deep copy of the execution result.

### `getHistory(): ExecutionResult[]`

Returns deep copies of all execution results.

### `update(dt: number): void`

Advances the lifecycle on the 30Hz tick. Called by `PresenceRuntime.tick()`.

## ExecutionRequest

```typescript
interface ExecutionRequest {
  capabilityId: string
  input: unknown
  context: ExecutionContext
  id?: string
  options?: ExecutionOptions
}
```

## ExecutionOptions

```typescript
interface ExecutionOptions {
  timeoutMs?: number
  maxRetries?: number
  retryDelayMs?: number
  cancellable?: boolean
  rollbackSupported?: boolean
  waitable?: boolean
  tag?: string
}
```

## ExecutionControls (handed to handlers)

```typescript
interface ExecutionControls {
  reportProgress(progress: number): void
  succeed(output: unknown): void
  fail(error: Error | string | ExecutionError): void
  isCancelled(): boolean
  elapsedMs(): number
}
```

## Events

The runtime publishes events via its internal `Set`-based pub/sub (same pattern as World, Cognitive, and Executive runtimes):

- `execution.queued`
- `execution.preparing`
- `execution.running`
- `execution.waiting`
- `execution.retrying`
- `execution.progress`
- `execution.completed`
- `execution.cancelled`
- `execution.failed`
- `execution.rolledback`
- `execution.audit`

## Permission Enforcement

When a `capabilityRuntime` is injected, the runtime validates that the execution context includes all permissions declared by the capability descriptor before invoking the handler. Missing permissions cause an immediate transition to `failed` with `kind: 'permission'`.

## Rollback Hooks

Handlers can register optional rollback hooks via `ExecutionInvoker.registerWithRollback()`. When `options.rollbackSupported` is true and the execution fails or is cancelled, the runtime invokes the rollback hook automatically. Rollback hooks can also be triggered manually via `rollback()`.

## DI Integration

The runtime is registered as a singleton in the DI container:

```typescript
container.register(
  TOKENS.executionRuntime,
  (c) => new ExecutionRuntime({
    invoker: new ExecutionInvoker(),
    capabilityRuntime: c.resolve<ICapabilityRuntime>(TOKENS.capabilityRuntime)
  }),
  { singleton: true }
)
```

## 30Hz Tick Integration

`PresenceRuntime` advances the Execution Runtime on its existing frame tick:

```typescript
if (this.executionRuntime) {
  this.executionRuntime.update(dt)
}
```

No new timers, polling loops, or `requestAnimationFrame` are introduced.

## Renderer Independence

The Execution Runtime must NOT import:

- Embodiment
- Renderer
- CharacterFrame
- Emotion
- Behaviour
- Presence
- LivingOrb
- MetaHuman
- Engine

This is enforced structurally by tests in `execution-runtime.test.ts`.

## File Structure

```
desktop/src/runtime/execution/
├── index.ts              # Barrel exports
├── types.ts              # All type contracts
├── execution-runtime.ts  # Core runtime implementation
├── execution-state-machine.ts  # Deterministic lifecycle transitions
├── execution-invoker.ts  # Handler registry
└── execution-context.ts  # Context/request factories
```

## Tests

`tests/runtime/execution/execution-runtime.test.ts` covers:

- Lifecycle transitions
- Retry logic
- Timeout enforcement
- Cancellation (queued and running)
- Rollback hooks
- Permission enforcement
- Performance (1k and 10k executions)
- Stress (5k concurrent)
- DI registration
- No timers/polling
- No forbidden imports
