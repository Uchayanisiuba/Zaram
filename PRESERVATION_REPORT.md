# Zaram Preservation Report

**Version:** 1.0
**Date:** 2026-07-28
**Purpose:** Document what is preserved, removed, needs adapters, and potential regressions after UI rebuild.

---

## 1. Files PRESERVED (Runtime Architecture)

### Frontend Core Runtime
```
frontend/src/main.jsx                      ← Entry point (providers order)
frontend/src/App.tsx                       ← REPLACE with EmptyShell mount
frontend/src/index.css                     ← Keep (CSS custom properties)
frontend/src/vite-env.d.ts                 ← TypeScript declarations

frontend/src/context/PresenceContext.tsx   ← CRITICAL: Presence Runtime bridge
frontend/src/context/ZaramContext.tsx      ← Legacy (deprecated, keep for useZaram)

frontend/src/theme/ThemeProvider.tsx       ← CRITICAL: Presence → CSS bridge
frontend/src/theme/presenceTheme.ts        ← CRITICAL: State → HSL color tokens
frontend/src/theme/design-tokens.ts        ← Design tokens (colors, spacing, radius)
frontend/src/theme/spacing.ts              ← Spacing scale

frontend/src/hooks/useZaram.js             ← Legacy (usePresenceRuntime preferred)
frontend/src/hooks/useNotifications.tsx    ← Toast notifications
frontend/src/hooks/useAccessibility.ts     ← A11y utilities

frontend/src/store/useZaramStore.ts        ← Legacy Zustand (deprecated)
```

### Frontend Engine (Production-Ready — DO NOT TOUCH)
```
frontend/src/engine/index.ts               ← Main export
frontend/src/engine/bootstrap.ts           ← Engine initialization
frontend/src/engine/animation/AnimationRuntime.ts
frontend/src/engine/animation/index.ts
frontend/src/engine/assets/AssetRegistry.tsx
frontend/src/engine/assets/index.ts
frontend/src/engine/camera/CinematicCameraController.tsx
frontend/src/engine/camera/SpatialCameraController.tsx
frontend/src/engine/components/CameraRig.tsx
frontend/src/engine/components/EdgeLine.tsx
frontend/src/engine/components/KnowledgeEdgeLine.tsx
frontend/src/engine/components/KnowledgeNodeMesh.tsx
frontend/src/engine/components/LivingOrbCenter.tsx
frontend/src/engine/components/NodeMesh.tsx
frontend/src/engine/culling/CullingSystem.ts
frontend/src/engine/embodiments/EmbodimentRegistry.tsx
frontend/src/engine/embodiments/index.ts
frontend/src/engine/factory/EmbodimentFactory.ts
frontend/src/engine/index.ts
frontend/src/engine/interaction/UniverseInteraction.tsx
frontend/src/engine/ldo/LODComponent.tsx
frontend/src/engine/lod/LODManager.ts
frontend/src/engine/lod/index.ts
frontend/src/engine/materials/MaterialRegistry.ts
frontend/src/engine/materials/index.ts
frontend/src/engine/particles/ParticleRuntime.ts
frontend/src/engine/particles/index.ts
frontend/src/engine/performance/PerformanceOverlay.tsx
frontend/src/engine/performance/index.ts
frontend/src/engine/renderers/OuterRimRenderer.ts
frontend/src/engine/renderers/index.ts
frontend/src/engine/shaders/ShaderRegistry.ts
frontend/src/engine/shaders/index.ts
frontend/src/engine/adapters/R3FRendererAdapter.tsx
frontend/src/engine/adapters/R3FFactory.ts
frontend/src/engine/adapters/index.ts
```

