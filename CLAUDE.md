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

Do not use: "faculty", "nursery", "aperture", "synapse web", "AI operating system",
"garage". These are retired. The provider layer is `backend/providers/`.

## Immutable rules

1. **Never buy inference.** The user brings their own key or their own model. No
   feature may require Zaram to pay per token. This is why the free tier can exist.
2. **Every recalled fact carries provenance.** An answer that cites nothing is a bug.
3. **Every byte that leaves is logged.** The egress log is append-only and
   tamper-evident. Build it into the core, never as a later add-on.
   This rule is only true because of the no-remote-assets rule below — the gate
   cannot see browser-originated requests, so the ban is what keeps Rule 3 from
   being a claim the software cannot keep.
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
- **`backend/providers/` is the provider layer. Connect it, do not duplicate it.**
  It was written, tested, and never wired up — which is how a second, simpler
  provider path grew beside it (`models_runtime.py` importing `OllamaEngine`
  directly). One of those has to go, and it is the shortcut.

  Routing, model residency, first-run hardware detection and the Models pane all
  consume this layer. `models_runtime.py` goes through it rather than importing
  an engine directly.

  It is named `providers/`, not `garage/`. "Garage" is not canonical vocabulary
  and never was; the rename is part of connecting it.

- **The egress gate covers Python-originated requests only.** Browser-originated
  requests bypass it entirely and *cannot be logged* — CSS `@import`, `<img
  src>`, `<script src>`, renderer `fetch`, iframes, webviews, and anything a
  stylesheet pulls in. No gate written in the backend can see them.

  Therefore: **no remote asset URLs anywhere in frontend code.** Fonts, icons,
  images, scripts and styles all ship in the bundle. A source scan enforces this
  alongside `backend/tests/test_egress_chokepoint.py`; the two together are what
  make Rule 3 true rather than aspirational.

  This is not hypothetical. `index.css` pulled three fonts from Google on every
  launch, before any UI rendered and before any consent existed, and no amount of
  work on the gate would ever have recorded it.

- **Hardware detection returns unknown, never a wrong number.** If VRAM cannot be
  determined — Metal, DirectML, no GPU, a driver that will not answer — the
  answer is `unknown`, not `0`. Do not report a GPU as available while its
  capacity is undetermined.

  A recommendation built on a false zero is worse than no recommendation: the
  user is told a model will not fit when it would, or the tier logic silently
  picks the smallest option and the product looks weak on capable hardware.
  Absent measurements never render as measured zeros — the same rule the egress
  log follows for `bytes_left_device_today`.

- **TTS is Kokoro-82M** (Apache 2.0), CPU-capable, the default and only shipped
  implementation. The binding constraint is that speech synthesis must not compete
  with local inference for VRAM, and must work on Macs and AMD. Better-sounding
  models exist — Fish Audio S2, Chatterbox, Qwen3-TTS — and every one fails on
  licence, VRAM, or platform coverage. Keep TTS behind an interface so the choice is
  replaceable, not embedded.

  This records *which* engine, not *when*. Voice remains out of scope for v1 — see
  the scope list above — and this decision does not license building it.

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
- The Orb shows system state. It does not perform. States are
  **idle / warming / thinking / swapping / speaking / listening**, plus the
  routing it reports (local only / can send / cloud enabled).
- **`swapping` is a required state, not a nicety.** When a route needs a model
  that will not fit alongside what is resident, Ollama unloads one and loads
  another, and the user waits with no explanation. An unload/reload that is not
  visible reads as a broken product — the same request that was fast a minute
  ago now hangs, and nothing on screen accounts for it. Any route that forces a
  swap must say so before it happens.
- The Orb must not describe a capability the system does not have. "Cloud
  enabled" means a cloud model can answer questions; it is not the same claim as
  "some route off this machine exists", and collapsing the two put a false
  status on the one indicator whose whole job is to be trusted.
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
