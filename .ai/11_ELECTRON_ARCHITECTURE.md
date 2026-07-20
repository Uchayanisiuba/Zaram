# Electron Architecture
**Version:** 1.0 | **Status:** Frozen

## 1. Purpose
Electron is the official desktop platform for Zaram. It hosts the embodiments and manages OS-level integrations.

## 2. Process Architecture
```mermaid
graph TD
    A[Main Process] -->|IPC| B[Renderer Process]
    A -->|Lifecycle| C[Presence Runtime Host]
    B -->|WebGL| D[Orb / MetaHuman Renderer]
    A -->|OS Events| E[System Tray / Global Hotkeys]