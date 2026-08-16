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

**Pre-v1**, and further along than this file said until 16 August 2026 — it claimed
there was no egress log, no cloud provider, no folder ingest and no installer, all of
which had stopped being true. Corrected rather than quietly rewritten, because a status
section that understates a project is the same defect as one that overstates it, and it
sits on the one page a stranger reads first.

What has been observed working, rather than merely written:

- **The recall loop, end to end.** The Spine persists to SQLite with Ollama `bge-m3`
  embeddings, the index rebuilds on boot, and a fact stored in one session is recalled
  in the next — verified across a process restart.
- **Every recalled fact arrives with provenance** the interface displays and can open.
  Correcting or deleting one changes the answers that depended on it.
- **The egress log.** Append-only, hash-chained, viewable, with the literal text of what
  left. Per-host policy, default deny, and a kill switch that lives in the policy rather
  than in a route, so it covers tool traffic and model discovery too.
- **Confirm before send**, verified against a live provider: preview, log and wire were
  byte-identical at 1650 bytes, with a struck fact absent from all three.
- **Cloud providers and web search**, several connections at once, routed per model.
- **Folder ingest**, with per-source privacy policy.
- **Generated documents** — .docx, .xlsx, .pdf, .md, .csv, charts — with preview.
- **Speech both directions**, local and optional, keeping pace with the text.
- **An installer**: `Zaram-0.1.0-x64.exe`, 186 MB, plus a portable build.
- **Export.** Everything Zaram holds, as JSONL and CSV in one .zip.

What is not built:

- **Obligation extraction is not wired.** The extractor reads payment, deliverable,
  expiry and renewal clauses with the sentence each came from, and nothing calls it.
  This is the differentiator and it is the next real feature.
- **Knowledge domains**, and ingestion by drop, paste or upload. The parsers exist; the
  way in does not.
- **The local API has no authentication.** A `Host` check refuses DNS rebinding, so a
  web page cannot reach it — but any process on this machine still can.
- **The installer has not been run on a machine that has never seen this repo.** Until
  that happens, treat "a stranger can install this" as unproven.

## v1 scope

In scope:

- Ingest a folder, a dropped file, or pasted text into the Spine
- Knowledge domains, linkable to projects
- Chat routed across local and cloud providers, including free tiers, with the data
  policy of each stated before it is chosen
- Recall across providers, with visible provenance
- Correct or delete a fact and see answers change
- Viewable egress log, per-source privacy policy, export
- The business base layer: invoices, quotes, receipts, expenses
- Obligation extraction, surfaced before it lapses
- Generative documents, and read-only MCP for Unreal and Blender
- The character: your own name, manner, voice and VRM for it

Explicitly out of scope until v1 ships and has been tested with real users: agents, IDE
integration, extensions marketplace, mutative tools, multi-user, and any additional
workspace.

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
