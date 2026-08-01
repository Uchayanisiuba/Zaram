# Architecture Audit

This document outlines the major architectural issues found in the Zaram frontend codebase.

## 1. Duplicate Components & Dead Code

A significant amount of code is duplicated or unused, creating confusion and increasing the maintenance burden.

- **`LivingOrb`**: The component at `src/components/orb/LivingOrb/` is a simplified, deprecated prototype. The active and feature-rich implementation is located at `src/components/orb/LivingOrb.tsx`.
  - **Recommendation**: Delete the entire `src/components/orb/LivingOrb/` directory and all its children.

- **`ContextSurface`**: Two conflicting implementations exist. `src/components/surfaces/ContextSurface.tsx` is a complex, state-managed component that aligns with the intended architecture. `src/features/surface/ContextSurface.tsx` is a simpler, stateless version that represents a divergent and abandoned pattern.
  - **Recommendation**: Delete `src/features/surface/ContextSurface.tsx`.

- **`cn` Utility**: The `cn` utility function for merging Tailwind classes is defined in both `src/lib/utils.ts` and `src/utils/cn.ts`.
  - **Recommendation**: Consolidate into a single `src/lib/utils.ts` file and delete `src/utils/cn.ts`.

- **Empty Scaffolding**: Numerous files and folders are empty placeholders, adding noise to the project structure.
  - **Affected**: `src/runtime/engines`, `src/runtime/modules`, `src/runtime/services`, `src/hooks/useAnimation.ts`, `src/hooks/useGlass.ts`, `src/hooks/useSpatialLayout.ts`, `src/hooks/useViewport.ts`.
  - **Recommendation**: Delete these empty files and directories.

## 2. Poor Folder Organization & Incorrect Abstractions

The project structure is inconsistent and violates the principle of discoverability.

- **`features` Directory**: The `src/features` directory appears to be a remnant of a parallel or deprecated development effort. It introduces conflicting architectural patterns and should be removed.

- **`core` vs. `runtime`**: This is the most critical organizational issue.
  - **`src/core`**: Contains the headless, renderer-agnostic simulation and composition engine. This is the "brain" of Zaram.
  - **`src/runtime`**: Is intended to be the application-level integration layer that connects the `core` engine to the React UI.
  - **Problem**: The naming is confusing, and the `runtime` directory is empty. This makes it extremely difficult to understand the intended data flow.
  - **Recommendation**: Rename `src/core` to `src/engine` to more accurately reflect its purpose. The `src/runtime` directory should then be populated with the logic that bridges the `engine` to the UI.

- **"Smart" Components**: Components like `CommandPalette` are overly intelligent. They directly manipulate multiple global state stores and contain business logic that should reside in the application runtime. This creates tight coupling and reduces reusability.
  - **Recommendation**: Refactor smart components into "dumb" presentational components. Move business logic and state orchestration to dedicated modules in the `src/runtime` directory.

## 3. Architectural Gap: Disconnected Core Engine

The single biggest architectural flaw is that the sophisticated `core` engine is almost completely disconnected from the UI.

- **The `FrameState` Contract**: The `FrameComposer` in `src/core/frame/composer.ts` produces a rich `FrameState` object that is meant to be the single source of truth for the renderer.
- **The Gap**: The UI is not consuming this `FrameState`. Instead, components are relying on simple, fragmented Zustand stores (e.g., `orbStore`'s simple `'idle' | 'thinking'` state).
- **Impact**: This completely defeats the purpose of the core engine and leads to a "dumb" UI that cannot reflect the nuanced state of the simulation.
- **Recommendation**: Create a `useFrameState` hook that subscribes to the `FrameState` produced by the `FrameComposer`. Refactor all components (`LivingOrb`, `SpatialBackground`, etc.) to be driven by this hook.

## 4. Styling Inconsistencies

- **Theme Consumption**: Some components correctly use the theme objects from `src/theme` (e.g., `glass.background`), while others use hardcoded values or generic CSS classes (`glass-panel`).
- **Recommendation**: Enforce a strict policy of using the design tokens and theme objects from the `src/theme` directory for all styling.