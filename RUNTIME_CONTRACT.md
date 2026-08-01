# Zaram Runtime Contract

**Version:** 1.0
**Purpose:** API contract for the frontend shell to consume the Zaram OS runtime.
**Scope:** Runtime only — no UI components, no design system, no workspace layouts.

---

## 1. Providers (React Context)

### `PresenceProvider` (`frontend/src/context/PresenceContext.tsx`)
Provides the **Presence Runtime** — the unified frame clock and presence state.

**Context Values:**
- `PresenceRuntimeContext` → `PresenceRuntimeState`
  - `frameState: FrameState` — Sacred FrameState contract (60fps from desktop)
  - `presenceState: PresenceState` — Current presence state (Idle, Listening, Thinking, Speaking, SearchingWeb, SearchingMemory, Planning, Learning, Error, Success)
  - `setPresenceState: (state: PresenceState) => void` — Override presence (for testing/fallback)
  - `isConnected: boolean` — Desktop IPC connection health

- `FrameStateRuntimeContext` → `FrameState | undefined` — High-frequency frame state (separate context to avoid 60fps re-renders on presence-only consumers)

**Hooks:**
- `usePresenceRuntime(): PresenceRuntimeState`
- `useFrameState(): FrameState`
- `usePresenceState(): PresenceState`

**IPC Subscriptions (auto-wired):**
- `desktop.presence.onFrame` → `frameState`
- `desktop.presence.onState` → `presenceState`
- `desktop.presence.onHealth` → `isConnected`

**Local Fallback:** 30Hz FrameComposer loop when desktop IPC unavailable (browser dev).

---

### `ThemeProvider` (`frontend/src/theme/ThemeProvider.tsx`)
Bridges Presence state → CSS custom properties for theme synchronization.

**Context Value:** `ThemeContextValue`
- `currentState: PresenceState` — Read-only current presence state
- `setState: (state: PresenceState) => void` — Applies theme immediately (no runtime state change)

**CSS Variables Applied (via `applyPresenceTheme`):**
```css
--presence-primary
--presence-secondary
--presence-glow
--presence-bg-accent
--presence-orb-core
--presence-ring-color
--presence-particle-color
[data-presence-state] /* attribute for CSS selectors */
```

**States:** `Idle`, `Listening`, `Thinking`, `SearchingMemory`, `SearchingWeb`, `Planning`, `Speaking`, `Learning`, `Error`, `Success`

---

### `QueryClientProvider` (`@tanstack/react-query`)
Global `QueryClient` instance for server state (backend API).

---

### `ErrorBoundary` (`frontend/src/components/common/ErrorBoundary.tsx`)
Catches render errors, prevents full app crash.

---

## 2. Hooks

### `usePresenceRuntime()` → `PresenceRuntimeState`
Access Presence Runtime state and controls.

### `useFrameState()` → `FrameState`
High-frequency frame state (60fps). **Use sparingly** — triggers re-render every frame.

### `usePresenceState()` → `PresenceState`
Lightweight presence state only (no frame data).

### `usePresenceTheme()` → `{ currentState, setState }`
Theme bridge — reads presence state, applies CSS variables.

### `useZaram()` → `ZaramContext`
Legacy Zustand store access (deprecated, use PresenceRuntime).

### `useNotifications()` → `{ notifications, addNotification, removeNotification }`
Toast notification system (Zustand).

---

## 3. Event Bus Events (Desktop Runtime)

**Source:** `desktop/src/runtime/event-bus.ts` — `eventBus` singleton.

### Presence Events
| Event | Payload | Direction |
|-------|---------|-----------|
| `presence:state_changed` | `{ state: PresenceState, previousState: PresenceState }` | Desktop → Frontend (IPC) |
| `presence:audio_level` | `{ audioLevel: number }` | Desktop → Frontend |
| `presence:voice_chunk` | `{ audioId: string, sequence: number, rmsLevel?: number }` | Desktop → Frontend |

### Executive Events (Decision Engine)
| Event | Payload | Direction |
|-------|---------|-----------|
| `executive:intent_changed` | `{ decision: string, confidence: number, reasoning: string }` | Internal |
| `executive:state_changed` | `{ focus: string, focus_strength: number, priority: string, urgency: number, goal_active: boolean, conversation_phase: string }` | Internal |
| `executive:focus_changed` | `{ focus: string, strength: number }` | Internal |
| `executive:priority_changed` | `{ priority: string, urgency: number }` | Internal |
| `executive:interrupt_raised` | `{ severity: string, source: string }` | Internal |

