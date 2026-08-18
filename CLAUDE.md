# Zaram

The memory and control layer for people who use more than one AI.

Zaram reads what the user produces and receives, remembers what they owe and what
they're owed, and acts before it's late.

Everything flows into one knowledge base on their machine. Any model can recall it. The
user sees what was recalled, can correct it, controls what leaves the device, and puts
the result to work through tools.

**The product is horizontal, and as of 16 August 2026 the entry point is too.**

The earlier line was *"the product is horizontal; the wedge is not — we start with
freelancers because that is where it can be proven fastest."* That was right about
obligation extraction and wrong about the product, and the daily-driver work is what
exposed it. **What earns the daily open is universal**: an assistant one keystroke away
that is fast, remembers you, reads your documents, and sends nothing anywhere. That
serves anyone who types on a computer. Only the *obligations* layer is freelance-shaped.

So the shape is now: **a universal base, with verticals as packs.** The freelance
business layer — invoices, quotes, expenses, obligations — stops being the wedge and
becomes **the first pack**, which is what the pack section below already describes and
what makes the abstraction real rather than imagined.

Who the architecture genuinely serves, and each of these is a pack rather than a rebuild:

| Who | What the base gives them | The pack |
|---|---|---|
| Freelancers, one-person businesses | memory of clients and terms | invoices, obligations |
| Researchers, academics | a library they can cite from | grant deadlines, submissions |
| Students | textbooks and papers as domains | study, revision |
| Writers, authors | long-project memory, their own research | manuscript, continuity |
| Developers | code that never leaves the machine | repositories, review |
| Consultants, agencies | what was decided, per client | SOW milestones |
| Anyone with confidential documents | local inference, nothing uploaded | — |

**Two audiences the architecture serves better than anyone has noticed.**

*People whose documents cannot leave.* Therapists, accountants, lawyers, HR, clinicians
handling notes. They are told to use AI and forbidden to upload. Local inference is not a
preference for them, it is the only permitted option — and provenance plus an egress log
is what a compliance conversation actually needs. Note the existing prohibitions still
hold: documents and drafting, never diagnosis or legal advice.

*People for whom cloud AI is expensive or unreliable.* Metered data, intermittent
connectivity, and subscriptions priced in USD against a local wage. A resident model
costs nothing per question and works with the connection down. This is a structural
advantage, not a philosophical one, and it is the market the maintainer is closest to.

**The wedge that remains is a demonstration, not a segment**: point Zaram at a folder and
have it say something true you did not know. That works for a freelancer's invoices, a
researcher's grant letters and a student's reading list without changing a line.

Full rationale: `docs/VISION.md`. Interface: `docs/UI-SPEC.md`. Sequence and
acceptance criteria: `docs/MILESTONES.md`. External framing: `docs/PITCH.md`. Read
before proposing product changes; none are auto-imported.

**Starting a session: read `docs/MILESTONES.md` first.** Its Current state block
is the handoff — what is done, what is in flight, which decisions are already
taken, and which gaps are deliberate and time-boxed. It is maintained for that
purpose; if it disagrees with this file about *status*, it is more recent. This
file remains the authority on the rules.

## Canonical vocabulary

Use these terms only.

- **Spine** — the local knowledge base (index + embeddings + provenance records)
- **Recall** — retrieving prior context into a new exchange
- **Provenance** — the link from a recalled fact or generated claim to its source
- **Routing** — deciding local vs cloud for a given request
- **Egress log** — the append-only record of what left the machine
- **Orb** — the system-state indicator. Not a mascot, not a launcher.
- **Tool** — an MCP server Zaram can call

Retired, do not use: "faculty", "nursery", "aperture", "synapse web",
"AI operating system", "workspace" (as a top-level surface).

## Navigation — six nodes

**Work · Project · Memory · Knowledge · Activity · Settings**, as six nodes orbiting
the Living Orb on the landing state. Sources live inside Knowledge. Tools are
configured inside Settings.

Six is the count. Adding a seventh requires a reason that survives "why is this not
part of Conversation?" — the retired design had six and four of them held nothing,
which is what the count is guarding against.

**Project earned the sixth node, 10 August 2026.** It was argued down first, on the
grounds that a project only groups artifacts and a grouping of artifacts is a filter
inside Work rather than a surface. That reasoning was wrong, and rule 7i is what makes
it wrong: **project scope applies to facts, not only to files.** `project:<id>` is a
field on the Spine, the queued plan object is scoped the same way, and sources in
Knowledge carry it too. A project therefore spans Work, Memory and Knowledge at once —
and a filter living inside Work cannot own something that scopes Memory.

The precedent is Memory and Knowledge themselves. Both are stores of information,
similar enough that grouping them is tempting, and they are separate because one holds
derived facts about the user and the other holds the documents those came from. Project
stands in the same relation to Work: adjacent, overlapping, not the same thing.

It passes the test below more clearly than Work does. A project holds a **type**, which
activates a pack; the facts scoped to it; the artifacts assigned to it; and — once the
plan object lands — the steps, decisions taken and decisions rejected.

**What Project is not.** It is not a file manager. No folder tree, no subfolders, no
nesting: one level of grouping, the project itself. A hierarchy would be a second
organising system competing with the one that *is* the product — scope, provenance and
recall — and if a tree is needed to find your own work then recall has failed and the
tree hides the failure rather than fixing it. It also collides with 7h, since every
folder is a decision made in advance about where something goes.

The split with Work is: **Work is the output, Project is the organisation of it.** Work
browses, previews and opens what was made. Project creates, names, types, assigns,
moves and deletes. Deleting a project is never one button — it holds facts and files,
so it must ask whether those are re-scoped, reassigned, or deleted with it. Rule 4
applies to everything inside it.

**Work is where output lives** — documents, spreadsheets, charts the user made, each
with the conversation that produced it and its sources. It exists because a navigation
made only of Memory, Knowledge and Activity is entirely about the system and contains
nothing the user made. Nobody pays for a memory browser. Memory matters because it is
memory *of work*.

The test for any future surface: **does it hold something real?** Work holds files.
Canvas and Plugins held nothing, which is why they were cut.

Conversation is **not** a node. It is the shell — the landing state, entered by
the orb, animated aside when a surface opens. But the return path must be visible and
one click: the orb reverses the animation, and the persistent bar's topic line is
clickable. Never let the animation be the only route back.

**Tools never get menu items.** They are actions inside the conversation. This is what
lets capability grow without the navigation growing.

Generated files appear as cards in the conversation and land in the output directory.
There is no Files surface — that duplicates the operating system. Project assigns files
to a project; it does not browse a filesystem.

**Work does not gain sub-apps for editing.** Proposed 10 August 2026 and declined on
the grounds already recorded in the dependency stack: OnlyOffice is AGPL and would
force the whole product under it, LibreOffice headless is several hundred megabytes,
and both are separate services rather than libraries. Zaram *generates* documents and
users edit them in whatever they already have — different problems, and the second one
is solved.

The defensible narrow version, post-v1 and not promised: because HTML is the source of
truth for every generated document, editing **Zaram's own generated HTML** before
export is conceivable without embedding an editor at all. That is a preview that
accepts edits, not a word processor, and it is worth building only if users ask for it
after v1 ships. It is not a sub-app and it does not get a menu item.

## Immutable rules

1. **Never buy inference.** The user brings their own key or their own model. No
   feature may require Zaram to pay per token.
2. **Every recalled fact carries provenance.** An answer that cites nothing is a bug.
   This extends to generated documents: claims trace to their source.
3. **Every byte that leaves is logged** — including bytes sent by tools, not only by
   chat. The egress log is append-only and tamper-evident, built into the core.
