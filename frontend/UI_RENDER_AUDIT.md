# UI Render Audit — Sprint 5

**Date:** 2026-07-27
**Status:** Production Review
**Scope:** Frontend rendering pipeline, Living Orb, Presence Runtime, DesktopShell, Conversation UI, Spatial UI, Glass UI, Camera transitions, Animation consistency
**Directive:** One rendering pipeline. Living Orb integrated. Presence synchronized. No duplication.

---

## 1. Executive Summary

The Zaram frontend has a solid architectural foundation with a defined 4-stage pipeline (Semantic → Simulation → Frame → Visual) and a unified Presence Runtime that synchronizes visual state across subsystems. However, the Sprint 5 review reveals **critical fragmentation** in the rendering layer: multiple duplicate component directories, two separate Orb renderer implementations, two competing camera systems, and a rendering pipeline that is not consistently enforced.

The core issue is **structural duplication** — the same logical UI surface exists in both `components/` and `components/spatial/` directories, with no clear ownership or deprecation path. This audit identifies every duplication, ranks severity, and prescribes a consolidation plan.

---

## 2. Rendering Pipeline Assessment

### 2.1 Architecture (as Designed)

The 4-Stage Pipeline defined in `ZARAM_FRONTEND_ARCHITECTURE.md`:

| Stage | Contract | Producer | Consumer |
|-------|----------|----------|----------|
| Stage 1: Semantic | `SpatialNode`, `SpatialEdge`, `SpatialGraph` | Semantic layer | Simulation layer |
| Stage 2: Simulation | `SimulationNode`, `SimulationState` | Physics engine | Frame Composer |
| Stage 3: Frame | `FrameState` | `FrameComposer` | All renderers |
| Stage 4: Visual | `VisualNode`, `VisualState` | `VisualMapper` | R3F Renderer |

### 2.2 Architecture (as Implemented)

**Status: PARTIALLY COMPLIANT**

- ✅ `FrameComposer` (`core/frame/composer.ts`) is the single producer of `FrameState`
- ✅ `FrameState` (`core/frame/types.ts`) is the sacred contract consumed by all renderers
- ✅ `PresenceContext` provides `FrameState` to all React components via two contexts (`PresenceRuntimeContext` + `FrameStateRuntimeContext`)
- ✅ `usePresenceReactions` maps `PresenceState` → visual properties consistently
- ⚠️ `UniverseView.tsx` bypasses `FrameComposer` for the 3D scene — it receives `presenceState` as a prop and calls `updatePresence()` on the bridge directly, then passes `visualState` and `systemState` to `LivingOrbCenter` and `OuterRimLayer`
- ⚠️ `OrbEngine.tsx` (2D Canvas) receives `FrameState` via IPC or props, but has its own hardcoded `STATE_HUE`/`STATE_ENERGY`/`STATE_FOCUS`/`STATE_ACTIVITY` mappings that duplicate the logic in `usePresenceReactions.tsx` and `presenceTheme.ts`
- ❌ `LivingOrbCenter.tsx` (3D R3F) reads `frameState.system.state` directly and maps colors via `PRESENCE_COLORS` — this is a third copy of the same presence→color mapping

### 2.3 Pipeline Violations

| Violation | Location | Severity |
|-----------|----------|----------|
| `UniverseView.tsx` imports `PresenceState` from theme and reimplements color mapping (`getPresenceColor`) | `pages/UniverseView.tsx:447-461` | High |
| `OrbRenderer.ts` hardcodes `STATE_HUE`, `STATE_ENERGY`, `STATE_FOCUS`, `STATE_ACTIVITY` dictionaries | `components/OrbEngine/OrbRenderer.ts:16-82` | High |
| `LivingOrbCenter.tsx` imports `PRESENCE_COLORS` directly and uses `frameState.system.state` for color lookup | `engine/components/LivingOrbCenter.tsx:6,34-37` | Medium |
| `FrameComposer.getPresenceModifiers()` duplicates the same state→visual mapping as `usePresenceReactions` | `core/frame/composer.ts:109-134` | Medium |

