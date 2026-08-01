
# ZARAM TEAM B2 — Application Layer Sprint 1
## Desktop Shell Implementation — Build Roadmap

Architecture is frozen. Do not redesign. Do not touch runtime code or the renderer.

---

## 0. Guiding Constraints

- Frontend: `C:\Zaram\frontend\`
- Desktop: `C:\Zaram\desktop\`
- **Do not modify** `desktop/src/runtime/`.
- **Do not modify** `desktop/src/main/` unless adding IPC handlers.
- **Do not modify** any files in `frontend/src/core/`, `frontend/src/engine/`, `frontend/src/engine/adapters/`.
- Communicate only through `window.zaram` (defined in `desktop/src/preload/index.ts`).

---

## 1. Existing Runtime API Surface

The preload bridge exposes these surfaces. Consume only these:

| Surface | Methods | Source |
|---------|---------|--------|
| `window.zaram.presence` | `onFrame`, `onViewport`, `onEvent`, `getStatus`, `getHealth` | `desktop/src/preload/index.ts` |
| `window.zaram.executive` | `getSnapshot`, `plan`, `getPlan`, `getConfidence`, `getEvidence`, `getMetrics`, `setPendingSpeech`, `subscribe` | `desktop/src/preload/index.ts` |
| `window.zaram.capability` | `getSnapshot`, `getById`, `getByCategory` | `desktop/src/preload/index.ts` |
| `window.zaram.execution` | `execute`, `getExecution`, `getHistory`, `cancel`, `retry`, `onEvent` | `desktop/src/preload/index.ts` |
| `window.zaram.workspace` | `getState`, `getContext`, `getSnapshot`, `setRootPath`, `getProject`, `getAllProjects`, `discover`, `subscribe` | `desktop/src/preload/index.ts` |
| `window.zaram.runtime` | `desktopGetSources`, `onPresenceEvent` | `desktop/src/preload/index.ts` |
| `window.zaram.notification` | `show` | `desktop/src/preload/index.ts` |
| `window.zaram.dialog` | `openFile`, `saveFile`, `selectDirectory` | `desktop/src/preload/index.ts` |
| `window.zaram.shell` | `openExternal`, `openPath` | `desktop/src/preload/index.ts` |
| `window.zaram.clipboard` | `readText`, `writeText` | `desktop/src/preload/index.ts` |
| `window.zaram.settings` | `get`, `set` | `desktop/src/preload/index.ts` |
| `window.zaram.backend` | `getStatus`, `checkHealth` | `desktop/src/preload/index.ts` |
| `window.zaram.app` | `getInfo`, `getVersion`, `getPlatform` | `desktop/src/preload/index.ts` |
| `window.zaram.system` | `getPlatform`, `getVersion`, `getArch` | `desktop/src/preload/index.ts` |
| `window.zaram.vscode` | `getSnapshot`, `getEditor`, `getWorkspaceFolders`, `getDiagnostics`, `getGitStatus`, `onEvent` | `desktop/src/preload/index.ts` |
| `window.zaram.filesystem` | `getMetrics` | `desktop/src/preload/index.ts` |
| `window.zaram.character` | `getFrame` | `desktop/src/preload/index.ts` |
| `window.zaram.cognitive` | `getState`, `getAttention`, `getRelationship` | `desktop/src/preload/index.ts` |
| `window.zaram.world` | `getState` | `desktop/src/preload/index.ts` |

The frontend `desktop-bridge.ts` already wraps these in a `desktop` object.

---

## 2. STEP 1 — Application Layout

**Goal:** A single root `App.tsx` that composes the shell, without tying itself to the renderer.

### Required structure

```
frontend/src/
├── App.tsx                          ← REPLACE contents (currently instantiates SimulationRuntime + R3FRendererAdapter directly)
├── components/
│   └── layout/
│       ├── DesktopShell.tsx         ← CREATE
│       └── SpatialUniverseViewport.tsx ← CREATE
├── stores/
│   ├── uiStore.ts                   ← CREATE
│   ├── searchStore.ts               ← CREATE
│   ├── commandStore.ts              ← CREATE
│   ├── notificationStore.ts         ← CREATE
│   └── contextMenuStore.ts          ← CREATE
```

### What to change

1. **`frontend/src/App.tsx`** (existing) — Make it a shell-only component:
   - Remove all direct `SimulationRuntime`, `FrameComposer`, `mapToVisualState`, `R3FRendererAdapter` instantiation.
   - Return `<DesktopShell>` as the sole child (minus ThemeProvider / QueryClientProvider which remain in `main.tsx`).

2. **`frontend/src/main.tsx`** (existing) — Keep it as-is. It should continue wrapping `<App />` with `React.StrictMode → QueryClientProvider → ThemeProvider`.

3. **`frontend/src/components/layout/DesktopShell.tsx`** (new) — Import and compose:
   - `SpatialUniverseViewport`
   - `GlassHUD`
   - `ConversationPanel`
   - `CommandPalette`
   - `SearchOverlay`
   - `NotificationLayer`
   - `Dock`
   - `ContextMenus`

   Use CSS Grid / absolute positioning. Do not embed business logic.

4. **`frontend/src/components/layout/SpatialUniverseViewport.tsx`** (new) — A wrapper component that lazily mounts the renderer. Renderer instantiation belongs to the renderer layer, not the shell; use a dynamic import or lazy boundary.

### Zustand stores to create

Create a single file per store under `frontend/src/stores/`:

- **`uiStore.ts`** — GlassHUD open/closed, dock position, conversation panel expanded/collapsed.
- **`searchStore.ts`** — Search query, results, recent searches, suggestions, active overlay boolean.
- **`commandStore.ts`** — Command palette open/closed, selected command, command history.
- **`notificationStore.ts`** — Toast queue, add/remove/pin.
- **`contextMenuStore.ts`** — Context menu position, visible state, items array.

All stores must be plain Zustand with no dependencies on runtime code.

---

## 3. STEP 2 — Glass HUD

**Goal:** VisionOS-style floating interface container.

### Required files

Update or create:

```
frontend/src/components/glass-hud/
├── GlassHUD.tsx              ← CREATE
├── HUDOverlay.tsx            ← CREATE
├── HUDWindow.tsx             ← CREATE
├── useHUD.ts                 ← CREATE
└── index.ts                  ← CREATE
frontend/src/styles/
└── glass.css                 ← CREATE
```

### Requirements

- **Position**: Absolute-positioned within `DesktopShell`. Default position: top-left.
- **Style**: Use `backdrop-blur-xl`, `bg-white/5`, `border-white/10`, rounded corners.
- **Motion**: Auto-hide after 3s idle. `framer-motion` `AnimatePresence`.
- **Dockable**: When collapsed, show a tab; when expanded, show content.
- **No business logic**: Do not import from `core/`, `engine/`, `runtime/`.
- **Data only from Runtime APIs**: Read presence state (`usePresenceState` from `PresenceProvider`) for contextual status.

### Hook

Create `frontend/src/components/glass-hud/useHUD.ts`:

```tsx
export function useHUD() {
  const [open, setOpen] = useState(true)
  const [docked, setDocked] = useState(false)
  const [autoHideTimer, setAutoHideTimer] = useState<any>(null)

  const resetAutoHide = useCallback(() => { ... }, [])
  const dock = useCallback(() => setDocked(true), [])
  const undock = useCallback(() => setDocked(false), [])

  return { open, setOpen, docked, dock, undock, resetAutoHide }
}
```

---

## 4. STEP 3 — Conversation Window

**Goal:** Primary read/write interface for messages.

### Existing assets to reuse

- Do NOT rewrite. Use/conserve:
  - `frontend/src/components/chat/Chat.jsx` (messages, send, audio)
  - `frontend/src/components/chat/ChatInput.jsx`
  - `frontend/src/components/chat/ChatMessage.jsx`
  - `frontend/src/stores/chatStore.ts`

### Required files

```
frontend/src/components/conversation/
├── ConversationPanel.tsx      ← REPLACE contents of pages/ConversationPanel.tsx, strip non-UI orchestration
├── ConversationFeed.tsx       ← EXISTS (imported by ConversationPanel.tsx)
├── ConversationInput.tsx      ← EXISTS (imported by ConversationPanel.tsx)
├── ConversationHeader.tsx     ← CREATE
├── MessageActions.tsx         ← CREATE (copy, stop, regenerate)
├── VoiceWaveform.tsx          ← CREATE (placeholder)
├── ThinkingIndicator.tsx      ← CREATE
└── MarkdownRenderer.tsx       ← CREATE
```

### Requirements

- **Message history**: Render from `useChatStore`.
- **Streaming responses**: Consume `desktop.execution.onEvent` for token delta (use `TokenAccumulator` from `frontend/src/lib/tokenAccumulator.ts`).
- **Voice waveform**: UI-only placeholder; wire to `desktop.presence.onFrame` for `audioInput.voiceLevel` when audio is active.
- **Thinking indicator**: UI-only animated dots, shown when message status is `thinking`.
- **Stop generation**: Call `desktop.execution.cancel(executionId)`.
- **Copy response**: Call `desktop.clipboard.writeText`.
- **Markdown / code blocks**: Use a lightweight renderer. No external AI logic.
- **Auto scroll**:Scroll to latest message on new content.
- **Resizable / Dockable**: Hook into `uiStore` for size and dock state.

---

## 5. STEP 4 — Dock

**Goal:** Animated app launcher.

### Required files

```
frontend/src/components/dock/
├── Dock.tsx                   ← CREATE
├── DockItem.tsx               ← CREATE
└── index.ts                  ← CREATE
```

### Requirements

- **Items**: Conversation, Knowledge, Projects, Memory, Agents, Settings.
- **Animated icons**: `framer-motion` scale/spring on hover.
- **Tooltips**: Show on hover via `title` or custom tooltip.
- **Responsive**: Dock shrinks/expands with window width. `useWindowSize` hook.
- **Location**: Bottom center or side, configured in `uiStore`.

---

## 6. STEP 5 — Search Overlay

**Goal:** Spotlight-style `<Ctrl+K>` search.

### Required files

```
frontend/src/components/search/
├── SearchOverlay.tsx          ← CREATE
├── SearchInput.tsx            ← CREATE
├── SearchResults.tsx          ← CREATE
├── SearchGroup.tsx            ← CREATE
└── index.ts                  ← CREATE
```

### Requirements

- **Trigger**: `⌘K` / `Ctrl+K` keyboard shortcut registered in `DesktopShell.tsx`.
- **Glass overlay**: Full-screen modal with `backdrop-blur`, `bg-black/40`.
- **Recent searches**: Persisted in `searchStore`.
- **Suggestions**: Static placeholder list; consume `searchStore`.
- **Results grouped**: Projects, Documents, Memory, Knowledge, Agents.
- **No search logic**: UI only. Call `desktop.workspace.getState()` and `desktop.capability.getSnapshot()` to populate results when needed.

---

## 7. STEP 6 — Command Palette

**Goal:** Universal action runner.

### Required files

```
frontend/src/components/command-palette/
├── CommandPalette.tsx         ← CREATE
├── CommandList.tsx            ← CREATE
├── CommandItem.tsx            ← CREATE
└── index.ts                  ← CREATE
```

### Requirements

- **Trigger**: `⌘/Ctrl+Shift+P` or via Dock.
- **Surface**: Same glass overlay style as Search.
- **Commands**:
  - Open Settings → `desktop.settings...`
  - Create Project → `desktop.workspace...` (UI-only scaffolding)
  - New Conversation → `useChatStore.newConversation()`
  - Import Document → `desktop.dialog.openFile`
  - Open Memory → navigate to Memory page (future)
  - Open Knowledge → navigate to Knowledge view (future)
  - Launch Agent → `desktop.capability.getByCategory('agents')` (UI-only)
- **State**: `commandStore` holds selected index, query filter.

---

## 8. STEP 7 — Notification Layer

**Goal:** Toast system.

### Existing asset to reuse

- **Do not rewrite.** Keep `frontend/src/hooks/useNotifications.tsx` and `NotificationContainer`.
- Convert from a hook-only pattern to a store-backed layer.

### Required files

```
frontend/src/components/notification-layer/
├── NotificationLayer.tsx      ← CREATE (wraps NotificationContainer)
├── NotificationQueue.tsx      ← CREATE
└── index.ts                  ← CREATE
```

### Requirements

- **Types**: Success, Warning, Error, Information.
- **Queue**: FIFO ordering, max visible toast count.
- **Auto dismiss**: 4s default.
- **Pinned**: Ability to pin.
- **Glass styling**: Match `glass-hud` palette.
- **API**: `desktop.notification.show(title, body)` for native OS notifications when appropriate.

---

## 9. STEP 8 — Context Menus

**Goal:** Generic right-click / long-press / keyboard context menu.

### Required files

```
frontend/src/components/context-menus/
├── ContextMenu.tsx            ← CREATE
├── ContextMenuTrigger.tsx     ← CREATE
├── ContextMenuItems.tsx       ← CREATE
└── index.ts                  ← CREATE
```

### Requirements

- **Trigger**: Right-click, long-press, `Shift+F10`, context-menu key.
- **Positioning**: Use `clientX` / `clientY` or element bounding rect. Store in `contextMenuStore`.
- **Dynamic items**: Menu items can be passed as a prop array.
- **Behavior**: Close when clicking outside or pressing Escape.
- **Styling**: Glass panel with white/10 border.

---

## 10. Preload / IPC Changes Required

Only `desktop/src/preload/index.ts` and `desktop/src/main/lifecycle.ts` may be minimally extended.

### Candidates for new IPC channels

Add only if a UI step needs them. Currently available:

- `notification:show` — already exists in `IpcBridge`.
- `dialog:open-file`, `dialog:save-file`, `dialog:select-directory` — already exist in main `index.ts`.

No new channels are strictly required for Steps 1–8. Search results and commands consume already-exposed runtime APIs.

---

## 11. Frontend Entry Wiring

After Step 1, `frontend/src/main.tsx` should look like this:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@/theme/ThemeProvider'
import { PresenceProvider } from '@/context/PresenceContext'
import App from './App.jsx'
import './index.css'

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <PresenceProvider>
          <App />
        </PresenceProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
)
```

