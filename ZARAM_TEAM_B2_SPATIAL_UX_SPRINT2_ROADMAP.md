# ZARAM TEAM B2 — Spatial UX Sprint 2
## Production-Quality Spatial User Experience

Architecture is frozen. Do not redesign. Do not touch runtime or renderer code.

---

## 0. Guiding Constraints

- Frontend: `C:\Zaram\frontend\`
- Desktop: `C:\Zaram\desktop\`
- **Do not modify** `desktop/src/runtime/`.
- **Do not modify** `desktop/src/main/` except IPC additions already defined in Sprint 1.
- **Do not modify** `frontend/src/core/`, `frontend/src/engine/`, `frontend/src/engine/adapters/`.
- Communicate only through `window.zaram` Runtime APIs.

**Reference Documents (visual authority):**
- `ZARAM_CINEMATIC_GUIDE.md`
- `ZARAM_LIGHTING_BIBLE.md`
- `ZARAM_MATERIAL_REFERENCE.md`
- `ZARAM_VISUAL_STORYBOARD.md`
- `ZARAM_VISUAL_POLISH_CHECKLIST.md`

---

## 1. Priority 1 — Spatial Dock

### Required files

```
frontend/src/components/dock/
├── Dock.tsx                    ← CREATE
├── DockItem.tsx                ← CREATE
├── useDockPhysics.ts           ← CREATE
└── index.ts                   ← CREATE
frontend/src/stores/uiStore.ts  ← UPDATE (add dock position and scale)
```

### Requirements

- **Floating**: Dock is absolutely positioned within `DesktopShell`, default bottom-center with configurable offset.
- **Magnetic**: On hover, nearby items subtly attract toward the cursor (`useDockPhysics.ts` with spring physics). No snap-to-grid; organic motion only.
- **Glass**: Each `DockItem` renders with `backdrop-blur-xl`, `bg-white/5`, `border-white/10`, and a 1px fresnel highlight to match `ZARAM_MATERIAL_REFERENCE.md — Documents & UI (Vision Pro Glass)`.
- **Animated**: `framer-motion` spring transitions on hover/leave. Scale target: 1.15× with `type: 'spring'`, `stiffness: 300`, `damping: 20`.
- **Adaptive scaling**: Dock items shrink proportionally as window width decreases below 1024px. Minimum scale 0.7×.
- **No flat taskbar**: Dock floats above the spatial universe with visible drop shadow and soft reflection.

### Implementation notes

- Reuse `uiStore.ts` (created in Sprint 1 Step 1) for `dockPosition: { x, y }` and `dockScale: number`.
- Read `desktop.app.getPlatform()` on mount to adjust default placement: macOS → bottom-center, Windows → bottom-left.
- Keep all physics in `useDockPhysics.ts`; keep `Dock.tsx` purely presentational.

---

## 2. Priority 2 — Glass HUD System

### Required files

```
frontend/src/components/glass-hud/
├── GlassHUD.tsx                 ← CREATE
├── HUDWindow.tsx                ← CREATE
├── HUDOverlay.tsx               ← CREATE
├── useHUD.ts                    ← CREATE
├── GlassMaterial.tsx            ← CREATE (shared backdrop-blur + edge-lit surface)
└── index.ts                    ← CREATE
```

### Requirements

- **Backdrop blur**: `backdrop-blur-2xl` plus a CSS noise texture overlay for the frosted material described in `ZARAM_MATERIAL_REFERENCE.md — Documents & UI`.
- **Dynamic edge lighting**: A 1px `box-shadow` or gradient border that reacts to `presenceState` from `PresenceProvider`. Idle = cyan, Thinking = purple, Speaking = green, Error = red.
- **Shadow & depth**: Multi-layered `box-shadow` for lift. Hover increases Y offset and spreads the shadow.
- **Soft reflections**: Add a pseudo-element with a subtle linear gradient (opacity 6–10%) near the bottom edge to simulate acrylic reflection.
- **Auto hide**: Dock behind `DesktopShell` after 4 seconds idle. Use `useHUD.ts` with `requestAnimationFrame` idle detection.
- **Dockable**: When pinned, collapse to a 48×48 tab. When expanded, show content.
- **Apple Vision Pro quality**: No hard edges. All radii `rounded-2xl` or `rounded-3xl` with `overflow-hidden` and `border-white/10`.

### Hook

Create `frontend/src/components/glass-hud/useHUD.ts`:

```tsx
export function useHUD() {
  const [open, setOpen] = useState(true)
  const [docked, setDocked] = useState(false)
  const [visible, setVisible] = useState(true)
  const idleTimer = useRef<number | null>(null)

  const resetIdle = useCallback(() => {
    setVisible(true)
    if (idleTimer.current) window.clearTimeout(idleTimer.current)
    idleTimer.current = window.setTimeout(() => setVisible(false), 4000)
  }, [])

  // ...
  return { open, setOpen, docked, setDocked, visible, resetIdle }
}
```

Register `mousemove` and `keydown` listeners in `GlassHUD.tsx` to call `resetIdle()`.

---

## 3. Priority 3 — Context Panels

### Required files

```
frontend/src/components/context-panels/
├── ConversationPanel.tsx        ← REPLACE pages/ConversationPanel.tsx with presentation-only shell
├── ProjectPanel.tsx             ← CREATE
├── MemoryPanel.tsx              ← CREATE
├── DocumentPanel.tsx            ← CREATE
├── InspectorPanel.tsx           ← CREATE
├── PanelShell.tsx               ← CREATE
├── PanelHeader.tsx              ← CREATE
└── index.ts                    ← CREATE
```

### Requirements

- **Smooth summon animation**: Panels enter with `initial={{ opacity: 0, y: 20, scale: 0.98 }}`, `animate={{ opacity: 1, y: 0, scale: 1 }}`, `transition={{ type: 'spring', damping: 24, stiffness: 200 }}`.
- **Cinematic easing**: Never linear. All panel transitions use `framer-motion` spring curves.
- **Depth aware**: Panels rendered in `DesktopShell` at z-40 to z-60. Presence canvas at z-0. Panels must not occlude critical spatial UI.
- **Rule-of-thirds positioning**: Panels default to left/right thirds. Center panels are forbidden. Left panels align at `left: 2rem`, right panels at `right: 2rem`.
- **ConversationPanel**: Strip all orchestration logic from `pages/ConversationPanel.tsx`. Extract into `pages/` only as a page router. The real UI lives in `components/context-panels/ConversationPanel.tsx`.
- **ProjectPanel**: Shows workspace projects via `desktop.workspace.getAllProjects()`. No business logic; display only.
- **MemoryPanel**: Shows memory entries from `useChatStore` or future Memory API. UI-only.
- **DocumentPanel**: Shows files via `desktop.workspace.getSnapshot()` and `desktop.vscode.getWorkspaceFolders()`.
- **InspectorPanel**: Generic inspector for selected entity. Consume `desktop.executive.getSnapshot()` or selected node data from `uiStore`.

### Shared shell

Create `PanelShell.tsx`:

```tsx
export function PanelShell({ children, title, onClose }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20, scale: 0.98 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 20, scale: 0.98 }}
      transition={{ type: 'spring', damping: 24, stiffness: 200 }}
      className="glass absolute right-4 top-4 bottom-4 w-96 z-40 rounded-2xl border border-white/10 shadow-2xl flex flex-col overflow-hidden"
    >
      <PanelHeader title={title} onClose={onClose} />
      <div className="flex-1 overflow-y-auto">{children}</div>
    </motion.div>
  )
}
```

---

## 4. Priority 4 — Spotlight Search

### Required files

```
frontend/src/components/search/
├── SearchOverlay.tsx            ← CREATE
├── SearchInput.tsx              ← CREATE
├── SearchResults.tsx            ← CREATE
├── SearchGroup.tsx              ← CREATE
├── useSearchShortcut.ts         ← CREATE
└── index.ts                    ← CREATE
```

### Requirements

- **Trigger**: Register `⌘K` / `Ctrl+K` in `DesktopShell.tsx` via `useEffect` + `keydown`. Close on `Escape`.
- **Glass overlay**: Full-screen `fixed inset-0 z-50` with `bg-black/40 backdrop-blur-sm`.
- **Cinematic dolly zoom**: On open, apply a CSS transform to the spatial background container: `scale(0.95)` + `filter: blur(4px)`. Transition duration 300ms cubic-bezier(0.16, 1, 0.3, 1). This matches `ZARAM_CINEMATIC_GUIDE.md — Search Cinematics`.
- **Focus mode**: Once a result group is selected, dim unrelated groups to `opacity: 30%`.
- **Particle attraction**: Optional; if time permits, add a subtle `framer-motion` `animate` on result cards that makes them drift slightly toward the center.
- **Recent searches**: Persisted in `searchStore`.
- **Results grouped**: Projects, Documents, Memory, Knowledge, Agents.
- **No search logic**: UI only. Consume `desktop.workspace.getAllProjects()`, `desktop.capability.getByCategory(...)`, and store them in `searchStore`. No semantic search implementation.

### Hook

Create `frontend/src/components/search/useSearchShortcut.ts`:

```tsx
export function useSearchShortcut(onOpen: () => void, onClose: () => void) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        onOpen()
      }
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onOpen, onClose])
}
```

---

## 5. Priority 5 — Spatial Selection

### Required files

```
frontend/src/components/spatial-selection/
├── HoverEffect.tsx              ← CREATE
├── SelectionEffect.tsx          ← CREATE
├── FocusEffect.tsx              ← CREATE
└── index.ts                    ← CREATE
```

### Requirements

- **Hover**: On entity hover, scale target 1.05×, apply soft bloom (`filter: drop-shadow(0 0 8px rgba(...))`), and show a 1px outline matching the entity's emotional hue. Hide after 150ms leave delay.
- **Selection**: When selected, shift camera offset using runtime-presence APIs. Show `InspectorPanel` with contextual details. Do not move the camera directly; emit a directive that the existing camera system consumes.
- **Focus**: Deep focus mode with DoF simulation. Background entities desaturate to 20% opacity. Selected entity receives a soft glow halo.

### Constraints

- Do not import from `frontend/src/engine/`, `frontend/src/core/`, `desktop/src/runtime/`.
- Use `desktop.presence.onFrame` and `desktop.executive.getSnapshot()` for contextual data.

---

## 6. Priority 6 — Camera Controller (UI-Side)

### Scope

Only UI-side camera directives. Do not modify renderer.

### Required files

```
frontend/src/components/camera/
├── CameraController.tsx         ← CREATE
├── CameraModes.tsx              ← CREATE (24mm / 50mm / 85mm presets)
├── useCameraDirector.ts         ← CREATE
└── index.ts                    ← CREATE
```

### Requirements

- **24mm**: Wide angle. Default. Used in Solar/Overview modes.
- **50mm / 85mm**: Intimate view. Triggered when opening a panel (Conversation, Inspector, Document). Use `framer-motion` `animate` on the presence canvas wrapper to simulate focal length shift via scale and border-radius.
- **Momentum / Inertia**: Track mouse velocity. On release, apply an exponential decay curve (`ease-out-cubic` minimum). Zero linear interpolation.
- **Bezier movement**: All position changes use cubic bezier spline paths. Implement via `framer-motion` path animation or manually computed spline with `requestAnimationFrame`.
- **No linear interpolation**: Enforce `ease: [0.16, 1, 0.3, 1]` or similar on all motion props.

### Hook

Create `frontend/src/components/camera/useCameraDirector.ts`:

```tsx
export function useCameraDirector() {
  const [mode, setMode] = useState<'solar' | 'intimate' | 'overview'>('solar')
  const [target, setTarget] = useState<{ x: number; y: number } | null>(null)
  
  const focusOnPanel = useCallback((panel: 'conversation' | 'inspector' | 'project') => {
    // Determine offset based on panel position (rule of thirds)
    setMode('intimate')
    setTarget({ x: panel === 'conversation' ? -30 : 30, y: 0 })
  }, [])

  const returnToSolar = useCallback(() => {
    setMode('solar')
    setTarget(null)
  }, [])

  return { mode, target, focusOnPanel, returnToSolar }
}
```

Apply `target` as a `framer-motion` `animate` prop on the presence canvas wrapper.

---

## 7. Priority 7 — Transition Library

### Required files

```
frontend/src/components/transitions/
├── TransitionLibrary.tsx        ← CREATE
├── StartupTransition.tsx        ← CREATE
├── ShutdownTransition.tsx       ← CREATE
├── SearchTransition.tsx         ← CREATE
├── ProjectEntryTransition.tsx   ← CREATE
├── ConversationFocusTransition.tsx ← CREATE
├── MemoryRecallTransition.tsx   ← CREATE
└── index.ts                    ← CREATE
```

### Requirements

Implement all sequences from `ZARAM_VISUAL_STORYBOARD.md` as reusable React transitions.

- **Startup (The Awakening)**: Black screen → Living Orb expands over 3s → ambient particles fade in. Implement as a stored state in `uiStore` (`appPhase: 'loading' | 'ready'`) and a full-screen overlay.
- **Shutdown (The Sleep)**: Orb dims → collapses to single pixel → fades to black. Triggered by window close or `desktop.app` quit.
- **Search (The Hunt)**: Dolly zoom as described in Priority 4. Reuse `SearchTransition` from `SearchOverlay.tsx`.
- **Project Entry (The Descent)**: Camera accelerates forward (`scale(1.2)` on spatial canvas, duration 800ms cubic-bezier(0.7, 0, 1, 0.5)). Particles stretch via CSS `filter: blur(2px)`.
- **Conversation Focus**: Gentle push-in to 50mm equivalent. Panel slides in from right. Background desaturates 20%.
- **Memory Recall**: Global white balance warms (CSS `sepia(10%)`), contrast drops slightly. Slow bloom increase.

### Implementation pattern

Use `framer-motion` `AnimatePresence` + context providers. Expose a `useTransition()` hook:

```tsx
export function useTransition() {
  const [active, setActive] = useState<string | null>(null)
  
  const play = useCallback((name: string) => {
    setActive(name)
    setTimeout(() => setActive(null), 1200)
  }, [])

  return { active, play }
}
```

---

## 8. Priority 8 — Performance Friendly UI

### Required files

```
frontend/src/components/performance/
├── PerformanceMonitor.tsx       ← CREATE (dev-only overlay)
└── useRenderOptimization.ts     ← CREATE
```

### Requirements

- **No unnecessary rerenders**: Wrap all panel content in `React.memo`. Use Zustand selectors with shallow equality.
- **Memoized panels**: `PanelShell` must be memoized. Child panels must not re-render when sibling panel state changes.
- **Virtualized lists**: Conversation feed, search results, and history lists use `@tanstack/react-virtual` or equivalent windowing.
- **Shared materials**: Extract all glass styles into `frontend/src/styles/glass.css`. Import via `@import` in `index.css`. Never inline repetitive blur/border/bg classes.
- **Shared glass shaders**: For R3F-rendered HUD elements (future), define a single `glassMaterial.ts` in `frontend/src/components/glass-hud/`. For DOM-based HUD, use the CSS approaches above.

### Checklist

- [ ] All heavy components wrapped in `React.memo`.
- [ ] Zustand stores use shallow selectors: `useStore(state => state.foo)` instead of `useStore(state => state)`.
- [ ] Long lists virtualized.
- [ ] Global CSS variables defined in `glass.css`:
  - `--glass-bg: rgba(255, 255, 255, 0.03)`
  - `--glass-border: rgba(255, 255, 255, 0.08)`
  - `--glass-blur: 24px`
  - `--glass-shadow: 0 8px 32px rgba(0, 0, 0, 0.4)`
  - `--glass-radius: 16px`

---

## 9. File Change Summary

### Create (new files)

```
frontend/src/components/dock/
├── Dock.tsx
├── DockItem.tsx
├── useDockPhysics.ts
└── index.ts

