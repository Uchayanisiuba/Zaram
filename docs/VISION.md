# Zaram — Vision and Rationale

---

## The work that pays you is not the work that gets you paid

You are good at the thing you do. You are not paid for the hours around it — writing
the quote, chasing the invoice, digging through a brief to remember what the client
actually asked for, realising on Thursday that a deadline was Tuesday.

That work is unpaid, unavoidable, and it is where small businesses quietly lose money.
Not to bad clients or bad luck — to a quote sent four days late, an invoice nobody
followed up, a revision round that was never in scope.

**Zaram takes that work.**

It reads the brief and knows what was promised. It writes the quote in your terms, at
your rate, because it remembers the last one. It turns the finished job into an
invoice, watches the clock on the payment terms, and tells you the day it's late —
with the clause and the draft already written.

It carries what you decided in March into what you're building today, so you stop
re-explaining your own project to a machine that forgot. When you're in Blender or
Unreal, it comes with you, still knowing what the client said.

And it shows its working. Every fact it uses links back to the document it came from,
so you can check before you act. Wrong? Correct it once, and everything downstream
changes.

All of it on your own machine. Your contracts, your clients, your rates. It works with
whichever AI you choose — a model running on your laptop, or a frontier model when the
job genuinely needs one — and nothing leaves unless you send it, with a record of every
byte that did.

**What actually changes:** you quote faster, so you win work you'd have lost to a
slower reply. You invoice the day you deliver instead of the end of the month. You get
paid on time because someone is watching the date. You stop losing hours to "what did
we agree?" You take on more work without hiring, because the unpaid half got smaller.

That is the product. Not an assistant. Not a memory. The difference between a good
month and a bad one, on work you were already doing.

---

## The mechanism: documents contain obligations

Every business runs on obligations buried in documents — payment terms in an invoice,
milestones in a contract, deliverables in a brief, expiry on a quote, renewal on a
lease. Today those dates live in a PDF in a folder. The calendar does not know about
them because nobody typed them in, and nobody types them in because it is tedious and
the deadline feels far away.

**Zaram already reads the document. It can extract the obligation.** And once it has,
it has a reason to speak first — which is the difference between a tool you remember to
open and one that earns its place.

The shape is identical across every business type; only the nouns change.

| Who | What the document holds |
|---|---|
| Freelancer / creative | payment terms, revision rounds, delivery dates, licence expiries |
| Agency | retainer renewals, deliverable dates, scope boundaries |
| Consultant | SOW milestones, contract end, renewal windows |
| Contractor / trades | quote expiry, material lead times, warranty periods |
| Landlord | lease renewals, rent dates, maintenance schedules |
| Retail | supplier lead times, reorder points, seasonal deadlines |
| Researcher | grant deadlines, submission dates, ethics renewals |
| Production | delivery dates, review rounds, render windows |

One mechanism, every vertical.

> **Revised 16 August 2026 — read `CLAUDE.md` first.** The paragraph below argues
> for a freelance wedge, and that is now only half right. Obligation extraction
> genuinely is freelance-shaped, and it is now **the first pack** rather than the
> entry point. What earns the daily open is universal — an assistant one keystroke
> away that is fast, remembers you, reads your documents and sends nothing
> anywhere — and that serves students, researchers, writers, developers,
> consultants, and anyone whose documents are not allowed to leave. The section
> below is kept because everything it says about the *mechanism* still holds.

**The product is horizontal; the wedge is not.** We
start with freelancers and one-person businesses because that is the sharpest version
of the pain, reachable without a sales team, decided by one person, and felt
personally. See `docs/PITCH.md`.

**Extraction accuracy is the whole thing.** A missed deadline is worse than no
reminder, because trust does not recover. Every extracted obligation shows its source
clause and is correctable. Never silently create a commitment.

**And do not become a calendar.** Zaram surfaces obligations in context and drafts the
response. It is not where anyone plans their week.

---

## Why this cannot be copied

**Project tools require you to enter the data.** Asana, Monday, Notion — all empty
until someone types, which is why most are abandoned. Zaram extracts it from documents
it helped produce. The data-entry problem that kills every project tool disappears.