**Root Cause:** The `FrameState` contract is correctly defined, but the mapping from `PresenceState` → visual parameters (color, energy, focus, activity) is replicated in **four separate locations** instead of being centralized in `presenceTheme.ts` and consumed by all renderers.

---

## 3. Living Orb Integration

### 3.1 Current State

The Living Orb has **three separate implementations**:

| Implementation | Path | Technology | Purpose |
|----------------|------|------------|---------|
| `OrbEngine` (2D Canvas) | `components/OrbEngine/OrbEngine.tsx` + `OrbRenderer.ts` | HTML5 Canvas 2D | Desktop orb renderer, receives FrameState via IPC or props |
| `LivingOrbCenter` (3D R3F) | `engine/components/LivingOrbCenter.tsx` | Three.js / R3F | 3D orb in the 3D scene, reads FrameState directly |
| `LivingOrb` wrapper | `components/LivingOrb/LivingOrb.tsx` + `embodiments/LivingOrb/LivingOrb.tsx` | React wrapper | Thin wrappers around `OrbEngine` |

### 3.2 Issues

1. **Two orb renderers, one state source.** The 2D Canvas orb (`OrbEngine`) and the 3D R3F orb (`LivingOrbCenter`) both respond to `FrameState` but render independently. The 2D orb is used in `ConversationPanel` (via `PresenceCanvas`), while the 3D orb is used in `UniverseView`. They must stay synchronized, but there is no explicit sync mechanism — they both read from the same `FrameState` source, which works only because `FrameComposer` produces a single `FrameState`.

2. **Duplicate animation logic.** `OrbRenderer.ts` has its own `drawOrb()` method with hardcoded breathing, glow, and ring animations. `LivingOrbCenter.tsx` has its own `useFrame` loop with separate breathing, ring rotation, and particle logic. Neither delegates to a shared animation runtime.

3. **`components/LivingOrb/` vs `embodiments/LivingOrb/` duplication.** Two nearly identical wrapper components exist:
   - `components/LivingOrb/LivingOrb.tsx` — simple wrapper, no `frameState` prop
   - `embodiments/LivingOrb/LivingOrb.tsx` — wrapper with `frameState` prop for embedded usage

4. **`components/OrbEngine/` is not in the `engine/` directory.** The `OrbEngine` and `OrbRenderer` live in `components/OrbEngine/` instead of `engine/`, violating the architectural boundary that places renderers in `engine/renderers/`.

### 3.3 Recommendations

- Consolidate the 2D Canvas orb into `engine/renderers/` as `OrbRenderer` (it already exists there conceptually — `OrbRenderer.ts` should move)
- Remove `components/LivingOrb/` and `embodiments/LivingOrb/` wrappers; use `LivingOrbCenter` from `engine/components/` as the single source
- Extract shared animation parameters (breathing rate, glow intensity, ring speed) into a single `OrbAnimationConfig` driven by `FrameState`
- Remove hardcoded `STATE_HUE`/`STATE_ENERGY`/`STATE_FOCUS`/`STATE_ACTIVITY` from `OrbRenderer.ts` — these should come from `presenceTheme.ts` via `FrameState`

---

## 4. Presence Runtime Synchronization

### 4.1 Assessment

**Status: WORKING WITH GAPS**

The Presence Runtime synchronization layer is functional:

- ✅ `PresenceContext.tsx` provides `FrameState` and `PresenceState` via React context
- ✅ `usePresenceReactions.tsx` maps `PresenceState` → `PresenceReactions` (visual properties)
- ✅ `presenceTheme.ts` defines `PRESENCE_COLORS` and `applyPresenceTheme()` for CSS custom properties
- ✅ `FrameComposer.ts` composes `FrameState` from simulation + presence + audio inputs
- ✅ `UniverseView.tsx` receives `presenceState` prop and calls `updatePresence()` on the bridge

