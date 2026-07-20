# ADR-007: GPU First Rendering
**Status:** Accepted
**Context:** CPU-bound rendering limits particle counts and shader complexity.
**Decision:** Orb Engine must use GPU-first rendering. CPU is restricted to orchestration and state management.
**Consequences:** Requires WebGL/WebGPU. Increases graphics driver dependency.