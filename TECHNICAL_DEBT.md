# Technical Debt

This document catalogs the primary sources of technical debt in the Zaram frontend. Technical debt is defined as any code that is confusing, duplicated, or architecturally unsound, which will slow down future development.

## 1. Code Duplication and Dead Code

- **Issue**: Multiple, conflicting implementations of core components (`LivingOrb`, `ContextSurface`) and utility functions (`cn`) exist. The codebase is also littered with empty, scaffolded files and directories.
- **Impact**: Increases cognitive load for developers, creates confusion about the source of truth, and bloats the codebase.
- **Resolution**: A "Jubilee" event where all identified dead and duplicated code is deleted.

## 2. Disconnected Core Engine

- **Issue**: The `core` simulation and composition engine, which produces a rich `FrameState`, is almost entirely disconnected from the React UI. The UI uses a separate, simplistic state management system.
- **Impact**: This is the **most severe form of technical debt** in the project. It negates the primary architectural advantage of the system and prevents the UI from reflecting the nuanced state of the AI. All work to make the UI "smarter" is wasted effort until this is fixed.
- **Resolution**: Implement the "producer-consumer" pattern outlined in the State Management Audit. Create a `frameStore` and `useFrameState` hook, and refactor all state-visualizing components to be driven by it.

## 3. Fragmented and Conflicting State Management

- **Issue**: The Zustand stores are duplicated (`themeStore` vs. `settingsStore`), conflicting (`surfaceStore` vs. `windowStore`), and poorly organized.
- **Impact**: Leads to bugs, makes state management difficult to reason about, and encourages components to become tightly coupled to multiple stores.
- **Resolution**: Consolidate and refactor the stores into a domain-driven structure as outlined in the State Management Audit.

## 4. "Smart" Components

- **Issue**: Components like `CommandPalette` contain significant business logic, directly manipulate multiple global stores, and are not reusable.
- **Impact**: Violates the principle of separation of concerns, makes the code difficult to test and maintain, and leads to logic being repeated across the application.
- **Resolution**: Refactor all "smart" components into "dumb" presentational components. Extract business logic and state orchestration into dedicated modules in the `src/runtime` directory.

## 5. Inconsistent Styling

- **Issue**: There is no enforced design system. Some components use theme variables, while others use hardcoded values or generic CSS classes.
- **Impact**: Leads to a visually inconsistent UI and makes global theme changes difficult and error-prone.
- **Resolution**: Formalize the existing theme files into a documented design system and enforce its usage via code reviews and linting rules.