**And the labs structurally cannot build it.** A model provider will not ship a memory
layer that works equally well with a competitor's model, and a platform owner will not
treat an open-weight local model as a first-class citizen. **A genuinely neutral layer
can only be built by someone with no model to sell.** A promise that nothing left your
machine can only come from someone whose business is not that it does.

Models churn constantly. The memory outlives every one of them.

---

## Direction

**Year one — the working freelancer and the one-person business.** Get paid, know where
you stand, never miss a date. Free for one person, forever.

**Year two — small teams.** The obligations become shared: who owes what, whose
deadline is whose. That is the paid tier, and it is a natural boundary rather than an
invented paywall.

**Year three — the packs deepen.** Verticals where obligations have domain shape:
production schedules, construction milestones, research deadlines. Each adds parsers
and templates, never navigation.

**Throughout — tools stay in service of the work.** Documents, 3D, whatever comes next.
They are how you act on what Zaram surfaces, not the product itself.

---

## Why the economics work

The user brings their own compute — an API key or a local model. Zaram never pays for
inference at any tier. Cost of goods stays near zero regardless of scale, which is
what makes a genuinely free single-user tier possible.

This is the business model, not a nice-to-have.

## What is already served, and what is not

Agent memory is a funded infrastructure category — Mem0, Letta, Zep, Supermemory,
Cognee. **Every one of them is a developer SDK.** Components you integrate into an
agent you are building. There is no end-user application of the memory layer.

The category has validated the problem and built the plumbing. Nobody has built the
product. Roughly 65% of enterprise agent failures are attributed to context drift
rather than model capability.

## Why MCP, not a custom plugin format

MCP is the de facto standard: ~97M monthly SDK downloads, ~9,600 registry servers,
native support from every major provider, governed by the Linux Foundation's Agentic
AI Foundation. Both major game engines shipped official servers in 2026 — Unity in
May, Epic in Unreal Engine 5.8 in June, with MCP signalled as core infrastructure
heading into Unreal Engine 6.

**Zaram does not build tool integrations. It orchestrates existing ones** — installing,
permissioning, hardware-grading, and remembering across them. That is
"conductor, not musician" made concrete.

**And MCP has a safety problem, which is the opening.** 30+ CVEs were filed in early
2026 including cross-tenant leaks and tool poisoning. The one large public deployment
that worked required per-server security review plus human-in-the-loop approval for
sensitive operations. A non-technical person cannot safely use MCP today. A curated,
safety-graded, permission-scoped client is a real product.

## The tool layer direction

Everyone will wire calendar and email. Almost nobody can competently wire creative
software — and that is where this project has an advantage that is not replicable.

**Two contributions no MCP server provides:**

1. **Memory across the tool boundary.** Blender MCP does not know what the client
   said. Unreal MCP does not know what was decided in March. Zaram does. Two servers
   plus one memory is materially different from two servers.
2. **Visual verification.** The known failure of agentic 3D work is that a blind agent
   fails constantly — the differentiator is a vision feedback loop, not tool count.
   Act, render a frame, look, correct. Judging whether the output is any good requires
   domain expertise that is not learnable from documentation.

Priority: documents first (universal, zero risk), then Unreal read-only, then Unreal
scoped writes, then Blender, then VS Code. ZBrush is not viably scriptable. "Adobe
Creative Suite" is not one integration — treat each application separately.

Being able to test an application is not a reason to integrate it. Each integration is
a permanent maintenance obligation.

## Building on existing open source

Zaram assembles rather than rebuilds. The whole v1 capability set is available as
permissively-licensed components.

**Ingestion is where the leverage is.** IBM's Docling is hosted under the Linux
Foundation with 37k+ GitHub stars, called by Red Hat the number one open-source
repository for document intelligence. Granite-Docling-258M is an Apache 2.0
vision-language model that parses a page in a single pass. One dependency covers PDF,
DOCX, PPTX, XLSX, HTML, audio and video, and at 258M parameters it sits alongside a
local model on modest hardware without a fight.

**Generation is small.** python-docx, openpyxl, WeasyPrint, matplotlib. A weekend of
work, not a platform.