### 4.2 Gaps

| Gap | Location | Impact |
|-----|----------|--------|
| `usePresenceReactions` depends on `presenceState` only, not `frameState` | `components/interaction/usePresenceReactions.tsx:69` | Frame-level smooth values (energy, audio) not exposed to UI consumers |
| `OrbRenderer.ts` has its own `STATE_HUE`/`STATE_ENERGY` maps that duplicate `PRESENCE_COLORS` | `components/OrbEngine/OrbRenderer.ts:16-82` | Color inconsistencies if either source is updated without the other |
| `LivingOrbCenter.tsx` reads `frameState.system.state` directly instead of using `usePresenceReactions` | `engine/components/LivingOrbCenter.tsx:45` | Bypasses the centralized reaction mapping |
| `UniverseView.tsx` has its own `getPresenceColor()` function | `pages/UniverseView.tsx:447-461` | Fourth copy of presence→color mapping |
| `ConversationPanel.tsx` (pages) has `mapExecutiveToPresenceState()` that maps executive states to `PresenceState` | `pages/ConversationPanel.tsx:93-118` | This mapping is correct but lives in the page component instead of a shared utility |

### 4.3 Recommendations

- Create a single `usePresenceVisuals()` hook that returns all visual parameters (color, energy, focus, activity, particle color, lighting color) derived from `FrameState` — consumed by both `usePresenceReactions` and the 3D/2D orb renderers
- Remove the duplicate color mapping dictionaries from `OrbRenderer.ts` and `UniverseView.tsx`
- Have `LivingOrbCenter.tsx` consume `usePresenceReactions` or receive visual props from `FrameState` via a selector

---

## 5. DesktopShell Consistency

### 5.1 Issues Found

| Issue | Location | Severity |
|-------|----------|----------|
| Incomplete startup handling — line 77 has `{'startup'/** Start-up awakening handled via appPhase */}` which is a comment, not rendered JSX | `components/layout/DesktopShell.tsx:77` | High |
| `StartupAwakening` component references `DURATION.awakening` and `EASING.cinematic` but these are not imported | `components/layout/DesktopShell.tsx:143-144` | High (runtime error) |
| `CameraController` imported from `@/components/spatial/camera` — the spatial version, not the top-level `components/camera` version | `components/layout/DesktopShell.tsx:22` | Medium (inconsistency) |
| `Dock` imported from `@/components/spatial/dock` — correct spatial version | `components/layout/DesktopShell.tsx:26` | — |
| `ConversationPanel` imported from `@/components/spatial/context-panels` — correct spatial version | `components/layout/DesktopShell.tsx:28` | — |
| `SearchOverlay` imported from `@/components/spatial/search` — correct spatial version | `components/layout/DesktopShell.tsx:24` | — |
| `TransitionLibrary` imported from `@/components/spatial/transitions` — correct spatial version | `components/layout/DesktopShell.tsx:25` | — |
| `PanelShell` imported from `@/components/primitives/PanelShell` — correct | `components/layout/DesktopShell.tsx:27` | — |

### 5.2 Recommendations

- Fix `StartupAwakening` — either render the startup UI or remove the dead code
- Import `DURATION` and `EASING` from `@/lib/animations` in `DesktopShell.tsx`
- Standardize all imports to use `components/spatial/` paths consistently (already mostly done)

---

## 6. Conversation UI

### 6.1 Structure

The conversation UI has **two layers**:

