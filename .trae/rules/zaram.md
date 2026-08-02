---
alwaysApply: true
---

# Zaram Project Rules

`CLAUDE.md` at the repo root is the project contract and wins over this file wherever
they differ. `docs/VISION.md` holds the rationale.

## What Zaram is

The memory and control layer for people who use more than one AI. It sits between the
user and whatever models they use, cloud or local. Everything flows into one knowledge
base — the **Spine** — on the user's machine. Any model can recall from it. The user
sees what was recalled, can correct it, and controls what leaves.

Zaram is **not** an operating system, not an agent framework, and not a workspace suite.
Earlier versions of this file described a five-panel "productivity operating system"
with workspaces as the hero. That direction is retired.

## Vocabulary

Use: **Spine**, **Recall**, **Provenance**, **Routing**, **Egress log**, **Orb**,
**Workspace** (an MCP-backed tool surface, post-v1 only).

Never use: "AI operating system", "faculty", "nursery", "aperture", "synapse web".

## Immutable rules

1. Never buy inference. The user brings their own key or model.
2. Every recalled fact carries provenance. An answer that cites nothing is a bug.
3. Every byte that leaves is logged — append-only, in the core, not bolted on later.
4. The user can correct or delete any stored fact, and answers must change.
5. Nothing leaves the device without an explicit per-source policy. Default deny.
6. Tools confirm before acting. Autonomy is granted, never assumed.
7. The Spine is exportable in an open format.

## Scope

v1 is: ingest a folder into the Spine; chat routed to at least two providers (one cloud,
one local); recall across providers with provenance; correct/delete a fact and see
answers change; a viewable egress log; per-source privacy policy.

Out of scope until v1 ships and is tested with users: agents, IDE integration,
marketplace, updates feed, voice, document generation, multi-user, additional
workspaces. Dormant code for several of these exists — do not activate it.

## UI

- Calm over delight. Motion has a budget. A quiet mode ships from the start.
- The **Orb** shows system state: idle, thinking, routing to cloud, local only. It does
  not perform, and it is not the application.
- Density beats animation on any surface used daily.
- The target user is not technical. No model filenames, quantisation settings or
  context-length sliders in the primary path — put them behind an advanced view.
- Show routing decisions in plain language: what handled this, and why.
- Never claim absolute security. State what is verifiable: inference ran locally, the
  index is on disk, egress is logged.
- Never hardcode colours. Consume design tokens.

## Stack

React 19, TypeScript, Tailwind, Framer Motion, Zustand on the frontend. FastAPI and
Python on the backend. MCP is the tool protocol — never invent a plugin or shim format.

Backend runtimes never import each other; they communicate through the `EventBus` in
`backend/core/event_bus.py`. Do not change backend interfaces unless the task asks for
it.

## Before building on anything

Much of this repo is written, tested, and not wired into the running product. Verify
current state rather than trusting documentation. As of 2 August 2026 the frontend makes
no network calls, only four runtimes boot, one model provider is wired, the Spine is
in-RAM, and 16 backend tests fail.

When a plan and the codebase disagree, the codebase wins — say so rather than building
against a stale assumption.