**Do not embed an office editor.** OnlyOffice and LibreOffice solve *editing*, which is
a completely different and much harder problem, and OnlyOffice's AGPL licence is
incompatible with an open-core business. Zaram generates; users edit elsewhere.

**Licence discipline is a business constraint, not hygiene.** A single AGPL dependency
forces the entire product under AGPL and forecloses the paid tier. Every dependency is
checked before it lands.

**And no ingestion path may route documents off-device.** Several of the best parsers
are managed cloud services. Using one would forfeit the product's central claim for a
quality gain. That is the exact trade Zaram exists to refuse.

## Agent frameworks are not competitors

ADK, LangGraph, CrewAI, Mastra, the OpenAI and Claude Agent SDKs — every one is a
developer framework. You import it, write code, deploy an agent you built. Nobody
installs ADK to remember things across their AI tools. They compete for the engineer,
not for the user.

None of them has: egress logging, confirm-before-send, a correction loop as a
user-facing product, provenance shown to a non-technical person, or consumer
packaging. That list is the whole product.

**So the right posture is to take more from them, not less.** Orchestration, provider
adapters and document parsing are commodity and get better every quarter. Rebuilding
any of it is an hour not spent on the four things only Zaram can do.

## The threat that is real

It is not ADK. It is a consumer product built on it.

A lab that already owns the browser, the operating system, the documents and the mail
can ship "remembers everything across your surfaces" with distribution that cannot be
matched. That is the same feature with a hundred times the reach.

The defence is the two moats, and they hold:

- **Neutrality.** No lab will make its own model work as well with a competitor's and a
  local open-weight model as it does with its own. That is not a product decision they
  have failed to make — it is structurally impossible for them.
- **Provable non-egress.** A lab cannot say "this never left your machine," because
  their business is that it does. This is the one claim they literally cannot copy.

But it means the race is **distribution and trust, not capability** — which changes
what is worth building, and puts packaging ahead of features.

## Guarding the Spine against itself

Zaram's own output must not silently become its own source. A generated proposal that
gets auto-indexed is recalled next week as a fact — provenance leading back to
something Zaram wrote rather than something the user did. Repeated, this fills the
Spine with restatements and quietly corrupts the one asset the product is built on.

So: generated artifacts are written but not remembered unless the user asks, and when
remembered, their origin stays visible.

The same principle generalises beyond files — not every conversation should produce
memory either. A visible "this conversation is not being saved" state is worth building
after the alpha. The file-level control is the first instance of a pattern, not a
special case.

## Business model

- **Free and open source** — one person, one machine, forever, no feature limits.
- **Paid** — the second person. Shared Spine, permissions, sync, admin.
- **Never charge for privacy itself.** Charge for the inconvenience the architecture
  creates.

Open source is not a distribution preference. The core claim is provable non-egress,
and a closed binary cannot substantiate that to anyone technical.

## Positioning

Not a model — it routes to yours. Not an operating system — it is a layer. Not an
agent framework — those serve developers building products; Zaram serves people doing
work.

## Known risks

- **Reliability, not scope, is what kills this.** An agent that corrupts an Unreal
  level file destroys more trust than fifty good operations earn. Confirm-by-default
  is a survival requirement, not a setting. Test against copied projects only.
- **The Spine leaking into outbound queries** is the worst possible failure for this
  product. Currently safe by structural accident; must become an enforced invariant.
- **Consumer local-AI tools are commoditized to free.** The paid tier must be
  multiplayer, never a crippled single-player experience.
- **Platform owners are building adjacent.** The defense is neutrality across models —
  the one thing they will not copy.

## The real blocker

Capability is not what stands between the current state and the retention test.
**A stranger cannot install this.** Every additional feature widens the gap between
what the product can do and what anyone can experience.

An installer and a guided first run belong on the milestone list, ahead of further
capability. A user who is still configuring at minute twenty does not become a user.

## The test that decides everything

Ship the narrowest useful version to 10–15 people from one segment. Watch them use it
without helping. Count how many are still using it weekly on day 30.

- 5+ of 15 — build the paid tier
- 2–4 — the job is wrong; interview those users specifically
- 0–1 — the thesis is wrong, learned in six weeks instead of two years

Closing question, instead of "would you pay for this":
**"If I turned this off tomorrow, what would you do?"**
