# State Management Audit

This document analyzes the Zustand-based state management layer of the Zaram frontend.

## Current State

The state management layer is fragmented, duplicated, and disconnected from the core application engine. It is the single largest source of architectural technical debt.

### Key Issues:

1.  **Duplicated State & Conflicting Stores**:
    -   **Theme**: `themeStore.ts` and `settingsStore.ts` both manage the application theme, creating a direct conflict.
    -   **Surfaces/Windows**: `surfaceStore.ts` and `windowStore.ts` both manage floating panels, representing two conflicting architectural approaches to the same problem.
    -   **Command Palette**: `paletteStore.ts` and the empty `commandPaletteStore.ts` point to further duplication.

2.  **Poor Store Organization**:
    -   The stores are organized in a flat, feature-based list (`orbStore`, `shellStore`, etc.). This structure is not scalable and will become unmanageable as the application grows.

3.  **Architectural Gap: Disconnected from Core Engine**:
    -   This is the most critical issue. There is **no store that holds the `FrameState`** produced by the `FrameComposer` in `src/core`.
    -   Components are subscribing to simple, derivative state (e.g., `orbStore`'s `'idle'` state) instead of the rich, multi-dimensional data from the core engine. This renders the engine's detailed simulation useless for the UI.

4.  **Potential for Unnecessary Rerenders**:
    -   Stores like `workspaceStore` combine rapidly changing data (camera position) with potentially static data. Any component subscribing to the static data will be forced to rerender whenever the camera moves.

## Recommendations

A major refactoring of the state management layer is required before adding new features.

### 1. Consolidate and Refactor Stores

-   **Single Source of Truth**: Immediately resolve the duplications.
    -   Delete `settingsStore.ts` and `windowStore.ts`.
    -   Standardize on `themeStore.ts` for theming and `surfaceStore.ts` for all floating surfaces.
-   **Centralize Logic**: Move logic out of components and into the stores/runtime. For example, the logic in `CommandPalette` for finding or creating a surface should be an action within `surfaceStore` itself (e.g., `openSurface(type, title, { focusIfExisting: true })`).

### 2. Reorganize Stores by Domain

Reorganize the `src/stores` directory to match the proposed domain-driven structure. This will improve scalability and clarity.

```
/src/stores
├── core/
│   ├── frameStore.ts      // CRITICAL: Holds the sacred FrameState
│   └── runtimeStore.ts    // Performance metrics, etc.
├── workspace/
│   ├── surfaceStore.ts
│   └── workspaceStore.ts  // Camera, etc.
├── orb/
│   └── orbStore.ts        // High-level commands/intent for the orb
├── user/
│   ├── settingsStore.ts
│   └── presenceStore.ts
└── ui/
    ├── commandPaletteStore.ts
    └── shellStore.ts
```

### 3. Bridge the Gap to the Core Engine

This is the most important change.

-   **Create `frameStore.ts`**: This new store will have one primary piece of state: `frame: FrameState`.
-   **Create a `RuntimeManager`**: In the `src/runtime` directory, create a `RuntimeManager` class.
    -   This manager will be responsible for creating an instance of the `FrameComposer`.
    -   It will run a `requestAnimationFrame` loop.
    -   On each frame, it will call `composer.compose(...)` to get the latest `FrameState`.
    -   It will then call `useFrameStore.setState({ frame: newFrameState })`.
-   **Refactor Hooks**: Create a `useFrameState` hook that subscribes to this store.
-   **Refactor Components**: All components that visualize the application's state (`LivingOrb`, `SpatialBackground`, etc.) **must** be refactored to use `useFrameState`. The old `orbStore` should be relegated to managing high-level user intent, not visual state.

By implementing this "producer-consumer" pattern, the UI will finally be connected to the core engine, unlocking the full potential of the simulation-driven architecture.