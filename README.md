# Zaram

**The memory and control layer for people who use more than one AI.**

You use a frontier model for writing, a local model for anything confidential, an image
tool for design, a coding assistant for builds. Each is capable. None of them remembers
what happened in the others.

Zaram sits between you and every model you use. One knowledge base — the **Spine** — on
your machine. Any model can recall from it. You see what was recalled, you can correct
it, and you control what leaves the device.

Not a model: it routes to yours. Not an agent framework: it serves people doing work,
not developers building products.

## Principles

- **Never buy inference.** You bring your own API key or your own local model. This is
  why the single-user tier can be free and unlimited.
- **Every recalled fact carries provenance.** An answer that cites nothing is a bug.
- **Every byte that leaves is logged**, in an append-only egress log you can read.
- **Nothing leaves without an explicit, per-source policy.** Default deny.
- **Tools confirm before acting.** Autonomy is granted, never assumed.
- **The Spine is exportable in an open format.** No lock-in.

## Status

**Pre-v1.** It runs from source, on one machine, against a local model. There is no
installer yet, so do not expect a working product from a clone alone.

What has been observed working, rather than merely written:

- The recall loop, end to end. The Spine persists to SQLite with Ollama `bge-m3`
  embeddings, the index rebuilds on boot, and a fact stored in one session is recalled
  in the next — verified across a process restart.
- Every recalled fact arrives with provenance the interface displays and can open.
- Deleting a fact changes the answers that depended on it.
- The frontend talks to the backend over NDJSON streaming on port 8420.

What is not built:

- **No egress log**, so no cloud provider is wired and web search is switched off.
  Rule 3 says the log comes first; that ordering is deliberate and is why the
  discovery runtime sits unreachable behind it.
- One provider only — local Ollama. The second, cloud provider is the next milestone.
- No folder ingest.
- Packaging is unproven.

Current milestone — the recall demo:

> Ask model A something. Ask model B about it later. Get a cited answer. Delete the
> fact. Watch the answer change. Open the egress log and see what left.

Four of those six steps work today. The two involving a second model and the egress log
do not. Everything outside this list waits.

## v1 scope

In scope:

- Ingest a folder into the Spine
- Chat routed to at least two providers (one cloud, one local)
- Recall across providers, with visible provenance
- Correct or delete a fact and see answers change
- Viewable egress log
- Per-source privacy policy

Explicitly out of scope until v1 ships and has been tested with real users: agents, IDE
integration, extensions marketplace, updates feed, voice, document generation,
multi-user, and any additional workspace.

## Layout

```text
backend/     FastAPI service. Kernel, event bus, execution engine, runtimes.
frontend/    React + Vite interface. The live UI.
electron/    Electron desktop host (JavaScript).
desktop/     Second Electron host (TypeScript). Duplicate — see below.
packages/    zaram-engine. Currently unused by the frontend.
figma-assets/ Design exports.
```

Known duplication: `electron/` and `desktop/` are two implementations of the same
desktop host, and the root build scripts do not agree on which one ships. One must be
chosen and the other removed.

## Contributing

`CLAUDE.md` is the project contract — vocabulary, immutable rules, v1 scope, technical
decisions. Read it before writing code. `docs/VISION.md` holds the rationale; read it
before proposing product changes.

The working agreement in short: read before you write, verify against the code rather
than the documentation, and when a plan and the codebase disagree, the codebase wins.

## Licence

Not yet chosen. Zaram's core claim is provable non-egress, which a closed binary cannot
substantiate — an OSI-approved licence is required before any public release.