4. **The user can correct or delete any stored fact**, and affected answers change.
5. **Nothing leaves the device without an explicit per-item policy.** Default deny.
6. **Tools confirm before acting.** Autonomy is granted by the user, never a default.
7. **The Spine is exportable in an open format.** No lock-in.
7b. **Every fact carries its origin: user document, conversation, or Zaram-generated.**
   Generated artifacts are indexed by default — the protection against Zaram citing its
   own restatements is origin tagging, not exclusion. Recall deprioritises generated
   content where a user source says the same thing, and recall explanations name the
   origin: "from a proposal Zaram generated in April" reads differently from "from your
   client brief". A "Don't remember this" override exists on file cards; it is an
   override, never a gate.
7d. **Conversation is ephemeral; entering the Spine is a decision the system makes,
   not the user.** Session state and long-term memory are separate stores. Working
   state, clarifications and false starts stay in the session. Conflating the two is
   what produces duplicate citations and Zaram quoting its own replies.
7i. **Every fact carries a scope: `global` or `project:<id>`.** Global is about the
   user — preferences, working style, how they like things written. Project is about
   the work — decisions, constraints, client feedback. Default to the current project;
   promote to global on evidence, not at capture time: a fact recalled across three
   different projects is probably about the person, and that is the moment to ask.
   Scope is one field on one store, not two stores — facts move, recall needs both at
   once, and the correction loop must stay uniform. It is also the multiplayer
   boundary: project memory is shareable, global memory never is.
7e. **Never ask the user a question the system can answer from behaviour.** A prompt at
   creation time asks someone to predict the future; recall count measures what
   actually happened. Facts enter provisionally, become durable through use, and decay
   if never recalled. The user is not asked to decide at creation — only to correct
   afterwards.
7g. **No network call occurs before the user has consented to one** — not for model
   recommendations, not for telemetry, not for update checks. Refreshing anything from
   the network is an explicit action, gated and logged like any other egress.

   **Amended 16 August 2026: update checks are asked for once, at first run,
   and default to yes.** The original wording made Zaram unpatchable. If a
   vulnerability is found in a product holding people's contracts, invoices and
   client correspondence, *silence forever* is not the privacy-preserving
   option — it is the dangerous one, and the rule was protecting the principle
   rather than the person. The check sends a version string and nothing else,
   which is a smaller disclosure than any single chat message, and it is still
   consented, still refusable, and still logged like any other egress. Telemetry
   is unchanged and stays prohibited: knowing a patch exists serves the user,
   and knowing how they use the product serves us.

7j. **Consent given deliberately for a destination is consent.** Connecting a
   cloud provider — choosing it, pasting a key for it, pressing Connect — *is*
   rule 5's explicit per-item decision about that provider's host. Requiring a
   second, separate host rule afterwards asks the same question twice and reads
   as the product being broken: it happened to the maintainer, on their own
   build, with nothing on screen explaining why. This does not weaken rule 5. A
   host nobody named is still denied, the rule is still per-item, still visible
   in Settings, and still revocable there.

   The same principle bounds confirm-before-send, which cannot survive daily use
   as a per-request dialog — forty dialogs a day is a product nobody opens on
   day two. **Confirm once per destination and data class, then remember**, with
   the egress log and the orb carrying it afterwards. Rule 6 says autonomy is
   granted by the user and never defaulted; granting it once, by name, for a
   named class of data, is the user granting it. Keep the hard stop for the case
   that earns one: the first time facts recalled from the Spine go to a
   destination that has not had them before.
7h. **Offer at the moment of doubt; never make the user choose in advance.** Always-on
   dual answers, always-on search prompts and always-on briefs tax every interaction to
   serve a minority of them. Contextual offers cost nothing when unneeded.
7f. **Do not build a feedback mechanism whose action has no purpose other than giving
   feedback.** Thumbs on replies conflate "the fact was wrong", "the tone was wrong"
   and "you misunderstood me" into one uninterpretable click. Correction is the
   feedback mechanism: specific, deliberate, and already visible in the product.
7c. **No ingestion path may route documents off-device**, regardless of quality gains.
   Managed parsing APIs are prohibited. This is the exact trade the product refuses.
8. **Nothing derived from the Spine may appear in an outbound query.** Enforced by
   test, not by convention.
9. **Generation must fail rather than invent.** When recall cannot resolve what the
   user is referring to, say so and ask. A document produced from unresolved context
   is confident, plausible and wrong — and unlike a chat reply, it leaves the
   building. A wrong reply is corrected in the next turn; a wrong document is sent
   to a client.

   This is not hypothetical. "Write that up as a proposal" is *referential*, and
   similarity recall over five referential words retrieves nothing: the model filled
   the gap with a whole invented client — a confident proposal for a "Project
   Phoenix" nobody had mentioned, with the real client's name and day rate absent.
   Every individual component was working.

   Carrying the recent exchange forward fixes the referential case. It does not fix
   every case, so **the refusal path exists alongside it and is not optional**.
   Generation is the one place where the product's ordinary failure mode does its
   most damage, so it is the one place that must rather stop than guess.

## Custody, not only consent

**The effort went into consent and not into custody, and that balance was the
wrong way round.** Dialogs, per-host rules and refusals are what a privacy
policy is made of. Custody is what actually keeps a user's contracts safe, and
it is the half a technical reviewer checks first.

**Loopback is a network boundary, not an identity one.** Binding to 127.0.0.1
closed the loud hole — the API had been published on every interface with no
authentication. It did not close the quiet one: a page the user visits can point
a hostname it controls at 127.0.0.1 and reach port 8420 with *same-origin*
requests, so CORS never runs. DNS rebinding, against `GET /memory`, `GET /egress`
and `PUT /egress/policy`. Measured 16 August: the same request returned **200 and
the whole Spine** without a guard and **400** with one.

A `Host` header check now refuses a rebound hostname —
`tests/test_host_header_guard.py`. **It is half the fix and must not be
described as the whole one.** There is still no authentication, so any *process*
on this machine can read every stored fact. The remaining half is a per-launch
secret minted at boot and handed to the frontend by the desktop host, and it
belongs before a stranger installs this.

**`X-Zaram-Client` is a label, not a credential.** It is sent by the interface
and enforced nowhere. Never reason as though it were a check.

**The user's data lives in the user's data directory.** Every store used to
resolve to the backend *source* directory, which is correct in a checkout and
unwritable in an install. `core/paths.py` owns the one answer;
`ZARAM_DATA_DIR` moves all of it; a checkout that already holds databases keeps
them, because silently relocating somebody's Spine is indistinguishable from
losing it.

## Tool risk tiers

Every tool falls into exactly one tier. The tier determines what must exist before it
ships. This is the organising principle for the whole tool layer.

| Tier | Does | Requires |
|---|---|---|
| **Generative** | Creates new artifacts only | Nothing. Ships in v1. |
| **Mutative** | Changes existing state | Undo, confirm, sandbox |
| **Egressive** | Sends data off-device | Egress log, per-source policy |

A cloud model performing a file edit is **both** mutative and egressive and needs both
gates. The two consents are separate: permitting cloud models does not permit
mutation, and permitting file edits does not permit cloud.

**Generative safety is structural, not promised.** Generated files go to a dedicated
output directory, never overwrite silently, and the write path has no delete or
overwrite capability at all. A filename collision increments or asks.

**A retrieval score authorises nothing.** Retrieval produces a shortlist; the model
chooses; the tier gate above still runs. Never let a similarity score stand in for a
permission check.

**Three questions, one number, and they must not be merged: what is *in* the
shortlist, what order it is *shown* in, and what is *cited*.** Membership and
citation are decided on relevance alone; ordering may use whatever blend is
useful. Merging any two has now cost this codebase twice — a citation floor
compared against the ranking blend cited facts with a true cosine of 0.20, and a
shortlist *selected* on the same blend discarded the single most relevant
document in a 1,000-document corpus at rank 43, because similarity swings the
blended score by ~0.10 while importance, recency, access and session together
swing ~0.55. A blend is a presentation choice. Never let it decide what the
model is allowed to see.