1. **Full implementation** in `components/conversation/`:
   - `ConversationFeed.tsx` — scrollable message feed with presence-reactive styling
   - `ConversationInput.tsx` — input area with voice, attachment, send
   - `MessageCard.tsx` — individual message rendering
   - `ThinkingIndicator.tsx` — thinking/spinner with presence-reactive color
   - `StreamingCursor.tsx` — blinking cursor with presence-reactive color
   - `PresenceCanvas.tsx` — canvas for the orb in conversation context
   - `ProgressiveMarkdown.tsx` — streaming markdown renderer
   - `ResizablePanels.tsx` — three-panel resizable layout
   - `ResponseActions.tsx` — action buttons on messages

2. **Thin wrapper** in `components/spatial/context-panels/`:
   - `ConversationPanel.tsx` — 21 lines, wraps `ConversationFeed` + `ConversationInput` in a `PanelShell`

3. **Full page** in `pages/ConversationPanel.tsx`:
   - 940 lines — the actual conversation page with backend integration, execution pipeline, voice recording, file handling, etc.

### 6.2 Issues

| Issue | Severity |
|-------|----------|
| `pages/ConversationPanel.tsx` (940 lines) and `components/spatial/context-panels/ConversationPanel.tsx` (21 lines) serve different purposes but share the same name — confusing for navigation and imports | Medium |
| `components/conversation/` contains the full implementation; `components/spatial/context-panels/` is a thin wrapper — this is correct layering but the naming is ambiguous | Low |
| `ConversationFeed.tsx` uses `usePresenceReactions()` correctly for reactive styling | — |
| `ThinkingIndicator.tsx` and `StreamingCursor.tsx` correctly use `usePresenceReactions()` | — |
| `ConversationPanel.tsx` (pages) imports from `@/components/conversation` (not `@/components/spatial/context-panels`) — correct | — |

### 6.3 Recommendations

- Rename `components/spatial/context-panels/ConversationPanel.tsx` to `ConversationPanelShell.tsx` to avoid confusion with the page component
- Consider whether `pages/ConversationPanel.tsx` should be refactored to use the spatial panel pattern consistently

---

## 7. Spatial UI

### 7.1 Directory Structure

The `components/spatial/` directory contains the production spatial UI:

```
components/spatial/
├── camera/          → CameraController, CameraModes, useCameraDirector
├── context-panels/  → ConversationPanel, DocumentPanel, InspectorPanel, MemoryPanel, ProjectPanel
├── dock/            → Dock, DockItem, SpatialDock, useDockPhysics
├── glass/           → GlassButton, GlassCard, GlassInput, GlassPanel, GlassSection, GlassWindow
├── glass-hud/       → GlassHUD, GlassMaterial, HUDOverlay, HUDWindow, useHUD
├── hud/             → CommandHints, FloatingLabels, HUDAnchor, HUDOverlay, HUDRoot, NotificationLayer
├── layout/          → LayoutManager, ResizablePanel
├── search/          → SearchGroup, SearchInput, SearchOverlay, SearchResults, useSearchShortcut
├── transitions/     → ConversationFocusTransition, MemoryRecallTransition, ProjectEntryTransition, SearchTransition, ShutdownTransition, StartupTransition, TransitionLibrary, context.ts
└── windows/         → ConversationWindow, DocumentWindow, InspectorWindow, MemoryWindow, ProjectWindow, WindowWrapper
```

### 7.2 Issues

- `SpatialSelection.tsx` in `components/spatial-selection/` is not under `components/spatial/` — inconsistent placement
- `AmbientAI.tsx` and `WeatherEngine.tsx` in `components/layers/` are not under `components/spatial/` — unclear if they are spatial UI

---

## 8. Glass UI

### 8.1 Duplication Found

| `components/glass/` | `components/spatial/glass/` |
|---------------------|---------------------------|
| `GlassPanel.tsx` (41 lines, simple wrapper) | `GlassPanel.tsx` (production, used by GlassHUD) |
| `useGlassEffects.ts` | — |
| `index.ts` | — |
| — | `GlassButton.tsx` |
| — | `GlassCard.tsx` |
| — | `GlassInput.tsx` |
| — | `GlassSection.tsx` |
| — | `GlassWindow.tsx` |