### Voice Runtime Events
| Event | Payload | Direction |
|-------|---------|-----------|
| `voice:started` | — | Internal |
| `voice:finished` | — | Internal |
| `voice:failed` | — | Internal |
| `voice:level` | `{ level: number, timestamp: number, request_id?: string }` | Internal |
| `voice:chunk` | `{ audioId: string, sequence: number, rmsLevel?: number, timestamp: number }` | Internal |

### Knowledge/Search Events
| Event | Payload | Direction |
|-------|---------|-----------|
| `knowledge:search_started` | — | Internal |
| `knowledge:search_complete` | — | Internal |
| `knowledge:memory_recalled` | — | Internal |

### Conversation Events
| Event | Payload | Direction |
|-------|---------|-----------|
| `conversation:phase_changed` | `{ phase: string, activity: number, previous_phase?: string }` | Internal |

### Reasoning Events
| Event | Payload | Direction |
|-------|---------|-----------|
| `reasoning:started` | — | Internal |
| `reasoning:finished` | — | Internal |

---

## 4. IPC Channels (Electron `contextBridge`)

**Exposed via:** `window.zaram` (see `frontend/src/desktop/desktop-bridge.ts`)

### App
- `app.getInfo(): Promise<AppInfo>`
- `app.getVersion(): Promise<string>`
- `app.getPlatform(): Promise<string>`

### Backend
- `backend.getStatus(): Promise<BackendStatus>`
- `backend.checkHealth(): Promise<HealthCheck>`
- `backend.onStatus(cb): () => void` — Subscribe to backend status changes

### Presence (Desktop Runtime → Frontend)
- `presence.getHealth(): Promise<PresenceHealth>`
- `presence.getStatus(): Promise<EmbodimentStatus>`
- `presence.getDiagnostics(): Promise<PresenceDiagnostics>`
- `presence.onFrame(cb): () => void` — **60fps FrameState push**
- `presence.onViewport(cb): () => void` — Viewport changes
- `presence.onEvent(cb): () => void` — Generic presence events

### Executive (Decision Engine)
- `executive.getSnapshot(): Promise<ExecutiveSnapshot>`
- `executive.plan(query, options?): Promise<ExecutionPlan>`
- `executive.getPlan(): Promise<ExecutionPlan>`
- `executive.getConfidence(): Promise<number>`
- `executive.getEvidence(): Promise<Evidence[]>`
- `executive.getMetrics(): Promise<ExecutiveMetrics>`
- `executive.setPendingSpeech(text, persona?): Promise<void>`
- `executive.onSnapshot(cb): () => void` — Subscribe to executive state

### Capability (OS Capability Registry)
- `capability.getSnapshot(): Promise<CapabilitySnapshot>`
- `capability.getById(id): Promise<CapabilityDescriptor>`
- `capability.getByCategory(cat): Promise<CapabilityDescriptor[]>`

### Execution (Capability Invocation)
- `execution.getHistory(): Promise<ExecutionRecord[]>`
- `execution.getExecution(id): Promise<ExecutionRecord>`
- `execution.execute(capabilityId, input, options?): Promise<ExecutionResult>`
- `execution.cancel(id): Promise<void>`
- `execution.retry(id): Promise<void>`
- `execution.onEvent(cb): () => void` — Execution lifecycle events

### World (Intelligence Runtime)
- `world.getState(): Promise<WorldState>`

### Cognitive (Internal AI State)
- `cognitive.getState(): Promise<CognitiveState>`
- `cognitive.getAttention(): Promise<AttentionState>`
- `cognitive.getRelationship(): Promise<RelationshipState>`

### Character (Renderer-Neutral Embodiment)
- `character.getFrame(): Promise<CharacterFrame>`

### Workspace (Project Intelligence)
- `workspace.getState(): Promise<WorkspaceState>`
- `workspace.getContext(): Promise<WorkspaceContext>`
- `workspace.getSnapshot(): Promise<WorkspaceSnapshot>`
- `workspace.setRootPath(path): Promise<void>`
- `workspace.getProject(path): Promise<ProjectInfo>`
- `workspace.getAllProjects(): Promise<ProjectInfo[]>`
- `workspace.discover(signals, mode): Promise<DiscoveryResult>`
- `workspace.onEvent(cb): () => void`