A tool description is **third-party text**. An MCP server author — sloppy or hostile —
can write a description that sits near every query, and ranking is not a security
boundary. If retrieval ever gates permission rather than ordering candidates, a
badly-written tool description becomes privilege escalation. Same rule for a document
excerpt or a search result: relevance is not consent, and nothing retrieved may widen
what a tool is allowed to do.

## The daily driver comes first

**Everything else is hinged on this, and it was not written down.** A memory
product only works if the thing it attaches to is opened every day. Obligations
give someone a reason to open Zaram in week one; they give nobody a reason to
open it on a Tuesday in month three. Without the habit there is no memory worth
having, no knowledge worth expanding and no invoice worth chasing, because
nothing went in.

The order is: **usable daily → useful because it remembers → indispensable
because it acts.** Skipping the first step builds the second and third for
nobody.

Consumer AI use collapses into eight jobs, and **five of them a local 8–14B
already does well**: writing, editing, summarising, rewriting, translating. Two
are adequate (explaining, coding) and one is not bridgeable locally (hard
reasoning). So the daily driver does not need frontier capability. It needs the
five to be fast and frictionless and the rest to route somewhere without the
user thinking about it.

### The ambient surface — the highest-leverage thing on this list

**Proximity beats capability for habit.** An app you have to find loses to a
browser tab that is already open. A global hotkey and a screen-edge handle that
appear over whatever the user is already looking at compete with nothing,
because there is nothing to switch to.

The pattern is proven and the market leader is **Superhuman Go** (Grammarly,
which acquired Superhuman in 2025): a tab docked to the screen edge that opens
on hover and offers to act on what you are typing, in any application. It is
the correct interaction and it is worth copying closely.

**What must not be copied is how it works.** Superhuman Go reads what you type
across applications and sends that text to their servers to process it. The
documented critique is exactly the one this product exists to answer: an
Incogni study in January 2026 recorded website content, personal communications
and user activity including keystrokes; Grammarly's defence that it excludes
"sensitive fields" is contested on the grounds that **HTML has no standard way
to mark a field sensitive**, so the exclusion is best-effort by construction.

That is the opening, and it is the sharpest one available:

> **The same ambient assistant, reading the same thing, sending none of it
> anywhere.** Grammarly structurally cannot ship this — their business is the
> server. Zaram can, because the model is already on the machine.

**Invoked, never passive — and this is a rule, not a caution.** Zaram reads the
selection *when asked*: a hotkey, a click on the edge handle, a drag. It does
not watch what is typed. That gives essentially all of the value and none of the
problem, and it sidesteps the failure above rather than promising to mitigate
it — Zaram makes no claim about detecting a password field because it is never
reading one. A passive-capture mode is prohibited, at any accuracy.

Three properties, each of which must hold:

* **Opt-in per application**, with the list visible and editable.
* **Nothing is retained** unless the user acts on it. Rule 7d already says
  entering the Spine is a decision the system makes; a glanced-at selection is
  working state, not memory.
* **The egress indicator is on the surface itself.** If a selection would go to
  a cloud model, that is stated on the panel before it goes — this is the one
  place where being ambient makes the disclosure more important, not less.

**Speed is the other half, and it is structurally available.** Superhuman's
whole thesis is that every interaction lands in under 100 ms, and people pay
$30/month for an email client because of it. A resident local model answers with
no network round trip at all, so for the five jobs local already does well
**Zaram can be the fastest AI a person has used** — not the smartest, the
fastest. Nobody has taken that position, and it is the one the architecture
gives away for free. It also composes with the surface above: ambient plus
instant is a habit; ambient plus slow is an irritation.

**Free API tiers are that route, and they are rule 1 exactly as written** — the
user brings the key, Zaram never pays. Gemini, Groq, OpenRouter's `:free`
models, Cerebras and GitHub Models all issue keys without a card. **Driving the
consumer web apps is prohibited**: it breaks the providers' terms, requires
defeating bot detection, shatters on every UI change, and would make the
product's one non-negotiable claim depend on a dishonest mechanism.

**Every free tier is paid for with the user's data, and Zaram is the only
product that can say so.** `DataPolicy.LOGGED_AND_TRAINED_ON` already exists
with that comment, and `selectable_by_default` already refuses to auto-route to
it — *free is not a good enough reason to make that choice on a user's behalf*.
Those are right and unchanged. What is missing is the **offer**: a first-run
path that says "add a free Gemini key — your prompts train Google, and Zaram
will tell you every time one goes."

That is also the strongest acquisition story available. The pitch stops being "a
private local assistant", which asks someone to give something up, and becomes
**everything you already use, in one place, and it tells you the truth about
each one.** Nobody is asked to trade capability for privacy, which is the trade
that has capped every privacy product at a niche.

## Scope for v1

In scope:
- Ingest a folder into the Spine
- **Ingest by drop, paste and upload.** The parsers already exist — `pdf`,
  `office`, `plaintext`, and `docling` behind the OCR extra — and the Knowledge
  surface has no way to reach them. Folder scanning as the only path in is what
  makes a knowledge base a folder scanner.
- **Knowledge domains.** A named, described collection of sources that a project
  can link to. A local 12B with a curated library beats a local 12B alone, and
  often beats a frontier model with none, because one is reading and the other
  is recalling training data. Four properties, each load-bearing:
  a domain is a **retrieval scope**, not a folder — if it only groups files it
  is a filter, and it has to change answers; **many-to-many, never a tree**,
  since a contract is Clients *and* Legal and a hierarchy is rule 7h smuggled
  back in; every domain carries a **one-line description**, so routing knows
  when to reach for it and the reply can say *"answered from your Investing
  domain"*; and **a domain is the shareable unit**, which makes it the thing
  that syncs, that a team shares, and that a pack eventually is.
  **No seventh node.** Sources already live inside Knowledge and a domain is how
  Knowledge organises them.
  **One memory, many domains.** Domains scope retrieval; they never fragment the
  Spine into per-domain silos, which is the trap custom GPTs fell into and the
  reason nothing compounds there.
- Chat routed to at least two providers (one cloud, one local)
- Recall across providers with visible provenance
- Correct or delete a fact and see answers change
- Egress log, viewable, recording chat and tool activity
- Per-source privacy policy
- **The business base layer**: invoices, quotes, receipt capture and extraction,
  expense categorisation, a monthly picture of the business. Native, no external app,
  no VRAM. This is the universal job — the same for a photographer in Lagos and a
  consultant in Berlin — and it is the best showcase for memory, because Zaram already
  knows the client's rate, their terms, and that they pay late.
  **Records and drafts, not filings and advice.** Generate the invoice, track the
  expense, show the trend. Never compute tax liability, never be the system of record,
  never file anything.
- **Generative tools**: .docx, .pdf, .md, .xlsx, and charts from the user's own data,
  with provenance carried into the output
- **Read-only MCP for Unreal and Blender**: inspect the scene, list actors, report on
  materials and lighting. No writes. Read-only needs no undo, no sandbox and no
  rollback, which is why it ships in v1 while scoped writes do not.
- **The pack catalogue**, with unavailable packs shown greyed out and honestly graded
  against the user's hardware, licence and installed apps.
- **Obligation extraction**: dates and commitments pulled from documents the user
  produces or receives — payment terms, milestones, deliverables, expiries — surfaced
  before they lapse. **Every obligation shows its source clause and is correctable.
  Never silently create a commitment**; a missed deadline is worse than no reminder,
  because trust does not recover. Zaram surfaces obligations in context and drafts the
  response — it is not a calendar and must not become one.