frontend/src/components/glass-hud/
├── GlassHUD.tsx
├── HUDWindow.tsx
├── HUDOverlay.tsx
├── useHUD.ts
├── GlassMaterial.tsx
└── index.ts

frontend/src/components/context-panels/
├── ProjectPanel.tsx
├── MemoryPanel.tsx
├── DocumentPanel.tsx
├── InspectorPanel.tsx
├── PanelShell.tsx
├── PanelHeader.tsx
└── index.ts

frontend/src/components/search/
├── SearchOverlay.tsx
├── SearchInput.tsx
├── SearchResults.tsx
├── SearchGroup.tsx
├── useSearchShortcut.ts
└── index.ts

frontend/src/components/spatial-selection/
├── HoverEffect.tsx
├── SelectionEffect.tsx
├── FocusEffect.tsx
└── index.ts

frontend/src/components/camera/
├── CameraController.tsx
├── CameraModes.tsx
├── useCameraDirector.ts
└── index.ts

frontend/src/components/transitions/
├── TransitionLibrary.tsx
├── StartupTransition.tsx
├── ShutdownTransition.tsx
├── SearchTransition.tsx
├── ProjectEntryTransition.tsx
├── ConversationFocusTransition.tsx
├── MemoryRecallTransition.tsx
└── index.ts

