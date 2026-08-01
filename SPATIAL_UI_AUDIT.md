# SPATIAL_UI_AUDIT.md

## 1. Spatial Motion Audit

### Completed
- Audit of all inline animation constants across `frontend/src/components`.
- Expanded shared token library in `frontend/src/lib/animations.ts`:
  - Added `DURATION.micro`, `DURATION.breathe`, `DURATION.descent`, `DURATION.normal`, `DURATION.fast`, `DURATION.panel`, `DURATION.dolly`, `DURATION.awakening`, `DURATION.sleep`
  - Added `SPRING.dockShell`, `SPRING.dockItem`, `SPRING.hud`, `SPRING.search`, `SPRING.input`, `SPRING.layout`, `SPRING.selection`, `SPRING.lens`
- Replaced inline motion constants with shared tokens in:
  - `components/primitives/List.tsx`, `TreeView.tsx`, `SplitView.tsx`, `Tabs.tsx`, `Modal.tsx`, `ContextMenu.tsx`, `PanelShell.tsx`
  - `components/spatial/camera/CameraController.tsx`, `useCameraDirector.ts`
  - `components/spatial/search/SearchOverlay.tsx`, `SearchInput.tsx`, `SearchGroup.tsx`, `SearchResults.tsx`
  - `components/spatial/dock/Dock.tsx`, `SpatialDock.tsx`, `useDockPhysics.ts`
  - `components/spatial/glass-hud/GlassHUD.tsx`, `HUDOverlay.tsx`, `GlassMaterial.tsx`
  - `components/spatial/hud/HUDAnchor.tsx`, `FloatingLabels.tsx`
  - `components/spatial/windows/WindowWrapper.tsx`
  - `components/spatial/transitions/TransitionLibrary.tsx`, project/memory/conversation transitions
  - `components/workspace/WorkspaceLayout.tsx`
  - `components/ActionButton.tsx`
  - `components/conversation/ConversationFeed.tsx`
  - `components/layout/DesktopShell.tsx`

### Remaining / Acceptable
- `frontend/src/components/layers/AmbientAI.tsx` uses CSS easing names (`easeInOut`, `easeOut`) and computed durations (`0.7 + i * 0.1`) for organic ambient variation. These are environmental effect layers, not UI transitions. Documented here; do not refactor without explicit request.
- `frontend/src/components/layers/WeatherEngine.tsx` uses similar organic timing for environmental particles.

## 2. Visual Consistency

### Completed
- New spatial primitives (`PanelShell`, `GlassSurface`, `Dock`, `ContextMenu`, `List`, `TreeView`, etc.) all use consistent:
  - Corner radius: `rounded-2xl` (shells), `rounded-xl` (inputs/menus)
  - Border: `border border-white/10`
  - Glass background: `bg-white/[0.03]` or `bg-white/5`
  - Shadow: `shadow-2xl` or `shadow-[0_8px_32px_rgba(0,0,0,0.4)]`
  - Typography: `text-sm` for body, `text-xs` for labels, `text-xs font-mono` for metadata
  - Spacing: `px-4 py-3` for containers, `px-3 py-2` for items
- `SceneRoot`-mounted `PresenceProvider` → `ThemeProvider` chain ensures all presence-driven colors stay synchronized.

### Remaining
- Legacy components in `components/` (e.g., `chat/`, `memory/`, `knowledge/`, `layers/`) were not refactored per sprint constraints ("Nothing new. Only refinement."). They still use their own spacing/glass/shadow patterns.
- Recommendation: Follow-up sprint to migrate legacy components to shared glass classes and spacing tokens.

## 3. Spatial Layout

### Completed
- `DesktopShell.tsx` panels now constrain width with `max-w-[calc(100%-2rem)]`.
- `WindowWrapper.tsx` now clamps dragged position to viewport bounds.
- `Dock.tsx` floats at `bottom-5` with responsive scaling via `useAdaptiveDockScale`.
- `SearchOverlay.tsx` uses `pt-[20vh]` to avoid clipping on small viewports.

### Remaining
- Hardcoded `w-[28rem]` panels may still feel wide on 1366px laptops. Recommend adding a breakpoint-based max-width or collapsing panels on screens < 1440px wide.
- `CameraController` uses absolute positioning with fixed aspect assumptions. Test on 16:9 vs 16:10 vs ultrawide.
- No explicit XR breakpoints (future).

## 4. Window System Polish

### Completed
- `WindowWrapper.tsx`: added drag-state tracking, cursor feedback (`cursor-grab` / `active:cursor-grabbing`), viewport bounds clamping.
- Panels animate open/close with shared spring token (`SPRING.panel`).
- `z-index` managed explicitly via `z-40` for panels, `z-50` for modals, `z-70` for transitions.