- **The 3D embodiment — moved into scope 9 August 2026.** A VRM renderer beside
  the orb, chosen by a toggle, both reading one state so neither knows the other
  exists. It embodies **what the system is doing**: no wandering gaze, no
  expression not derived from system state. The landing default stays the orb.

  **The no-name rule was reversed on 16 August 2026, and the reasoning is worth
  keeping because the reversal is narrow.** This section used to read "not a
  personality: no name, no pronoun". That prohibition was fixing two failures
  with one ban, and it only ever fixed one of them.

  The failure it fixed is real: a model asked what it is answers from training
  data — *"I am Qwen, made by Alibaba"* — and the eight named personas made it
  worse by supplying a third answer. The failure it claimed to fix, and does
  not, is parasocial attachment. **Attachment comes from being remembered, not
  from a name.** A system that knows the client's rate, that March was bad, and
  what was decided about the Northwind job feels like something to its user
  whether it is called Zaram or Ada. The ban was paying a very large product
  cost — personalisation is the strongest retention mechanism available here —
  for a protection it does not deliver.

  **So: a user may name it, style it, voice it and bring their own VRM. It may
  never deny what it is when asked directly.** The rule that replaced the ban is
  one sentence and it is enforced by test rather than by judgement, which is
  what stops it being re-argued every time a personality feature is proposed.

  The distinction that makes it safe is **additive versus substitutive**, and it
  is the same one `core/identity.py` already draws. *"You are Baba, a wise and
  analytical AI assistant"* replaces the truth and stays removed. *"You are
  Zaram. This person calls you Ada."* is a **fact the system supplies** — it
  lives in `user_settings`, not in the weights, exactly like the model name and
  the locality beside it. One answer, layered:

  > "I'm Ada — that's the name you gave me. Underneath I'm Zaram, and right now
  > qwen2.5:14b is answering, on your machine."

  **A manner is third-party text.** Characters are meant to travel as files, so
  a manner can arrive from a stranger, and the tool-description rule applies
  unchanged: nothing supplied from outside may widen what is permitted. The
  enforcement is **order, not filtering** — a blocklist of hostile phrasings is
  guessed rather than known, so instead the user's name and manner are placed
  *before* the rules about self-description, and the last instruction a model
  reads is the true one. `tests/test_identity_stays_truthful.py` asserts that
  ordering against hostile manners directly.

  Four guardrails come with it, and they are cheap: truthful when asked; never
  claims feelings it does not have (a manner is a register, not an inner life);
  **no engagement mechanics ever** — no streaks, no re-engagement prompts, no
  "you haven't talked to me in a while", since Zaram speaks first only when it
  has something real; and the character stays removable, because if personality
  ever becomes load-bearing for the utility something has gone wrong.

  **The state channel is still Zaram's.** The character is the user's — any VRM,
  any name, any voice — and the rim light still reports idle, working,
  listening, speaking, swapping, and still never reports routing. Bring your own
  VRM threatens none of that, because state comes from `useEmbodimentState` and
  the avatar only renders it.

  **It does not embody which model answered — narrowed 13 August 2026.** The
  earlier line was "which model is answering and what it is doing", and `local`
  and `cloud` were two of seven states. `LivingOrb` never rendered locality, so
  the avatar was the only renderer that did and the two disagreed about what
  they report. Locality is stated in words by `OrbStatusLabel` — "Local only",
  "Local · can send", "Cloud enabled" — a distinction a rim colour cannot make,
  on the one indicator whose whole job is to be trusted. And a face that reports
  routing is read as a *someone*, which is the projection the embodiment rule
  exists to prevent. **Known gap:** that label renders only while the
  conversation is open, so at rest nothing reports locality — true of the orb
  path already, and fixable in `Landing.tsx` rather than on a face.

  **One avatar ships, not three.** A character set is 16 MB each into a 186 MB
  installer against a rule that says never block on a download. The direction
  after one is **bring your own VRM** — the same posture as bring your own key
  and bring your own model.

  **The one that ships is a character, and it is also the mascot — 15 August
  2026.** A helmeted robot with a dot-matrix LED face behind a black visor.
  Two things follow and they must not be confused.

  *Mascot and renderer are two jobs for one asset.* On the site, the installer,
  the README and the icon it is a mascot and may smile — the reference art does.
  Inside the product it is the embodiment, and the rule above is unchanged:
  states only, no expression not derived from one. The rest face is `sil`, a
  flat line, not a smile. Nothing in the rule forbids key art; it forbids the
  *status indicator* being a someone, and keeping the smile in the marketing
  costs nothing to do.

  *The landing default is still the orb.* "Default character" means the avatar
  you get when you choose the avatar renderer, not what Zaram shows on launch.

  **The face is driven by texture transforms, not morph targets.** A VRM 1.0
  expression binds three kinds of thing and only one of them is a blend shape;
  `textureTransformBinds` slides a UV window across a sprite atlas, which is
  what a screen face needs and what `@pixiv/three-vrm` already implements. Two
  consequences the driver must respect, both read off
  `VRMExpressionTextureTransformBind.applyWeight`: weights are **binary**,
  because a fractional weight lands *between* atlas cells; and exactly **one
  expression per material** may be non-zero, because binds are additive and two
  of them sum into a cell that does not exist. Morph-rigged avatars keep the
  existing eased lerp — the two paths are told apart by the bind type, never by
  which avatar happens to be loaded, or bring-your-own breaks.

  **The face carries no state, which is what makes its colour safe.** It is a
  constant `#818cf8` and the state channel stays the rim light: slate at rest,
  cyan while working. The reference art glows violet, and violet is the one
  colour it could not have — `docs/UI-SPEC.md` assigns `#8B7FD4` to **cloud**,
  so a permanently violet face would put *"your data left the device"* on the
  indicator whose entire job is to be trusted, permanently and falsely. That is
  the 13 August failure with the sign reversed: there, a face reported routing
  it should not have; here it would report routing that was not happening.
  Indigo sits near the reference, is already the implementation's own accent,
  and is nobody's state.

  The sprite governs the **face panel only** — two quads on the visor, black
  base colour, atlas on `emissiveMap`. It does not extend to the shell, the ear
  rings or the body. Moving the state channel onto the ear rings was considered
  and **not built**: the rim light already works, needs no geometry, and reads
  on any VRM the user brings, which a character-specific mesh does not.

  **An avatar file may reference nothing outside itself.** glTF `buffers` and
  `images` carry an optional `uri` that the loader fetches, so a `.vrm` can make
  the browser call out while it loads — a request `EgressGate` cannot see, since
  that intercepts what the *backend* sends, and `check-no-remote-assets.mjs`
  cannot see, since that scans *source*. Rule 3 broken by a data file, with
  nothing anywhere reporting it, and a working beacon into the bargain. The
  policy is an allow-list of one form — embedded or `data:`, never a blocklist
  of hosts and never "same origin is fine" — and it **refuses rather than
  sanitises**, because rewriting somebody's asset produces a file subtly unlike
  the one they made. `frontend/src/lib/vrmSafety.ts`, built 14 August, which is
  what unblocks bring-your-own.

  An avatar **store** stays where the scope list
  already puts an extensions marketplace: after v1, and it is the feature that
  drags in accounts, since payment is one of the three things that require them.
  Attaching avatars to **agents** is the direction that replaces embodying a
  model — an agent is a thing with a job — and it waits on agents.

  **Pointer-tracking gaze was built and removed the same day, 11 August 2026.**
  Not on principle — the argument that cursor tracking is *attention* rather
  than drift still holds, and it would have been a narrowing of the rule rather
  than an exception to it. It was removed because **it did not visibly work**,
  and the reason it shipped in that state is the lesson: the maths had unit
  tests, the VRM was confirmed to carry a `lookAt` bone rig, and neither of
  those is evidence that an eye moved on screen. The asset's fringe covers the
  eyes at the rendered size, so the one check that mattered was the one not
  made. If it returns, it returns with a screenshot showing two different eye
  positions.

  Still unmeasured, and it is the measurement that decides: `docs/UI-SPEC.md`
  forbids 3D on the landing on GPU-budget grounds, and the avatar renders
  permanently while a local model is resident. The decision is **warn, never
  block** — which needs a real number to warn with.

