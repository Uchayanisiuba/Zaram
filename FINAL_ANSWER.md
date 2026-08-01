The audit is complete. All deliverables have been generated.

Here is the answer to the final question.

---

### **If this frontend had to support Zaram for the next five years, what architectural changes would you make before writing another line of feature code?**

The audit has revealed a foundational dichotomy in the codebase: a sophisticated, renderer-agnostic **Core Engine** that is almost completely disconnected from a fragmented and inconsistent **UI Layer**. The UI is not benefiting from the engine's primary output, the `FrameState`, which renders much of the engine's complexity useless.

Therefore, before writing another line of feature code, I would make one fundamental architectural change, executed in three parts: **Bridge, Refactor, and Centralize.**

**1. Bridge the Engine to the UI:**

The absolute highest priority is to forge the missing link between the `FrameComposer` and the React components.

*   **Action:** I would create a `RuntimeManager` that runs in a `requestAnimationFrame` loop. On each tick, it would compose a new `FrameState` from the core engine and update a single, sacred Zustand store, `frameStore`.
*   **Why:** This establishes a "producer-consumer" pattern where the engine is the single producer of state, and the UI is a pure consumer. This immediately unlocks the expressive power of the simulation, allowing the UI to reflect nuanced states like `energy`, `focus`, and `activity` instead of just binary states like `'thinking'`. This change alone makes the entire system coherent.

**2. Refactor the UI to be "Dumb" and Reactive:**

With the bridge in place, the UI layer must be refactored to be a "dumb" visual representation of the `FrameState`.

*   **Action:** I would refactor the `LivingOrb`, `SpatialBackground`, and any other state-visualizing components to be driven *exclusively* by a `useFrameState` hook that reads from the `frameStore`. All internal logic that tries to guess or manage state would be deleted.
*   **Why:** This enforces a unidirectional data flow. The UI no longer has a "mind of its own"; it becomes a deterministic reflection of the core engine's state. This simplifies the components, makes them easier to debug, and is the only way to guarantee visual consistency between different future renderers (e.g., React and Unreal Engine).

**3. Centralize Control in the Application Runtime:**

Finally, I would strip all business logic and state manipulation out of the components and place it in a dedicated **Application Runtime** layer.

*   **Action:** I would refactor "smart" components like `CommandPalette`. The component would become a simple form that emits events (e.g., `"command_executed"`). A `CommandRegistry` module in the `src/runtime` directory would listen for these events and orchestrate the necessary actions (e.g., calling the `surfaceStore` to open a new window, telling the core engine to enter a "thinking" state).
*   **Why:** This enforces a strict separation of concerns. The UI is for presentation, and the runtime is for orchestration. This makes the system modular, testable, and scalable. It allows for the creation of new surfaces, plugins, and agents without ever having to touch the core UI components. It establishes the `RuntimeBus` as the central nervous system of the application.

**Conclusion:**

These three changes—**Bridge, Refactor, and Centralize**—are not about adding features. They are about making the existing architecture functional and coherent. By establishing a clear, unidirectional data flow from the core engine to a dumb UI, and centralizing control in a dedicated runtime layer, we create a stable, scalable, and production-ready foundation.

Building on the current, fragmented system would be like building a skyscraper on sand. By making these changes first, we are pouring the concrete foundation necessary to support the weight of Zaram's ambitions for the next five years and beyond.