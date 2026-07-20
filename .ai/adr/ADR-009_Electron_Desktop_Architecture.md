# ADR-009: Electron Desktop Architecture
**Status:** Accepted
**Context:** Browser-only deployment limits OS integration (global hotkeys, system tray, background processes).
**Decision:** Adopt Electron as the official desktop platform. Main process handles OS integration; Renderer process handles WebGL.
**Consequences:** Increases app bundle size. Requires IPC management.