### Frontend Core Pipeline (4-Stage Constitution)
```
frontend/src/core/frame/types.ts           ← SACRED: FrameState contract
frontend/src/core/frame/composer.ts        ← FrameComposer (Stage 3)
frontend/src/core/frame/index.ts

frontend/src/core/simulation/types.ts      ← SimulationNode, SimulationState
frontend/src/core/simulation/runtime.ts    ← SimulationRuntime (Stage 2)
frontend/src/core/simulation/index.ts

frontend/src/core/visual/types.ts          ← VisualNode
frontend/src/core/visual/mapper.ts         ← mapToVisualState (Stage 4)
frontend/src/core/visual/index.ts
```

### Frontend Components — PRESERVE (Orb Rendering)
```
frontend/src/components/OrbEngine/OrbEngine.tsx      ← Canvas mount, IPC bridge
frontend/src/components/OrbEngine/OrbRenderer.ts     ← Canvas 2D renderer
frontend/src/components/conversation/PresenceCanvas.tsx ← React wrapper for Orb
frontend/src/components/common/ErrorBoundary.tsx     ← Error boundary
frontend/src/components/R3FErrorBoundary.tsx         ← R3F error boundary
```

### Desktop Runtime (Main Process) — PRESERVE ALL
```
desktop/src/runtime/bootstrap.ts           ← DI container wiring
desktop/src/runtime/di/container.ts        ← Container implementation
desktop/src/runtime/di/index.ts
desktop/src/runtime/event-bus.ts           ← Global event bus (singleton)
desktop/src/runtime/interfaces.ts          ← All runtime interfaces
desktop/src/runtime/types.ts               ← All shared types
desktop/src/runtime/index.ts               ← Barrel export

desktop/src/runtime/kernel/zaram-kernel.ts ← High-level lifecycle

desktop/src/runtime/presence/
  presence-runtime.ts                      ← CRITICAL: Frame clock, embodiment
  living-orb-adapter.ts                    ← Legacy orb adapter
  diagnostics.ts                           ← Health/metrics
  index.ts

desktop/src/runtime/embodiment/
  EmbodimentManager.ts                     ← Embodiment lifecycle
  registry.ts                              ← Descriptor registry
  null-embodiment.ts                       ← No-op fallback
  character-runtime.ts                     ← Emotion/intent → CharacterFrame
  character-frame.ts                       ← Renderer-neutral frame
  emotion-runtime.ts                       ← Emotion processing
  behaviour-runtime.ts                     ← Behavior trees
  gaze-controller.ts                       ← Eye/head tracking
  types.ts
  index.ts

desktop/src/runtime/cognitive/
  bundle.ts                                ← CognitiveBundle (attention, relationship)
  attention-runtime.ts                     ← Attention state
  relationship-runtime.ts                  ← Relationship model
  conversation-projection.ts               ← Conversation → cognitive
  memory-projection.ts                     ← Memory → cognitive
  types.ts
  index.ts

desktop/src/runtime/world/
  world-runtime.ts                         ← WorldState (notifications, env)
  world-attention-adapter.ts               ← Attention → world
  types.ts
  index.ts

desktop/src/runtime/executive/
  executive-runtime.ts                     ← SINGLE AUTHORITY: decisions
  executive-state.ts                       ← State machine
  focus-manager.ts                         ← Focus management
  priority-manager.ts                      ← Priority queue
  interrupt-manager.ts                     ← Interrupt handling
  goal-manager.ts                          ← Goal tracking
  intent-generator.ts                      ← Intent synthesis
  execution-plan.ts                        ← Plan representation
  types.ts
  index.ts

desktop/src/runtime/capability/
  capability-runtime.ts                    ← Capability registry
  capability-registry.ts                   ← Descriptors
  capability-resolver.ts                   ← Resolution
  capability-filter.ts                     ← Filtering
  capability-descriptor.ts                 ← Schema
  types.ts
  index.ts

desktop/src/runtime/execution/
  execution-runtime.ts                     ← ONLY invokes capabilities
  execution-state-machine.ts               ← Lifecycle
  execution-invoker.ts                     ← Invocation
  execution-context.ts                     ← Context
  types.ts
  index.ts

desktop/src/runtime/workspace/
  workspace-runtime.ts                     ← Semantic project understanding
  workspace-watcher.ts                     ← File watching
  workspace-pool.ts                        ← Pool management
  workspace-indexer.ts                     ← Indexing
  workspace-events.ts                      ← Events
  workspace-detector.ts                    ← Detection
  workspace-context.ts                     ← Context
  workspace-cache.ts                       ← Cache
  types.ts
  bootstrap.ts
  index.ts

desktop/src/runtime/voice/
  voice-runtime.ts                         ← Voice synthesis lifecycle

desktop/src/runtime/sources/
  aggregator.ts                            ← RuntimeSourceAggregator
  base.ts                                  ← Base source
  conversation-runtime.ts                  ← Conversation phase
  voice-runtime.ts                         ← Voice level (read-only)
  memory-runtime.ts                        ← Memory recall
  system-runtime.ts                        ← System metrics
  types.ts
  util.ts

desktop/src/runtime/personality/
  expressive-params.ts                     ← ExpressiveParamsSource

desktop/src/runtime/electron/
  render-transport.ts                      ← Renderer communication
  embodiment-host.ts                       ← Host process

desktop/src/runtime/engine/index.ts        ← Engine adapter
```

