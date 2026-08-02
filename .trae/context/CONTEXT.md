# Zaram — Shared Agent Context

**For:** Trae, Cursor, Kilo, Cline, Continue, and any other AI coding agent
**Last updated:** 2026-08-02

`CLAUDE.md` at the repo root is the project contract — vocabulary, immutable rules, v1
scope, technical decisions. Read it first; it wins over this file. `docs/VISION.md`
holds the rationale, to be read before proposing product changes.

This file exists for one thing the contract does not cover: **the actual state of the
code**, so you do not build against assumptions.

---

## What Zaram is

The memory and control layer for people who use more than one AI. It sits between the
user and whatever models they use, cloud or local. One knowledge base — the **Spine** —
on the user's machine. Any model can recall from it, with visible provenance. The user
controls what leaves the device.

Not an operating system. Not an agent framework. Not a workspace suite. Earlier context
documents described an "8 Engine" productivity OS with a unified memory graph and
industry plugin packs — that direction is retired in full.

## Verified state of the code

Established by running the code on 2 August 2026, not by reading documentation.

**Works:**

- Backend FastAPI service boots and serves 11 endpoints.
- 676 backend tests pass.
- Frontend compiles clean (0 TypeScript errors) and builds for production.
- Electron security configuration is correct: `contextIsolation: true`,
  `nodeIntegration: false`, `webSecurity: true`.

**Does not work, or is not connected:**

- **The frontend makes zero network calls.** It does not talk to the backend at all.
  Chat replies are a hardcoded string; the memory graph is fabricated sample data.
- **Only four runtimes boot** (`backend/core/bootstrapper.py`): memory, knowledge,
  models, speech. Agent, artifacts, capability, filesystem, intent, internet,
  reliability, tool, discovery and presence are reachable only from their own tests.
- **One model provider is wired.** `models_runtime.py` imports `OllamaEngine` and
  nothing else. Multi-provider code exists in `backend/garage/` and does not boot.
- **The Spine does not persist.** The bootstrapper requests `store_type="memory"`
  (in-RAM). `SQLiteMemoryStore` exists and is not selected. Embeddings are `hash`-based,
  not semantic.
- **16 backend tests fail**, 11 of them the streaming conversation pipeline.
- **There is no egress log.** Network calls originate independently from
  `knowledge/providers/*`, `runtimes/internet/*` and `runtimes/memory/embeddings.py`.
- `frontend/src/runtime/` contains 19 zero-byte files with real-sounding names.
- `packages/zaram-engine` (3,496 lines) is imported by nothing.
- `electron/` and `desktop/` are two Electron hosts; the build scripts disagree about
  which one ships.

Finding dormant code is not permission to activate it. Much of it belongs to surfaces
that have been cut.

## Stack

Frontend: React 19, TypeScript, Tailwind, Framer Motion, Zustand, Vite.
Backend: FastAPI, Python 3.11+, Ollama for local inference.
Tools: MCP only — never invent a plugin or shim format.

## Working method

- Read before you write. Verify against the code, not the docs. This repo's
  documentation has been wrong more often than right, which is why it was reduced to
  two files.
- Verify by observation — run it, look at it. Do not report progress you have not seen.
- Prefer a narrow thing that works over a broad thing that demos.
- When a plan and the codebase disagree, the codebase wins. Say so.
- Tools confirm before acting. If a permission is denied, stop and report it — do not
  route around it.

## Current milestone

The recall demo: ask model A something, ask model B about it later, get a cited answer,
delete the fact, watch the answer change, open the egress log and see what left.

Everything else waits.
