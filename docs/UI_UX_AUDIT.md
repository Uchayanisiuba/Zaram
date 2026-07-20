# Zaram OS — UI/UX Audit (Sprint 2.7 / 2.7A)

## 1. High-Level Architecture

| Layer | Implementation | Status |
|-------|---------------|--------|
| **Shell** | Electron main process + BrowserWindow | Stable |
| **Frontend framework** | React 18 + Vite + Tailwind CSS | Stable |
| **State management** | React hooks + Zustand stores | Stable |
| **IPC bridge** | `desktop-bridge.ts` wraps `window.zaram` / `window.electron` | Stable |
| **Animations** | Framer Motion + Canvas `OrbRenderer` | Stable (crash fixed) |

### Layout Pattern
- Fixed sidebar (`w-64`) + top bar (`h-12`) + content area + status bar (`h-8`)
- Dark theme only: `bg-[#050810]` / `bg-[#0a0f1c]` / `slate-200` text
- Glass-morphism cards: `glass` class with `bg-black/40 border border-white/10`

---

## 2. Navigation & Information Architecture

### Sidebar Navigation (`App.jsx:21-28`)
```ts
const NAV_ITEMS = [
  { id: 'orchestration', label: 'Orchestration', icon: Activity },
  { id: 'conversation', label: 'Conversation', icon: MessageSquare },
  { id: 'audit', label: 'Audit Terminal', icon: Terminal },
  { id: 'runtime', label: 'Runtime Inspector', icon: Cpu },
  { id: 'capabilities', label: 'Capabilities', icon: Search },
  { id: 'filesystem', label: 'Filesystem', icon: FolderOpen },
]
```

### UX Observations
- **Persistence**: View selection saved to `localStorage` (`zaram-dev-preview-view`) — good.
- **Active state**: White background + border + chevron — clear affordance.
- **Missing**: No keyboard shortcuts, no breadcrumbs, no history back/forward.

---

## 3. Page-by-Page UX Review

### 3.1 Orchestration (`Orchestration.tsx`)
- **Purpose**: Primary landing page; shows Living Orb + runtime state + metrics.
- **Strengths**:
  - Large centered orb creates immediate visual identity.
  - State badge (`STATE: THINKING`) color-coded via `STATE_COLORS`.
  - Bottom metric cards (Frame Rate, Dropped Frames, GPU Time, Embodiment).
- **Gaps**:
  - Controls are minimal (only refresh button). No play/pause/skip actually wired.
  - `togglePause` stub does nothing (line 45-49).
  - No explanation of what the orb represents for new users.

### 3.2 Conversation (`ConversationPanel.tsx`)
- **Purpose**: Chat interface that executes real runtime plans.
- **Strengths**:
  - End-to-end execution timeline with per-step status indicators.
  - Executive state pill shows current AI state (Thinking, Planning, Searching, etc.).
  - Workspace context pill with confidence percentage.
  - File reference extraction + preview buttons.
  - Markdown rendering for assistant responses.
  - Voice input button (stub — opens file dialog).
- **Gaps**:
  - Empty state text is generic ("Start a conversation with the Executive Runtime").
  - No suggested prompts or example queries.
  - No retry/edit for failed steps.
  - Timeline auto-scrolls but no manual scroll anchoring.
  - Error messages show raw exception text — no user-friendly retry action.

### 3.3 Runtime Inspector (`RuntimeInspector.tsx`)
- **Purpose**: Dashboard showing all registered runtimes and their health.
- **Strengths**:
  - 2-column grid of runtime cards with status dots.
  - Color-coded status (healthy/degraded/offline).
  - System diagnostics section (frame rate, dropped frames, GPU time).
  - Executive runtime section with goal, plan steps, evidence.
  - Workspace runtime section with advanced mode toggle for hashes.
  - Filesystem and VS Code capability pack sections.
  - Capability metrics table (calls, avg time, success rate).
- **Gaps**:
  - Auto-refreshes every 1s via `refresh()` — but `refresh` is called in `useEffect` without deps, causing potential double-refresh.
  - No way to drill into a specific runtime for deeper diagnostics.
  - Metrics table has no sorting/filtering.

### 3.4 Capability Explorer (`CapabilityExplorer.tsx`)
- **Purpose**: Browse registered capabilities.
- **Status**: Standard list/grid view. Not deeply reviewed in this sprint.

### 3.5 Filesystem Demo (`FilesystemDemo.tsx`)
- **Purpose**: Manual filesystem capability testing.
- **Status**: Functional demo UI.

### 3.6 Runtime Health Dashboard (NEW — Sprint 2.7)
- **Purpose**: Compact health overview in sidebar.
- **Strengths**:
  - Always-visible status for 6 core runtimes.
  - Browser mode gracefully shows `Unavailable`.
  - Icons + color-coded badges.
- **Gaps**:
  - Only checks once after 1s delay — no continuous polling or re-check on failure.
  - No drill-down from dashboard to detailed inspector.

---

## 4. Visual Design System

### Color Palette
| Role | Color | Usage |
|------|-------|-------|
| Background | `#050810` / `#0a0f1c` | App background, sidebar |
| Surface | `rgba(0,0,0,0.4)` | Cards, bubbles |
| Border | `rgba(255,255,255,0.1)` | Cards, inputs |
| Primary accent | `cyan-400` / `cyan-500` | Brand, active states |
| Secondary accent | `orange-500` | Gradient, bot avatar |
| Success | `green-400` | Healthy, completed |
| Warning | `yellow-400` | Initializing |
| Error | `red-400` | Failed, error states |
| Text primary | `slate-200` / `white` | Body, headings |
| Text secondary | `slate-400` / `slate-500` | Subtitles, metadata |