### Desktop Services — PRESERVE ALL
```
desktop/src/services/desktop-service.ts
desktop/src/services/window-service.ts
desktop/src/services/shell-service.ts
desktop/src/services/settings-service.ts
desktop/src/services/notification-service.ts
desktop/src/services/file-dialog-service.ts
desktop/src/services/download-service.ts
desktop/src/services/backend-service.ts
desktop/src/services/index.ts
```

### Desktop Capabilities — PRESERVE ALL
```
desktop/src/capabilities/filesystem/
  filesystem-capability.ts
  safe-path.ts
  permission-manager.ts
  path-validator.ts
  types.ts

desktop/src/capabilities/vscode/
  vscode-capability.ts
  vscode-handler.ts
  vscode-adapter.ts

desktop/src/capabilities/vision/
  vision-capability.ts

desktop/src/capabilities/knowledge/
  knowledge-capability.ts

desktop/src/capabilities/speech/
  speech-handler.ts
  speech-capabilities.ts
```

### Desktop Tests — PRESERVE ALL
```
desktop/tests/**/*.test.ts                 ← 80+ test files, all runtime
```

### Backend (Python) — PRESERVE ALL
```
backend/main.py                            ← FastAPI app, all endpoints
backend/core/                              ← Kernel, ChatRouter, events
backend/voice/                             ← Voice runtime, providers
backend/orchestrator/                      ← Executive orchestrator
backend/knowledge/                         ← Knowledge service
backend/implementations/                   ← Ollama LLM
backend/services/                          ← Legacy conversation manager
backend/runtimes/                          ← Model engines
```

### Desktop Package Config
```
desktop/package.json                       ← electron, typescript, vitest
desktop/tsconfig.json
desktop/vitest.config.ts
desktop/start-electron.js
```

---

## 2. Files REMOVED (Entire Presentation Layer)

### Frontend Workspaces (All 6 — Delete Entire Directories)
```
frontend/src/components/workspaces/
  WorkspaceShell.tsx
  PresenceWorkspace.tsx
  ConversationWorkspace.tsx
  KnowledgeWorkspace.tsx
  MemoryWorkspace.tsx
  ProjectsWorkspace.tsx
  SystemWorkspace.tsx
  index.ts
```