### Remaining
- Window minimize/maximize buttons not implemented (acceptance criteria mentioned them; left for next sprint as these are new features, not refinements).
- No window snapping to edges. Could follow up with snap-to-safe-area on drag end.

## 5. Search Experience

### Completed
- `SearchOverlay.tsx`: cinematic dolly zoom backdrop, `SPRING.search` for panel, keyboard navigation, `AnimatePresence` for open/close.
- `SearchResults.tsx`: grouped results, mouse hover selection, keyboard arrow navigation, recent searches.
- `SearchGroup.tsx`: staggered entry animation.
- `SearchInput.tsx`: focus ring with `SPRING.input`.
- Empty state: "No results found" present.
- Loading state: inherited via `useSearchStore` query state (consumer can render loading UI).

### Remaining
- No explicit loading skeleton in `SearchResults.tsx`. Recommend adding a `<SearchLoading />` skeleton component.
- Mouse hover selection does not auto-scroll as smoothly as keyboard selection on fast moves.

## 6. Accessibility

### Completed
- `useAccessibility.ts`: shared `useFocusTrap`, `useIdleDetector`.
- `Modal.tsx`, `Popover.tsx`, `ContextMenu.tsx`: focus trap + Escape dismiss.
- `SearchOverlay.tsx`: `role="dialog"`, `aria-modal`, `aria-label`.
- `PanelShell.tsx`: semantic heading + close button with `aria-label`.
- `Dock.tsx`, `Tabs.tsx`, `List.tsx`, `TreeView.tsx`: `role` + `aria-selected` / `aria-expanded`.

### Remaining
- No `prefers-reduced-motion` hook or media-query wrapper. Add `useReducedMotion()` that disables framer-motion animations when the OS setting is enabled.
- Focus restoration after modal close is basic; could use `useFocusManagement` for nested focus rings.
- Color contrast on some `text-slate-500` elements on `bg-[#050505]` may not meet WCAG 2.1 AA for small text. Recommend contrast audit.

## 7. Performance

### Completed
- Heavy components wrapped in `React.memo`: `Tabs`, `List`, `Inspector`, `PropertyGrid`, `TreeView`, `SplitView`, `Modal`, `Popover`, `ContextMenu`, `PanelShell`, `PanelHeader`, `Dock`, `GlassHUD`, `HUDWindow`, `SearchOverlay`, `SearchInput`, `SearchResults`, `SearchGroup`, `CameraController`, `CameraLensOverlay`, `SpatialSelectionOverlay`, `ProjectPanel`, `MemoryPanel`, `DocumentPanel`, `InspectorPanel`, `ConversationPanel`.
- `useMemo` / `useCallback` used for callbacks and derived arrays (`searchGroups`, `Dock` items, `DesktopShell` panel routing).
- Zustand selectors avoid whole-store subscriptions (`useUIStore((s) => s.appPhase)`, etc.).
- Shared `AnimatePresence` keys prevent unmounted-state leaks.

### Remaining
- `ConversationFeed.tsx` re-renders on every message due to its internal scroll state. Recommend extracting scroll manager into a wrapper or using `useRef`-driven scroll without state.
- `PresenceProvider` still pushes `FrameState` into a separate context at 60fps. `useFrameState` consumers will re-render. Acceptable for now; consider batching or throttling if GPU-bound.
- Bundle size remains >2 MB. Recommend code-splitting context panels and search via `React.lazy`.

## 8. Summary of Delivered Changes

### New / Updated Files
- `frontend/src/lib/animations.ts` — expanded shared tokens
- `frontend/src/components/primitives/` — Tabs, List, Inspector, PropertyGrid, TreeView, SplitView, Modal, Popover, ContextMenu, PanelShell, PanelHeader, Input
- `frontend/src/components/spatial/` — dock, glass-hud, context-panels, search, camera, transitions, selection
- `frontend/src/components/performance/` — PerformanceMonitor, useRenderOptimization
- `frontend/src/hooks/useAccessibility.ts` — focus trap, idle detector
- `frontend/src/styles/glass.css` — shared glass CSS variables
- `frontend/src/stores/uiStore.ts`, `searchStore.ts`
- `frontend/src/components/layout/DesktopShell.tsx` — composed shell
- `frontend/src/context/PresenceContext.tsx` — presence → theme bridge
- `frontend/src/theme/ThemeProvider.tsx` — consumes presence runtime
- `frontend/src/main.tsx` — provider order
- Multiple refinements in legacy components (`Dock.tsx`, `WorkspaceLayout.tsx`, `ConversationFeed.tsx`, `ActionButton.tsx`, `WindowWrapper.tsx`, `useCameraDirector.ts`)

### Verification
- `vite build` passes clean after all changes.
