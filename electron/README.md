# Zaram Desktop (JavaScript host)

An Electron desktop host for Zaram, written in JavaScript. This is the host that
`electron-builder.yml` currently packages (`main: electron/main.js`).

See `CLAUDE.md` at the repo root for the project contract.

## Unresolved: there are two desktop hosts

This directory and `desktop/` are **two implementations of the same thing**. The root
`build:desktop` script compiles `desktop/` and then packages `electron/` — it builds one
and ships the other. One must be chosen and the other deleted before any release.

## Layout

```text
main.js              App entry: lifecycle, window, backend, IPC, native
preload.js           contextBridge — whitelisted IPC only
config.js            Dev/prod config and platform-aware paths
logger.js            Structured JSON logging
staticServer.js      Production: serve frontend/dist, reverse-proxy the backend
ipc/                 channels.js (names), handlers.js (channel -> service)
backend/             backendLauncher.js, health.js
window/              windowManager.js, windowState.js, splash.js, assets/
services/            Window, Notification, Shell, FileDialog, Download, Settings
native/              Tray, AutoUpdater, FileAssociations, DeepLinks, GlobalShortcuts
```

The `native/` modules are abstractions and foundations, not finished features.

## How it runs

- **Dev:** Electron loads the Vite dev server at `http://localhost:5173`. The renderer
  reaches the backend through the same-origin Vite proxy.
- **Prod:** Electron serves `frontend/dist` from a local static server on
  `127.0.0.1:5180` and reverse-proxies API routes to the backend. One origin, no CORS,
  and the backend is not exposed to arbitrary web origins.

## Backend

Electron spawns the backend as a child process
(`python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`). Python is resolved
in order: `ZARAM_PYTHON` env var, then the project `.venv`, then `python3`, then
`python`. If the backend is unavailable an error screen is shown and Electron retries.

## Scripts

Earlier versions of this document listed `npm run desktop:dev`,
`desktop:build:renderer`, `desktop:build`, `desktop:pack`, `test:desktop` and
`lint:desktop`. **None of those scripts exist** in the root `package.json`. The
documented developer workflow for this host is currently missing.

What does exist at the root: `dev`, `dev:frontend`, `dev:backend`, `dev:desktop`,
`build`, `build:frontend`, `build:desktop`, `build:desktop:portable`, `preview`.

## Packaging

Windows installer and portable targets require the frontend to be built first. Python
must already be present on the target machine — bundling it is unresolved. There is no
code signing.

Distribution is not a solved problem here. Anyone planning a release should treat this
section as open work rather than instructions.
