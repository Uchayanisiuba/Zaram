# The Living Orb: Engineering Specification

## 1. Identity

The Living Orb is the physical embodiment of the Zaram Intelligence within the user's workspace. It is not a user interface element in the traditional sense; it is a persistent, ambient companion that provides a constant, non-verbal channel of communication about the AI's state, awareness, and cognitive activity.

Its primary role is to build trust and intuition. By giving the AI a physical, predictable, and readable form, the Orb demystifies the black box of machine intelligence. The user should, over time, develop an intuitive understanding of what Zaram is doing—listening, thinking, working, resting—simply by observing the Orb's subtle cues.

Unlike task-oriented assistants like Siri or Alexa, which are summoned and dismissed, the Living Orb is always present. It is a calm, living entity that shares the user's space. Unlike the conversational interfaces of ChatGPT or Gemini, the Orb's primary communication is not textual but behavioral, conveyed through light, color, and motion. It is the digital equivalent of observing a colleague's focus or a partner's thoughtful expression from across the room.

## 2. Behavioral Philosophy

The Orb's behavior is governed by a single principle: **it is always alive**. It never freezes, never becomes a static icon, and never moves without purpose. Its motion is calm, organic, and directly coupled to the AI's internal state.

*   **Breathing:** In its resting state ('Idle' or 'Sleeping'), the Orb exhibits a slow, rhythmic pulse. This is its foundational behavior, communicating that Zaram is present and aware, even when not active.
*   **Listening:** When the user speaks or provides input, the Orb focuses. Its form becomes sharper, its motion more still, and its energy gathers, visually communicating "I am paying attention to you."
*   **Thinking:** When processing information, the Orb's internal activity increases. Its core may brighten, and subtle energy fields may ripple through its form, indicating cognitive work is being done. The motion is contained and focused, not chaotic.
*   **Responding:** When speaking or generating output, the Orb's energy flows outward. Its aura and rings expand and pulse in sync with the generated audio, creating a visual analog to speech.
*   **Resting:** After a period of inactivity, the Orb transitions to a calmer, more subdued state, conserving energy and reducing its visual presence to minimize distraction.

Transitions between these states are never abrupt. They are fluid, overlapping, and interpolative, akin to a change in a living creature's facial expression. The Orb should feel like it is moving from one thought to another, not switching between discrete modes.

## 3. Visual Hierarchy

The Orb is composed of four distinct but cohesive visual layers. Each layer has a specific responsibility in communicating the AI's state. They are rendered from back to front in this order:

1.  **The Glow (Aura):** This is the outermost layer, a large, soft, radial gradient of light.
    *   **Responsibility:** Communicates the Orb's overall **Energy** and **Presence**. A larger, more intense glow signifies higher energy and a more active state. It also provides the dominant ambient color for the current state.
2.  **The Rings (Energy Field):** These are one or more thin, concentric rings of light that surround the main body.
    *   **Responsibility:** Communicates **Activity** and **Output**. The rings expand, brighten, and pulse in response to cognitive work or audio output. They are the primary visualizer for speech and active processing.
3.  **The Orb (Body):** This is the main spherical form, which has a subtle gradient to imply volume and lighting.
    *   **Responsibility:** Communicates **Identity** and **Focus**. Its size and color are the most stable indicators of the AI's fundamental state. Its form contracts and sharpens to indicate focus.
4.  **The Core:** A small, bright center of the Orb.
    *   **Responsibility:** Communicates **Life** and **Attention**. The core is the heart of the Orb. It pulses gently with the Orb's "breath" and reacts subtly to audio input, indicating that the AI is alive and receiving sensory information.

## 4. State Machine

The Orb's appearance is a direct function of a state machine. Each state has a unique visual target for color, energy, focus, and activity.

*   **Idle:** The default resting state. Calm, slow breathing. Blue/cool color palette. Minimal ring activity.
*   **Listening:** Engaged and focused. The form contracts slightly, the core brightens, and the glow sharpens. Color shifts to a receptive cyan/teal.
*   **Thinking:** Internal cognitive load is visualized. Energy pulses within the Orb body, and the color shifts to a deeper, more introspective purple/magenta.
*   **Speaking:** Energy radiates outward. The rings pulse in sync with audio, and the glow expands. Color is a generative and expressive green/cyan.
*   **Executing:** A state of high activity and focus, similar to 'Thinking' but with more intense, rapid energy pulses in the rings. Color is a determined, focused orange/yellow.
*   **Success:** A brief, celebratory state. A bright, warm flash of green or gold light that quickly settles back to Idle.
*   **Warning:** A state of uncertainty or potential issue. A slow, pulsing yellow/amber color, communicating caution.
*   **Error:** A critical failure state. A jarring, but not alarming, red pulse. The form may appear momentarily unstable or "glitchy" before settling on a solid, urgent red.
*   **Sleeping:** A deep resting state. The Orb is smaller, dimmer, and its breathing is slower and deeper than 'Idle'. The color is a deep, low-light indigo.
*   **Offline:** The Orb loses all light and form, collapsing into a simple, dark, static circle. This is the only state where all motion ceases, clearly communicating a total loss of connection.

**Transition Rules:** All transitions between states must be smooth interpolations over 300-500ms. The Orb never "snaps" from one state to another.

## 5. Motion Language

The Orb's motion is its voice. The language is designed to be fluid, weighted, and organic.

