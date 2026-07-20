# Sprint Alpha.1 — Implementation Summary

## Root Causes Fixed

### 1. Chat Pipeline Broken
**Root cause:** The desktop runtime registered `FilesystemCapabilityPack` and `VSCodeCapabilityPack` but had NO handler for `conversation.runtime` (the Executive's fallback step). When a user sent a message, the plan was created but execution failed with "No handler registered for conversation.runtime".

**Fix:** Registered backend capability handlers in `bootstrap.ts` that call the Python backend's `/chat` endpoint via HTTP. The handler collects the SSE stream and returns the full LLM response as the execution output.

### 2. Confidence Was Hardcoded
**Root cause:** `ConversationPanel.tsx` called `desktop.executive.getConfidence()` which returned the Executive's internal intent confidence (default 0.5). This had nothing to do with the actual plan execution.

**Fix:** Changed to use `plan.confidence` which is computed by `ExecutiveRuntime.computePlanConfidence()` from actual evidence sources (workspace, VS Code, filesystem capabilities present in the plan).

### 3. Workspace Showed "root" / "0 projects"
**Root cause:** `WorkspaceRuntime` was initialized with an empty `rootPath`. `computeWorkspaceName('')` returned `'root'` and the snapshot showed 0 projects with 0 confidence.

**Fix:** `electron/main.js` now sets `workspace.setRootPath(config.appPath)` on startup. `WorkspaceRuntime.getWorkspaceSnapshot()` returns `'No workspace selected'` when no root is set.

### 4. Orb Stayed Idle
**Root cause:** Two problems: (a) the backend's `/ws/presence` WebSocket endpoint does not exist, so no frames were ever pushed; (b) `OrbEngine` used the legacy `window.electron.receive` API which was not exposed by the current preload.

**Fix:** (a) Added `PresenceRuntime.getRendererFrame()` which produces a FrameState-compatible object from the executive snapshot; (b) `electron/main.js` pushes these frames to the renderer at 30Hz via IPC; (c) `OrbEngine` now uses `desktop.presence.onFrame` from the active `window.zaram` bridge.

### 5. Browser Mode Had No Banner
**Root cause:** The frontend showed "Browser Mode" only in the footer. Users had no clear indication that desktop capabilities were unavailable.

**Fix:** Added a red warning banner at the top of the app when `backendStatus.state !== 'available'`, with a "Retry" button.

### 6. Developer Dashboard Was Default View
**Root cause:** `App.jsx` defaulted to `'orchestration'` and showed all nav items equally.

**Fix:** Default view is now `'conversation'`. Developer tools are collapsed under a toggleable "Developer" section.

### 7. Duplicate Runtime Health Page
**Root cause:** `RuntimeHealthDashboard` (sidebar widget) and `RuntimeInspector` (full page) duplicated runtime health information.

**Fix:** Removed `RuntimeHealthDashboard` component and `useRuntimeHealth` hook. `RuntimeInspector` is the single source of truth.

### 8. Missing IPC Surface
**Root cause:** `preload.js` and `ipc/channels.js` only exposed a subset of the desktop runtime's API. Executive plan/confidence/evidence, workspace state, and VS Code snapshot were unreachable from the frontend.

**Fix:** Added 20+ new IPC channels and handlers, exposed them through `window.zaram.executive`, `window.zaram.workspace`, `window.zaram.filesystem`, and `window.zaram.vscode`.

## Files Modified

| File | Change |
|------|--------|
| `electron/ipc/channels.js` | Added 20+ channels + MAIN_EVENTS entries |
| `electron/ipc/handlers.js` | Added handlers for executive, workspace, filesystem, vscode |
| `electron/preload.js` | Exposed new channels in `window.zaram` |
| `electron/main.js` | Pass `backendUrl` to bootstrap; push presence frames; remove dead WebSocket code; cleanup |
| `electron/backend/backendLauncher.js` | Unchanged |
| `frontend/src/desktop/desktop-bridge.ts` | Rewritten: `window.zaram` only, no `window.electron` |
| `frontend/src/App.jsx` | Default conversation view; developer mode; backend banner |
| `frontend/src/pages/ConversationPanel.tsx` | Backend status check; plan confidence/evidence |
| `frontend/src/components/OrbEngine/OrbEngine.tsx` | Use `desktop.presence.onFrame` |
| `frontend/src/components/RuntimeHealthDashboard.tsx` | **Removed** (duplicate) |
| `frontend/src/hooks/useRuntimeHealth.ts` | **Removed** (duplicate) |
| `desktop/src/runtime/bootstrap.ts` | `backendUrl` option; backend capability handlers; `callBackendChat` |
| `desktop/src/runtime/executive/executive-runtime.ts` | Pass query text in `conversation.runtime` step input |
| `desktop/src/runtime/workspace/workspace-runtime.ts` | "No workspace selected" when no root |
| `desktop/src/runtime/presence/presence-runtime.ts` | `getRendererFrame()` + `mapIntentToSystemState()` |

## Runtime Dependency Graph

```
electron/main.js
  ├── WindowManager
  ├── BackendLauncher ──► Python backend (FastAPI)
  │     └── /chat ──► Ollama LLM
  ├── Desktop Runtime (bootstrapPresence)
  │     ├── DI Container
  │     ├── PresenceRuntime (30Hz tick owner)
  │     │     ├── EngineAdapter (@zaram/engine)
  │     │     ├── CharacterRuntime
  │     │     ├── CognitiveBundle
  │     │     ├── WorldRuntime
  │     │     ├── ExecutiveRuntime
  │     │     ├── ExecutionRuntime
  │     │     └── WorkspaceRuntime
  │     ├── ExecutiveRuntime
  │     ├── ExecutionRuntime
  │     │     └── ExecutionInvoker
  │     ├── CapabilityRuntime
  │     ├── WorkspaceRuntime
  │     ├── FilesystemCapabilityPack ──► 12 handlers
  │     ├── VSCodeCapabilityPack ──► 4 handlers
  │     └── Backend capability handlers ──► HTTP /chat
  └── IPC Handlers ──► window.zaram (preload)
        └── Frontend (React)
              ├── App.jsx
              ├── ConversationPanel
              ├── Orchestration (OrbEngine)
              ├── RuntimeInspector
              └── AuditTerminal
```

## Startup Sequence

1. Electron `app.whenReady()` → `bootstrap()`
2. Build config + logger
3. Create static server (production)
4. Create WindowManager → splash + main window
5. Create desktop services
6. Create BackendLauncher
7. `loadDesktopRuntime()` → `bootstrapPresence({ backendUrl })`
   - DI container registers all runtimes
   - Registers Filesystem + VSCode + Backend capability handlers
   - Returns `{ container, presenceRuntime, embodiment }`
8. `presenceRuntime.start()` → begins 30Hz tick
9. `registerHandlers()` → all IPC channels active
10. Subscribe execution events → push to renderer
11. Subscribe executive snapshots → push to renderer
12. Subscribe workspace events → push to renderer
13. Subscribe VS Code events → push to renderer
14. Start presence frame timer (30Hz) → push `getRendererFrame()` to renderer
15. Create tray, shortcuts, updater, deep links, file associations
16. `backend.start()` → spawn Python process
17. Poll backend `/personalities` every 2s
18. On backend `available` → load app, show main window, close splash
19. On backend `unavailable` → show error screen

## IPC Verification

### Invokable Channels (Renderer → Main)
| Channel | Handler |
|---------|---------|
| `executive:plan` | `ExecutiveRuntime.plan()` |
| `executive:get-plan` | `ExecutiveRuntime.getCurrentPlan()` |
| `executive:get-confidence` | `ExecutiveRuntime.getConfidence()` |
| `executive:get-evidence` | `ExecutiveRuntime.getEvidence()` |
| `executive:get-metrics` | `ExecutiveRuntime.getCapabilityMetrics()` |
| `workspace:get-state` | `WorkspaceRuntime.getWorkspaceState()` |
| `workspace:get-context` | `WorkspaceRuntime.getWorkspaceContext()` |
| `workspace:get-snapshot` | `WorkspaceRuntime.getWorkspaceSnapshot()` |
| `workspace:discover` | `WorkspaceRuntime.discover()` |
| `workspace:get-all-projects` | `WorkspaceRuntime.getAllProjects()` |
| `runtime:execute-capability` | `ExecutionRuntime.execute()` |
| `runtime:get-execution-history` | `ExecutionRuntime.getHistory()` |
| `runtime:get-execution` | `ExecutionRuntime.getExecution()` |
| `filesystem:get-metrics` | `FilesystemCapabilityPack.getMetrics()` |
| `vscode:get-snapshot` | `VSCodeCapabilityPack.getAdapter().getSnapshot()` |
| ... plus all original channels | |

### Push Events (Main → Renderer)
| Event | Source |
|-------|--------|
| `presence:frame` | `PresenceRuntime.getRendererFrame()` (30Hz) |
| `presence:viewport` | Window resize |
| `runtime:executive-snapshot` | `ExecutiveRuntime.subscribe()` |
| `runtime:execution-event` | `ExecutionRuntime.subscribe()` |
| `workspace:event` | `WorkspaceRuntime.subscribe()` |
| `vscode:event` | `VSCodeAdapter.subscribe()` |
| `backend:status` | `BackendLauncher.onStatus()` |

## Event Flow Verification

### Chat Flow
1. User types message → `ConversationPanel.sendMessage()`
2. `desktop.executive.plan(text)` → IPC `executive:plan`
3. Main process calls `ExecutiveRuntime.plan(text)`
4. Plan returned with steps (e.g., `workspace.getWorkspaceSnapshot`, `conversation.runtime`)
5. For each step: `desktop.execution.execute(capabilityId, input)` → IPC `runtime:execute-capability`
6. Main process calls `ExecutionRuntime.execute()`
7. Execution queued → returns ID
8. 30Hz tick advances execution → `tickQueued` → `invokeHandler`
9. Handler for `conversation.runtime` calls `callBackendChat()`
10. `callBackendChat` POSTs to `/chat`, collects SSE tokens
11. Handler calls `controls.succeed({ response: fullText })`
12. Execution publishes `execution.completed` event
13. Frontend receives event via `desktop.execution.onEvent`
14. `waitForExecution` resolves → timeline updated
15. `buildOrchestratedResponse` assembles final message with plan confidence + evidence
16. Message displayed in chat

### Presence Frame Flow
1. `PresenceRuntime.tick()` runs at 30Hz
2. Advances Executive, Execution, Workspace, Cognitive, World, Character runtimes
3. `electron/main.js` timer calls `presenceRuntime.getRendererFrame()` at 30Hz
4. Frame pushed to renderer via `presence:frame` IPC event
5. `OrbEngine` receives frame → `renderer.setFrameState()`
6. Orb renders with updated colors/energy based on system state

### Workspace Flow
1. `electron/main.js` calls `workspace.setRootPath(config.appPath)` on startup
2. `WorkspaceRuntime` initializes with project root
3. `workspace.discover([], 'shallow')` triggered after 500ms
4. WorkspaceIndexer scans root for manifests, configs, entrypoints
5. Projects detected → `workspace.discovered` event published
6. Main process pushes event to renderer
7. `useWorkspaceContextStore` receives event → updates snapshot
8. Conversation panel shows workspace context pill

## Backend Verification

- **Health check:** `/personalities` endpoint polled every 2s
- **Chat endpoint:** `/chat` accepts `{ text, model, personality }`, returns SSE stream
- **Fallback:** If new kernel disabled (`USE_NEW_KERNEL=false`), legacy `OllamaLLM` + `ConversationManager` path is used
- **Error handling:** Backend errors are propagated through execution controls → shown in conversation UI
- **Reconnection:** BackendLauncher auto-restarts on crash with 3s delay

## Workspace Verification

- Root path set to `config.appPath` on startup
- `getWorkspaceSnapshot()` returns:
  - `workspace`: folder name (not "root")
  - `framework`: detected or "none"
  - `language`: detected or "none"
  - `projects`: actual count
  - `confidence`: computed from evidence (0-100%)
  - `open_modules`: detected project names
- When no root path: returns `"No workspace selected"`, `0 projects`, `0% confidence`

## Executive Verification

- `plan(query)` always returns a valid plan with at least one step
- `conversation.runtime` fallback step includes `{ text: query, prompt: query }` in input
- `computePlanConfidence()` derives confidence from evidence sources:
  - Workspace capability present → +15%
  - VS Code capability present → +15%
  - Filesystem capability present → +15%
  - Base: 50%, max: 98%
- `getEvidence()` returns workspace name, active file, language, git branch, diagnostics
- Plan confidence and evidence are used directly by `ConversationPanel` (not the executive's internal intent confidence)

## Electron Verification

- **Entry point:** `electron/main.js` (not `desktop/src/main/index.ts`)
- **Preload:** `electron/preload.js` exposes `window.zaram`
- **IPC:** All channels whitelisted in `RENDERER_INVOKABLE`
- **Context isolation:** `contextIsolation: true`, `nodeIntegration: false`
- **Window hardening:** `setWindowOpenHandler` denies new windows; `will-navigate` blocked
- **Single instance:** `app.requestSingleInstanceLock()`
- **Cleanup:** `before-quit` stops timers, shuts down presence runtime, stops backend
- **Dead code removed:** WebSocket connection to non-existent `/ws/presence` endpoint removed

## Acceptance Test

See `docs/SPRINT_ALPHA_1_ACCEPTANCE_TEST.md` for the full verification checklist.
