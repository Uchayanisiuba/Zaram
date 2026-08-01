# Zaram Runtime Dependency Map

```
FRONTEND (React + Vite)
│
├── main.jsx ─────────────────────────────────────────────────────┐
│   ├── QueryClientProvider (@tanstack/react-query)               │
│   ├── ErrorBoundary (components/common/ErrorBoundary.tsx)       │
│   ├── PresenceProvider (context/PresenceContext.tsx) ──────────┼──► DESKTOP BRIDGE (IPC)
│   │   ├── FrameComposer (core/frame/composer.ts)               │       │
│   │   ├── SimulationRuntime (core/simulation/runtime.ts)       │       ├── desktop.presence.onFrame → FrameState @ 60fps
│   │   ├── desktop.presence.onFrame (IPC) ──────────────────────┼───┤
│   │   ├── desktop.presence.onState (IPC) ──────────────────────┼───┤   └── desktop.presence.onState → PresenceState
│   │   ├── desktop.presence.onHealth (IPC) ─────────────────────┼───┤       └── desktop.presence.onHealth → ConnectionStatus
│   │   └── applyPresenceTheme (theme/presenceTheme.ts) ─────────┤       │
│   │       └── document.documentElement.style.setProperty()     │       │
│   └── ThemeProvider (theme/ThemeProvider.tsx) ◄────────────────┘       │
│       └── usePresenceRuntime() ──────────────────────────────────┘
│
├── App.jsx (LEGACY — REMOVED IN REBUILD)
│   ├── SimulationRuntime (local fallback)
│   ├── FrameComposer (local fallback)
│   ├── R3FRendererAdapter (engine/adapters/R3FRendererAdapter.tsx)
│   └── Canvas rendering loop (requestAnimationFrame)
│
├── PROVIDERS / CONTEXTS (PRESERVED)
│   ├── PresenceContext.tsx ─────────────────────────────────────►
│   │   ├── PresenceProvider: Creates PresenceRuntimeContext + FrameStateRuntimeContext
│   │   ├── usePresenceRuntime(): { frameState, presenceState, setPresenceState, isConnected }
│   │   ├── useFrameState(): FrameState (high-frequency, separate context)
│   │   └── usePresenceState(): PresenceState
│   │
│   ├── ThemeProvider.tsx ───────────────────────────────────────►
│   │   ├── usePresenceTheme(): { currentState, setState }
│   │   └── Applies PRESENCE_CSS_VARS to document.documentElement
│   │
│   └── ZaramContext (store/useZaramStore.ts) — DEPRECATED
│       └── useZaram(): { currentState, environmentMode, setCurrentState, setEnvironmentMode }
│
├── HOOKS (PRESERVED)
│   ├── useZaram.js → ZaramContext (deprecated)
│   ├── useNotifications.tsx → Notification system
│   └── useAccessibility.ts → a11y helpers
│
├── CORE RUNTIME (PRESERVED — ENGINE)
│   ├── core/frame/
│   │   ├── types.ts — FrameState, VisualFrame, AudioFrame, EmotionFrame, SystemFrame, MetadataFrame
│   │   ├── composer.ts — FrameComposer (single FrameState producer)
│   │   └── IDLE_FRAME — Default frame state
│   │
│   ├── core/simulation/
│   │   ├── types.ts — SimulationNode, SimulationState, Vector3
│   │   └── runtime.ts — SimulationRuntime (physics simulation)
│   │
│   ├── core/visual/
│   │   ├── types.ts — VisualNode
│   │   └── mapper.ts — mapToVisualState (semantic → visual)
│   │
│   └── engine/ (FULL ENGINE — PRESERVED)
│       ├── animation/AnimationRuntime.ts — Central animation system
│       ├── assets/AssetRegistry.tsx — Asset loading & caching
│       ├── materials/MaterialRegistry.ts — Material management
│       ├── particles/ParticleRuntime.ts — Particle systems
│       ├── lod/LODManager.ts — Level of detail
│       ├── lod/LODComponent.tsx — LOD React component
│       ├── shaders/ShaderRegistry.ts — Shader management
│       ├── embodiment/EmbodimentRegistry.tsx — Embodiment registration
│       ├── factory/EmbodimentFactory.ts — Embodiment instantiation
│       ├── adapters/R3FRendererAdapter.tsx — React Three Fiber bridge
│       ├── adapters/R3FFactory.ts — R3F component factory
│       ├── camera/SpatialCameraController.tsx — Camera control
│       ├── camera/CinematicCameraController.tsx — Cinematic camera
│       ├── components/ — NodeMesh, LivingOrbCenter, KnowledgeNodeMesh, EdgeLine, CameraRig
│       ├── culling/CullingSystem.ts — Frustum culling
│       ├── interaction/UniverseInteraction.tsx — Interaction handling
│       ├── performance/PerformanceOverlay.tsx — Perf monitoring
│       └── bootstrap.ts — Engine initialization
│
├── DESKTOP BRIDGE (PRESERVED — IPC LAYER)
│   └── desktop/desktop-bridge.ts
│       ├── desktop.app.* — App info, version, platform
│       ├── desktop.backend.* — Backend health, status
│       ├── desktop.presence.* — onFrame, onViewport, onEvent, getHealth, getStatus, getDiagnostics
│       ├── desktop.executive.* — Snapshot, plan, confidence, evidence, metrics, setPendingSpeech, onSnapshot
│       ├── desktop.capability.* — getSnapshot, getById, getByCategory
│       ├── desktop.execution.* — History, getExecution, execute, cancel, retry, onEvent
│       ├── desktop.world.* — getState
│       ├── desktop.cognitive.* — getState, getAttention, getRelationship
│       ├── desktop.character.* — getFrame
│       ├── desktop.workspace.* — State, context, snapshot, projects, discover, onEvent
│       ├── desktop.dialog.* — File dialogs, messages
│       ├── desktop.notify.* — Notifications
│       ├── desktop.shell.* — Open external, paths
│       ├── desktop.clipboard.* — Read/write text
│       ├── desktop.system.* — Platform info
│       ├── desktop.settings.* — Get/set settings
│       ├── desktop.filesystem.* — Metrics
│       ├── desktop.vscode.* — Snapshot, editor, workspace, diagnostics, git, onEvent
│       └── desktop.runtime.* — desktopGetSources, onPresenceEvent
│
├── STORES (PARTIALLY PRESERVED)
│   ├── store/useZaramStore.ts — PRESERVED (legacy, deprecated)
│   ├── stores/uiStore.ts — REMOVED (workspace UI state)
│   ├── stores/workspaceStore.ts — REMOVED
│   ├── stores/workspaceContextStore.ts — REMOVED
│   ├── stores/chatStore.ts — REMOVED
│   ├── stores/artifactStore.ts — REMOVED
│   ├── stores/themeStore.ts — REMOVED (use ThemeProvider)
│   ├── stores/hudStore.ts — REMOVED
│   ├── stores/dockStore.ts — REMOVED
│   ├── stores/spatialWindowStore.ts — REMOVED
│   ├── stores/glassStore.ts — REMOVED
│   ├── stores/searchStore.ts — REMOVED
│   ├── stores/modelStore.ts — REMOVED
│   └── stores/api.ts — REMOVED
│
└── TYPES (PRESERVED)
    ├── types/index.ts — Core type exports
    ├── types/workspace.ts — REMOVED
    ├── types/spatial-ux.d.ts — REMOVED
    ├── types/jsx.d.ts — PRESERVED (JSX intrinsics)
    └── types/artifacts.ts — REMOVED

DESKTOP (Electron Main Process)
│
├── start-electron.js — Entry point
│
├── src/runtime/ (PRESERVED — ALL RUNTIMES)
│   ├── bootstrap.ts — DI container, registers ALL runtimes
│   ├── kernel/zaram-kernel.ts — ZaramKernel (boots PresenceRuntime)
│   ├── interfaces.ts — All runtime interfaces (IPresenceRuntime, IEmbodiment, etc.)
│   ├── event-bus.ts — Global EventBus (ZaramEventType)
│   ├── di/container.ts — Dependency injection container
│   │
│   ├── presence/
│   │   ├── presence-runtime.ts — PresenceRuntime (30Hz tick, orchestrates all runtimes)
│   │   ├── living-orb-adapter.ts — Legacy orb adapter
│   │   ├── diagnostics.ts — PresenceDiagnostics
│   │   └── index.ts
│   │
│   ├── embodiment/
│   │   ├── character-runtime.ts — CharacterRuntime (emotion, intent)
│   │   ├── character-frame.ts — CharacterFrame (renderer-neutral)
│   │   ├── emotion-runtime.ts — EmotionRuntime
│   │   ├── behaviour-runtime.ts — BehaviourRuntime
│   │   ├── gaze-controller.ts — GazeController
│   │   ├── registry.ts — EmbodimentRegistry
│   │   ├── manager.ts — EmbodimentManager
│   │   ├── descriptors.ts — Embodiment descriptors
│   │   ├── null-embodiment.ts — NullEmbodiment
│   │   ├── metahuman.ts — MetaHuman embodiment
│   │   ├── gnm.ts — GNM embodiment
│   │   └── index.ts
│   │
│   ├── cognitive/
│   │   ├── bundle.ts — CognitiveBundle (attention, relationship, reasoning)
│   │   ├── attention-runtime.ts — AttentionRuntime
│   │   ├── conversation-projection.ts — Conversation projection
│   │   ├── memory-projection.ts — Memory projection
│   │   ├── relationship-runtime.ts — RelationshipRuntime
│   │   └── index.ts
│   │
│   ├── world/
│   │   ├── world-runtime.ts — WorldRuntime (WorldState)
│   │   ├── world-attention-adapter.ts — Attention adapter
│   │   └── index.ts
│   │
│   ├── executive/
│   │   ├── executive-runtime.ts — ExecutiveRuntime (decision engine)
│   │   ├── focus-manager.ts — FocusManager
│   │   ├── priority-manager.ts — PriorityManager
│   │   ├── interrupt-manager.ts — InterruptManager
│   │   ├── goal-manager.ts — GoalManager
│   │   ├── intent-generator.ts — IntentGenerator
│   │   ├── execution-plan.ts — ExecutionPlan
│   │   ├── executive-state.ts — ExecutiveState
│   │   └── index.ts
│   │
│   ├── capability/
│   │   ├── capability-runtime.ts — CapabilityRuntime (OS capabilities)
│   │   ├── capability-registry.ts — CapabilityRegistry
│   │   ├── capability-resolver.ts — CapabilityResolver
│   │   ├── capability-filter.ts — CapabilityFilter
│   │   └── index.ts
│   │
│   ├── execution/
│   │   ├── execution-runtime.ts — ExecutionRuntime (capability invocation)
│   │   ├── execution-invoker.ts — ExecutionInvoker
│   │   ├── execution-state-machine.ts — ExecutionStateMachine
│   │   ├── execution-context.ts — ExecutionContext
│   │   └── index.ts
│   │
│   ├── workspace/
│   │   ├── workspace-runtime.ts — WorkspaceRuntime (semantic projects)
│   │   ├── workspace-watcher.ts — File watching
│   │   ├── workspace-indexer.ts — Indexing
│   │   ├── workspace-pool.ts — Project pool
│   │   ├── workspace-detector.ts — Detection
│   │   ├── workspace-context.ts — Context
│   │   ├── workspace-cache.ts — Cache
│   │   └── index.ts
│   │
│   ├── voice/
│   │   └── voice-runtime.ts — VoiceRuntime (full speech synthesis)
│   │
│   ├── sources/ (Aggregated data sources for PresenceRuntime)
│   │   ├── aggregator.ts — RuntimeSourceAggregator
│   │   ├── conversation-runtime.ts — ConversationRuntime
│   │   ├── voice-runtime.ts — VoiceRuntime (source)
│   │   ├── memory-runtime.ts — MemoryRuntime
│   │   ├── system-runtime.ts — SystemRuntime
│   │   └── base.ts — Base runtime
│   │
│   ├── personality/
│   │   └── expressive-params.ts — ExpressiveParamsSource
│   │
│   └── electron/
│       ├── render-transport.ts — IRenderTransport (IPC → renderer)
│       └── embodiment-host.ts — EmbodimentHost (renderer process)
│
├── src/services/ (PRESERVED)
│   ├── window-service.ts — Window management
│   ├── shell-service.ts — Shell integration
│   ├── settings-service.ts — Settings persistence
│   ├── notification-service.ts — Notifications
│   ├── file-dialog-service.ts — File dialogs
│   ├── download-service.ts — Downloads
│   ├── desktop-service.ts — Desktop integration
│   └── backend-service.ts — Backend API client
│
├── src/capabilities/ (PRESERVED — Capability Packs)
│   ├── filesystem/ — FilesystemCapabilityPack
│   ├── vscode/ — VSCodeCapabilityPack
│   ├── vision/ — VisionCapabilityPack
│   ├── knowledge/ — KnowledgeCapabilityPack
│   └── speech/ — Speech capabilities
│
└── tests/ — All runtime tests (PRESERVED)

BACKEND (Python FastAPI)
│
├── main.py — FastAPI app, endpoints
│   ├── GET  /health — Kernel health, capabilities, knowledge providers, speech
│   ├── POST /chat — Streaming chat (ChatRouter → Kernel)
│   ├── POST /vision/analyze — Vision analysis
│   ├── POST /knowledge/search — Internet search
│   ├── GET  /audio/{filename} — Audio file serving
│   ├── POST /voice/synthesize — TTS single utterance
│   ├── POST /voice/stream — TTS streaming (SSE)
│   ├── GET  /voice/voices — Available voices
│   ├── GET  /voice/health — Speech runtime health
│   ├── GET  /personalities — All personas
│   └── GET  /personalities/{id} — Single persona
│
├── core/
│   ├── bootstrapper.py — KernelBootstrapper
│   ├── chat_router.py — ChatRouter (execution engine + legacy)
│   ├── streaming_events.py — StreamEvent (SSE format)
│   └── event_bus.py — Backend event bus
│
├── voice/
│   ├── voice_manager.py — VoiceManager
│   ├── registry.py — Voice registry
│   ├── config.py — Voice config
│   ├── health.py — Health checks
│   ├── events.py — Voice events
│   ├── exceptions.py — Exceptions
│   ├── audio_events.py — Audio events
│   └── providers/ — Kokoro, base provider
│
├── orchestrator/ — Executive orchestrator
│   ├── contracts.py, capabilities.py, policies.py, preferences.py, profiles.py, scoring.py, events.py
│
├── knowledge/
│   └── knowledge_service.py — Knowledge service, search
│
├── implementations/
│   └── ollama_llm.py — Ollama LLM wrapper
│
├── services/
│   └── conversation_manager.py — Legacy conversation manager
│
└── runtimes/
    └── models/engines/ollama_engine.py — Ollama engine

IPC CHANNELS (Electron contextBridge)
│
├── backend:* — Backend API proxy
├── presence:* — PresenceRuntime events (onFrame, onState, onEvent, onHealth)
├── executive:* — ExecutiveRuntime events (onSnapshot)
├── execution:* — ExecutionRuntime events (onEvent)
├── workspace:* — WorkspaceRuntime events (subscribe)
├── vscode:* — VSCode events (onEvent)
├── runtime:* — desktopGetSources, onPresenceEvent
├── capability:* — Capability events
├── dialog:* — File dialogs
├── notify:* — Notifications
├── shell:* — Shell integration
├── clipboard:* — Clipboard
├── system:* — System info
├── settings:* — Settings
└── filesystem:* — Filesystem metrics

EVENT BUS EVENT TYPES (desktop/src/runtime/types.ts)
│
├── executive:intent_changed — { decision, confidence, reasoning }
├── executive:state_changed — { focus, focus_strength, priority, urgency, goal_active, conversation_phase }
├── executive:focus_changed — { focus, strength }
├── executive:priority_changed — { priority, urgency }
├── executive:interrupt_raised — { severity, source }
├── voice:started — {}
├── voice:finished — {}
├── voice:failed — {}
├── voice:level — { level, timestamp, request_id }
├── voice:chunk — { audioId, sequence, rmsLevel, timestamp }
├── knowledge:search_started — {}
├── knowledge:search_complete — {}
├── knowledge:memory_recalled — {}
├── conversation:phase_changed — { phase, activity, previous_phase }
├── reasoning:started — {}
├── reasoning:finished — {}
├── presence:state_changed — { state, previousState }
├── presence:audio_level — { audioLevel }
└── presence:voice_chunk — { audioId, sequence, rmsLevel }

RUNTIME TICK FLOW (30Hz)
│
┌─────────────────────────────────────────────────────────────────┐
│ PresenceRuntime.tick() (every 33ms)                            │
├─────────────────────────────────────────────────────────────────┤
│ 1. aggregator.getSnapshot() → RuntimeSnapshot                  │
│ 2. mapSnapshot() → RuntimeState (for engine)                   │
│ 3. engineAdapter.update(dt, runtimeState) → FrameState         │
│ 4. consumeFrameState(FrameState) → embodiment.setFrameState()  │
│ 5. characterRuntime.update(dt) → emotion/intent                │
│ 6. cognitiveRuntime.update(dt) → attention/relationship        │
│ 7. worldRuntime.update(dt) → world state decay                 │
│ 8. executiveRuntime.update(dt) → focus/intent resolution       │
│ 9. executionRuntime.update(dt) → capability lifecycle          │
│ 10. workspaceRuntime.update(dt) → semantic understanding       │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼ IPC (desktop.presence.onFrame)
     │
┌─────────────────────────────────────────────────────────────────┐
│ Frontend: PresenceContext.onFrame → setFrameState(FrameState)  │
│   ├── FrameStateRuntimeContext.Provider (high-freq)            │
│   └── PresenceRuntimeContext.Provider (presenceState)          │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│ Renderers consume via:                                         │
│   - useFrameState() → FrameState (60fps)                       │
│   - usePresenceRuntime() → { frameState, presenceState, ... }  │
│   - OrbEngine(frameState) — Canvas renderer                    │
│   - PresenceCanvas(mode='orb') — React wrapper                 │
└─────────────────────────────────────────────────────────────────┘
```

