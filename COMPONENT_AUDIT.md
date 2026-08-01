# Component Audit

This document provides a detailed audit of the major components in the Zaram frontend.

## Shell Components

The main UI shell is a skeleton that provides structure but lacks implementation.

- **Components**: `App.tsx`, `TopNavigation.tsx`, `LeftContextRail.tsx`, `CenterWorkspace.tsx`, `RightRuntimePanel.tsx`, `BottomCommandDock.tsx`
- **Purpose**: To define the primary layout regions of the Zaram OS.
- **Analysis**: All shell components except `BottomCommandDock` are non-functional placeholders. The layout is rigid and uses absolute positioning.
- **Recommendations**:
  - **Remain**: The shell components should remain as they define the fundamental structure.
  - **Refactor**: `App.tsx` should be refactored to use a more flexible layout system (e.g., CSS Grid) to better support dynamic surfaces.
  - **Implement**: The placeholder components need to be built out with their intended functionality.

## Core UI Components

These components provide the main interactive elements of the application.

### `LivingOrb.tsx`

- **Purpose**: The central AI companion, responsible for visualizing the system's state.
- **Dependencies**: `framer-motion`, `lucide-react`, `orbStore`, numerous sub-components.
- **Complexity**: High. It is a composite component with many layers of animation.
- **Future Scalability**: Good, as it is composed of many smaller, single-purpose components.
- **Performance**: Needs evaluation, especially the `AnimatePresence` and multiple layers of animation.
- **Should it remain?**: Yes. It is the heart of the UI.
- **Should it be broken apart?**: It is already well-decomposed.
- **Architectural Issue**: It is driven by the simple `orbStore` instead of the rich `FrameState` from the core engine. This is its single biggest flaw.
- **Recommendation**: **Crucial Refactor**. This component *must* be refactored to be driven by a `useFrameState` hook that consumes the output of the `FrameComposer`.

### `CommandPalette.tsx`

- **Purpose**: Provides a global command interface (Cmd/Ctrl+K).
- **Dependencies**: `framer-motion`, `paletteStore`, `surfaceStore`, `orbStore`.
- **Complexity**: High. It manages its own state, keyboard listeners, and directly manipulates global state.
- **Reusability**: Poor, due to tight coupling with multiple global stores.
- **Should it remain?**: Yes, the functionality is essential.
- **Should it be broken apart?**: **Yes, urgently.**
  - The UI should become a "dumb" presentational component.
  - The list of commands and their execution logic should be managed by a `CommandRegistry` in the `src/runtime` directory.
  - It should not directly call `useSurfaceStore` or `useOrbStore`. It should dispatch events to the `RuntimeBus`.

### `SpatialBackground.tsx`

- **Purpose**: Provides an ambient, animated background.
- **Dependencies**: `framer-motion`, `orbStore`.
- **Complexity**: Low.
- **Architectural Issue**: Like the `LivingOrb`, its animations are tied to the simple `orbStore`.
- **Recommendation**: Refactor to be driven by the `FrameState` (e.g., `energy`, `activity`) for a more dynamic and responsive background.

### `RuntimeHUD.tsx`

- **Purpose**: Displays system status and performance metrics.
- **Dependencies**: `framer-motion`, `orbStore`.
- **Complexity**: Low.
- **Architectural Issue**: Displays mock data and is tied to the simple `orbStore`.
- **Recommendation**: Connect the component to the `runtimeStore` to display real performance data and derive its status from the `FrameState`.

## Surface Components

- **`WorkspaceSurface.tsx`**: A placeholder within the `CenterWorkspace`.
- **`ContextSurface.tsx`**: The primary component for creating floating windows/surfaces. It is well-architected internally (using `useDragControls`, managing z-index via the store) but is used by the flawed `CommandPalette`.
- **Recommendation**: The `ContextSurface` component itself is good, but the system for creating and managing surfaces needs to be centralized in the application runtime, not handled on a case-by-case basis within the `CommandPalette`.