- **Voice, both directions — moved into scope 9–10 August 2026.** Speech output
  (Kokoro) and speech input (faster-whisper, local) alongside the 3D embodiment.
  This reverses the earlier "voice is out of scope" line, deliberately and by the
  maintainer's decision, on the grounds that a character that cannot speak or
  listen is a skin rather than an embodiment.

  **Speech follows the renderer**: avatar selected, replies speak; orb, silent
  unless asked. One decision the user already made by choosing a face, so it
  needs no second setting.

  **Speech keeps pace with the text; it never waits for the reply.** Synthesis
  starts on the first sentence that will not change again, while the model is
  still writing the next — measured 14 August, speech began 16.6s before
  generation finished on one reply, and the gap grows with length. Two failures
  this rules out, and both are worse than the delay they avoid: waiting for the
  whole reply, which is silence that scales with how much there is to say; and
  releasing a sentence that can still be merged into, which puts a pause where
  the text has none and a listener hears that as a fault rather than as
  latency. Word-by-word is not the goal and would be worse — a clause is the
  smallest unit with prosody.

  **Citation markers are grounding, not language.** `[M1]` and `[S2]` reach
  neither a reader nor a synthesiser, and stripping happens on accumulated text
  because a marker arrives split across tokens. One function, all callers —
  there were three and the one that had been missed was the one that spoke.

  Both are **local and optional**. `zaram[voice]` speaks (~905 MB), `zaram[mic]`
  listens (81 MB measured — faster-whisper plus every dependency). Split because
  someone who wants Zaram to talk should not have to buy a microphone stack, and
  because the second number is an order of magnitude smaller than the first.

  **Cloud speech recognition is prohibited outright, not governed.** Chrome's
  `webkitSpeechRecognition` streams the user's *audio* — not a transcript — to
  Google, where no gate can see or log it. That is the same class as the remote
  font imports `check-no-remote-assets.mjs` bans, carrying far worse cargo, and
  it is enforced by `frontend/scripts/check-no-cloud-speech.mjs` on every build.
  The check asserts two things: no live module names the API, and no live module
  imports from `legacy/`, which still contains it. Asserting the quarantine
  rather than describing it is the lesson the DuckDuckGo fix cost.

- **Images, both directions — moved into scope by the maintainer, 17 August
  2026.** Upload an image and have Zaram read it; ask for one and have it
  routed to a provider that can draw. The brief is the reason: *a user should
  be able to spend a whole day in Zaram without feeling short-changed*, and an
  assistant that cannot look at a screenshot fails that on the first morning.

  **The shape was already settled and does not change.** Zaram ships no image
  or video weights, ever. It routes to a provider, logs the egress, carries
  project context, and shows what left. What changed is the schedule, and one
  fact underneath it: the objection recorded here was that image generation
  "cannot ship before the cloud engine exists, which is still a failing v1
  scope line". **The cloud engine landed.** `core/bootstrapper.py` wires
  `cloud_config` → `CloudFanout` → `RoutedEngine`, with `EgressGate` in the
  path. That blocker is spent.

  Four things follow, and the third is the one that will be got wrong:

  *Reading an image can be local, and that is the demonstration.* Ollama serves
  vision models and `core/planner.py` already routes a `vision` intent. A photo
  of a receipt or a contract that never leaves the machine is the product's
  whole thesis in one interaction, and every competitor must upload it. It is
  also a prerequisite the scope list already owes: **receipt capture and
  extraction cannot work without it.**

  *Deterministic manipulation is not AI and needs no model.* Crop, rotate,
  resize, convert — Pillow is already a dependency. Like every generated file
  these write somewhere new and never overwrite, so they are **generative
  tier** and need no undo, confirm or sandbox.

  *Modality is a capability gate, never a ranking.* "Which model writes better"
  is a similarity question and may use a blend. **"Can this model accept an
  image, or emit one?" is binary and is a precondition** — it filters the
  candidate set, and task similarity then orders what survives. Letting a score
  decide modality gets a text model asked to draw, answering with confident
  prose about a picture it did not make: rule 9's failure in a new medium, and
  the membership-versus-ordering error this codebase has already paid for three
  times.

  **Corrected 18 August 2026, and the correction is the useful part.** This
  paragraph first said "`ProviderEntry` carries no modality field today; that
  is the first piece of work". Both halves were wrong, and reading the code
  rather than the note is what found it. `ProviderEntry` is a *provider*
  record — id, endpoint, auth, key URL — and holds no models at all, so
  modality was never going to live there. Modality belongs on **`ModelInfo`**,
  which already carries `supports_vision`, `capabilities`, and a
  `ModelCategory` whose members already include `VISION`, `IMAGE` and `VIDEO`;
  Ollama discovery already populates the flag from `/api/show`. The vocabulary
  mostly exists.

  Two things are genuinely missing, and neither is the field that was asked
  for. **There is no way to say a model *emits* an image.**
  `orchestrator/capabilities.py` maps `ModelCategory.IMAGE` to
  `Capability.VISION: 1.0` — the same score a model that *reads* images gets —
  so "can see" and "can draw" are one number, and asking for one can return
  the other. And **nothing gates**: modality exists only as a 0..1 score built
  for ranking, which is this section's own warning already realised in code.

  *An image is its own consent class.* A chat message is ~2KB and an image is
  1–5MB, far more personal, and rule 7j grants consent per destination **and
  data class**. Connecting a provider for text is not consent to send it a
  photograph — that is asked once more, per provider, and then remembered.
  `selectable_by_default` already refuses to auto-route to
  `LOGGED_AND_TRAINED_ON`, and that must hold hardest here: a free image tier
  training on a user's uploaded photo is the worst version of the trade this
  product exists to refuse.

  **Video stays out.** Nothing above argues for it, the file sizes are another
  order of magnitude, and no part of the day-in-Zaram brief needs it.

Out of scope until v1 ships and is tested with real users:
- Any mutative tool (file edits, VS Code, Blender writes, Unreal writes)
- Web search — see sequencing below
- Agents, extensions marketplace, updates feed, multi-user, sharing
- **Video generation.** See the images entry above for why it separates from
  image generation rather than travelling with it.

## Sequencing

**Egress log → per-source policy → web search as its first governed source.**
Search does not return before those two exist. Bytes cannot be logged retroactively.

**Tools: generative → read-only inspection → scoped writes.**
Priority order for integrations: documents (v1), Unreal read-only (v1),
Unreal scoped writes, Blender, VS Code. Everything else waits for a user to ask.

Do not integrate an application because it is testable. Each integration is a
permanent maintenance obligation that breaks on every host-app update.

## Dependency stack

Licence-checked. **No AGPL anywhere** — it would force the whole product under AGPL and
break the open-core model. Verify the licence of every new dependency before it lands.

**Verify a dependency is unused by removing it and running the suite, never by
metadata alone.** `pip show` reports an empty `Required-by` for packages that are
genuinely required: misaki reaches spaCy at runtime without declaring it, so a
reverse-dependency check said spaCy had no dependents, and removing it broke speech
with `No module named 'spacy'` at synthesis time. An audit built on metadata will
confidently recommend deleting something load-bearing. Removal plus a green suite is
the only evidence that counts, and the suite has to actually cover the feature —
which is the second half of the same trap.

| Purpose | Choice | Licence |
|---|---|---|
| Ingestion / parsing | pypdf, python-docx, openpyxl (base) | BSD / MIT |
| Ingestion / OCR + scans | Docling, under the `[ingest]` extra | MIT |
| Word | python-docx | MIT |
| Excel | openpyxl | MIT |
| PDF | WeasyPrint (HTML-first) or ReportLab | BSD |
| Charts | matplotlib | permissive |
| Diagrams | Mermaid | MIT |
| Local inference | Ollama | MIT |
| Vector store | LanceDB or sqlite-vec | Apache 2.0 |
| Memory engine (if used) | Letta | Apache 2.0 |
| Provider routing | LiteLLM | MIT |
| Text to speech | Kokoro-82M | Apache 2.0 |

