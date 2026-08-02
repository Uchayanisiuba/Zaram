# Zaram — Vision and Rationale

Background context for product decisions. Not auto-loaded; read on demand.

---

## The product

**The memory and control layer for people who use more than one AI.**

You use a frontier model for writing, a local model for anything confidential, an
image tool for design, a coding assistant for builds. Each is capable. None of them
remembers what happened in the others. Every conversation restarts from nothing.

The intelligence is not the bottleneck any more. The forgetting is.

Zaram sits between the user and every model they use. One knowledge base, on their
machine. Recall that follows them across providers. Provenance they can inspect.
Correction they control. A log of everything that left.

## Why this is defensible

The labs structurally cannot build it. A model provider will not ship a memory layer
that works equally well with a competitor's model, and a platform owner will not treat
an open-weight local model as a first-class citizen. **A genuinely neutral layer can
only be built by someone with no model to sell.**

Models churn constantly. The memory outlives every one of them.

## Why the economics work

The user brings their own compute — an API key or a local model. Zaram never pays for
inference at any tier. Cost of goods stays near zero regardless of scale, which is what
makes a genuinely free, genuinely unlimited single-user tier possible.

This is the same structural property that lets small local-first companies serve very
large user bases with tiny teams. It is not a nice-to-have; it is the business model.

## What is already served, and what is not

Agent memory is a funded infrastructure category — Mem0, Letta, Zep, Supermemory,
Cognee, Hindsight, MemPalace. Mem0 alone has raised ~$24M with 51k+ GitHub stars.

**Every one of them is a developer SDK.** They are components you integrate into an
agent you are building. There is no end-user application of the memory layer — nothing
a person installs and uses.

The category has validated the problem and built the plumbing. Nobody has built the
product. That gap is the opportunity.

Reference point: roughly 65% of enterprise agent failures are attributed to context
drift rather than model capability.

## Why MCP, not a custom plugin format

MCP is the de facto standard: ~97M monthly SDK downloads, ~9,600 registry servers,
native support from every major provider, governed by the Linux Foundation's Agentic
AI Foundation. Building a proprietary shim would forfeit thousands of existing
integrations for no gain.

**But MCP has a safety problem, and that is the opening.** 30+ CVEs were filed in early
2026, with real production incidents including cross-tenant data leaks, path traversal
affecting thousands of apps, and tool poisoning. The one large public deployment that
worked required per-server security, legal and privacy review plus human-in-the-loop
approval for sensitive operations.

A non-technical person cannot safely use MCP today. A curated, safety-graded,
permission-scoped, hardware-graded MCP client is a real product — not a UI preference.
The existing hardware-grading concept extends directly into safety-grading.

## Business model

- **Free and open source** — one person, one machine, forever, no feature limits.
  Costs nothing to serve because the user's hardware does the work.
- **Paid** — the second person. Shared Spine, permissions, sync, admin.
- **Never charge for privacy itself.** Charge for the inconvenience the architecture
  creates. That is the mechanism, and it is what local-first competitors get wrong.

Open source is not a distribution preference here. The core claim is provable
non-egress, and a closed binary cannot substantiate that claim to anyone technical.

## Positioning

Not a model — it routes to yours.
Not an operating system — it is a layer.
Not an agent framework — those serve developers building products; Zaram serves people
doing work.

Retire "AI operating system" from all external language. The term has been claimed by
enterprise infrastructure vendors and now means something else to buyers. The OS-shaped
internal architecture is fine; the marketing is not.

## Sequencing

1. **Recall across two models.** The demo nobody else has shipped to an end user.
2. **Safety-graded MCP tools.** One workspace, hand-built, proven end to end.
3. **A second workspace, also hand-built.** Only now extract the pack abstraction.
4. **Multiplayer.** Shared Spine, permissions — the paid tier.

The engine is industry-agnostic. The pack is not. Build agnostic, sell specific, ship
one pack.

## Known risks

- **Reliability, not scope, is the thing that kills this.** Agents driving external
  tools fail in ways users cannot diagnose, and one bad autonomous action destroys more
  trust than fifty good ones earn. Confirm-by-default is not a setting, it is a
  survival requirement.
- **Continuous observation is one broken promise from being a surveillance product.**
  Per-source consent and a hard local kill switch ship in v1, not v3.
- **Consumer local-AI tools are commoditized to free.** The paid tier must be
  multiplayer, never a crippled single-player experience.
- **Platform owners are building adjacent.** The defense is neutrality across models —
  the one thing they will not copy.

## The test that decides everything

Ship the narrowest version to 10–15 people from one industry. Watch them use it without
helping. Count how many are still using it weekly on day 30.

- 5+ of 15 → build the paid tier
- 2–4 → the job is wrong; interview those users specifically
- 0–1 → the thesis is wrong, learned in six weeks instead of two years

Closing question for each participant, instead of "would you pay for this":
**"If I turned this off tomorrow, what would you do?"**

A shrug means no product. Visible irritation about the workaround means there is one.
