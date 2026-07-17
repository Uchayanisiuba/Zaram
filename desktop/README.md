# Zaram Desktop Foundation

## Architecture Summary

The Electron Desktop Foundation provides a secure, production-ready desktop host for the Zaram application. It preserves the existing React frontend and Python backend while adding native desktop capabilities through a layered architecture.

### Process Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    IPC Bridge    ┌─────────────────────┐  │
│  │   Main       │ ◄──────────────► │   Preload           │  │
│  │   Process    │                  │   (contextBridge)   │  │
│  │              │                  │                     │  │
│  │  • Window    │                  │  • Expose APIs      │  │
│  │    Manager   │                  │  • Validate input   │  │
│  │  • Backend   │                  │  • No Node APIs     │  │
│  │    Service   │                  │                     │  │
│  │  • Desktop   │                  └─────────────────────┘  │
│  │    Services  │                         │                  │
│  │  • IPC       │                         ▼                  │
│  │    Handlers  │                  ┌─────────────────────┐  │
│  │  • Lifecycle │                  │   Renderer          │  │
│  │              │                  │   (React App)       │  │
│  └──────────────┘                  │                     │  │
│         │                          │  • Existing UI      │  │
│         │                          │  • window.electron  │  │
│         │                          │  • HTTP to backend  │  │
│         ▼                          └─────────────────────┘  │
│  ┌──────────────┐                                            │
│  │   Backend    │                                            │
│  │   (Python)   │                                            │
│  │   :8000      │                                            │
│  └──────────────┘                                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Security Model

1. **Context Isolation**: Enabled by default. Renderer process cannot access Node.js APIs directly.
2. **Sandbox**: Disabled for initial foundation to allow backend spawning. Can be enabled in future milestones.
3. **Node Integration**: Disabled in renderer.
4. **Preload Script**: Only exposes specific, validated APIs via `contextBridge`.
5. **IPC Validation**: All IPC handlers validate input before processing.
6. **No Direct Node APIs**: React code interacts only through `window.electron` API.

### Directory Structure

```
desktop/
├── src/
│   ├── main/
│   │   ├── index.ts          # Electron main entry point
│   │   ├── lifecycle.ts      # App initialization & shutdown
│   │   └── window-manager.ts # BrowserWindow management
│   ├── preload/
│   │   └── index.ts          # Context bridge isolation
│   ├── ipc/
│   │   ├── channels.ts       # Channel definitions & types
│   │   └── bridge.ts         # IPC handler registration
│   ├── services/
│   │   ├── desktop-service.ts # Service interfaces
│   │   ├── backend-service.ts # Backend lifecycle
│   │   ├── window-service.ts  # Window controls
│   │   ├── notification-service.ts
│   │   ├── shell-service.ts
│   │   ├── file-dialog-service.ts
│   │   ├── download-service.ts
│   │   └── settings-service.ts
│   └── config/
│       ├── paths.ts          # Platform-aware paths
│       └── environment.ts    # Environment detection
├── tests/
│   ├── lifecycle.test.ts
│   ├── window-manager.test.ts
│   ├── backend-service.test.ts
│   ├── settings-service.test.ts
│   └── channels.test.ts
├── resources/
│   └── splash.html           # Startup splash screen
├── package.json
├── tsconfig.json
├── electron-builder.json
└── vitest.config.ts
```

### IPC Architecture

The IPC layer uses a channel-based architecture:

- **Window**: Window controls (maximize, minimize, restore)
- **Notification**: Desktop notifications
- **Shell**: OS shell integration
- **File Dialog**: Native file pickers
- **Download**: Download management (placeholder)
- **Settings**: Persistent key-value storage
- **Backend**: Backend health and status
- **Clipboard**: Clipboard operations
- **System**: OS information

### Backend Integration

The `BackendService` manages the Python backend lifecycle:

1. **Development Mode**: Spawns `python main.py` from the backend directory
2. **Production Mode**: Spawns packaged backend executable
3. **Health Checks**: Periodic HTTP health checks to `/health` endpoint
4. **Auto-reconnect**: Detects backend restarts (foundation only)
5. **Graceful Shutdown**: SIGTERM on app quit

### Platform Support

- **Windows**: Primary target (NSIS installer + portable)
- **macOS**: Supported via path abstractions
- **Linux**: Supported via path abstractions

### Development Mode

- React frontend served from Vite dev server (localhost:5173)
- Backend runs directly via Python
- Electron main process connects to dev server
- Hot reload supported for frontend

### Production Build

- Frontend built to `dist/frontend/`
- Desktop compiled to `dist/desktop/`
- Packaged with electron-builder
- Windows installer (NSIS) and portable builds

## Files Created

1. `desktop/src/main/index.ts` - Main process entry
2. `desktop/src/main/lifecycle.ts` - App lifecycle management
3. `desktop/src/main/window-manager.ts` - Window state & controls
4. `desktop/src/preload/index.ts` - Context bridge isolation
5. `desktop/src/ipc/channels.ts` - IPC channel definitions
6. `desktop/src/ipc/bridge.ts` - IPC handler registration
7. `desktop/src/ipc/index.ts` - IPC barrel export
8. `desktop/src/services/backend-service.ts` - Backend lifecycle
9. `desktop/src/services/desktop-service.ts` - Service interfaces
10. `desktop/src/services/window-service.ts` - Window service
11. `desktop/src/services/notification-service.ts` - Notification service
12. `desktop/src/services/shell-service.ts` - Shell service
13. `desktop/src/services/file-dialog-service.ts` - File dialog service
14. `desktop/src/services/download-service.ts` - Download service
15. `desktop/src/services/settings-service.ts` - Settings service
16. `desktop/src/services/index.ts` - Services barrel export
17. `desktop/src/config/paths.ts` - Platform-aware paths
18. `desktop/src/config/environment.ts` - Environment detection
19. `desktop/resources/splash.html` - Splash screen
20. `desktop/package.json` - Desktop package config
21. `desktop/tsconfig.json` - TypeScript config
22. `desktop/electron-builder.json` - Packaging config
23. `desktop/vitest.config.ts` - Test config
24. `desktop/tests/lifecycle.test.ts` - Lifecycle tests
25. `desktop/tests/window-manager.test.ts` - Window tests
26. `desktop/tests/backend-service.test.ts` - Backend tests
27. `desktop/tests/settings-service.test.ts` - Settings tests
28. `desktop/tests/channels.test.ts` - Channel tests
29. Updated `package.json` - Root scripts & dependencies
30. Updated `vite.config.ts` - Electron alias support
31. Removed `frontend/tsconfig.node.json.json` - Duplicate file

## Files Modified

1. `package.json` - Added Electron dependencies, scripts, dev tools
2. `vite.config.ts` - Added Electron main process alias

## Desktop Architecture Diagram

See "Architecture Summary" section above for the process diagram.

## Security Model Explanation

The desktop foundation implements a defense-in-depth security model:

1. **Renderer Process Isolation**: React code runs in a standard renderer with no Node.js access.
2. **Preload Script**: Acts as a secure bridge, exposing only validated APIs through `contextBridge`.
3. **Input Validation**: All IPC handlers validate input types and values.
4. **No Direct Node APIs**: The React frontend cannot call `require()`, `process`, or any Node.js APIs.
5. **Path Traversal Protection**: Backend static file serving resolves paths canonically to prevent traversal.
6. **Context Isolation**: Enabled by default, preventing prototype pollution attacks.
7. **Sandbox**: Initially disabled for backend spawning flexibility; can be enabled in future.

## Test Results

Tests are configured with Vitest. Run with:

```bash
cd desktop && npm test
```