### Dialog (Native OS Dialogs)
- `dialog.showOpen(opts?): Promise<string[]>`
- `dialog.showSave(opts?): Promise<string>`
- `dialog.showMessage(title?, body?): Promise<void>`
- `dialog.selectDirectory(opts?): Promise<string>`

### Notify (OS Notifications)
- `notify.show(opts?): Promise<void>`

### Shell (OS Integration)
- `shell.openExternal(url): Promise<void>`
- `shell.openPath(path): Promise<void>`
- `shell.showItemInFolder(path): Promise<void>`

### Clipboard
- `clipboard.readText(): Promise<string>`
- `clipboard.writeText(text): Promise<void>`

### System
- `system.getPlatform(): Promise<string>`
- `system.getVersion(): Promise<string>`
- `system.getArch(): Promise<string>`

### Settings (Persistent Config)
- `settings.get(key): Promise<any>`
- `settings.set(key, value): Promise<void>`
- `settings.getAll(): Promise<Record<string, any>>`

### Filesystem (Metrics)
- `filesystem.getMetrics(): Promise<FilesystemMetrics>`

### VS Code Integration
- `vscode.getSnapshot(): Promise<VSCodeSnapshot>`
- `vscode.getEditor(): Promise<VSCodeEditorState>`
- `vscode.getWorkspaceFolders(): Promise<string[]>`
- `vscode.getDiagnostics(): Promise<VSCodeDiagnostic[]>`
- `vscode.getGitStatus(): Promise<VSCodeGitStatus>`
- `vscode.onEvent(cb): () => void`

### Runtime (Desktop Bridge)
- `runtime.desktopGetSources(opts?): Promise<DesktopSource[]>`
- `runtime.onPresenceEvent(cb): () => void` — Raw presence events

---

## 5. Backend APIs (FastAPI, port 8000)

**Base URL:** `http://localhost:8000` (configurable via `VITE_BACKEND_URL`)

### Health & Status
```
GET /health
→ { status, kernel, capabilities[], knowledge_providers{}, speech{} }
```

### Chat (Streaming SSE)
```
POST /chat
Body: { text: string, model?: string, personality?: string, persona?: string }
→ text/event-stream (StreamEvent: token, error, status, done)
```

### Vision Analysis
```
POST /vision/analyze
Body: { prompt: string, image: string (base64 or data URI) }
→ text/event-stream
```

### Knowledge Search
```
POST /knowledge/search
Body: { query: string, persona?: string }
→ { results[], provider, query }
```

### Voice Synthesis
```
POST /voice/synthesize
Body: { text: string, voice?: string, persona?: string }
→ { success, audio_id, duration_ms, voice_id }

POST /voice/stream
Body: { text: string, voice?: string, persona?: string }
→ text/event-stream (audio chunks)

GET /voice/voices
→ { voices: Record<string, VoiceInfo> }

GET /voice/health
→ { status, providers[], latency_ms }
```

### Audio Files
```
GET /audio/{filename}
→ audio/wav
```

### Personalities
```
GET /personalities
→ { personalities: Record<id, { name, gender, description, system_prompt, voice }> }

GET /personalities/{persona_id}
→ { id, name, gender, description, system_prompt, voice }
```

---

## 6. Runtime Dependencies (Desktop)

### Core Runtimes (30Hz tick via `PresenceRuntime`)
| Runtime | Token | Purpose |
|---------|-------|---------|
| `PresenceRuntime` | `presenceRuntime` | Frame clock, embodiment bridge, state aggregation |
| `CharacterRuntime` | `characterRuntime` | Emotion/intent → renderer-neutral `CharacterFrame` |
| `CognitiveBundle` | `cognitiveRuntime` | Internal AI state (attention, relationship, reasoning) |
| `WorldRuntime` | `worldRuntime` | Environment perception (notifications, foreground) |
| `ExecutiveRuntime` | `executiveRuntime` | **Single authority** for high-level decisions |
| `CapabilityRuntime` | `capabilityRuntime` | OS capability registry & discovery |
| `ExecutionRuntime` | `executionRuntime` | **Only runtime** that invokes capabilities |
| `WorkspaceRuntime` | `workspaceRuntime` | Semantic project understanding |
| `ConversationRuntime` | `conversationRuntime` | Conversation phase/activity tracking |
| `VoiceRuntime` (source) | `voiceRuntime` | Voice level/phase aggregation (read-only) |
| `VoiceRuntime` (full) | `voiceRuntimeFull` | Speech synthesis lifecycle owner |
| `MemoryRuntime` | `memoryRuntime` | Memory recall/activity tracking |
| `SystemRuntime` | `systemRuntime` | Cognitive load, visual identity |

