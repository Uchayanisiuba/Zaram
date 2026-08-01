# ZARAM CINEMATIC GUIDE

**Version:** 1.0  
**Status:** Frozen (Production Authority)  
**Target Audience:** Camera Programmers, Technical Artists, UI/UX Designers  

---

## Core Philosophy
The camera in Zaram is not a mathematical observer; it is a physical, anamorphic lens operating in a frictionless vacuum. It possesses mass, inertia, and a cinematic eye. It should feel as deliberate as the orbital mechanics in *Interstellar* and as fluid as the Director mode in *Destiny*.

---

## 1. Camera Language & Lens Choices

### The Default Lens (The Macro View)
*   **Focal Length:** 24mm equivalent.
*   **Usage:** Wide, expansive, capturing the vastness of the Zaram universe. Used when navigating the Outer Rim or viewing large constellations of Projects and Tasks.

### The Focus Lens (The Intimate View)
*   **Focal Length:** 50mm to 85mm equivalent.
*   **Usage:** When zooming into a Document, Memory, or Conversation, the focal length dynamically compresses. This flattens the perspective and brings the object into intimate, distortion-free focus, isolating it from the background.

### Depth of Field (DoF)
*   **Settings:** Aggressive and physically based. The aperture is wide open (f/1.4 to f/2.8).
*   **Behavior:** When the camera locks onto an object, the background instantly falls into a heavy, creamy bokeh. This is our primary tool for guiding user focus and reducing cognitive load.

---

## 2. Motion Language & Framing

### Inertial Damping
*   There are **zero linear interpolations** in Zaram. 
*   Every pan, orbit, and zoom relies on cubic bezier curves with a heavy ease-out. 
*   When the user stops panning, the camera drifts for a fraction of a second, bleeding off momentum naturally.

### Framing (The Rule of Thirds)
*   When engaging with a UI element (like a Glass HUD), the camera should never center the target object dead-on. 
*   It should smoothly offset the Living Orb or the target Project to the left or right third of the screen, balancing the composition with the UI panel.

---

## 3. Special Cinematics

### Search Cinematics (The Vertigo Effect)
*   **Trigger:** Spotlight Search activation.
*   **Effect:** Triggers a subtle Dolly Zoom (Zolly). The camera physically pulls back on the Z-axis while the FOV narrows. 
*   **Feel:** Creates an instant feeling of "locking in" or tunnel vision, heavily inspired by *Death Stranding's* Odradek scans.

### Sub-Universe Transitions
*   **Trigger:** Entering a sub-universe (e.g., a specific Project cluster).
*   **Effect:** Not a fade-to-black. It is a continuous, high-speed push forward. 
*   **Particles:** As the camera accelerates, the ambient particle dust stretches into radial streaks (subtle motion blur), dropping the user seamlessly into the new local coordinate space.