frontend/src/components/performance/
├── PerformanceMonitor.tsx
└── useRenderOptimization.ts

frontend/src/styles/
└── glass.css
```

### Modify (existing files)

- `frontend/src/stores/uiStore.ts` — Add dock position/scale, active panels, app phase, camera mode.
- `frontend/src/stores/searchStore.ts` — Add recent searches, suggestions, grouped results placeholders.
- `frontend/src/components/layout/DesktopShell.tsx` — Wire all new layers (Dock, GlassHUD, ContextPanels, SearchOverlay, Transitions).
- `frontend/src/components/pages/ConversationPanel.tsx` — Strip orchestration logic; move to presentation-only shell.
- `frontend/src/main.tsx` — Ensure `PresenceProvider` wraps `App` (already in Sprint 1).

---

## 10. Runtime API Usage (Only These)

All new UI code must consume data exclusively through:

- `desktop.presence.onFrame` / `getStatus` / `getHealth`
- `desktop.executive.getSnapshot` / `plan` / `setPendingSpeech`
- `desktop.capability.getSnapshot` / `getById` / `getByCategory`
- `desktop.execution.getHistory` / `onEvent` / `cancel`
- `desktop.workspace.getState` / `getSnapshot` / `getAllProjects` / `setRootPath`
- `desktop.vscode.getSnapshot` / `getWorkspaceFolders` / `getDiagnostics`
- `desktop.settings.get` / `set`
- `desktop.dialog.openFile` / `selectDirectory`
- `desktop.notification.show`
- `desktop.clipboard.readText` / `writeText`
- `desktop.backend.checkHealth` / `getStatus`
- `desktop.app.getInfo` / `getVersion` / `getPlatform`

No other desktop imports are allowed.

---

## 11. Acceptance Criteria

- [ ] Spatial Dock renders bottom-center, floats above universe, scales responsively.
- [ ] Glass HUD renders with frosted glass, dynamic edge lighting, auto-hide after 4s idle.
- [ ] Context panels summon with cinematic easing, respect rule-of-thirds.
- [ ] Search overlay opens via `Ctrl+K` with dolly zoom cinematic.
- [ ] Selection / hover / focus effects render without touching renderer internals.
- [ ] Camera transitions use cubic bezier exclusively—zero linear interpolation.
- [ ] All storyboard sequences from `ZARAM_VISUAL_STORYBOARD.md` have an implementation.
- [ ] Conversation, Project, Memory, Document, and Inspector panels are functional UI shells consuming Runtime APIs.
- [ ] Zero regression in existing shell loading.
- [ ] Renderer remains untouched.
- [ ] Runtime code remains untouched.
