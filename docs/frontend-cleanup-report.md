# Frontend Cleanup Report

**Date:** 2026-07-28  
**Auditor:** Frontend Cleanup Engineer  
**Project:** Zaram Frontend

---

## Executive Summary

The Zaram frontend has already undergone significant cleanup. The current state is minimal with a single entry point rendering a `WorkspaceMount` component that displays presence state and the Living Orb. However, there are several broken imports, unused code, and unnecessary dependencies that need removal before the Shell 2.0 rebuild.

---

## 1. Audit Results

### 1.1 Current File Structure (Frontend)

```
frontend/
├── src/
│   ├── main.jsx                    ✅ Entry point - WORKS
│   ├── WorkspaceMount.jsx          ✅ Root component - WORKS
│   ├── index.css                   ✅ Global styles
│   ├── index.html                  ✅ HTML template
│   ├── vite.config.js              ✅ Vite config
│   │
│   ├── components/
│   │   ├── common/
│   │   │   └── ErrorBoundary.tsx   ✅ Used in main.jsx
│   │   └── OrbEngine/
│   │       ├── OrbEngine.tsx       ✅ Used in WorkspaceMount
│   │       └── OrbRenderer.ts      ✅ Used by OrbEngine
│   │
│   ├── context/
│   │   └── PresenceContext.tsx     ✅ Core runtime context - PRESERVE
│   │
│   ├── theme/
│   │   ├── ThemeProvider.tsx       ✅ Used in main.jsx - PRESERVE
│   │   └── presenceTheme.ts        ✅ Used by PresenceContext - PRESERVE
│   │
│   ├── hooks/
│   │   ├── useNotifications.tsx    ✅ Not used anywhere - REMOVE
│   │   ├── useAccessibility.ts     ✅ Not used anywhere - REMOVE
│   │   └── useZaram.js             ❌ BROKEN - references non-existent ZaramContext
│   │
│   ├── store/
│   │   └── useZaramStore.ts        ✅ Zustand store - PRESERVE (runtime)
│   │
│   ├── desktop/
│   │   └── desktop-bridge.ts       ✅ IPC bridge - PRESERVE
│   │
│   ├── core/
│   │   └── frame/
│   │       ├── types.ts            ✅ FrameState contract - PRESERVE
│   │       └── composer.ts         ✅ FrameComposer - PRESERVE
│   │
│   ├── engine/                     ✅ Engine runtime - PRESERVE
│   │   ├── index.ts
│   │   ├── bootstrap.ts
│   │   ├── animation/AnimationRuntime.ts
│   │   ├── assets/AssetRegistry.tsx
│   │   ├── lod/LODManager.ts
│   │   ├── materials/MaterialRegistry.ts
│   │   ├── particles/ParticleRuntime.ts
│   │   ├── shaders/ShaderRegistry.ts
│   │   └── ...
│   │
│   └── assets/                     ✅ Static assets - KEEP
│       ├── vite.svg
│       ├── react.svg
│       └── hero.png
```

---

## 2. Issues Identified

### 2.1 Broken Imports (Critical)

| File | Issue | Severity |
|------|-------|----------|
| `src/hooks/useZaram.js:2` | Imports `ZaramContext` from `../context/ZaramContext` which **does not exist** | **CRITICAL** - Will crash if imported |

### 2.2 Unused Components (Dead Code)

| File | Used By | Action |
|------|---------|--------|
| `src/hooks/useNotifications.tsx` | Nowhere | **REMOVE** |
| `src/hooks/useAccessibility.ts` | Nowhere | **REMOVE** |
| `shared/LivingOrb/LivingOrb.tsx` | Nowhere in frontend | **REMOVE** (shared) |

### 2.3 Unused Shared Types

| File | Used By | Action |
|------|---------|--------|
| `shared/types/workspace.ts` | Nowhere in frontend | **REMOVE** (shared) |
| `shared/types/artifacts.ts` | Nowhere in frontend | **REMOVE** (shared) |
| `shared/personaVoices.ts` | Nowhere in frontend | **REMOVE** (shared) |

### 2.4 Excessive Dependencies (package.json)

The following dependencies appear unused in the current minimal frontend:

