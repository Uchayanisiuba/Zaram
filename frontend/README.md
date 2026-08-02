# Zaram Frontend

The React interface for Zaram — the memory and control layer for people who use more
than one AI. See `CLAUDE.md` at the repo root for the project contract.

## Stack

React 19, TypeScript, Vite, Tailwind, Framer Motion, Zustand.

## Commands

```bash
npm run dev        # Vite dev server on :5173
npm run build      # production build to dist/ (works)
npm run typecheck  # tsc --noEmit — currently clean, keep it that way
npm run lint       # BROKEN: eslint is not installed
```

## Current state — read before building

**This interface does not talk to the backend.** There are no `fetch` calls, no API
client, and no network requests of any kind in `src/`. What you see running is a
high-fidelity prototype:

- Chat replies come from a hardcoded string in `src/components/chat/ChatSurface.tsx`.
  The same sentence is returned for every input.
- The memory graph in `src/workspaces/MemoryWorkspace.tsx` is a hand-written array of
  fabricated nodes.
- Every workspace renders sample data.

Wiring one surface to the backend for real is the current priority. The backend serves
`POST /chat` and ten other endpoints on `:8000`.

## Known problems

- `npm run lint` crashes — `eslint` is absent from `node_modules`.
- `tests/*.test.ts` are all **0 bytes**. `vitest.config.ts` only scans `src/**/*.test.*`
  so it would not find them anyway, and its `setupFiles` points at `src/test-setup.ts`,
  which does not exist. The test harness is broken three ways.
- `src/runtime/` contains 19 zero-byte files with real-sounding names
  (`RuntimeBus.ts`, `RuntimeProvider.tsx`, `OrbRuntime.ts`, …). They are empty.
- `src/theme/ThemeProvider.tsx` calls `usePresenceRuntime()`, which throws unless a
  `PresenceProvider` is mounted. None is mounted anywhere, so rendering `ThemeProvider`
  would crash the app. Currently dormant.
- `package.json` pins `react@19.0.0-rc` (a release candidate) against React **18** type
  definitions.
- Several components in `src/components/` have no importers and never render.

## Scope

v1 needs exactly these surfaces: folder ingest, a chat view routed to two providers,
recall with visible provenance, fact correction/deletion, and an egress log view.

Agents, code studio, marketplace, updates feed, voice and document generation are out of
scope. Some have components in the tree; they are not to be revived.
