# Runtime_Capability v1.0

Status: Accepted (Milestone 1.5)

## Purpose

The Capability Runtime is the Operating System's **capability discovery and
execution interface**. It answers

> "What can Zaram do?"

instead of

> "How should Zaram think?"

It is the single source of truth for every capability available to the OS:
filesystem, browser, calculator, clipboard, email, vision, speech, camera, OCR,
code execution, search, plugins, automation, and future agent capabilities.

The Executive Runtime must NEVER call tools directly. Instead the flow is:

```
Executive Runtime
      ↓  (requests capabilities, never tools)
Capability Runtime        ← this runtime (metadata only)
      ↓  (descriptors flow to)
Execution Engine          ← separate layer, not built in M1.5
      ↓
Capability                ← concrete implementation
```

Milestone 1.5 builds directly on the verified M1.0–M1.4 architecture. The
existing runtimes, the renderer, the embodiment framework, `CharacterFrame`,
`AnimationRuntime`, and the renderer pipeline are untouched.

## Architecture Rules

The Capability Runtime must NOT know about:

- Renderer
- Embodiments
- `CharacterRuntime`
- `EmotionRuntime`
- `BehaviourRuntime`
- `PresenceRuntime`
- `CharacterFrame`
- Unreal / Living Orb / MetaHuman / Robot

The runtime exposes **only capability metadata** — no behaviour, no execution,
no side effects.

## Dependencies

- `./types` — `CapabilityDescriptor`, `CapabilityRegistration`, `CapabilityFilter`, `CapabilityCategory`, etc.
- `./capability-descriptor` — `createDescriptor` / `reviseDescriptor` / `cloneDescriptor` (immutable, validated).
- `./capability-registry` — `CapabilityRegistry` (O(1) by id, indexed by category).
- `./capability-filter` — pure predicate filtering.
- `./capability-resolver` — `CapabilityResolver` (best-candidate selection).
- The existing DI container (`TOKENS.capabilityRuntime`).

It does **not** depend on: the drawing layer, the body layer, concrete avatars,
the character projection, the animation engine, frame snapshots, the orb drawing
code, the desktop shell, any GPU/3D engine, or the Emotion/Behaviour/Presence/
Character/Embodiment runtimes.

## Files

- `src/runtime/capability/types.ts` — all capability types: `CapabilityDescriptor`,
  `CapabilityRegistration`, `CapabilityCategory` (12 categories), `CapabilityPermission`,
  `CapabilityAvailability`, `CapabilityExecutionLocation`, `CapabilitySchema`,
  `CapabilityFilter`, `CapabilityResolution`, `CapabilitySnapshot`.
- `src/runtime/capability/capability-descriptor.ts` — `createDescriptor` (validation
  + defaults + cost clamp), `reviseDescriptor` (immutable revision bump), `cloneDescriptor`.
- `src/runtime/capability/capability-registry.ts` — `CapabilityRegistry`: O(1) lookup
  by `id` (`Map`), indexed lookup by `category` (`Map<category, Set<id>>`),
  duplicate detection, `update`/`unregister`, revision bookkeeping.
- `src/runtime/capability/capability-filter.ts` — pure `matchesFilter` / `applyFilter`
  and convenience builders (`filterByCategory`, `filterEnabledOnly`,
  `filterLocalOnly`, `filterCloudOnly`).
- `src/runtime/capability/capability-resolver.ts` — `CapabilityResolver` +
  `CapabilityQuery`: resolves the best candidate by explicit id or by need,
  with a deterministic score (enabled > available > local > low cost > low latency).
- `src/runtime/capability/capability-runtime.ts` — `CapabilityRuntime` implementing
  `ICapabilityRuntime`. The public, DI-injectable surface. Exposes ONLY metadata.
- `src/runtime/capability/index.ts` — barrel.

## Capability Descriptor