### Source Aggregator
- `RuntimeSourceAggregator` (`runtimeAggregator`) — Merges all runtimes into single `RuntimeSnapshot` for `PresenceRuntime` consumption.

### Engine Adapter
- `EngineAdapter` (`engineAdapter`) — Wraps `@zaram/engine` AnimationRuntime (front-end engine).

### Embodiment System
- `EmbodimentManager` (`embodiment`) — Manages embodiment lifecycle via `IRenderTransport`
- `EmbodimentRegistry` (`embodimentRegistry`) — Embodiment descriptors
- `NullRenderTransport` / `ElectronRenderTransport` — Renderer bridge

### Personality
- `DefaultExpressiveParamsSource` (`expressiveParams`) — Expressive parameters for animation.

### Kernel
- `ZaramKernel` (`kernel`) — High-level lifecycle (boot, shutdown, diagnostics).

---

## 7. Stores (Zustand)

| Store | File | Purpose |
|-------|------|---------|
| `useUIStore` | `frontend/src/stores/uiStore.ts` | App phase, active workspace, panels, dock, camera |
| `useZaramStore` | `frontend/src/store/useZaramStore.ts` | Legacy presence state (deprecated) |
| `useChatStore` | `frontend/src/stores/chatStore.ts` | Conversation messages, streaming state |
| `useArtifactStore` | `frontend/src/stores/artifactStore.ts` | Code/file artifacts from assistant |
| `useThemeStore` | `frontend/src/stores/themeStore.ts` | Theme preferences |
| `useWorkspaceStore` | `frontend/src/stores/workspaceStore.ts` | Workspace layout persistence |
| `useHUDStore` | `frontend/src/stores/hudStore.ts` | HUD state (deprecated) |
| `useDockStore` | `frontend/src/stores/dockStore.ts` | Dock state (deprecated) |
| `useSpatialWindowStore` | `frontend/src/stores/spatialWindowStore.ts` | Spatial windows (deprecated) |
| `useSearchStore` | `frontend/src/stores/searchStore.ts` | Search overlay state |
| `createGlassPanelStore` | `frontend/src/stores/glassStore.ts` | Glass panel factory |

---

## 8. Services

### Frontend Engine (`frontend/src/engine/`)
| Module | Export | Purpose |
|--------|--------|---------|
| `AnimationRuntime` | `AnimationRuntime` | Procedural animations (breathing, floating, orbit, etc.) |
| `LODManager` | `LODManager` | Level-of-detail for 3D scenes |
| `ShaderRegistry` | `ShaderRegistry` | Shader compilation & caching |
| `AssetRegistry` | `AssetRegistry` | Asset loading & management |
| `MaterialRegistry` | `MaterialRegistry` | Material definitions |
| `ParticleRuntime` | `ParticleRuntime` | Particle systems |
| `EmbodimentRegistry` | `EmbodimentRegistry` | Embodiment descriptors |
| `PerformanceOverlay` | `PerformanceOverlay` | FPS/memory/GPU overlay |

### Desktop Services (`desktop/src/services/`)
| Service | Purpose |
|---------|---------|
| `window-service` | Electron window management |
| `shell-service` | OS shell integration |
| `settings-service` | Persistent settings |
| `notification-service` | OS notifications |
| `file-dialog-service` | Native file dialogs |
| `download-service` | File downloads |
| `desktop-service` | Desktop-level coordination |
| `backend-service` | Backend health & communication |

---

## 9. FrameState Contract (Sacred)

**File:** `frontend/src/core/frame/types.ts`