### Frontend Layout & Shell (Delete Entire Directories)
```
frontend/src/components/layout/
  DesktopShell.tsx        ← Main 5-region shell (DELETE)
  TopBar.tsx
  Sidebar.jsx
  Header.jsx
  index.ts

frontend/src/components/primitives/
  FloatingNav.tsx
  FloatingDock.tsx
  ContextPanel.tsx
  PanelShell.tsx
  PanelHeader.tsx
  GlassPanel.tsx (duplicate)
  Glass.tsx
  GlassPrimitives.tsx
  FloatingDock.tsx
  index.ts
  inputs/ (Input.tsx, index.ts)

frontend/src/components/dock/
  Dock.tsx
  index.ts

frontend/src/components/search/
  SearchOverlay.tsx
  useSearchShortcut.ts
  index.ts

frontend/src/components/settings/
  Settings.jsx
```

### Frontend Glass/Design System (Delete Entire Directories)
```
frontend/src/components/glass/
  GlassPanel.tsx
  useGlassEffects.ts
  index.ts

frontend/src/components/transitions/
  TransitionLibrary.tsx
  index.ts

frontend/src/components/performance/
  useRenderOptimization.tsx
  PerformanceMonitor.tsx
  index.ts
```

### Frontend Workspace Components (Delete)
```
frontend/src/components/workspace/
  WorkspaceLayout.tsx
  RightPanel.tsx
  InputArea.tsx
  ChatWindow.tsx
```

### Frontend Conversation UI (Delete Entire Directory)
```
frontend/src/components/conversation/
  PresenceCanvas.tsx       ← KEEP (moved to components/OrbEngine)
  ThinkingIndicator.tsx
  StreamingCursor.tsx
  ResponseActions.tsx
  ResizablePanels.tsx
  ProgressiveMarkdown.tsx
  ConversationInput.tsx
  ConversationFeed.tsx
  MessageCard.tsx
  index.ts
```

### Frontend Interaction Primitives (Delete Entire Directory)
```
frontend/src/components/interaction/
  useTooltip.tsx
  useSelectionState.tsx
  usePresenceReactions.tsx
  useParticleReactions.tsx
  useLightingReactions.tsx
  useKeyboardNavigation.tsx
  useFocusManagement.tsx
  useContextMenu.tsx
  useAccessibility.tsx
  Tooltip.tsx
  SelectionStateMachine.tsx
  PresenceLighting.tsx
  ContextMenu.tsx
  index.ts
```

### Frontend Spatial/Camera (Delete)
```
frontend/src/components/spatial/
  camera/
  dock/
  search/
  index.ts
```

### Frontend Living Orb Legacy (Delete — Replaced by OrbEngine)
```
frontend/src/components/LivingOrb/
  LivingOrb.tsx
  v2/
    AudioEnvelope.ts
```

### Frontend OrbEngine v2 (Delete — Duplicate)
```
frontend/src/components/OrbEngine/
  OrbEngine.tsx          ← KEEP (the one in components/OrbEngine/)
  OrbRenderer.ts         ← KEEP
```

### Frontend Embodiments (Delete — UI implementations)
```
frontend/src/embodiments/
  ProjectNodeEmbodiment.tsx
  Orb/
    OrbEmodiment.tsx
    manifest.json
  MemoryNodeEmbodiment.tsx
  LivingOrb/
    LivingOrb.tsx
  KnowledgeUniverse/
    KnowledgeUniverseEmbodiment.tsx
    manifest.json
  KnowledgeNodeEmbodiment.tsx
  DefaultNodeEmbodiment.tsx
```

### Frontend Engine Components (Delete — UI implementations)
```
frontend/src/engine/components/
  LivingOrbCenter.tsx        ← DELETE (UI embodiment)
  KnowledgeNodeMesh.tsx      ← DELETE (UI embodiment)
  KnowledgeEdgeLine.tsx      ← DELETE (UI embodiment)
  EdgeLine.tsx               ← KEEP (core primitive)
  NodeMesh.tsx               ← KEEP (core primitive)
  CameraRig.tsx              ← KEEP (core primitive)
```

### Frontend Engine Embodiments (Delete — UI implementations)
```
frontend/src/engine/embodiments/
  EmbodimentRegistry.tsx     ← DELETE (UI embodiment registry)
```

