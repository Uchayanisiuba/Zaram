# Refactor Plan

This document outlines a sequential, multi-step plan to address the technical debt identified in the audit and establish a stable architectural foundation for future development.

**Guiding Principle**: Do not write any new feature code until this refactoring is complete.

## Step 1: The Jubilee (Code Deletion)

The first step is to remove all identified dead and duplicated code. This is a low-risk, high-reward action that will immediately simplify the codebase.

- [ ] Delete the `src/components/orb/LivingOrb/` directory.
- [ ] Delete `src/features/surface/ContextSurface.tsx`.
- [ ] Delete `src/utils/cn.ts` (and update imports to point to `src/lib/utils.ts`).
- [ ] Delete all empty files and directories in `src/runtime`, `src/hooks`, etc.
- [ ] Delete `src/stores/settingsStore.ts`, `src/stores/windowStore.ts`, and `src/stores/commandPaletteStore.ts`.

## Step 2: Bridge the Core Engine to the UI

This is the most critical step. The goal is to connect the `FrameComposer` to the React UI.

- [ ] Create `src/stores/core/frameStore.ts`. This store will hold the `FrameState` object.
- [ ] Create a `useFrameState` hook that subscribes to this store.
- [ ] Create a `RuntimeManager` class in `src/runtime`. This class will instantiate the `FrameComposer` and run a `requestAnimationFrame` loop to update the `frameStore` on every frame.
- [ ] Instantiate and run the `RuntimeManager` in the main `App.tsx` file (or a `RuntimeProvider`).

## Step 3: Refactor the Living Orb

With the `useFrameState` hook available, refactor the `LivingOrb` to be driven by it.

- [ ] In `LivingOrb.tsx`, replace `useOrbStore` with `useFrameState`.
- [ ] Go through each sub-component (`Aura`, `Pulse`, `ThinkingGlow`, etc.) and modify its animations to be driven by the numerical values from the `frame.visual` object (e.g., `energy`, `focus`, `activity`).
- [ ] Refactor the `Waveform` components to be driven by `frame.audio.smoothedRms`.
- [ ] Remove the old, simplistic `orbState` from `orbStore`. This store should now be used for high-level intent, not visual state.

## Step 4: Refactor "Smart" Components

De-couple components from the state layer.

- [ ] **`CommandPalette`**:
    -   Transform the component to be purely presentational. It should receive commands and an `onExecute` callback as props.
    -   Create a `CommandRegistry` module in `src/runtime` that defines all commands and their actions.
    -   The logic for opening surfaces should be moved into a centralized action in `surfaceStore`.
    -   The `CommandRegistry` will be responsible for calling the `surfaceStore` action.

- [ ] **`SpatialBackground` & `RuntimeHUD`**:
    -   Refactor these components to be driven by the `useFrameState` hook and the `runtimeStore`.

## Step 5: Consolidate and Reorganize State

Finalize the state management refactor.

- [ ] Reorganize the `src/stores` directory into the domain-driven structure (`core`, `workspace`, `ui`, etc.).
- [ ] Update all imports across the application to point to the new store locations.
- [ ] Ensure all state duplication has been eliminated.

## Step 6: Formalize the Design System

- [ ] Create a `DESIGN_SYSTEM.md` file to document the color palette, typography, and spacing.
- [ ] Audit all components in `src/components/design-system` and ensure they have a consistent API (props, variants).
- [ ] Perform a codebase-wide search for hardcoded style values and replace them with theme variables.

After completing these six steps, the Zaram frontend will have a stable, scalable, and maintainable architecture, ready for the next five years of development.