---

## 12. Acceptance Criteria

For each step, verify:

1. **App Layout**
   - Entire application loads.
   - SpatialUniverseViewport mounts without touching runtime code.
   - Zustand stores instantiate cleanly.
   - Renderer remains untouched.

2. **Glass HUD**
   - Renders with frosted glass.
   - Auto-hides after 3s idle.
   - Is responsive.
   - Is scalable (reparents on layout change).

3. **Conversation Window**
   - Messages render from `chatStore`.
   - Streaming works via `desktop.execution.onEvent`.
   - Stop button calls `desktop.execution.cancel`.
   - Copy button calls `desktop.clipboard.writeText`.
   - No mock business logic.

4. **Dock**
   - Items visible and animated.
   - Responsive to window resize.

5. **Search Overlay**
   - Opens with `Ctrl+K`.
   - Glass overlay renders.

6. **Command Palette**
   - Opens with `Cmd+Shift+P`.
   - Filters commands.
   - Launches actions.

7. **Notification Layer**
   - Toasts appear and auto-dismiss.
   - Pinning works.

8. **Context Menus**
   - Right-click opens menu.
   - Keyboard opens menu.

---

## 13. Do Not Build

Do not touch these:

- `frontend/src/core/` — simulation, frame composer, mapper
- `frontend/src/engine/` — R3F adapter, renderer
- `frontend/src/engine/adapters/`
- `desktop/src/runtime/` — any file in here
- `desktop/src/main/lifecycle.ts` — except optional minimal IPC additions
- AI logic, mock chat services, mock providers (`frontend/src/services/api.js`, `frontend/src/stores/api.ts`)
- React Router / routing pages beyond what exists in `frontend/src/pages/`

---

## 14. Definition of Done

The user should be able to:

1. Launch Zaram.
2. See the Spatial Universe through `SpatialUniverseViewport`.
3. Open the Conversation Window.
4. Open Search.
5. Open Command Palette.
6. Use the Dock.
7. Receive Notifications.
8. Interact with Glass HUD.

All while remaining completely decoupled from the renderer and runtime implementations.
