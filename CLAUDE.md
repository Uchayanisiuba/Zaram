# Zaram

The memory and control layer for people who use more than one AI.

Zaram reads what the user produces and receives, remembers what they owe and what
they're owed, and acts before it's late.

Everything flows into one knowledge base on their machine. Any model can recall it. The
user sees what was recalled, can correct it, controls what leaves the device, and puts
the result to work through tools.

**The product is horizontal; the wedge is not.** Obligation extraction works identically
for a contractor's quote expiry, a landlord's lease renewal and a researcher's grant
deadline. We start with freelancers and one-person businesses because that is where it
can be proven fastest.

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

## Scope for v1

In scope:
- Ingest a folder into the Spine
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
  the orb, chosen by a toggle, both reading one derived state so neither knows
  the other exists. It embodies which model is answering and what it is doing —
  **not a personality**: no name, no pronoun, no wandering gaze, no expression
  not derived from system state. The landing default stays the orb.

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

Out of scope until v1 ships and is tested with real users:
- Any mutative tool (file edits, VS Code, Blender writes, Unreal writes)
- Web search — see sequencing below
- Agents, extensions marketplace, updates feed, multi-user, sharing
- **Image and video generation — post-v1, and via cloud routing only.** The
  original objection was VRAM and grounding, and the VRAM half is answered by
  the existing rule that VRAM limits *route* a task rather than reject a
  vertical. So the shape is settled even though the schedule is not: Zaram ships
  no image or video weights, ever. It routes to a provider, logs the egress,
  carries project context, and shows what left. It cannot ship before the cloud
  engine exists, which is still a failing v1 scope line.

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

## Models and routing

**Route with embeddings, not a generative model.** Task classification is a similarity
problem: embed the query, compare against task exemplars, take the nearest. `bge-m3` is
already resident for the Spine, so this costs ~10-30ms and zero extra VRAM, and it is
deterministic — misrouting is reproducible and fixable. A small generative model is the
fallback only if embeddings prove insufficient. Exemplars are user-editable.

**Routing must be legible.** Every reply names the model that answered and why
("routed to qwen2.5-coder — coding task"), with a per-message override available inline.
Same posture as memory correction, applied to routing.

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
