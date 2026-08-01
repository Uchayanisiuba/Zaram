# Living Orb Architecture

This document reverse-engineers the user experience and visual architecture of the Living Orb component, treating all backend data generation as a black box.

## 1. How the Orb Works Visually

The Living Orb is a layered, 2D visual component rendered on an HTML canvas. Its appearance is designed to communicate the AI's internal state through a combination of color, size, motion, and texture. It is not a single object, but a composition of four distinct, overlapping layers that are drawn on every frame:

1.  **Inner Core:** A small, bright, solid circle at the very center. It pulses subtly with audio.
2.  **Orb Body:** The main spherical element. It has a top-down gradient to give it a sense of lighting and depth. Its overall size and color change based on the AI's state.
3.  **Concentric Rings:** A series of 2-3 thin, semi-transparent rings that emanate from the orb. Their radius and visibility are tied to the AI's level of "activity" and audio output, creating a pulsing or rippling effect.
4.  **Outer Glow:** A large, soft, radial gradient that surrounds the entire orb. It provides ambient light and color, and its size and intensity are the primary indicators of the AI's "energy."

## 2. Rendering Pipeline

The rendering pipeline is simple, direct, and self-contained within the browser.

1.  **Host Component (`OrbEngine.tsx`):** A React component creates a `<canvas>` element and passes it to the renderer.
2.  **Renderer (`OrbRenderer.ts`):** This class holds the 2D rendering context of the canvas.
3.  **Data Input:** The renderer receives a `FrameState` object on a regular basis. This object contains all the necessary information (e.g., `presence`, `energy`, `hue`, `rmsLevel`).
4.  **Frame Loop:** On each `requestAnimationFrame`, the renderer clears the canvas.
5.  **Drawing:** It then draws each of the four layers (Glow, Orb, Rings, Core) from back to front, using the values from the latest `FrameState` to calculate the exact size, color, and opacity for each layer.

## 3. Animation Pipeline

All animation is procedural and data-driven, calculated on every frame. There are no pre-defined animation timelines (e.g., CSS transitions or keyframes).

1.  **Driver:** The `FrameState` object is the sole driver of animation.
2.  **State Mapping:** The current `PresenceState` (e.g., 'Thinking') sets a baseline for visual properties like hue, energy, and focus via hardcoded constants.
3.  **Live Modulation:** These baseline values are then modulated in real-time by live data points from the `FrameState`, such as `audio.smoothedRms` and `visual.activity`.
4.  **Calculation:** The `OrbRenderer` uses these final values to calculate properties for the current frame. For example, `ringRadius = baseRadius * (1.3 + activity * 0.2 + smoothedRms * 0.3)`.
5.  **Result:** This creates a fluid, dynamic animation that directly reflects the incoming data, rather than playing back a canned animation. The "pulse" of the orb is a direct visual representation of the audio RMS level.

## 4. State Transitions

Transitions between states (e.g., from 'Idle' to 'Listening') are handled by the `FrameComposer` (a black box), which smoothly interpolates the values in the `FrameState` over ~400ms. The `OrbRenderer` itself is stateless; it simply renders whatever values it is given for the current frame. The visual effect is a smooth cross-fade of color and form, as the renderer draws intermediate values during the transition. The color transitions are particularly smooth because they are defined and interpolated in the HSL color space.

## 5. Interaction Model

The Orb is a non-interactive component. The user cannot click, drag, or otherwise directly manipulate it. It serves as a passive feedback mechanism, a "face" for the AI. The only "interaction" is indirect: the Orb reacts to the user's voice (via `microphoneLevel`) and the AI's voice (`voiceLevel`), creating a conversational feel.

## 6. Performance Observations

The architecture is designed for high performance.
*   It uses a 2D Canvas, which is generally faster for this type of full-screen procedural drawing than DOM manipulation or SVG.
*   The animation loop is tied to `requestAnimationFrame`, which is the browser's standard for efficient animation.
*   The renderer can be suspended and resumed when the page is not visible, saving CPU/GPU resources.
*   Calculations are simple arithmetic and do not involve heavy physics or 3D transformations, keeping the per-frame workload low.

## 7. Accessibility Observations

Accessibility is a significant weakness.
*   The component is a canvas element with no fallback content or DOM representation of its state. Screen readers have no information to announce.
*   State is communicated exclusively through color and motion. This is inaccessible to users with visual impairments, color blindness, or motion sensitivities. There are no labels or alternative text descriptions.

## 8. Weaknesses

*   **Accessibility:** As noted above, the current implementation is not accessible.
*   **Rigidity:** The visual logic is hardcoded directly in the `render` methods of `OrbRenderer.ts`. Changing the appearance (e.g., adding a new layer, changing a gradient) requires modifying complex, imperative drawing code.
*   **No Theming:** While colors are tokenized, the overall "look" is not. A designer cannot easily adjust parameters like gradient stops, ring spacing, or pulse intensity without a developer editing the renderer's source code.

## 9. Strengths

*   **Performance:** The implementation is lightweight and performant.
*   **Decoupling:** The strict separation between the `FrameState` data contract and the `OrbRenderer` is a major strength. The rendering logic is completely independent of the business logic that generates the data.
*   **Encapsulation:** The entire visual identity of the Orb is encapsulated in a single class (`OrbRenderer.ts`) and its theme file, making it portable and easy to reason about as a self-contained unit.
*   **Expressiveness:** The procedural animation system creates a highly expressive and "live" feel that would be difficult to achieve with standard CSS or timeline-based animation libraries.

## 10. Recommendations

Based on this visual audit:

1.  **Preserve the Core Architecture:** The fundamental model of a stateless renderer consuming a `FrameState` contract is sound and should be kept.
2.  **Address Accessibility:** Introduce an ARIA-compliant mechanism to expose the Orb's state. This could involve a visually hidden `aria-live` region that receives text updates (e.g., "Zaram is now listening") in sync with the `PresenceState`.
3.  **Externalize Visual Configuration:** Refactor `OrbRenderer.ts` to accept a "theme" or "style" object at instantiation. This object would contain parameters like gradient stops, scale factors, and animation multipliers, moving them out of the hardcoded drawing methods. This would empower designers and make it easier to evolve the Orb's visual identity without rewriting rendering logic.