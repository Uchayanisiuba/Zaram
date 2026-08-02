# Zaram Desktop (TypeScript host)

An Electron desktop host for Zaram, written in TypeScript. See `CLAUDE.md` at the repo
root for the project contract.

## Unresolved: there are two desktop hosts

This directory and `electron/` are **two implementations of the same thing**. They are
not layers of one system; they are duplicates, built at different times.

The root build scripts do not agree on which one ships:

```json
"build:desktop": "cd desktop && npm run build && cd .. && electron-builder --win"
```

That builds `desktop/`, then hands off to `electron-builder`, which
`electron-builder.yml` points at `electron/main.js`. **It builds one host and packages
the other.**

One of the two must be chosen and the other deleted. Until that decision is made, treat
anything here as provisional and do not invest in it.

## Layout

```text
src/main/       Electron main process — entry, lifecycle, window manager
src/preload/    contextBridge isolation
src/ipc/        Channel definitions and handler registration
src/services/   Window, notification, shell, file dialog, download, settings
src/config/     Platform-aware paths, environment detection
tests/          Vitest suites
resources/      Splash screen
```

## Security

The configuration is correct and should stay that way:

- `contextIsolation: true`
- `nodeIntegration: false`
- `webSecurity: true`
- `sandbox: false` — required for backend spawning. Enable it if that dependency is
  removed.

All IPC handlers must validate input. The renderer reaches native capability only
through the preload bridge.

## Backend integration

`BackendService` spawns the Python backend as a child process and health-checks
`/health`. In production the backend is not yet packaged — Python must be present on
the target machine. That is unresolved distribution work, not a solved problem.

## Scope note

Earlier versions of this document described a "Developer Preview UI" with Orchestration,
Audit Terminal, Runtime Inspector, Capability Explorer and Filesystem Demo views wired
to Presence, Executive, Capability and Execution runtimes.

Those runtimes do not boot in the current backend, and those surfaces are out of scope.
The claims have been removed rather than carried forward.