**Docling is an optional extra, not a base dependency — decided by measurement.**
It pulls 321 MB of wheels (torch, torchvision, opencv, transformers, scipy,
rapidocr) against a 267 MB base, which would undo most of the 81% packaging
reduction and put the installer back where someone on metered data does not
finish it. Probed against 1,080 real files on a working machine, the
dependency-light parsers read **50 of 54 PDFs**; the four they cannot are
image-only scans. So Docling buys a real but narrow capability at more than
double the download, and it stays behind `pip install zaram[ingest]`.

The gap is never silent. A scan lands in Knowledge with its reason and the
command, **with the size stated** — "Reading scans needs OCR: pip install
zaram[ingest] (321 MB, one time)" — the same shape as the voice extra. Naming
the fix without naming its cost is not a choice the user can make on a metered
connection.

Parsers sit behind one interface (`backend/ingest/parsers/base.py`) so the
library is replaceable rather than embedded, exactly as with TTS. Light parsers
resolve first and Docling is the fallback, so **installing the extra never
changes how an already-working file is read** — a folder must not index
differently depending on what happens to be installed.

Do **not** embed an office editor. OnlyOffice is AGPL and is a separate service;
LibreOffice headless is a several-hundred-megabyte dependency. Zaram generates
documents; users edit them in whatever they already use. Different problems.

Pandoc is GPL — acceptable as an optional external binary, not as a core dependency.

**TTS is Kokoro-82M and only Kokoro.** The binding constraint is that speech synthesis
must not compete with local inference for VRAM, and must work on Macs and AMD. Kokoro
runs on CPU under 2.5GB, Apache 2.0, 54 voices. Better-sounding models exist — Fish
Audio S2 (non-commercial weights, paid cloud API for the good version), Chatterbox
(gaming GPU, English only), Qwen3-TTS (6GB+ NVIDIA only) — and every one fails on
licence, VRAM, or platform coverage. Keep TTS behind an interface so the choice is
replaceable rather than embedded.

**Agents get no menu item.** An icon whose only function is to prompt setup is an
advertisement in the navigation. Agents are actions inside the conversation, configured
under Settings alongside Tools. Discoverability comes from a contextual offer at the
first moment a local answer is weak.

**Do not adopt an agent framework.** ADK, LangGraph, CrewAI, the OpenAI and Claude
Agent SDKs all ship their own memory and session abstraction, and memory is the
product. Provider-coupled frameworks are excluded on principle — neutrality across
models is the moat. Frameworks may be mined for *patterns* and evaluated as
*components*, never adopted as architecture.

**Do not send anything to a cloud observability service.** LangSmith and equivalents
trace prompts, tool calls and full input/output to a third party. Same prohibited class
as cloud parsing APIs.

**A pack is data and adapters, never navigation.** A vertical adds four things:
parsers, tools, output templates, and routing exemplars. It adds no screens. Projects
have a type, chosen once at creation, and that choice activates the pack. This is what
lets capability grow while the navigation stays at six nodes. **Project is where that
type is chosen** — creation is the only honest moment to ask, and it is the one thing
the user genuinely cannot be asked later without guessing.

**Premium pricing is available, and Superhuman is the evidence.** They charge
**$30/user/month** for an email client, against Gmail at zero, and what they
sell is speed, craft and feel rather than capability. The lesson is not to copy
the number — their buyers are salespeople and executives whose hour is expensive,
and the freelance wedge is more price-sensitive — but to stop assuming the
ceiling is low. A product that feels like a made object supports a price a
feature list does not, and Zaram's design discipline is already at that level.
Test the price; do not assume it.

**Give personalisation away; charge for continuity — settled 16 August 2026.**
Name, manner, voice, bring-your-own-VRM, memory, domains, documents,
obligations: free forever, one person, one machine, no caps. Personalisation is
the **retention** engine, not the revenue engine, and that is worth more —
putting the stickiest asset behind a paywall converts it into a conversion
barrier on a product whose pitch is that it is not extractive.

The paid rung is **their Zaram, everywhere**: end-to-end encrypted sync across
the user's own devices, plus encrypted backup. It is rule "charge for the
inconvenience the architecture creates" applied literally — the inconvenience
local-first creates is not the second person, it is the **second device**, which
every freelancer has and hits in week one. The earlier "pay for the second
person" answer aimed the paid tier at users the wedge explicitly excludes.
Multiplayer stays the rung above it.

**The margin is the point, and it follows from rule 1.** Every competing AI
product pays 40–70% of revenue back out as tokens. Zaram's cost of goods is
approximately zero, and a relay passing encrypted text deltas does not scale
with usage — someone who chats ten times more does not sync ten times more. That
is what makes a genuinely uncapped free tier permanent rather than promotional.

**Do not build an avatar marketplace.** VRM already has a creator economy —
VRoid Hub, Booth, thousands of artists. Supporting import inherits all of it for
free, with no moderation liability, no payments, no cross-border payouts and no
accounts. A curated *directory* that links outward is the most that should ever
be built; the storefront is a second company.

**Voice cloning is refused.** Kokoro's 54 voices are Apache 2.0 and sufficient.
Cloning from a sample is a consent and impersonation problem that would put
Zaram on the wrong side of the one argument it is winning. If it is ever built:
the user's own voice only, with a spoken consent phrase recorded at enrolment,
and never a sample supplied from elsewhere.

**Zaram never sells access to anything.** If a pack is ever priced, what is sold
is domain knowledge that runs on the user's machine — parsers that handle real
messy documents of one type, extraction validated against real examples,
templates, exemplars. Only one of a pack's four parts is MCP, and it is the
least load-bearing. Hosting tool servers would give Zaram cost of goods, route
user data through its own infrastructure, and become the trade the product
exists to refuse. Nothing is accessed; something is installed.

**Any MCP server may always be connected, including one that competes with a
paid pack.** A paid tier that restricts what the user may attach is a crippled
free tier wearing a different label, and it would make the tool layer a
gatekeeping surface — which the risk tiers already forbid for a different
reason. A *third-party* pack marketplace is a separate business and stays where
the scope list puts an extensions marketplace: after v1. It inherits the
tool-description-is-third-party-text problem below, plus accounts, moderation
and cross-border payouts.

**Build two packs by hand before building the pack system.** The abstraction cannot be
designed from imagination — only from two real examples and the friction between them.

**Integrations must pass five tests**, and only two verticals pass for v1:
1. Zaram drives an app the user already has, rather than shipping model weights
2. It does not compete with local inference for VRAM — *or it routes to cloud, see below*
3. The licence is permissive. GPL means separate process only; AGPL is excluded
4. Memory across sessions genuinely improves it — long projects, not one-shot tasks
5. The maintainer can test the output and judge whether it is good

**Will not build, ever, and not as a pack:**
- **Medical diagnosis.** Software that suggests diagnoses is regulated as a medical
  device in most jurisdictions. Medical *documents* — transcription, letters — are a
  different and defensible thing. Diagnosis is not.
- **Trading signals or financial advice.** Regulated, and indistinguishable in
  marketing from the operators that saturate the space. A trade journal is fine.
- **Legal advice.** Same class.

These are recorded so they do not return as reasonable-sounding suggestions later.

**v1 verticals: documents and 3D (Unreal, Blender).** Deferred: data/BI (DuckDB plus
text-to-SQL) is the leading third. Rejected: medical (regulated, credentials),
protein/science (cannot evaluate output), trading (copyleft tooling, memory adds little
to a bot). "We could integrate it" and "we can maintain it part-time" are different
lists, and the second is two long.

**VRAM limits route a task; they do not reject a vertical.** Where a task exceeds local
capacity, Zaram names the constraint, recommends models from the dated manifest with
their data policy, and carries project context into the cloud request — showing the
user exactly what leaves before it does. Video and image generation are deferred on
maintenance grounds, not because they are cloud-only.

