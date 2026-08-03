# Zaram

The memory and control layer for people who use more than one AI.

Zaram sits between the user and whatever models they use — cloud or local. Everything
flows into one knowledge base on their machine. Any model can recall it. The user sees
what was recalled, can correct it, and controls what leaves the device.

Full rationale: `docs/VISION.md` (read it before proposing product changes — it is
deliberately not auto-imported).

## Canonical vocabulary

Use these terms only. Never substitute alternatives.

- **Spine** — the local knowledge base (index + embeddings + provenance records)
- **Recall** — retrieving prior context into a new exchange
- **Provenance** — the link from a recalled fact to its source
- **Routing** — deciding local vs cloud for a given request
- **Egress log** — the record of what left the machine, when, to which provider
- **Orb** — the system-state indicator. Not a mascot, not a launcher.
- **Workspace** — an MCP-backed tool surface (post-v1)

Do not use: "faculty", "nursery", "aperture", "synapse web", "AI operating system".
These are retired.

## Immutable rules

1. **Never buy inference.** The user brings their own key or their own model. No
   feature may require Zaram to pay per token. This is why the free tier can exist.
2. **Every recalled fact carries provenance.** An answer that cites nothing is a bug.
3. **Every byte that leaves is logged.** The egress log is append-only and
   tamper-evident. Build it into the core, never as a later add-on.
4. **The user can correct or delete any stored fact**, and the affected answers must
   change. This loop is the product.
5. **Nothing leaves the device without an explicit, per-item policy.** Default deny.
6. **Tools confirm before acting.** Autonomy is granted by the user, never a default.
7. **The Spine is exportable in an open format.** No lock-in, ever.

## Scope for v1 — do not exceed

In scope:

- Ingest a folder into the Spine
- Chat routed to at least two providers (one cloud, one local)
- Recall across providers, with visible provenance
- Correct/delete a fact and see answers change
- Egress log, viewable
- Privacy policy per source

Explicitly out of scope until v1 ships and is tested with real users:

- Agents / agent constellations
- Code studio or IDE integration
- Extensions marketplace
- Updates feed
- Voice
- Document generation
- Multi-user, permissions, sync
- Any additional workspace

If a task would add something from the out-of-scope list, stop and say so rather than
building it.

## Technical decisions

- **MCP is the tool protocol.** Never invent a plugin or shim format. Tools are MCP
  servers, curated and permission-scoped.
- **Do not build a memory engine from scratch.** Evaluate Letta (open source,
  self-hostable) or an equivalent before writing retrieval internals. Benchmark
  against LoCoMo / LongMemEval rather than by feel.
- **Design the Spine as federatable from day one** — tenancy seams present even
  though multi-user ships later. Retrofitting is a rewrite.
- **Domain-specific logic stays in a separate layer** from the engine (parsers,
  vocabulary, output templates). Do not build a pack *system* until two packs exist
  and have been built by hand.

## Sequencing commitments

These orderings are decided. Do not reorder them for convenience.

**Egress log → per-source policy → web search as its first governed source.**

Web search does not return until the first two exist. The discovery runtime, its
providers and its 111 tests are built and are deliberately unreachable from the chat
path until then. Rule 3 is the reason: you cannot retroactively log what has already
left the machine.

Corollaries, all binding:

- **Nothing derived from the Spine may appear in an outbound query.** Today this holds
  structurally — the planner passes the raw user prompt as the search query, and
  recalled memories only reach `system_prompt`, which search never reads. That is luck,
  not design. `backend/tests/test_outbound_query_invariant.py` makes it deliberate.
  The obvious future improvement — having a model rewrite the question into a better
  search query — would break it silently.
- **The egress log records the literal outbound text**, not merely that a request
  occurred. What left matters more than that something left.
- **Retention ships with the egress log, not after it.** A log of query text is a
  permanent record of private questions, which is its own privacy problem. The
  retention control belongs in the Settings privacy pane from the first version.
- **Confirm-before-send is a headline feature, not an option.** A dialog showing the
  literal text about to leave, with send and cancel, is the demonstrable form of the
  entire product claim. Build it as the primary path.

## UI/UX principles

- Calm over delight. Motion has a budget. Ship a quiet mode from the start.
- The Orb shows system state (idle / thinking / routing to cloud / local only).
  It does not perform.
- Density beats animation on any surface used daily.
- The target user is not technical. No model filenames, quantization settings, or
  context-length sliders in the primary path. Put them behind an advanced view.
- Show routing decisions in plain language: what handled this, and why.
- Never claim absolute security ("perfectly sealed", "zero leakage"). State what is
  verifiable: inference ran locally, index is on disk, egress is logged.

## Working agreement

- Read before you write. Verify assumptions against the actual code, not the docs.
- Verify by seeing it work — run it, look at it in the browser. Do not report
  progress that has not been observed.
- One honest entrance at a time. Prefer a narrow thing that works over a broad thing
  that demos.
- When a plan and the codebase disagree, the codebase wins — say so rather than
  building against a stale assumption.

## Current milestone

Ship the recall demo: ask model A something, ask model B about it later, get a cited
answer, delete the fact, watch the answer change, open the egress log and see what
left. Everything else waits.
