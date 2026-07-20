# Runtime_Embodiment v1.0  (updated for Milestone 1.1)

Status

Accepted — Milestone 1.1 Embodiment Framework implemented.

Dependencies

- Runtime Core v1.0 (Container / TOKENS)
- Animation Runtime (unchanged; remains the FrameState producer)
- Presence Runtime (consumes CharacterState, projects CharacterFrame)
- Source Runtimes: Conversation, Voice, Memory, System, Knowledge (event feeds)

Public API

Embodiment abstraction layer (renderer-independent):

- `IEmbodiment` — lifecycle contract every embodiment satisfies
  (initialize/start/pause/resume/shutdown/setFrameState/getStatus).
- `EmbodimentRegistry` — declares & resolves descriptors; never instantiates.
- `EmbodimentDescriptor` — static declaration { type, label, description,
  enabled, create: EmbodimentFactory }.
- `EmbodimentFactory` — `(ctx: EmbodimentContext) => IEmbodiment`.
- `EmbodimentContext` — the only injectables an embodiment may use
  (transport, metaHuman, headGenerator).
- `EmbodimentManager` — selects/switches embodiments via the registry; the
  single `IEmbodiment` the PresenceRuntime talks to.
- `NullEmbodiment` — inert default (headless/tests).
- `CharacterRuntime` — converts AI state -> CharacterState (owns Emotion,
  Behaviour, Gaze, Breathing, Micro Movement).
- `EmotionRuntime` — continuous emotional model with smoothing.
- `BehaviourRuntime` — behaviour state machine (no renderer logic).
- `GazeController` — eye/head/blink targets (no renderer logic).
- `toCharacterFrame()` — the ONLY projection the Renderer receives.

Future-only interfaces (no implementation, no Unreal/ARKit/GNM imports):

- `IMetaHumanAdapter`, `IFaceRig`, `IFacialExpressionProvider`, `IARKitDriver`
- `IHeadGenerator`, `HeadDescriptor`, `FaceTopology`, `MorphTargetSet`

Lifecycle

1. `bootstrapPresence()` registers the built-in registry and a singleton
   `CharacterRuntime` in the DI container.
2. `EmbodimentManager` resolves its initial embodiment (living-orb) through
   the registry using injected context — never `new`-ing directly.
3. `PresenceRuntime` subscribes to the aggregated runtime snapshot and feeds
   `CharacterRuntime` (event-driven; no polling).
4. On its existing 30Hz frame tick, `PresenceRuntime` advances
   `AnimationRuntime` (FrameState) AND `CharacterRuntime` (CharacterState)
   — no second render loop is introduced.
5. `PresenceRuntime.getCharacterFrame()` projects CharacterState into the
   renderer-neutral `CharacterFrame`.

Notes

- AnimationRuntime, LivingOrbAdapter, RenderTransport, and OrbRenderer are
  UNTOUCHED. The Milestone 1.0 pipeline is preserved.
- The Renderer receives only `CharacterFrame`. It has zero visibility into
  emotion semantics, thinking, conversation, voice, memory, or knowledge.
- All embodiments are dependency-injected via the registry. No runtime news
  up an embodiment.