**Analysis:** `components/glass/` contains a minimal `GlassPanel.tsx` and `useGlassEffects.ts`. `components/spatial/glass/` contains the full production glass system. The `components/glass/` directory appears to be an earlier, incomplete version that was superseded by `components/spatial/glass/`.

### 8.2 Recommendations

- Remove `components/glass/` — it is a subset of `components/spatial/glass/` and creates confusion
- Update any imports from `@/components/glass` to `@/components/spatial/glass`

---

## 9. Camera Transitions

### 9.1 Duplication Found

| `components/camera/` | `components/spatial/camera/` |
|---------------------|---------------------------|
| `CameraController.tsx` (67 lines, uses `framer-motion` + `CameraLensOverlay`) | `CameraController.tsx` (1577 bytes, different implementation) |
| `CameraModes.tsx` (82 lines, `LensPreset` type + `CameraLensOverlay` component) | `CameraModes.tsx` (1799 bytes, different `LensPreset` + `CameraLensOverlay`) |
| `useCameraDirector.ts` (168 lines, uses `requestAnimationFrame` + custom easing) | `useCameraDirector.ts` (106 lines, uses `framer-motion` springs) |
| `index.ts` | `index.ts` |

**Analysis:** Two completely separate camera implementations exist with different approaches:
- `components/camera/` uses `requestAnimationFrame` + custom cubic bezier easing (`lib/animations`)
- `components/spatial/camera/` uses `framer-motion` springs (`SPRING.lens`)

`DesktopShell.tsx` imports from `@/components/spatial/camera` — the spatial version is the production one.

### 9.2 Recommendations

- Remove `components/camera/` — it is a superseded implementation
- Keep `components/spatial/camera/` as the single source of truth
- Ensure `CameraController.tsx` in `components/spatial/camera/` is complete (it references `cn()` utility which may not be imported — check for missing imports)

---

## 10. Animation Consistency

### 10.1 Shared Animation Constants

`lib/animations.ts` provides:
- `EASING` — cubic bezier curves (cinematic, focus, organic, ambient)
- `DURATION` — timing values (micro, fast, normal, panel, dolly, descent, breathe, drift, awakening, sleep)
- `SPRING` — spring physics configs (hover, panel, dock, layout, hud, search, input, selection, breathing, lens)
- `STAGGER` — stagger delays (messages, search, timeline)
- Utility functions: `cubicBezier()`, `catmullRom()`, `exponentialDecay()`, `applyEase()`

### 10.2 Usage Assessment

| Component | Uses `lib/animations`? | Consistent? |
|-----------|----------------------|-------------|
| `usePresenceReactions.tsx` | ✅ Uses `DURATION`, `EASING` | Yes |
| `GlassMaterial.tsx` | ✅ Uses `DURATION.panel`, `EASING.cinematic` | Yes |
| `GlassHUD.tsx` | ✅ Uses `SPRING.hud` | Yes |
| `Dock.tsx` (spatial) | ✅ Uses `SPRING.dock`, `STAGGER.search` | Yes |
| `CameraController.tsx` (spatial) | ✅ Uses `catmullRom`, `SPRING.lens` from `@/lib/animations` | Yes |
| `CameraModes.tsx` (spatial) | ✅ Uses `SPRING.lens` | Yes |
| `ConversationFeed.tsx` | ✅ Uses `DURATION.breathe`, `EASING.ambient` | Yes |
| `OrbRenderer.ts` (2D Canvas) | ❌ Has its own hardcoded animation logic (no `lib/animations`) | **No** |
| `LivingOrbCenter.tsx` (3D R3F) | ❌ Has its own hardcoded animation logic (no `lib/animations`) | **No** |
| `OrbEngine.tsx` | ❌ Does not use `lib/animations` | **No** |

### 10.3 Recommendations