### Frontend Pages (Delete Entire Directory)
```
frontend/src/pages/
  Workspace.tsx
  VoiceStudio.tsx
  UniverseView.tsx
  RuntimeInspector.tsx
  Providers.tsx
  Placeholder.tsx
  Orchestration.tsx
  Models.tsx
  Memory.tsx
  KnowledgeVault.tsx
  FilesystemDemo.tsx
  ConversationPanel.tsx
  CapabilityExplorer.tsx
  AuditTerminal.tsx
  fix_sse.py
  fix_sse2.py
```

### Frontend Mock Data (Delete)
```
frontend/src/mock/
  mockThemes.ts
  mockSemanticGraph.ts
```

### Frontend Lib (Delete UI-specific)
```
frontend/src/lib/
  glassTokens.ts
  designTokens.ts
  animations.ts
  workspaceConversation.ts
  __tests__/workspaceConversation.test.ts
```

### Frontend Styles (Delete)
```
frontend/src/styles/
  glass.css
```

### Frontend Stores (Delete — All UI State)
```
frontend/src/stores/
  uiStore.ts              ← DELETE (workspace, dock, panels, camera)
  workspaceStore.ts       ← DELETE (layout persistence)
  workspaceContextStore.ts← DELETE (context panel data)
  chatStore.ts            ← DELETE (conversation messages)
  artifactStore.ts        ← DELETE (code artifacts)
  themeStore.ts           ← DELETE (theme preferences)
  hudStore.ts             ← DELETE (HUD state)
  dockStore.ts            ← DELETE (dock state)
  spatialWindowStore.ts   ← DELETE (spatial windows)
  glassStore.ts           ← DELETE (glass panel factory)
  searchStore.ts          ← DELETE (search overlay)
  modelStore.ts           ← DELETE (model selection)
  api.ts                  ← DELETE (API wrappers)
  index.ts                ← DELETE (barrel export)
  __tests__/artifactStore.test.ts
```

### Frontend Types (Delete UI-specific)
```
frontend/src/types/
  workspace.ts
  spatial-ux.d.ts
  jsx.d.ts
  artifacts.ts
  index.ts
```

### Desktop Electron Host (Delete — Old shell)
```
desktop/src/main.ts              ← Old main process (if exists)
desktop/src/preload.ts           ← Old preload (if exists)
```

---

## 3. Files NEEDING ADAPTERS

| File | Reason | Adapter Needed |
|------|--------|----------------|
| `frontend/src/main.jsx` | Current `App` renders 3D scene; new shell needs empty mount | Replace `<App />` with `<WorkspaceMount />` |
| `frontend/src/App.tsx` | Full simulation + renderer loop | **DELETE** — Replace with minimal mount |
| `frontend/src/components/OrbEngine/OrbEngine.tsx` | Expects `frameState` prop OR desktop IPC | Works as-is if `frameState` passed from new shell |
| `frontend/src/components/conversation/PresenceCanvas.tsx` | Wrapper for OrbEngine | Works as-is |
| `frontend/src/hooks/useZaram.js` | Uses deprecated `ZaramContext` | Keep for legacy; new code uses `usePresenceRuntime` |
| `frontend/src/store/useZaramStore.ts` | Legacy Zustand store | Keep for legacy; mark deprecated |

---

## 4. POTENTIAL REGRESSIONS

