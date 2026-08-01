# Zaram Engine Audit

This document provides a comprehensive audit of the Zaram project's core engine components.

## Core Engine Modules (`src/core`)

The `core` directory implements the foundational, renderer-agnostic 4-stage data pipeline (Semantic -> Simulation -> Frame -> Visual). This is the architectural backbone of the Zaram runtime.

---

### Module: `core/simulation`

-   **Files**: `physics.ts`, `runtime.ts`, `types.ts`
-   **Purpose**: Operates in **Stage 2** of the pipeline. It takes a `SpatialGraph` (the semantic representation of data) and calculates the physical state (position, velocity) of nodes in a 3D space. It is a pure, mathematical simulation, completely decoupled from any rendering logic.
-   **Dependencies**:
    -   **Incoming**: `core/semantic/types` (for `SpatialGraph`).
    -   **Outgoing**: None. It produces `SimulationState`.
-   **Public API**: `SimulationRuntime` class, which manages the simulation state and provides a `tick()` method.
-   **Current Completeness**: Appears complete for its defined purpose. The physics model includes gravity, repulsion, and edge attraction, which is sufficient for creating dynamic, graph-like structures.
-   **Architectural Quality**: Excellent. It strictly adheres to the principle of separation of concerns. It is stateless (in the sense that `tick` is a pure function of state + graph + dt) and has no side effects. The use of plain `Vector3` interfaces instead of a vector library like `THREE.Vector3` enforces its renderer-agnostic nature.
-   **Coupling Level**: Very Low. Only coupled to the data contracts from the `semantic` and its own `types` modules.
-   **Performance Implications**: The physics calculations are O(n^2) due to the repulsion calculations between all nodes. For very large graphs, this could become a bottleneck. This is an expected trade-off for this type of simulation.
-   **Classification**: **A - Core Runtime**

#### Audit Answers:
-   **Why does this exist?** To translate the abstract relationships in the `SpatialGraph` into a dynamic, physical layout that can be visualized. It gives the data "life" and "form" before it's rendered.
-   **What problem does it solve?** It solves the problem of how to spatially arrange a complex graph of interconnected data in a way that is aesthetically pleasing and informationally relevant (e.g., clustering, attraction).
-   **Can Zaram Shell V1 function without it?** No. This is the fundamental engine that drives the "living" aspect of the data visualization.
-   **Would removing it break architectural integrity?** Yes. It would break the 4-stage pipeline, which is the core architectural pattern.
-   **Does it align with the vision?** Yes, perfectly. It is a key component in "communicating intelligence" by giving it a physical, dynamic form.

---

### Module: `core/frame`

-   **Files**: `composer.ts`, `types.ts`
-   **Purpose**: Operates in **Stage 3** of the pipeline. It consumes the `SimulationState` (from Stage 2) and various environmental inputs (e.g., presence, audio) to produce the "sacred" `FrameState` contract. This `FrameState` is the single source of truth for *all* renderers.
-   **Dependencies**:
    -   **Incoming**: `core/simulation/types`, `theme/presenceTheme`.
    -   **Outgoing**: None. It produces `FrameState`.
-   **Public API**: `FrameComposer` class, which provides a `compose()` method.
-   **Current Completeness**: Complete. It effectively merges simulation data with system state to generate a comprehensive set of visual, audio, and emotional parameters for rendering.
-   **Architectural Quality**: Excellent. This is a critical decoupling layer. By creating the `FrameState` contract, it allows any number of renderers (Canvas, Three.js, Unreal) to be driven by the same underlying system state without being coupled to the simulation or each other.
-   **Coupling Level**: Low. Coupled only to its input data contracts.
-   **Performance Implications**: The composition logic is very lightweight (mostly lookups and interpolations). Performance impact is negligible.
-   **Classification**: **A - Core Runtime**

#### Audit Answers:
-   **Why does this exist?** To create a standardized, renderer-agnostic "frame" of data that describes *what* to render, not *how* to render it. It's the bridge between the abstract simulation and the concrete visual output.
-   **What problem does it solve?** It prevents renderers from needing to know about the complexities of the simulation, audio inputs, or presence state. It provides a simple, unified data structure they can consume.
-   **Can Zaram Shell V1 function without it?** No. It is the sole producer of the `FrameState` that all renderers depend on.
-   **Would removing it break architectural integrity?** Yes. It's the lynchpin of the entire rendering pipeline.
-   **Does it align with the vision?** Yes, absolutely. The concept of a "sacred FrameState contract" is the key to enabling future renderers (Unreal, Spatial Computing) without refactoring the core logic.

---

### Module: `core/visual`

-   **Files**: `mapper.ts`, `types.ts`
-   **Purpose**: Operates in **Stage 4** of the pipeline. This is a pure, stateless mapping layer. It takes the `SimulationState`, the `FrameState`, and a `VisualTheme` and maps them to a `VisualState`. The `VisualState` is a concrete set of properties (e.g., color, radius, opacity) that a renderer can use directly.
-   **Dependencies**:
    -   **Incoming**: `core/semantic/types`, `core/simulation/types`, `core/frame/types`, `theme/presenceTheme`.
    -   **Outgoing**: None. It produces `VisualState`.
-   **Public API**: `mapToVisualState()` function.
-   **Current Completeness**: Complete. It handles a rich set of transformations, including heat decay, illumination, search highlighting, and presence-based color blending.
-   **Architectural Quality**: Excellent. It's a pure, stateless function, which makes it predictable and easy to test. It correctly isolates all the complex "business logic" of visual appearance from the renderer itself. The renderer's only job is to paint what the `VisualState` tells it to.
-   **Coupling Level**: Medium. It is coupled to several data contracts, which is expected for its role as a "mapper". It has no implementation dependencies.
-   **Performance Implications**: This mapper performs a significant amount of work, iterating over all nodes and edges. Like the simulation, it's O(n). For very large graphs, this could be a performance consideration.
-   **Classification**: **A - Core Runtime**

#### Audit Answers:
-   **Why does this exist?** To translate the abstract properties of the `FrameState` (e.g., `energy: 0.8`) and the semantic properties of the graph into concrete visual properties (e.g., `color: '#ffffff'`, `scale: 1.2`).
-   **What problem does it solve?** It keeps the renderers "dumb". A renderer shouldn't have to decide how "heat" affects color, or how "energy" affects scale. This mapper centralizes all of that presentation logic.
-   **Can Zaram Shell V1 function without it?** No. It's the final step in the data pipeline before rendering. Without it, the renderer would have no concrete instructions on what to draw.
-   **Would removing it break architectural integrity?** Yes. It would force presentation logic into the renderers, violating the separation of concerns.
-   **Does it align with the vision?** Yes. It ensures that the "look and feel" of Zaram is consistent across all renderers because they are all fed by the same mapping logic.