- `OrbRenderer.ts` should reference `DURATION.breathe` and `EASING.ambient` from `lib/animations` instead of hardcoding `4s` cycle and sine wave
- `LivingOrbCenter.tsx` should reference `SPRING.breathing` and `DURATION.drift` from `lib/animations` instead of hardcoding delta multipliers
- Create an `OrbAnimationConfig` that derives animation parameters from `FrameState` and uses shared constants

---

## 11. Duplication Inventory

### 11.1 Duplicate Directories

| Duplicate Pair | Status | Action |
|----------------|--------|--------|
| `components/camera/` vs `components/spatial/camera/` | Superseded | **Remove `components/camera/`** |
| `components/dock/` vs `components/spatial/dock/` | Superseded | **Remove `components/dock/`** |
| `components/glass/` vs `components/spatial/glass/` | Superseded | **Remove `components/glass/`** |
| `components/search/` vs `components/spatial/search/` | Superseded | **Remove `components/search/`** |
| `components/transitions/` vs `components/spatial/transitions/` | Superseded | **Remove `components/transitions/`** |
| `components/LivingOrb/` vs `embodiments/LivingOrb/` | Overlapping | **Merge or remove `components/LivingOrb/`** |
| `components/OrbEngine/` vs `engine/` | Misplaced | **Move `OrbEngine/OrbRenderer.ts` to `engine/renderers/`** |
| `components/conversation/` vs `components/spatial/context-panels/` | Different layers | Keep both (conversation = full impl, context-panels = thin wrapper) but rename wrapper |
| `components/hud/` (does not exist) vs `components/spatial/hud/` | N/A | No action needed |

### 11.2 Duplicate Files (Same Name, Different Content)

| File Pair | Difference | Action |
|-----------|-----------|--------|
| `components/camera/CameraController.tsx` vs `components/spatial/camera/CameraController.tsx` | Different implementations | Remove `components/camera/` version |
| `components/camera/CameraModes.tsx` vs `components/spatial/camera/CameraModes.tsx` | Different `LensPreset` types | Remove `components/camera/` version |
| `components/camera/useCameraDirector.ts` vs `components/spatial/camera/useCameraDirector.ts` | Different animation approaches | Remove `components/camera/` version |
| `components/glass/GlassPanel.tsx` vs `components/spatial/glass/GlassPanel.tsx` | Simple vs production | Remove `components/glass/` version |
| `components/LivingOrb/LivingOrb.tsx` vs `embodiments/LivingOrb/LivingOrb.tsx` | Simple wrapper vs props-aware wrapper | Remove `components/LivingOrb/` version |
| `components/OrbEngine/OrbRenderer.ts` vs `engine/renderers/` | Canvas orb vs R3F orb | Keep both but move `OrbRenderer.ts` to `engine/renderers/` |
| `pages/ConversationPanel.tsx` vs `components/spatial/context-panels/ConversationPanel.tsx` | Full page vs thin shell | Rename one to avoid confusion |

---

## 12. Summary of Findings

### Critical (Must Fix)

1. **Four copies of presence→color mapping** — in `presenceTheme.ts`, `usePresenceReactions.tsx`, `OrbRenderer.ts`, and `UniverseView.tsx`
2. **Duplicate camera systems** — `components/camera/` and `components/spatial/camera/` with different animation approaches
3. **Duplicate glass systems** — `components/glass/` and `components/spatial/glass/`
4. **Duplicate dock systems** — `components/dock/` and `components/spatial/dock/`
5. **Duplicate search systems** — `components/search/` and `components/spatial/search/`
6. **Duplicate transition systems** — `components/transitions/` and `components/spatial/transitions/`
7. **DesktopShell `StartupAwakening` references undefined constants** (`DURATION`, `EASING`)

### High (Should Fix)