**Take the commodity layer, spend the time on what only Zaram can do.** Orchestration,
provider adapters and document parsing are commodity and improve every quarter. Egress
logging, the correction loop, user-facing provenance and packaging are not. Every hour
spent rebuilding the former is an hour not spent on the latter.

## Technical decisions

- **MCP is the tool protocol.** Never invent a plugin or shim format.
- **Backend port is 8420, not 8000.** Unreal Engine 5.8's first-party MCP plugin
  binds `127.0.0.1:8000` inside the editor process and auto-starts. Port 8000 will
  collide for any user running both.
- **Frontend calls the backend directly over HTTP**, not through Electron IPC.
  Streaming through `ipcMain.handle` makes a real abort hard, and direct fetch keeps a
  browser surface possible. Base URL in an env var.
- **Hardware detection returns unknown, never a wrong number.** `vram_bytes` is a
  number or `None`; 0 is a measurement meaning "a GPU with no memory", which is not
  a machine that exists, and anything sizing a model against it concludes nothing
  fits. Metal and DirectML report `None` — Apple shares one pool with the CPU, and
  quoting system RAM would overstate what a model can claim.

  Read it from the driver, not from a framework. `torch.cuda.get_device_properties`
  made a 528MB dependency the only route to the card's capacity, and it does not
  exist in a packaged build — so VRAM was `None` for every user and the residency
  fit gate never ran, while its tests passed against pinned profiles. nvidia-smi
  ships with the driver; Windows records a 64-bit figure in the registry.

  **Never use `Win32_VideoController.AdapterRAM`.** It is a uint32 and saturates
  at 4GB, reporting 4294967295 for a 12GB card. It is the obvious source and it is
  a trap: taking it would have replaced a wrong `None` with a confident wrong
  number, which is the worse failure — a caller can check for `None`.

- **Do not build a memory engine from scratch.** Evaluate Letta or equivalent.
  Benchmark against LoCoMo / LongMemEval, not by feel.
- **Design the Spine as federatable from day one** — tenancy seams present even
  though multi-user ships later.
- **Domain-specific logic stays in a separate layer** from the engine. Do not build a
  pack *system* until two packs exist and have been built by hand.

## UI principles

- Calm over delight. Motion has a budget. Quiet mode from the start.
- The Orb shows system state (idle / thinking / local / cloud). It does not perform.
- Density beats animation on any surface used daily.
- The target user is not technical. No model filenames, quantization settings, or
  context-length sliders in the primary path.
- Show routing decisions in plain language.
- Never claim absolute security. State what is verifiable: inference ran locally,
  index is on disk, egress is logged.
- **Never render invented values.** A status indicator over hardcoded data is worse
  than no indicator. If a field can only say one thing today, it says one thing today.
- **Disabled capabilities are visible, not silent.** If a question would have used
  search and search is off, say so rather than answering quietly without it.

## Working agreement

- Read before you write. Verify against the code, not the docs.
- Verify by seeing it work. Do not report progress that has not been observed.
- **Assume unreachable until the caller is seen.** Parts of Zaram were built
  with Kilo Code and Trae, which produce a plausible, well-commented, fully
  tested whole and cannot check that anything calls it — and the tests they
  write assert the scaffolding rather than the contract. **Fifteen complete,
  tested, unreachable subsystems have been found**, including the
  prompt-injection defence and a 1,261-line model-ranking engine. This is the
  base rate here, not pessimism, and it is why "tests green" has repeatedly
  meant nothing. `npm run check:reachability` reports two of the shapes and is
  explicit that it misses three more — a dead branch inside a live function, an
  unused export, and a component mounted that should not be.
- **Say which environment you measured in, because it changes the result.**
  With Ollama running the backend suite takes ~4 minutes; with it down, ~20 —
  and more importantly it executes *different code*. A crash that stopped the
  backend booting hid for two weeks behind a green suite because its branch
  only runs when models are discovered and every one is unselectable: never
  with Ollama up, always on a stranger's machine. A number without its
  condition is not a measurement.
- **Check the instrument before reading its output.** The reachability guard's
  first run reported 183 dead modules that were all alive, and a written
  assessment once claimed the orb's core was painted with the cloud accent
  when that component never mounted. A tool built to find wrong things is not
  exempt from being wrong.
- Wire one surface to real data, then make it beautiful. The reverse produces
  interfaces that look finished and do nothing.
- When a plan and the codebase disagree, the codebase wins — say so.
- **A failure is out of scope only if the code it exercises is out of scope.**
  Classify by the contract a test asserts, never by the module it lives in.
  Grouping by module hides live bugs behind a label that discourages reading
  them: "13 core, 14 voice" made 27 failures feel understood for four
  milestones, and they turned out to be four unrelated bugs including a live
  `NameError` in shipped code and a test demanding a rule violation. Not one
  of the 14 was about voice. See `docs/KNOWN-FAILURES.md`.
- **A failing test is fixed or deleted, never left.** A test asserting a
  contract that no longer exists is noise that hides real regressions, and a
  permanent failure is a permanent invitation to stop looking.
- **A test that asserts nothing is worse than no test**, because it reports
  coverage it does not have. Two live defects were found by making two
  assertion-free tests assert what their names claimed.
- **A score built for ranking is not a score for deciding.** Where a number
  gates a decision, name which quantity it is and assert on *that*, never on
  whatever the pipeline happened to leave in the field. This has bitten three
  times: the citation threshold compared a ranking blend against a floor
  measured as a cosine, so a fact with a true similarity of 0.20 was cited on
  recency alone; the shortlist was then *selected* on the same blend, which
  discarded the single most relevant document in a 1,000-document corpus at
  rank 43; and the recall eval graded itself. Ranking, selection and permission
  are three different questions. A blend is a presentation choice — legitimate
  for ordering, never for deciding what is in the running or what the user is
  told.
- **A synthetic eval corpus must be checked before its numbers are read.**
  Filler that plausibly answers the query produces false negatives
  indistinguishable from retrieval defects. `_filler()` emitted "title
  sequence" briefs while one eval question asked how long the title sequence
  was: 64 of 995 documents answered it as well as the target did, the eval
  reported a recall miss for three measurement cycles, and it nearly bought a
  cross-encoder. **Distractors must be near the target without answering it**,
  and the corpus needs a test asserting that — cheap, no model required, and it
  guards every other number in the file. A stable failure count nobody can
  explain is how a broken instrument survives, exactly as a stable count nobody
  reads is how a real regression hides.

## Patterns worth borrowing (not adopting)

- **Session / memory split** — two stores, not one. See rule 7d.
- **Artifact service** — generated files saved explicitly, versioned, addressed by
  name. Maps onto the no-silent-overwrite and no-auto-index rules.
- **Before/after tool callbacks** — the interception point that can block or rewrite a
  call. This is where the risk-tier gate lives. The tier taxonomy is ours and is
  better, because it is about consequence rather than lifecycle.

- **Rank fusion instead of a weighted blend (RRF).** Read from TencentDB Agent
  Memory, 11 August 2026, and it is the most valuable thing there. It fuses
  rankers by **rank position** — `Σ 1/(k + rank)` — never by score magnitude.

  That matters here more than anywhere, because merging a ranking blend with a
  selection or citation threshold is **this codebase's most expensive recurring
  bug** and has cost it three times. The current fix is a discipline: keep
  `relevance` for selection and `score` for ordering, and remember which is
  which. RRF removes the class rather than guarding it — its output is on no
  source's scale, so there is no blended magnitude that *could* be compared
  against a floor measured as a cosine. A rule you cannot break beats a rule you
  must remember.

  Take it for **ordering**. It does not answer membership or citation, and
  wiring it into either would reintroduce the defect by a new route.