| Area | Risk | Mitigation |
|------|------|------------|
| **Provider Order** | `PresenceProvider` must wrap `ThemeProvider` (not reverse) | Verify `main.jsx` order: `QueryClientProvider → PresenceProvider → ThemeProvider` |
| **IPC Bridge** | `desktop.presence.onFrame` must be registered before render | `PresenceContext` subscribes in `useEffect([])` — ensure desktop ready |
| **FrameState Shape** | `FrameComposer` output must match `FrameState` contract | Contract is in `core/frame/types.ts` — DO NOT CHANGE |
| **Presence States** | Theme colors map 1:1 to `PresenceState` enum | `presenceTheme.ts` has all 10 states — DO NOT REMOVE |
| **CSS Variables** | `--presence-*` vars applied by `ThemeProvider` | Ensure new shell has `<ThemeProvider>` in tree |
| **Desktop Bootstrap** | `bootstrapPresence()` wires all runtimes | Desktop `main.ts` must call `bootstrapPresence().then(r => r.buildKernel().boot())` |
| **Engine Adapter** | `@zaram/engine` AnimationRuntime must initialize | `bootstrap.ts` creates `EngineAnimationRuntime` — verify |
| **Vite Proxy** | `/chat`, `/voice`, `/knowledge` proxy to backend | `vite.config.js` has all proxies — DO NOT REMOVE |
| **Electron contextBridge** | `window.zaram` must expose all channels | `desktop-bridge.ts` is frontend-side; main process preload exposes `zaram` |
| **Zustand Imports** | `useZaramStore` uses `create` from `zustand` (not default) | Already fixed per `corrections.md` — verify `import create from 'zustand'` |
| **OrbEngine Mount** | Requires `<canvas>` ref, handles resize | New shell must provide container with size |
| **Theme Transition** | 400ms HSL interpolation in `presenceTheme.ts` | CSS `transition: var(--theme-transition-duration)` |

---

## 5. VERIFICATION CHECKLIST (Post-Cleanup)

Run after cleanup to verify runtime integrity:

```bash
# 1. Frontend dev server starts
cd frontend && npm run dev
# → Vite starts on :5173, no module resolution errors

# 2. TypeScript compiles (frontend)
cd frontend && npx tsc --noEmit
# → No errors

# 3. Desktop compiles
cd desktop && npm run build
# → TypeScript compiles to dist/, no errors

# 4. Desktop tests pass
cd desktop && npm run test
# → All runtime tests pass (80+ tests)

# 5. Backend starts
cd backend && python main.py
# → FastAPI on :8000, /health returns kernel: online

# 6. Electron app launches
cd desktop && npm run dev
# → Electron window opens, no console errors
# → PresenceRuntime boots (check console for [STARTUP] logs)
# → FrameState flows via IPC (check React DevTools: PresenceContext.frameState)
```

---

## 6. NEW SHELL INTEGRATION POINTS

The new frontend shell MUST wire these preserved contracts:

```tsx
// frontend/src/main.jsx (EXACT ORDER)
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PresenceProvider } from '@/context/PresenceContext'
import { ThemeProvider } from '@/theme/ThemeProvider'
import { ErrorBoundary } from '@/components/common/ErrorBoundary'
import WorkspaceMount from './WorkspaceMount'  // NEW

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <PresenceProvider>
          <ThemeProvider>
            <WorkspaceMount />
          </ThemeProvider>
        </PresenceProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  </React.StrictMode>
)
```

```tsx
// frontend/src/WorkspaceMount.tsx (NEW)
import { usePresenceRuntime } from '@/context/PresenceContext'
import { OrbEngine } from '@/components/OrbEngine/OrbEngine'

export default function WorkspaceMount() {
  const { frameState, presenceState, isConnected } = usePresenceRuntime()

  return (
    <div style={{ width: '100%', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Top: Connection status */}
      <div style={{ padding: 8, fontSize: 12, opacity: 0.6 }}>
        Presence: {presenceState} | IPC: {isConnected ? 'connected' : 'fallback'} | Frames: {frameState?.sequence ?? 0}
      </div>

      {/* Center: Orb (preserved renderer) */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <OrbEngine frameState={frameState} className="w-96 h-96" />
      </div>

      {/* Bottom: New workspace slot (empty for now) */}
      <div id="workspace-root" style={{ flex: 1, minHeight: 200 }} />
    </div>
  )
}
```

---

*End of Preservation Report*