# Orb Engine Architecture
**Version:** 1.0 | **Status:** Frozen

## 1. Rendering Philosophy
- **GPU-First:** All heavy visual computation (particles, shaders, rings) occurs on the GPU.
- **CPU Orchestration Only:** The CPU handles state management, FrameState interpolation, and event routing.

## 2. Adaptive Performance
Replace static graphics presets with dynamic scaling:
- **Modes:** Adaptive, Balanced, Maximum.
- **Metrics:** GPU Frame Time, CPU Frame Time, VRAM, GPU Utilization, Battery.
- **Rule:** Never disable visual identity. Progressively reduce complexity (particle count, shader resolution) based on metrics.

## 3. Visual Memory
The Orb retains a subtle visual history of recent interactions, preventing it from feeling like a stateless machine.