- **BM25 beside the vectors, fused rather than averaged.** Same source. Zaram's
  `_keyword_match` is naive term overlap, and its own comment records the
  problem: function words score against everything.

  The reason to want real lexical retrieval is rule 9's failure, not tidiness.
  "Write that up as a proposal" retrieves nothing because five referential words
  have no similarity to anything — but the *rare tokens* in a project, a client
  name or a reference number, are exactly what a lexical index is good at and a
  dense embedding is worst at. This is the one retrieval change with a
  documented failure waiting for it.

**Their four-tier pyramid is our scope field with more machinery, and ours is
the better shape.** L1 atom / L2 scenario / L3 persona maps onto facts carrying
`global` or `project:<id>` — rule 7i already argues why that belongs in one
field on one store rather than in separate tiers: facts move, recall needs both
at once, and the correction loop must stay uniform. Adopting the tiers would buy
nothing and cost the uniformity.

**L0 is rejected outright.** Persisting raw dialogue is rule 7d inverted, and
that rule was written from a specific failure — duplicate citations and Zaram
quoting its own replies. Their pipeline keeps L0 for verification; ours keeps
provenance instead, which is the same guarantee without the store.

**Not a dependency, at any licence.** It is MIT, so nothing is excluded on those
grounds — it is excluded on packaging. It is Node ≥22.16 shipped as three Docker
services, and the actual blocker is that a stranger cannot install Zaram. Adding
a container runtime to a Python backend moves that blocker backwards. Mine it
for patterns; do not link it.

## Models and routing

**Route with embeddings, not a generative model.** Task classification is a similarity
problem: embed the query, compare against task exemplars, take the nearest. `bge-m3` is
already resident for the Spine, so this costs ~10-30ms and zero extra VRAM, and it is
deterministic — misrouting is reproducible and fixable. A small generative model is the
fallback only if embeddings prove insufficient. Exemplars are user-editable.

**Routing must be legible.** Every reply names the model that answered and why
("routed to qwen2.5-coder — coding task"), with a per-message override available inline.
Same posture as memory correction, applied to routing.

**Identity is a fact the system supplies, not a story the model tells.** A model
does not know what it is deployed as — ask a local Qwen and it answers from
training data, which is how "I am Qwen, made by Alibaba" became the product's
answer to "what are you". The true answer exists only where routing resolved it,
so `core/identity.py` composes it and puts it in front of every request:
what Zaram is, which model is answering, and where that model runs.

**This is identity, not personality, and the distinction is the whole point.**
It does not refuse the product describing itself; a status indicator that cannot
say what it is is not calm, it is broken. What is refused is a **competing**
claim: the eight named personas that each opened "You are Baba, a wise and
analytical AI assistant" were removed on 13 August 2026 because each one made a
rival identity claim and gave the model a third candidate answer about itself.

**A user's own name for it is not a competing claim — revised 16 August 2026.**
`assistant_name`, `manner` and `voice` live in `user_settings` and reach
`identity_preamble` as facts, in an order that is the guarantee: what Zaram is,
what the person calls it, what is answering, *their manner*, then how to answer
about itself. The user's text comes before the truthful rules so the rules
answer it rather than the other way round. Bounded on the way in and again at
the prompt — an unbounded manner is the cheapest attack on the guarantee, since
it needs no cleverness, only length. Full reasoning under the embodiment section
above.

**Never hide the model.** The temptation, once the assistant stops naming
somebody else's, is to have it name none. That forfeits routing legibility and
the product's best demonstration: the memory holds while the model changes
underneath it. A model switch is not a leak in the story, it *is* the story.

**Locality is three-valued for identity and two-valued for routing.**
`_is_remote_model` answers `False` for a model it cannot resolve, because
routing must fail safe — guessing local costs a possibly-wrong model, guessing
cloud costs the user's documents leaving on a lookup that failed. Identity must
not inherit that: `locality_of` returns `None`, because "runs on this machine"
would be a confident false claim on the one thing the user is most likely to
check. Same input, two questions, two answers, and they must not be merged —
the same split `vram_bytes` makes by returning `None` rather than `0`.

**Model residency is a hardware-grading problem.** Measured on a 12 GB RTX 3060,
8 August 2026, with `nvidia-smi` and Ollama's `/api/ps` — not estimated:

| | |
|---|---|
| bge-m3 embeddings, resident | **0.66 GB** |
| Reranker, resident | **0 GB** — nothing runs; see `docs/RERANKER.md` |
| KV-cache reserve (20% of VRAM, a judgement) | 2.58 GB |
| **Budget a chat model may claim** | **~9.1 GB** |

The old figure here was "~1.8 GB for embeddings and reranker resident, roughly
9 GB remains". The 9 GB was right by coincidence and the 1.8 GB was wrong in
both directions: embeddings are 0.66 GB resident, and the reranker share was
never spent because `bge-reranker-v2-m3` cannot run through Ollama at all.

**The gate does not read this table** — `ProviderManager.resident_budget_bytes`
computes from whichever embedder discovery actually found. That is the right
design and it is why the wrong prose never became a wrong decision. Keep it
that way: a constant in a document that a gate reads is the same failure as a
wrong `vram_bytes`, only quieter.

One real imprecision remains: the gate uses the embedder's **on-disk size**
(1.16 GB for bge-m3) as a proxy for its **resident VRAM** (0.66 GB), so it
over-reserves by ~0.5 GB. Checked across 4–24 GB against the installed model
set, that never changes which model is selected — the gaps between model sizes
are 1–3 GB and swamp it. Worth fixing when something depends on finer
granularity, not before.

Some model pairs are co-resident; others force an unload/reload costing
seconds. Settings must show which is which, and a route that requires a swap
must be visible in the orb's state. An invisible swap reads as a broken product.

**Three tiers of control**, so a non-technical user never sees the third:
1. Default — Zaram picks, one local and one cloud, auto-routed
2. Preference — *Prefer local · Auto · Prefer cloud*, one control, plain language
3. Per-task assignment — chat, coding, vision, long-document — behind Advanced

Conversation mode persists until changed, overridable per message. Do not classify with
a model call before every reply.

## First run

1. Detect VRAM, RAM, and installed Ollama models. **No questions yet.**
2. One question: what will you mostly use this for? Seeds routing exemplars.
3. Show what was found. Primary action is **"start with what you have."**
4. Cloud keys optional, framed as optional: "Everything works without this."
5. Point at one folder, index, reach a cited answer.

**Never block on a download.** A user on metered data asked to pull 7GB before their
first answer closes the app. If a download is needed, start with the smallest capable
model and fetch better in the background.

**Model recommendations ship as a dated local manifest** — JSON in the bundle, grouped
by VRAM tier, with a visible `generated` date. Never fail closed: a missing or corrupt
manifest falls back to whatever is installed. Detection (hardware, installed models) is
separate from recommendation (names, sizes) — the first never goes stale.

Re-runnable from Settings as **re-scan**, not as a replayed wizard: it re-detects and
shows a diff, changing nothing without confirmation. A model assigned to a task that is
no longer installed is detected at startup, not at re-scan.

## Generation pipeline

**HTML is the source of truth for every generated document.** Generate HTML, then
convert: WeasyPrint to PDF, a second export to .docx. This gives one pipeline instead
of four, and makes preview trivially faithful — the preview *is* the HTML that
produced the file, so what the user sees is what downloads.

Preview support ships in order: PDF in v1 (native, high fidelity, already generated);
a lightweight HTML render for .docx and .xlsx in v1.5, clearly labelled as approximate;
PowerPoint and high-fidelity Office later, only if asked. Everything without a preview
offers download and open-in-default-app.

## Current milestone

The recall demo, end to end: ask model A something, ask model B about it later, get a
cited answer, delete the fact, watch the answer change, open the log and see what left.
Then generative documents on top of it.

## The actual blocker

**A stranger cannot install this.** Capability is not what stands between the current
state and a 15-person retention test — packaging is. An installer and a guided first
run are a milestone, not an afterthought, and no amount of additional capability
substitutes for them.
