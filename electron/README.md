# Zaram Desktop (Electron) — Developer Guide

This folder hosts the Electron **desktop host** that wraps the existing React
frontend (`frontend/`) and the Python backend (`backend/`). It is a pure
architectural migration: the existing frontend and backend are untouched in
behaviour.

## Layout

```
electron/
  main.js              # App entry: lifecycle, window, backend, IPC, native
  preload.js           # Secure contextBridge (whitelisted IPC only)
  config.js            # Dev/prod config + platform-aware paths (no electron import)
  logger.js            # Structured JSON logging (no print)
  staticServer.js      # Prod: serve frontend/dist + reverse-proxy backend
  ipc/
    channels.js        # Single source of truth for all IPC channel names
    handlers.js        # Maps channels -> desktop services
  backend/
    backendLauncher.js # Spawn Python, health-check, reconnect
    health.js          # Lightweight health probe
  window/
    windowManager.js   # Main window + state persistence + error state
    windowState.js     # Pure load/save/clamp of window geometry
    splash.js          # Sandboxed splash window
    assets/splash.html # Static splash
    assets/error.html  # Friendly backend-unavailable screen
  services/            # DesktopService, Window, Notification, Shell,
                       # FileDialog, Download, Settings, FileSystem
  native/              # Tray, AutoUpdater, FileAssociations, DeepLinks,
                       # GlobalShortcuts (abstractions / foundations)
  electron-builder.yml # Windows installer + portable packaging
```

The renderer bridge lives in the frontend at `frontend/src/desktop/`
(`bridge.js`, `useBackendStatus.js`). It is non-visual and degrades gracefully
in a plain browser.

## Scripts (run from repo root)

| Command | Purpose |
| --- | --- |
| `npm run desktop:dev` | Run Vite dev server + Electron (hot reload). Electron auto-launches the backend. |
| `npm run desktop:build:renderer` | Build the frontend to `frontend/dist`. |
| `npm run desktop:build` | Build frontend then package Windows installer + portable via electron-builder. |
| `npm run desktop:pack` | Build + unpacked (dir) package for quick testing. |
| `npm run test:desktop` | Run the Node `node:test` desktop test suite (`test/`). |
| `npm run lint:desktop` | Syntax-check the main process / preload / static server. |

## How it runs

- **Dev:** Electron loads `http://localhost:5173` (the Vite dev server). The
  renderer calls the backend through the same-origin Vite proxy.
- **Prod:** Electron serves `frontend/dist` from a local static server on
  `127.0.0.1:5180` and reverse-proxies API routes to the backend. One origin,
  no CORS, backend hidden from arbitrary web origins.

## Backend

Electron spawns the backend as a child process
(`python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`). Python is
resolved in this order: `ZARAM_PYTHON` env → project `.venv` → `python3` →
`python`. If the backend is unavailable, a friendly error screen is shown and
Electron keeps trying to reconnect.

## Packaging prerequisites

The Windows installer/portable targets require the frontend to be built first
(`desktop:build:renderer`). Python is expected to be available on the target
machine for now (bundling Python via PyInstaller is tracked as technical debt).
