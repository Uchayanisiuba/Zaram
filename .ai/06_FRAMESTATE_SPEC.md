# Zaram FrameState Specification
**Version:** 1.0
**Status:** Frozen (Requires ADR to modify)
**Dependencies:** `00_AI_ENGINEERING_MANIFEST.md`, `02_RUNTIME_CONTRACT.md`

> **This document defines the canonical visual and state contract for all Zaram embodiments (Orb, MetaHuman, XR, Robotics). It is the single source of truth for how the AI's internal state is translated into visual representation.**

---

## 1. Purpose & Scope
The `FrameState` is a standardized, nested data structure emitted by the Zaram Kernel and consumed by Embodiment Runtimes. It ensures that whether the user is interacting with a 2D Living Orb, a 3D MetaHuman, or a future robotic avatar, the visual feedback remains perfectly synchronized, emotionally consistent, and architecturally decoupled from the underlying intelligence.

---

## 2. The Nested FrameState Contract
To maintain order and allow independent evolution of subsystems, the `FrameState` is strictly grouped into five namespaces.

```typescript
interface FrameState {
  // --- 1. Visual Foundation ---
  // Drives breathing, glow, body language, idle motion, and gaze.
  visual: {
    presence: number;   // 0.0 to 1.0 (Overall "aliveness" and grounding)
    energy: number;     // 0.0 to 1.0 (Physical vitality and movement speed)
    focus: number;      // 0.0 to 1.0 (Attention directed at user vs internal processing)
    activity: number;   // 0.0 to 1.0 (Overall activity level: 0.1=Sleeping, 0.5=Chatting, 0.9=Deep Reasoning)
  };

  // --- 2. Audio Metrics ---
  // High-frequency data for lip-sync, waveform visualization, and interruption.
  audio: {
    voiceLevel: number;        // 0.0 to 1.0 (Normalized RMS amplitude of AI speech)
    microphoneLevel: number;   // 0.0 to 1.0 (Normalized RMS amplitude of user speech)
  };

  // --- 3. Emotional Vector ---
  // Multi-dimensional. Values 0.0 to 1.0. Sum does not need to equal 1.0.
  emotion: {
    calmness: number;
    confidence: number;
    curiosity: number;
    warmth: number;
    empathy: number;
    playfulness: number;
  };

  // --- 4. System & Identity ---
  // Internal state, cognitive demand, and persistent visual identity.
  system: {
    state: string;             // Discrete state machine: 'idle' | 'listening' | 'thinking' | 'speaking' | 'interrupted'
    cognitiveLoad: number;     // 0.0 to 1.0 (How mentally occupied Zaram feels; replaces raw CPU 'processingLoad')
    adaptiveQuality: number;   // 0.0 to 1.0 (Visual fidelity scaling based on performance)
    visualIdentity: string;    // signatureSeed (Persistent visual signature for the user's specific embodiment)
  };

  // --- 5. Metadata ---
  metadata: {
    timestamp: number;         // Unix epoch in milliseconds
    correlationId: string;     // Links this frame to a specific ExecutionPlan/Conversation
    version: string;           // Semantic version of this FrameState contract (e.g., "1.0.0")
  };
}