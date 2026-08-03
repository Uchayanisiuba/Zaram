# Zaram — Continue Rules

`CLAUDE.md` at the repo root is the project contract. It wins over this file wherever
they differ. `docs/VISION.md` holds the rationale — read it before proposing product
changes, not before routine implementation.

## What Zaram is

The memory and control layer for people who use more than one AI. It sits between the
user and whatever models they use, cloud or local. One knowledge base — the **Spine** —
on the user's machine. Any model can recall from it, with visible provenance, and the
user controls what leaves the device.

Not an operating system. Not an agent framework. Do not use the phrase "AI operating
system", or the retired terms "faculty", "nursery", "aperture", "synapse web".

## Rules

1. **Never buy inference.** The user brings their own key or their own model. No feature
   may require Zaram to pay per token.
2. **Every recalled fact carries provenance.** An answer that cites nothing is a bug.
3. **Every byte that leaves is logged.** Append-only, tamper-evident, built into the
   core rather than added later.
4. **The user can correct or delete any stored fact**, and affected answers must change.
5. **Nothing leaves the device without an explicit per-source policy.** Default deny.
6. **Tools confirm before acting.** Autonomy is granted by the user, never assumed.
7. **MCP is the tool protocol.** Never invent a plugin or shim format.
8. **Runtimes never import each other.** Use the `EventBus` in
   `backend/core/event_bus.py`.

## Scope

v1 is six things: ingest a folder into the Spine; chat routed to at least two providers;
recall across providers with provenance; correct/delete a fact and see answers change; a
viewable egress log; per-source privacy policy.

Out of scope until v1 ships: agents, IDE integration, marketplace, updates feed, voice,
document generation, multi-user, additional workspaces. Dormant code for several of
these exists in the repo — finding it is not permission to activate it. If a task
requires something out of scope, stop and say so.

## Before you build on anything

Much of this repo is written, tested, and not connected to the running product. Verify
rather than assume. As of 3 August 2026:

Working — do not "fix" these: the recall loop runs end to end (the Spine persists to
SQLite at `backend/spine.db` with Ollama `bge-m3` embeddings, and recalled memories
emit provenance events); `POST /chat` works against local Ollama.

Not connected: the frontend makes no network calls at all and has nowhere to display
provenance; only four runtimes boot; one model provider is wired and there is no cloud
path; there is no egress log. 13 backend tests fail, 11 of them a stale test double
rather than broken product code.

Anything you inject into a model's context must also emit a `StreamEvent.source`.
`backend/tests/test_provenance_invariant.py` enforces this.

## Quality

```bash
./backend/venv/Scripts/python.exe -m ruff check backend/   # ~1264 errors outstanding
cd frontend && npx tsc --noEmit                            # currently clean — keep it
```

Leave the tree no worse than you found it. Do not mass-fix unrelated files.