Current test coverage:
- `lifecycle.test.ts`: App initialization and service provision
- `window-manager.test.ts`: Window creation and state management
- `backend-service.test.ts`: Backend service configuration and status
- `settings-service.test.ts`: Settings persistence and retrieval
- `channels.test.ts`: IPC channel definition validation

## Remaining Technical Debt

1. **Backend Auto-start**: Currently spawns backend; needs better error handling and retry logic
2. **Sandbox Mode**: Should be enabled once backend spawning is refactored
3. **Auto-updater**: Placeholder only; needs implementation
4. **System Tray**: Placeholder only; needs implementation
5. **File Associations**: Placeholder only; needs implementation
6. **Deep Links**: Placeholder only; needs implementation
7. **Global Shortcuts**: Placeholder only; needs implementation
8. **Download Manager**: Basic structure only; needs full implementation
9. **Error Screen**: Backend unavailability screen not implemented
10. **Production Backend Packaging**: Python backend not yet packaged for production
11. **Code Signing**: Not implemented (not required for milestone)
12. **Installer Logic**: Basic NSIS/portable config; needs manifest and smart uninstall

## Suggested Next Milestone

**Orb Runtime 2.0**: Implement the Orb as the primary desktop embodiment, leveraging the desktop foundation for native window management, system integration, and runtime isolation.

## Developer Preview UI

The desktop now exposes a full Developer Preview UI that connects the frontend directly to the existing TypeScript runtime system. All views are read-only observers; no runtime logic is duplicated in the UI.

### Views

| View | Purpose | Runtime Source |
|------|---------|----------------|
| **Orchestration** | Living Orb + runtime state | PresenceRuntime, ExecutiveRuntime |
| **Conversation** | Chat panel wired to Executive Runtime | ExecutiveRuntime, ExecutionRuntime, WorkspaceRuntime (context) |
| **Audit Terminal** | Execution + Workspace event stream | ExecutionRuntime, WorkspaceRuntime |
| **Runtime Inspector** | All registered runtimes, health, Workspace Snapshot | PresenceRuntime diagnostics, WorkspaceRuntime |
| **Capability Explorer** | Read-only Capability Runtime registry | CapabilityRuntime |
| **Filesystem Demo** | Test filesystem capabilities | ExecutionRuntime → FilesystemCapabilityPack |

### Runtime Integration

The frontend never imports backend execution logic. Communication flows through:

```
Renderer (React)
    ↓ IPC / preload
Main Process (Electron)
    ↓ DI container
Runtime System (Presence, Executive, Capability, Execution)
    ↓ Event Bus (per-runtime pub/sub)
Filesystem Capability Pack
```

### New IPC Channels

Runtime-specific channels added to the desktop preload:

- `runtime:get-presence-health` — Presence diagnostics
- `runtime:get-presence-status` — Presence status + frame rate
- `runtime:get-executive-snapshot` — Executive state + intent
- `runtime:get-capability-snapshot` — Full capability registry
- `runtime:get-capability-by-id` — Single capability descriptor
- `runtime:get-capability-by-category` — Category-filtered capabilities
- `runtime:get-execution-history` — Execution history
- `runtime:get-execution` — Single execution record
- `runtime:execute-capability` — Execute through Execution Runtime
- `runtime:cancel-execution` — Cancel execution
- `runtime:retry-execution` — Retry failed execution
- `runtime:get-world-state` — World state snapshot
- `runtime:get-cognitive-state` — Cognitive state
- `runtime:get-attention-state` — Attention state
- `runtime:get-relationship-state` — Relationship state
- `runtime:get-character-frame` — Character frame

### Event Forwarding

The main process forwards runtime events to the renderer:

- `runtime:executive-snapshot` — Live executive state updates
- `runtime:execution-event` — Live execution lifecycle events

### Desktop Bridge

`frontend/src/desktop/desktop-bridge.ts` provides a unified API that works in both:
- Electron desktop (`window.zaram` from preload)
- Browser mode (`window.electron` fallback with graceful degradation)