Every capability includes:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable unique id, e.g. `filesystem.read` |
| `name` | string | Human-readable name |
| `description` | string | What the capability does |
| `category` | `CapabilityCategory` | One of 12 categories |
| `permissions` | `CapabilityPermission[]` | Declared required permissions |
| `inputSchema` | `CapabilitySchema` | Expected input (metadata) |
| `outputSchema` | `CapabilitySchema` | Produced output (metadata) |
| `availability` | `CapabilityAvailability` | `available` \| `unavailable` \| `disabled` \| `requires-setup` \| `degraded` |
| `latencyEstimateMs` | number | Planning metadata |
| `location` | `local` \| `cloud` | Execution environment |
| `cost` | number (0..1) | Relative cost for planning |
| `enabled` | boolean | User/OS toggle |
| `revision` | number | Bumped on every change |
| `updatedAt` | number | Epoch ms of last update |

## Capability Categories

`system`, `workspace`, `filesystem`, `communication`, `ai`, `automation`,
`developer`, `media`, `vision`, `speech`, `plugins`, `security`.

## Public API (ICapabilityRuntime)

```ts
interface ICapabilityRuntime {
  register(reg: CapabilityRegistration): CapabilityDescriptor
  registerOrReplace(reg: CapabilityRegistration): CapabilityDescriptor
  unregister(id: string): boolean
  update(id: string, patch: Partial<Omit<CapabilityRegistration, 'id'>>): CapabilityDescriptor | null
  has(id: string): boolean
  get(id: string): CapabilityDescriptor | null          // O(1)
  getByCategory(category): CapabilityDescriptor[]        // O(1) indexed
  all(): CapabilityDescriptor[]
  filter(filter: CapabilityFilter): CapabilityDescriptor[]
  resolve(query: CapabilityQuery): CapabilityResolution
  getSnapshot(): CapabilitySnapshot
  getRevision(): number
}
```

## Filtering

Supported via `CapabilityFilter`:

- `categories` — OR match on category list
- `permissions` — AND match (all required permissions declared)
- `availability` — exact availability
- `localOnly` — `location === 'local'`
- `cloudOnly` — `location === 'cloud'`
- `enabledOnly` — `enabled === true`

## Architectural Invariants

1. **Metadata only.** The runtime stores and serves capability *descriptors*. It
   does not execute, invoke, or hold behaviour. No `execute`/`invoke` surface exists.
2. **O(1) lookup by id.** `get(id)` is a `Map` read. `getByCategory(cat)` is an
   index read (`Map<category, Set<id>>`); registration maintains the index.
3. **Duplicate detection.** Re-registering an existing id throws
   (`already registered`). `registerOrReplace` is the idempotent alternative.
4. **Interface-only consumption.** The Executive Runtime depends on
   `ICapabilityRuntime`, never the concrete `CapabilityRuntime`, and requests
   capabilities — it never calls tools directly.
5. **No timers / polling / RAF.** No `setInterval`, `setTimeout`,
   `requestAnimationFrame`, or `while` loop in the module. Discovery is push/
   register based.
6. **Full drawing-layer & body-layer independence.** Zero imports of the drawing
   layer, body layer, concrete avatars, character projection, animation engine,
   frame snapshots, orb drawing code, desktop shell, GPU/3D engines, or the
   Emotion/Behaviour/Presence/Character/Embodiment runtimes.
7. **Dependency injection.** Registered as a singleton token `capabilityRuntime`
   and resolved (never `new`ed inline) by the bootstrap; the Executive Runtime
   receives it via DI.

## Performance

Benchmarks (`tests/runtime/capability/capability-bench.test.ts`) assert:

- 10,000 registrations complete in < 250ms.
- O(1) lookup avg < 0.01ms across 20,000 lookups over 5,000 capabilities.
- Resolution avg < 1ms over a 5,000-capability registry.
- Filtering avg < 2ms over 200 passes on 5,000 capabilities.
- No `setInterval`/`setTimeout`/`requestAnimationFrame`/`while` in the module.

Unit tests (`tests/runtime/capability/*.test.ts`, 66 tests) verify registration,
O(1) + indexed lookup, filtering (category / permissions / availability /
location / enabled), duplicate detection, resolution precedence, dependency
injection, the Executive Runtime integration through the interface, and
renderer/embodiment independence (asserted structurally).