## Dependency Direction Rules

```
FRONTEND (React)          DESKTOP (Main)           BACKEND (Python)
      │                        │                       │
      ▼                        ▼                       ▼
  ──────────────────────────────────────────────────────────
  │  IPC (contextBridge)  │  Event Bus  │  REST/SSE    │
  ──────────────────────────────────────────────────────────
      │                        │                       │
      ▼                        ▼                       ▼
  Consumes              Produces/              Implements
  FrameState            Consumes               Business
  PresenceState         FrameState             Logic
  ExecutiveSnapshot     CognitiveState         Voice/Chat
  WorkspaceSnapshot     WorldState             Knowledge
                                              Search
```

## Preserved vs Removed Summary

| Layer | Preserved | Removed |
|-------|-----------|---------|
| **Providers** | PresenceContext, ThemeProvider | — |
| **Contexts** | PresenceRuntimeContext, FrameStateRuntimeContext, ThemeContext | ZaramContext (deprecated) |
| **Hooks** | usePresenceRuntime, useFrameState, usePresenceState, usePresenceTheme | useZaram (deprecated) |
| **Core/Frame** | types.ts, composer.ts | — |
| **Core/Simulation** | types.ts, runtime.ts | — |
| **Core/Visual** | types.ts, mapper.ts | — |
| **Engine** | ALL (AnimationRuntime, AssetRegistry, MaterialRegistry, ParticleRuntime, LODManager, ShaderRegistry, EmbodimentRegistry, Adapters, Camera, Components, Culling, Interaction, Performance, Bootstrap) | — |
| **Desktop Bridge** | ALL channels | — |
| **Stores** | useZaramStore (legacy) | uiStore, workspaceStore, workspaceContextStore, chatStore, artifactStore, themeStore, hudStore, dockStore, spatialWindowStore, glassStore, searchStore, modelStore, api.ts |
| **Components** | OrbEngine, OrbRenderer, PresenceCanvas | ALL workspaces, layout, primitives, glass, conversation, interaction, layers, transitions, settings, dock, OrbEngine (v2), OrbEngine (OrbRenderer), CameraController, SearchOverlay, DiagnosticsPanel, PerformanceMonitor, SpatialSelection, Settings, HUD, Dock, TopBar, Sidebar, DesktopShell, WorkspaceLayout, ChatWindow, InputArea, MessageCard, ConversationFeed, ConversationInput, ThinkingIndicator, StreamingCursor, ResponseActions, ProgressiveMarkdown, ResizablePanels, ContextPanel, PanelShell, PanelHeader, Modal, List, Inspector, PropertyGrid, Popover, SplitView, Tabs, TreeView, FloatingNav, FloatingDock, GlassPanel, GlassPrimitives, Glass, Button, Markdown, Loader, ErrorBoundary, Tooltip, ContextMenu, SelectionStateMachine, PresenceLighting, WeatherEngine, AmbientAI, TransitionLibrary, Knowledge, Chat, MessageCard, ChatInput, ChatMessage, AssistantPanel, Inputs, LivingOrb (v2), LivingOrb (v1), OrbEngine, OrbRenderer |
| **Pages** | — | ALL (Workspace, VoiceStudio, UniverseView, RuntimeInspector, Providers, Placeholder, Orchestration, Models, Memory, KnowledgeVault, FilesystemDemo, ConversationPanel, CapabilityExplorer, AuditTerminal) |
| **Desktop Runtime** | ALL (bootstrap, kernel, presence, embodiment, cognitive, world, executive, capability, execution, workspace, voice, sources, personality, electron, event-bus, di, interfaces, types) | — |
| **Desktop Services** | ALL | — |
| **Desktop Capabilities** | ALL | — |
| **Backend** | ALL | — |

