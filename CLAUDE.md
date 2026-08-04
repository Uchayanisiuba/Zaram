# Zaram

The memory and control layer for people who use more than one AI.

Zaram sits between the user and whatever models they use — cloud or local. Everything
flows into one knowledge base on their machine. Any model can recall it. The user sees
what was recalled, can correct it, controls what leaves the device, and can put the
result to work through tools.

Full rationale: `docs/VISION.md`. Interface: `docs/UI-SPEC.md`. Read both before
proposing product changes; neither is auto-imported.

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

## Navigation — four surfaces plus Settings

**Work · Memory · Knowledge · Activity**, with Settings bottom-anchored. Sources live
inside Knowledge. Tools are configured inside Settings.

**Work is where output lives** — documents, spreadsheets, charts the user made, each
with the conversation that produced it and its sources. It exists because a navigation
made only of Memory, Knowledge and Activity is entirely about the system and contains
nothing the user made. Nobody pays for a memory browser. Memory matters because it is
memory *of work*.

The test for any future surface: **does it hold something real?** Work holds files.
Canvas and Plugins held nothing, which is why they were cut.

Conversation is **not** a rail item. It is the shell — the landing state, entered by
the orb, animated aside when a surface opens. But the return path must be visible and
one click: the orb reverses the animation, and the persistent bar's topic line is
clickable. Never let the animation be the only route back.

**Tools never get menu items.** They are actions inside the conversation. This is what
lets capability grow without the navigation growing. Adding a fourth top-level surface
requires a reason that survives "why is this not part of Conversation?"

Generated files appear as cards in the conversation and land in the output directory.
There is no Files surface — that duplicates the operating system.

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

## Scope for v1

In scope:
- Ingest a folder into the Spine
- Chat routed to at least two providers (one cloud, one local)
- Recall across providers with visible provenance
- Correct or delete a fact and see answers change
- Egress log, viewable, recording chat and tool activity
- Per-source privacy policy
- **Generative tools**: .docx, .pdf, .md, .xlsx, and charts from the user's own data,
  with provenance carried into the output
- **Read-only Unreal MCP**: inspect scene, list actors, report on materials and
  lighting. No writes.

Out of scope until v1 ships and is tested with real users:
- Any mutative tool (file edits, VS Code, Blender writes, Unreal writes)
- Web search — see sequencing below
- Agents, extensions marketplace, updates feed, voice, multi-user, sharing
- Image generation (competes with local inference for VRAM, not grounded in user data)

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

| Purpose | Choice | Licence |
|---|---|---|
| Ingestion / parsing | Docling (+ Granite-Docling-258M) | MIT / Apache 2.0 |
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
lets capability grow while the navigation stays at four items.

**Build two packs by hand before building the pack system.** The abstraction cannot be
designed from imagination — only from two real examples and the friction between them.

**Integrations must pass five tests**, and only two verticals pass for v1:
1. Zaram drives an app the user already has, rather than shipping model weights
2. It does not compete with local inference for VRAM — *or it routes to cloud, see below*
3. The licence is permissive. GPL means separate process only; AGPL is excluded
4. Memory across sessions genuinely improves it — long projects, not one-shot tasks
5. The maintainer can test the output and judge whether it is good

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

**Model residency is a hardware-grading problem.** On 12GB with embeddings and reranker
resident (~1.8GB), roughly 9GB remains. Some model pairs are co-resident; others force
an unload/reload costing seconds. Settings must show which is which, and a route that
requires a swap must be visible in the orb's state. An invisible swap reads as a broken
product.

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