```typescript
interface FrameState {
  visual: {
    presence: number;    // 0-1 overall intensity
    energy: number;      // 0-1 animation energy
    focus: number;       // 0-1 attention level
    activity: number;    // 0-1 busyness
  };
  audio: {
    voiceLevel: number;        // 0-1 TTS output
    microphoneLevel: number;   // 0-1 mic input
    rmsLevel: number;          // 0-1 real-time audio RMS
    smoothedRms: number;       // 0-1 smoothed RMS
  };
  emotion: {
    calmness: number;
    confidence: number;
    curiosity: number;
    warmth: number;
    empathy: number;
    playfulness: number;
  };
  system: {
    state: PresenceState;      // Current presence state
    cognitiveLoad: number;     // 0-1 mental workload
    adaptiveQuality: number;   // 0-1 render quality
    visualIdentity: string;    // e.g., 'orb-v2'
  };
  metadata: {
    timestamp: number;
    correlationId: string;
    version: string;
  };
  sequence: number;  // Monotonically increasing
}
```

**Producer:** `FrameComposer` (`frontend/src/core/frame/composer.ts`) — Single source of truth.
**Consumers:** All renderers (OrbEngine, LivingOrb, future shells).

---

## 10. PresenceState Enum

```typescript
type PresenceState = 
  | 'Idle'
  | 'Listening'
  | 'Thinking'
  | 'SearchingMemory'
  | 'SearchingWeb'
  | 'Planning'
  | 'Speaking'
  | 'Learning'
  | 'Error'
  | 'Success';
```

**Color Tokens:** `frontend/src/theme/presenceTheme.ts` — `PRESENCE_COLORS[state]`

---

## 11. Frontend Entry Contract

**File:** `frontend/src/main.jsx`

```jsx
<QueryClientProvider client={queryClient}>
  <PresenceProvider>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </PresenceProvider>
</QueryClientProvider>
```

**Mount Point:** `<div id="root">` in `index.html`

**New Shell Contract (for rebuild):**
```tsx
<App>
  ↓ Providers
    ↓ RuntimeBridge (IPC + EventBus)
      ↓ WorkspaceMount (slot for workspace component)
        ↓ EmptyShell (placeholder — replaced by new UI)
```

---

## 12. What the New Shell MUST Provide

1. **Mount `<PresenceProvider>`** at root (wraps entire app)
2. **Mount `<ThemeProvider>`** inside PresenceProvider
3. **Mount `<QueryClientProvider>`** at root
4. **Call `desktop.presence.onFrame`** subscription for 60fps FrameState
5. **Render a workspace component** that consumes `usePresenceRuntime()` / `useFrameState()`
6. **No direct imports** from `frontend/src/components/**` (all deleted)
7. **No imports** from `frontend/src/pages/**` (all deleted)
8. **No imports** from `frontend/src/engine/**` (engine is preserved but not coupled)

---

## 13. What the New Shell MUST NOT Do

- ❌ Import any `components/workspaces/*`, `components/layout/*`, `components/primitives/*`
- ❌ Import `DesktopShell`, `Sidebar`, `Dock`, `TopBar`, `GlassPanel`, `GlassPrimitives`
- ❌ Import `LivingOrb`, `PresenceCanvas`, `OrbEngine`
- ❌ Import `ConversationWorkspace`, `KnowledgeWorkspace`, etc.
- ❌ Use `useUIStore` for workspace switching (use PresenceRuntime instead)
- ❌ Use `framer-motion` for shell animations (use CSS transitions only)
- ❌ Import design tokens from `theme/design-tokens.ts`

---

## 14. Backward Compatibility

**Preserved imports that new shell may use:**
- `frontend/src/context/PresenceContext.tsx` — `PresenceProvider`, `usePresenceRuntime`, `useFrameState`, `usePresenceState`
- `frontend/src/theme/ThemeProvider.tsx` — `ThemeProvider`, `usePresenceTheme`
- `frontend/src/theme/presenceTheme.ts` — `PresenceState`, `PRESENCE_COLORS`, `applyPresenceTheme`
- `frontend/src/core/frame/types.ts` — `FrameState`, `IDLE_FRAME`, `VisualFrame`, etc.
- `frontend/src/core/frame/composer.ts` — `FrameComposer` (for local fallback)
- `frontend/src/desktop/desktop-bridge.ts` — `desktop` IPC bridge, `isDesktop`
- `frontend/src/store/useZaramStore.ts` — `useZaramStore` (legacy, deprecated)
- `frontend/src/engine/**` — All engine runtimes (AnimationRuntime, LODManager, etc.)
- `@tanstack/react-query` — `QueryClient`, `QueryClientProvider`
- `zustand` — `create`

---

## 15. Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_BACKEND_URL` | `http://localhost:8000` | Backend API base URL |
| `NODE_ENV` | `development` | Build mode |

---

*End of Runtime Contract*