## New Shell Integration Points

The new frontend shell MUST wire these preserved contracts:

```tsx
// 1. Root providers (EXACT ORDER)
<QueryClientProvider client={queryClient}>
  <PresenceProvider>           // ← desktop/src/runtime/presence/presence-runtime.ts via IPC
    <ThemeProvider>            // ← frontend/src/theme/ThemeProvider.tsx
      <App />
    </ThemeProvider>
  </PresenceProvider>
</QueryClientProvider>

// 2. Runtime Bridge (new component)
function RuntimeBridge({ children }) {
  // Subscribe to desktop.presence.onFrame for 60fps FrameState
  // Subscribe to desktop.presence.onState for PresenceState
  // Subscribe to desktop.presence.onHealth for connection status
  // Forward to PresenceContext (already handled by PresenceProvider)
  return children;
}

// 3. Workspace Mount (slot for new UI)
function WorkspaceMount() {
  const { frameState, presenceState } = usePresenceRuntime();
  // New workspace component receives runtime state via props/context
  return <NewWorkspace frameState={frameState} presenceState={presenceState} />;
}

// 4. Empty Shell (placeholder)
function EmptyShell() {
  return <div id="workspace-root" style={{ width: '100%', height: '100%' }} />;
}
```

---

*End of Runtime Dependency Map*