### Typography
- Headings: `text-lg font-bold tracking-wide`
- Body: `text-sm text-slate-200`
- Metadata: `text-[10px] font-mono uppercase tracking-widest`
- Consistent use of `font-mono` for status, metrics, and code-like data.

### Spacing
- Sidebar padding: `p-6` (header) / `p-4` (nav) — consistent.
- Content padding: `px-6 py-4` — consistent.
- Card padding: `p-5` — consistent.
- Gap patterns: `gap-2`, `gap-3`, `gap-4` — used consistently.

---

## 5. Desktop vs. Browser Mode UX

### Bridge (`desktop-bridge.ts`)
- `safe()` wrapper returns `null` fallback when API unavailable.
- `isDesktop` flag computed from `window.zaram` or `window.electron`.
- All desktop APIs gracefully degrade in browser.

### Browser Mode Behavior
- Runtime Health Dashboard shows all runtimes as `Unavailable`.
- Conversation panel still renders but `desktop.executive.plan()` returns `null` → shows error message.
- OrbEngine mounts but receives no frame data — stays on `IDLE_FRAME`.

### UX Gap
- No prominent "Browser Mode — Desktop features unavailable" banner.
- Users may not understand why conversation doesn't work in browser.

---

## 6. Real-Time Data & State Management

### Patterns Observed
1. **Polling**: `Orchestration.tsx` polls `desktop.presence.getHealth()` every 1s.
2. **Event subscriptions**: `ConversationPanel.tsx` subscribes to `desktop.execution.onEvent()` and `desktop.executive.onSnapshot()`.
3. **Zustand stores**: `useWorkspaceContextStore` for workspace snapshot + indexing state.
4. **Notifications**: `useNotifications` hook with toast container.

### Issues
- **Memory leaks**: `onEvent` subscriptions in `RuntimeInspector.tsx` (lines 90-106) may not clean up properly if `refresh` changes.
- **Race conditions**: `waitForExecution` in `ConversationPanel.tsx` resolves on both event AND polling — could double-resolve.

---

## 7. Accessibility & Usability

### Current State
- **Keyboard**: Enter to send message — good. No other keyboard navigation.
- **Focus states**: Not explicitly styled — relies on browser defaults.
- **Screen reader**: No `aria-label` on icon-only buttons (Mic, Play, Refresh).
- **Contrast**: Light cyan/green on dark blue — generally passes WCAG AA.
- **Loading states**: Spinner + text label present in conversation.
- **Error states**: Shown inline but not summarized in a status bar.

---

## 8. Known Bugs & Edge Cases

| Bug | Location | Severity |
|-----|----------|----------|
| `togglePause` stub does nothing | `Orchestration.tsx:45-49` | Low |
| `refresh` in `RuntimeInspector` recreated every render | `RuntimeInspector.tsx:58-83` | Medium |
| Browser mode shows raw "Error: Executive Runtime did not return a plan" | `ConversationPanel.tsx:331` | Medium |
| Voice button opens file picker instead of recording | `ConversationPanel.tsx:344-361` | Low |
| `onHistoryChange` subscribes same handler twice | `desktop-bridge.ts:100-107` | Low |
| Runtime Health Dashboard polls only once | `useRuntimeHealth.ts:108` | Medium |

---

## 9. Recommended Next Steps for GPT

### Priority 1 — Fix Existing UX Bugs
1. Fix `togglePause` to actually call `desktop.presence.resume()` / `.pause()`.
2. Fix `refresh` callback stability in `RuntimeInspector` (wrap in `useCallback` with correct deps or move out of render).
3. Add browser-mode banner so users understand why features are unavailable.
4. Fix `onHistoryChange` double-subscription leak.

### Priority 2 — Improve Conversation UX
5. Add suggested prompts / example queries in empty state.
6. Show user-friendly error with retry button instead of raw exception.
7. Add ability to re-run a failed step from timeline.
8. Persist conversation history to `localStorage`.

### Priority 3 — Enhance Runtime Inspector
9. Add drill-down modal for each runtime showing detailed metrics.
10. Implement proper polling interval (e.g., 2s) instead of 1s to reduce IPC load.
11. Add sort/filter to capability metrics table.
12. Show capability descriptions and permission requirements.

### Priority 4 — Visual Polish
13. Add loading skeleton screens for Runtime Inspector cards.
14. Implement smooth page transitions (framer motion `AnimatePresence` on route change).
15. Add dark/light theme toggle (system preference detection).
16. Improve empty states across all pages with illustrations or icons.

### Priority 5 — Accessibility
17. Add `aria-label` to all icon-only buttons.
18. Implement keyboard navigation for sidebar (arrow keys).
19. Add focus-visible ring styles.
20. Test with screen reader (NVDA/JAWS).

### Priority 6 — Performance
21. Virtualize long conversation lists (`react-window` or `react-virtual`).
22. Debounce timeline updates to reduce re-renders.
23. Lazy-load heavy pages (Capability Explorer, Filesystem Demo).

---

## 10. Summary for GPT

Zaram OS has a **cohesive dark-themed desktop shell** with a clear sidebar navigation pattern. The **Orchestration** page establishes visual identity via the Living Orb. The **Conversation** panel is the most complex UX — it successfully bridges real runtime execution with a chat interface, including execution timelines and file references. The **Runtime Inspector** provides deep diagnostic visibility but needs stability fixes and drill-down capabilities.

The biggest UX gaps are:
- **Stubs and incomplete wiring** (pause/play, voice input).
- **Browser mode transparency** (no clear indication that desktop features are unavailable).
- **Error handling** (raw exceptions shown to users).
- **Polling stability** (unstable callback refs causing potential double-fetches).

The design system is consistent and modern. The next phase should focus on **completing the wiring** of existing controls, **hardening the real-time data layer**, and **polishing empty/error states** before adding new features.