8. **OrbRenderer.ts** has hardcoded animation constants instead of using `lib/animations`
9. **LivingOrbCenter.tsx** has hardcoded animation constants instead of using `lib/animations`
10. **Two LivingOrb wrappers** (`components/LivingOrb/` and `embodiments/LivingOrb/`)
11. **OrbEngine** is in `components/OrbEngine/` instead of `engine/renderers/`
12. **`usePresenceReactions`** depends only on `presenceState`, not `frameState` — missing frame-level smooth values

### Medium (Should Fix)

13. **ConversationPanel naming collision** between `pages/` and `components/spatial/context-panels/`
14. **`SpatialSelection.tsx`** is in `components/spatial-selection/` instead of `components/spatial/`
15. **`UniverseView.tsx`** has its own `getPresenceColor()` function instead of using `presenceTheme.ts`
16. **`FrameComposer.getPresenceModifiers()`** duplicates the mapping in `usePresenceReactions.tsx`

---

## 13. Recommended Action Plan

### Phase 1: Remove Superseded Duplicates (Week 1)
1. Remove `components/camera/` → keep `components/spatial/camera/`
2. Remove `components/dock/` → keep `components/spatial/dock/`
3. Remove `components/glass/` → keep `components/spatial/glass/`
4. Remove `components/search/` → keep `components/spatial/search/`
5. Remove `components/transitions/` → keep `components/spatial/transitions/`
6. Remove `components/LivingOrb/` → keep `embodiments/LivingOrb/`

### Phase 2: Consolidate Presence→Visual Mapping (Week 2)
7. Create `usePresenceVisuals()` hook in `components/interaction/` that returns all visual parameters from `FrameState`
8. Update `OrbRenderer.ts` to consume visual parameters from `FrameState` instead of hardcoded dictionaries
9. Update `LivingOrbCenter.tsx` to consume visual parameters from `FrameState` instead of direct `PRESENCE_COLORS` lookup
10. Remove `getPresenceColor()` from `UniverseView.tsx` — use `usePresenceReactions` or `usePresenceVisuals`
11. Remove `getPresenceModifiers()` from `FrameComposer.ts` — consolidate into `usePresenceVisuals`

### Phase 3: Fix DesktopShell and Pipeline (Week 3)
12. Fix `DesktopShell.tsx` — import `DURATION` and `EASING`, fix `StartupAwakening`
13. Move `OrbEngine/OrbRenderer.ts` to `engine/renderers/`
14. Rename `components/spatial/context-panels/ConversationPanel.tsx` → `ConversationPanelShell.tsx`
15. Move `SpatialSelection.tsx` to `components/spatial/`

### Phase 4: Unify Animation System (Week 4)
16. Create `OrbAnimationConfig` that derives all orb animation parameters from `FrameState` using shared `lib/animations` constants
17. Update `OrbRenderer.ts` to use `DURATION.breathe`, `EASING.ambient`, `SPRING.breathing`
18. Update `LivingOrbCenter.tsx` to use `DURATION.drift`, `SPRING.breathing`
19. Add `frameState` parameter to `usePresenceReactions` to expose smooth values

---

## 14. Constitutional Compliance

| Rule | Status |
|------|--------|
| Strict Downward Flow | ⚠️ `UniverseView.tsx` imports `PresenceState` from theme — acceptable for consumer |
| 4-Stage Pipeline | ⚠️ `FrameComposer` is the single producer, but renderers bypass it in some paths |
| Renderer Ignorance | ✅ `core/` has zero renderer imports |
| Embodiment Factory | ⚠️ `OrbEngine` is not registered via `EmbodimentFactory` |
| Event Bus Only | ✅ Cross-runtime communication via `EventBus` |
| Thread Isolation | ✅ Physics in Worker, rendering on Main Thread |
| Asset Pipeline | ✅ Async loading with instant proxy fallbacks |

---

*Audit produced by Nova, Frontend Owner, Zaram Team Nova. Sprint 5 review.*