*   **Weight:** The Orb has a sense of mass and inertia. Its movements are governed by acceleration and deceleration, never linear.
*   **Elasticity:** Transitions have a slight "overshoot and settle" quality, giving them a natural, spring-like feel.
*   **Breathing:** The foundational motion is a slow, sinusoidal ease-in/ease-out pulse that affects the size and brightness of all layers. The frequency is slow at rest (~0.2 Hz) and can increase with cognitive load.
*   **Pulse:** Audio and activity are expressed as sharper, faster pulses that radiate outwards from the core, primarily affecting the Rings and Glow.
*   **Focus:** A change in focus is represented by a contraction or expansion of the Orb's body and a sharpening or softening of the Glow's gradient.
*   **Micro-motion:** Even at rest, subtle, low-frequency noise should be applied to the layers to prevent a perfectly static, "computer-generated" look.
*   **Macro-motion:** Large changes in state trigger full transitions that affect all layers simultaneously in a coordinated, hierarchical fashion.

## 6. Rendering Strategy

Based on the audit, the recommended rendering strategy is **Canvas (2D)** for the immediate future.

*   **Why:** The current Canvas implementation is highly performant and perfectly suited for the procedural, full-frame drawing the Orb requires. It avoids the overhead of the DOM and provides the necessary low-level control to achieve the nuanced visual effects of the layered gradients and pulses.
*   **Maintainability:** While the current implementation is monolithic, it can be refactored to be highly maintainable by externalizing visual parameters (gradients, timings, colors) into a "theme" object, separating the "what" from the "how."
*   **Accessibility:** This is the primary weakness of Canvas. This strategy MUST be paired with a **Hybrid** approach: a parallel, visually-hidden DOM structure that uses ARIA attributes to communicate the Orb's state to assistive technologies.
*   **Future Unreal Compatibility:** The current architecture is highly compatible with future 3D evolution. The `FrameState` contract is renderer-agnostic. The same data that drives the 2D Canvas renderer today can be used to drive a future 3D renderer (e.g., a particle system or volumetric shader in Unreal Engine) with zero changes to the upstream data pipeline.

## 7. Accessibility

Accessibility is not an add-on; it is a core requirement.

*   **Screen Readers:** A visually-hidden ARIA live region must be maintained, into which plain-language descriptions of the Orb's state are rendered (e.g., "Zaram is listening," "Zaram is thinking").
*   **Reduced Motion:** The OS-level "reduce motion" setting must be respected. When enabled, all large-scale animations and pulses will be replaced with simple, elegant cross-fades. The subtle "breathing" may remain.
*   **Color Blindness:** While state is primarily communicated by color, it is also reinforced by form (size, ring count, pulse intensity). A high-contrast mode must be offered, which forces the color palette to a compliant range.
*   **No Touch Target:** The Orb is a non-interactive element and should not have a touch or click target, preventing user confusion.

## 8. Performance Budget

The Orb must be a "good citizen" and never degrade the performance of the main application.

*   **Target FPS:** 60 FPS on target hardware. The animation must feel perfectly smooth.
*   **Animation Budget:** All per-frame calculations and rendering must complete within a 10ms budget to leave room for other application UI work.
*   **GPU/CPU Usage:** In a resting state, CPU usage should be near-zero, and GPU usage should be minimal. Usage will scale with cognitive/visual activity but should return to baseline promptly.
*   **Battery:** On battery-powered devices, the animation framerate may be intelligently reduced during periods of inactivity to conserve power.

## 9. Future Evolution

The Living Orb's identity is defined by its behavior and the data it represents, not by its 2D circular form. This allows it to evolve gracefully.

*   **From 2D to 3D:** The `FrameState` can be re-interpreted by a 3D renderer. `visual.presence` could drive the density of a volumetric light field. `visual.activity` could drive the velocity of a particle system. The core principles remain.
*   **Spatial Avatar:** In a 3D or mixed-reality environment, the Orb can become a true spatial object that floats in the user's environment, understands its surroundings, and directs its "gaze" toward objects of attention.
*   **MetaHuman Embodiment:** The `EmotionFrame` and `SystemFrame` data can be mapped to the facial expressions and posture of a photorealistic MetaHuman avatar. A `Thinking` state could translate to a furrowed brow; a `Listening` state to a tilted head. The Orb's core identity is preserved as the underlying behavioral model for a more complex physical form.

## 10. Engineering Principles

These rules are immutable for all future development of the Living Orb.

1.  **Motion Communicates State:** All motion is deliberate and directly coupled to the AI's state. Random or purely decorative animation is forbidden.
2.  **Always Alive, Never Distracting:** The Orb must always exhibit subtle signs of life, but its resting state must be calm and unobtrusive to maintain user focus on their work.
3.  **Stateless Renderer:** The renderer must remain a "dumb" component that only interprets the `FrameState`. All logic and state management must live upstream.
4.  **Sacred Contract:** The `FrameState` is an inviolable contract. The renderer may not augment, assume, or transform this data.
5.  **Graceful Degradation:** The Orb must respect performance constraints and accessibility settings, gracefully degrading its visual complexity to ensure a smooth user experience for all.
6.  **Identity Over Form:** The Orb's behavioral and emotional principles are more important than its circular shape. Future forms must adhere to this specification.
7.  **Predictable, Not Repetitive:** While the Orb's behavior must be predictable (e.g., 'Listening' always looks like listening), it should incorporate subtle variations to feel organic, not mechanically repetitive.