| Dependency | Reason to Remove |
|------------|------------------|
| `@react-three/drei` | Not imported anywhere |
| `@react-three/fiber` | Not imported anywhere |
| `three` | Not imported anywhere |
| `framer-motion` | Only used in removed `useNotifications.tsx` |
| `lucide-react` | Only used in removed `useNotifications.tsx` |
| `react-markdown` | Not imported anywhere |
| `react-syntax-highlighter` | Not imported anywhere |

**Actually needed:** `react`, `react-dom`, `zustand`, `@tanstack/react-query`

### 2.5 Orphaned Engine Exports

The `engine/index.ts` exports many systems that may not be used. Verify each:
- `LODManager` - Check usage
- `ShaderRegistry` - Check usage  
- `AssetRegistry` - Check usage
- `MaterialRegistry` - Check usage
- `ParticleRuntime` - Check usage
- `AnimationRuntime` - Used by OrbRenderer? No, OrbRenderer is canvas-based
- `PerformanceOverlay` - Check usage
- `EmbodimentRegistry` - Check usage

---

## 3. Preservation Checklist (Must Keep)

These components are **critical runtime infrastructure** and must NOT be removed:

| Category | Files | Purpose |
|----------|-------|---------|
| **Entry Point** | `main.jsx`, `index.html`, `vite.config.js` | App bootstrap |
| **Root Component** | `WorkspaceMount.jsx` | Shell mount point |
| **Error Boundary** | `components/common/ErrorBoundary.tsx` | Crash protection |
| **Presence Runtime** | `context/PresenceContext.tsx` | FrameState, IPC, presence |
| **Theme System** | `theme/ThemeProvider.tsx`, `theme/presenceTheme.ts` | CSS variables, state colors |
| **Orb Engine** | `components/OrbEngine/OrbEngine.tsx`, `components/OrbEngine/OrbRenderer.ts` | Living Orb rendering |
| **IPC Bridge** | `desktop/desktop-bridge.ts` | Electron communication |
| **Core Contracts** | `core/frame/types.ts`, `core/frame/composer.ts` | FrameState, FrameComposer |
| **Runtime Store** | `store/useZaramStore.ts` | Zustand state |
| **Engine Runtime** | `engine/` (all) | Backend engine systems |

---

## 4. Cleanup Plan

### Phase 1: Remove Broken/Unused Code
1. Delete `src/hooks/useZaram.js` (broken import)
2. Delete `src/hooks/useNotifications.tsx` (unused)
3. Delete `src/hooks/useAccessibility.ts` (unused)

### Phase 2: Remove Unused Shared Code
4. Delete `shared/LivingOrb/` (not used in frontend)
5. Delete `shared/types/workspace.ts` (not used in frontend)
6. Delete `shared/types/artifacts.ts` (not used in frontend)
7. Delete `shared/personaVoices.ts` (not used in frontend)

### Phase 3: Clean Dependencies
8. Update `package.json` - remove unused deps:
   - `@react-three/drei`, `@react-three/fiber`, `three`
   - `framer-motion`, `lucide-react`
   - `react-markdown`, `react-syntax-highlighter`

### Phase 4: Verify
9. Run `npm run dev` - confirm launches without errors
10. Run `npm run build` - confirm production build works

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking OrbEngine | Low | High | OrbEngine only uses canvas + FrameState types |
| Breaking PresenceContext | Low | High | No changes to PresenceContext |
| Breaking desktop-bridge | Low | High | No changes to bridge |
| Missing dep at runtime | Medium | Medium | Test dev server after cleanup |

---

## 6. Post-Cleanup State

After cleanup, the frontend will have:

```
frontend/
├── src/
│   ├── main.jsx
│   ├── WorkspaceMount.jsx
│   ├── index.css
│   ├── context/PresenceContext.tsx
│   ├── theme/ThemeProvider.tsx
│   ├── theme/presenceTheme.ts
│   ├── store/useZaramStore.ts
│   ├── desktop/desktop-bridge.ts
│   ├── core/frame/types.ts
│   ├── core/frame/composer.ts
│   ├── components/
│   │   ├── common/ErrorBoundary.tsx
│   │   └── OrbEngine/OrbEngine.tsx
│   │   └── OrbEngine/OrbRenderer.ts
│   └── engine/ (all preserved)
├── package.json (minimal deps)
├── vite.config.js
└── index.html
```

**Result:** Clean, stable foundation for Shell 2.0 rebuild. No UI, just runtime.