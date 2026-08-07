# Zaram — Milestones

Ordered. Each has an acceptance criterion phrased as something you can *see*, not
something that passes. "Tests green" is not done; "I ran it and watched X happen" is.

Read with `CLAUDE.md` (the contract) and `docs/UI-SPEC.md` (the interface).

**This file is the handoff.** A new session should be able to read it and know
where the work stands without being told. Keep the Current state block below
accurate — it is the first thing anyone reads.

---

## Current state — 6 August 2026

**Suite:** 1161 collected · 1134 passed · **27 failed** on a full dev install,
in ~2m. The 27 are unchanged and pre-existing — listed under Known broken.
The base-install figures are stale: the 95 new artifact tests should all pass
there too, since their dependencies are in the base requirements, but that has
not been measured. Previously: 951 passed · 13 failed · 52 skipped.

**Base install: ~317 MB.** 267 MB plus a *measured* 50 MB for the exporters
(matplotlib 31, fonttools 16, openpyxl and the rest 3). Voice remains an
optional 905 MB extra. If that 50 MB has to come back, the split is charts-only
— .docx, .md and .xlsx together are 2 MB, and matplotlib is the whole cost.

**M9b and Session 4 are committed.**
`backend/artifacts/` now has the model, the write path, the HTML layer,
`export/` (Markdown, .docx, .xlsx, PNG), `records.py` (SQLite) and
`service.py`. `main.py` serves `/artifacts`. Work reads real records and
`sampleArtifacts.ts` is deleted. **PDF is the only exporter not working**, and
it is blocked on packaging rather than on code — see Open questions.

**Verified against a live server**, not just tests: three artifacts generated
over HTTP, listed, previewed and downloaded through the Vite dev proxy on the
same path the browser uses.

**Generation is reachable from chat.** "Write that up as a proposal" routes to
`document.generate`, writes a .docx grounded in the conversation, and returns
it as a card in the transcript and a row in Work. M9b's acceptance criterion
is met.

**Routing is embedding-based.** `core/retrieval/` embeds the query with bge-m3
and compares against task exemplars. Keywords remain the fallback.

**Last commits:** semantic routing + chat-reachable generation → Work reads
real artifacts → the exporters → artifacts write path → Work surface →
dependency removals → packaging split → VRAM detection.

### Decisions taken that are not yet obvious from the code

- **An externally edited file returns as a new artifact**, origin
  `user_document`, never as an update to the generated one. We cannot verify
  which claims survived a Word edit, and letting unverified text inherit
  citations is the product failing in miniature. **The UI must say this** when
  it happens — silent lossiness is the same class of problem as silent
  ingestion failure. Not yet built.
- **`Artifact.indexed` defaults to `False`**, against rule 7b's default-on. The
  deprioritisation that makes default-on safe needs origin *on facts*, which
  lands with M8. Until then, not indexing is safer than indexing unranked.
  **Flip it in the M8 commit.** This is a known, time-boxed gap.
- **Collisions increment by default** (`proposal-2.docx`); asking is the escape
  hatch when the bounded retry exhausts.
- **`Claim.source_revision` and `verified_at` exist and are unused.** Staleness
  detection is not built; the fields are there so adding it later does not mean
  migrating every artifact.
- **Claims reach Word as bookmarks, not as attributes.** `data-zaram-claim`
  does not survive export — Word discards unknown markup — so each claim is a
  real internal hyperlink to a real bookmark on its Sources entry. Clicking a
  sentence in Word jumps to the source, with Zaram not running. The
  machine-readable mapping stays on `Artifact.claims`, independently. Word
  drops a bookmark whose name has a hyphen or exceeds 40 characters *silently*,
  rendering every link as dead text, so `_bookmark_name` is asserted by test
  rather than trusted.
- **The .xlsx exporter refuses to guess.** "₦425,000" becomes the number
  425000; "50%" and "2026-07-02" stay text. 50% is 0.5 to Excel and 50 to a
  naive strip, and writing the wrong one into a cell that feeds a formula is
  the failure the module exists to prevent. Text is visibly unfinished; a wrong
  number is invisibly wrong.
- **Charts always ship their data table, and it cannot be turned off.** Three
  of the eight categorical slots fall below 3:1 contrast on white, which
  obligates relief. The table is that relief, so the picture is never the only
  copy of the numbers. A ninth series is refused rather than given an invented
  hue.
- **Unavailability is a return value, not an exception.** `export.formats()`
  lists every format with whether it runs here and why not. An `ImportError`
  surfaced as "PDF failed" tells a user nothing actionable and reads as a bug
  in Zaram rather than a missing system library.
- **Two artifact stores, on purpose.** `store.py` holds files and cannot unmake
  them; `records.py` holds records and has no general `update` and no `delete`
  — one named method for the one field the user controls
  (`set_remember_override`). The module this replaced had an `update()` that
  `setattr`'d anything passed to it. A second mutation has to be a second named
  method, which is a conversation rather than a keyword argument nobody
  reviews.
- **The file is written before the record, always.** The reverse ordering makes
  Work show a row for a document that does not exist. This ordering, on
  failure, leaves a file the user has and Work has not listed — under-claiming,
  which is visible and recoverable. Over-claiming is neither.
- **`remember_override` is three-valued.** `None` (undecided, a default may
  still apply), `True`, `False` (a refusal, which a default may not override).
- **Work shows project *ids*, not names.** There is no project-name store, and
  turning `harbour` into "Harbour Lane Studio" would be a value nobody entered.
  The sample data had names because it was invented.
- **The preview is an iframe of the stored HTML**, sandboxed with no
  permissions. HTML is the source of truth, so the preview *is* what the file
  was rendered from — not a second rendering that can disagree with it.

### Routing and generation

`core/retrieval/` is **one index with two decision rules**, built that way so
MCP tool selection lands on it rather than beside it. Routing needs a decision
(one winner, above a floor, with the margin over the runner-up as confidence);
tool selection needs a shortlist (top-k, no floor). `search()` ranks and stops;
both rules sit on top as thin functions.

For MCP, what already holds: namespaces with independent drop/re-register (a
server disconnects, its tools stop being offered), a content-hash embedding
cache (a reconnect re-registering 200 unchanged descriptions costs nothing),
and a dimension lock (cosine across two embedders is meaningless, not weaker,
so the index refuses). **What must never change: a retrieval score authorises
nothing.** A tool description is third-party text and can be written to sit
near every query; retrieval produces a shortlist, the model chooses, the risk
tier gate still runs.

**Keywords remain the fallback and should stay.** The embedder degrades to a
hash backend when Ollama is unreachable, and similarity over hash vectors is
arbitrary rather than merely worse. The router reports that and hands back.

Four bugs stood between "every piece works" and "the feature works", and all
four were only visible end to end:

1. **The reasoning step got the literal prompt.** Asked to "write that up as a
   proposal" with no framing, the model described its own operating protocol
   and that text became the file. The planner now derives a writing
   instruction; the *user's* words still reach the runtime, which reads them
   for "spreadsheet" or "invoice".
2. **Recall could not resolve "that".** Similarity against five referential
   words retrieves nothing, and the model invented a whole client — one run
   produced a confident document about a "Project Phoenix" with the real
   client's name and day rate nowhere in it. Fixed with an **ephemeral session
   buffer on the engine** (rule 7d: session state and the Spine are separate
   stores). `_remember` deliberately stores the user's words as a fact and not
   the exchange, which is right for memory and leaves nothing that can answer
   "what is 'that'".
3. **The card lacked `exists`.** The `/artifacts` listing had it and the card
   did not, so a card for a file written a second earlier said "file not found
   where it was written".
4. **The title printed two or three times**, and Markdown `**` reached the
   .docx as literal asterisks.

**Charts from chat are refused, deliberately.** A chart is a claim about
numbers and the runtime has prose; inventing figures to plot would be worse
than refusing, and quietly returning a document nobody asked for would be too.
The refusal names what is missing and offers what works. A real chart path
arrives with the business layer, where figures come from invoices.

### Open questions

- **Dev tooling still ships in the base install** — mypy, ruff, pytest,
  pip-licenses, wheel. Probably 30–40 MB. Same split-verify-measure method as
  the voice extra. Belongs in the packaging spike.
- **Jinja2 is declared in the *voice* extra and used by nothing.** An earlier
  version of this file listed it as available for M9b; it is not on a base
  install. Nothing needs it — the HTML layer builds strings directly — so the
  question is whether it is a real transitive dependency of the voice stack or
  a leftover. Removal plus a green suite is the only way to find out.
- **WeasyPrint on Windows needs native GTK libraries**, which is a packaging
  decision rather than a `pip install`. This is the only part of M9b not
  working. The exporter is written and the format reports itself unavailable
  with the reason and a per-platform remedy, so the gap is visible rather than
  silent — but a Windows user cannot produce a PDF until the installer carries
  the MSYS2 GTK runtime. **Decide this in the packaging spike, not before**:
  the alternative is ReportLab, which would mean a second document pipeline
  and breaks "HTML is the source of truth". Markdown and .docx work on every
  machine, so nobody is blocked from getting a file out meanwhile.
- **Code signing** is the long-lead packaging item. Windows business
  verification as a Nigerian sole trader needs investigating now, in parallel.
  Unsigned costs Zaram more than a typical app: SmartScreen's warning appears on
  a product whose entire claim is trustworthiness.
- **`speech.tts` is reachable from the chat path** while voice is out of scope.

---

## Done

### M0 — Recall loop ✅
Spine on SQLite with `bge-m3` embeddings. Facts stored, retrieved, injected with
citation markers, provenance events emitted.

**Verified:** a fact stored in one session was recalled in a separate session
with provenance.

### M1 — Egress log ✅
Append-only hash-chained log, per-host policy, default deny, all outbound calls
through one gate. `test_egress_chokepoint.py` fails the build on any direct HTTP
call outside `core/egress/`, and on a stale exemption naming a deleted file.

### M2 — Provider layer ✅
`backend/providers/` connected, renamed from `garage/`. Model metadata carries a
data policy with no default value — unknown is `None`, never a guarantee.
`select_default_model()` refuses rather than choosing something unlabelled, and
reports *why* each candidate was refused.

**Verified:** booted against real Ollama, 10 models discovered and labelled.

### M3 — Frontend integration ✅
`chatClient.ts` does `POST /chat`, parses NDJSON, handles JSON split across
chunks and multi-byte characters split mid-character.

### M4 — Verify the integration ✅ (partly)
Verified at transport level against a live backend. Found and fixed two real
bugs:

- **`invoice` contains `voice`** — keyword matching was substring-based, so every
  invoice request routed to text-to-speech and returned a fallback with no model
  call. Also `essay`→`say`, `profile`→`file`, `research`→`search`. Now matched on
  word boundaries.
- **The requested model was logged and then discarded.** `/chat` accepted a
  model, the dispatcher logged it on the line above the call that did not pass
  it, and the engine always used its own default.

**Not done:** no UI walkthrough. The Playwright browser install failed on this
connection, so the interface has never been driven. Whether **stop** actually
aborts a request is still unverified.

### M5 — VRAM detection ✅
`_vram_bytes` read `torch.cuda.get_device_properties`, which does not exist in a
packaged build — so VRAM was `None` for every user and the residency fit gate
never ran, while its tests passed against pinned profiles. Now nvidia-smi, with
the Windows registry for AMD/Intel. **Never `Win32_VideoController.AdapterRAM`**:
uint32, saturates at 4 GB, reports 4294967295 for a 12 GB card.

**Verified on the dev machine:** RTX 3060, 12 GB detected, a 9 GB model refused
when a 5 GB one fits, with the reason logged.

### M6 — Shell cleanup ✅
Orbit carries five nodes: Work · Memory · Knowledge · Activity · Settings.
19 unreachable files moved to `legacy/`. **Bundle unchanged — byte-identical,
same content hash** — which is the proof they were never linked. The win was
repo clarity, not size.

Found on the way: the surface list was restated by hand in TopNav, LeftRail and
CommandPalette, and the palette had silently lost Activity. All three now derive
from `surfaceOrder` with `Record<WorkspaceId, …>` icon maps, so the compiler
names every file needing an entry.

### Packaging ✅ (the big one)
**1,436 MB → 267 MB base**, an 81% reduction, and the single most consequential
thing done for the alpha — the difference between an installer someone on
metered data will download and one they won't.

- Voice is an optional 905 MB extra. Voice tests skip with the install command in
  the reason rather than failing.
- `soundfile` was imported at module scope in the Kokoro provider, so the
  graceful-degradation path could never run — the module died three lines into
  its own imports. Now lazy.
- Removed `diffusers`, `openai-whisper`, `edge-tts`, `onnxruntime`, `accelerate`,
  then `scipy`, `numba`, `llvmlite`, `tiktoken`.
- **spaCy was nearly removed by mistake.** `pip show` reported no dependents
  because misaki reaches it at runtime without declaring it. Removing it broke
  speech. **Verify by removal and a green suite, never by metadata.**

### Session 1–2 — Orbit and Work ✅
Work added as the fifth node. The Work surface built against clearly-labelled
sample data: 20 artifacts, two projects, filter by project and type, detail panel
from the right with preview, sources and a link back to the conversation.
Download is inert and says why — a working button emitting a plausible invoice
from invented data is worse than no button, because the file outlives the screen
that explained it.

The landing hint ("Click Orb to Chat") replaced the persistent bar. **Two things
went with it:** the clickable topic line was the third route back and the only
one that named its destination, and the `local · model · N facts recalled` line
is no longer visible. `sessionStatusStore` still tracks all of it.

### Session 4 — Work reads real artifacts ✅
`sampleArtifacts.ts` is deleted. Work fetches from `/artifacts` through
`services/artifactsClient.ts`, with loading, error-with-retry and a truthful
empty state. The detail panel previews the stored HTML in a sandboxed iframe,
lists claims with their source excerpts, and downloads the real file.

The sample's shape had drifted from the backend model — `projectId` against
`project_id`, a nested `conversation` object against two flat fields, and a
`previewText` with nothing behind it. The model won, and the client uses its
field names directly rather than mapping, because a mapping layer is a second
vocabulary and a place for the two to disagree quietly.

**Download is real now.** It was inert and said why, because a working button
over invented data emits a file that outlives the screen explaining it. The
button now also distinguishes "no file" from "the file is not where it was
written" — the record can outlive the file, and 410 is a different problem from
404.

**Verified end to end against a live backend**, through the Vite dev proxy on
the browser's own path: generate → list → preview HTML with claim anchors →
download 37 kB of .docx with the right content type. Not driven in a browser —
Playwright is still unavailable here.

---

## Next

### M9b — Generative documents ✅
Reachable from chat as of this commit. See "Routing and generation" below for
the four bugs that stood between the pieces working and the feature working.

### M9b — the pieces (kept for the reasoning)
**Committed:** the artifact model, the write path, the HTML layer, and the
exporters — Markdown, .docx, .xlsx and PNG, verified end to end against real
output. 58 tests in `test_artifact_exporters.py`.

The write path is a property of the code, not a convention: `open(path, "xb")`
is create-or-fail atomically, there is no function named for deletion, and
`test_artifact_write_path.py` scans the module's source so the build fails on the
commit that introduces the capability rather than at runtime after a file is
gone. Path confinement gets eight traversal payloads — the *model* proposes
filenames, so `../../.ssh/config` is an input to assume.

**That guarantee now has a second gate.** The exporters return bytes and never
touch the filesystem; `ArtifactStore` stays the only writer. A source scan over
`artifacts/export/` enforces it, so adding a sixth format cannot quietly route
around the store. It matches *calls* rather than names, because `workbook.save`
and `write_pdf` both write to memory.

**Remaining:** PDF, blocked on GTK packaging (see Open questions), and the
**conversation half** — nothing generates from chat.

**Acceptance:** ask a question, say "write that up as a proposal", get a .docx
where claims link back to the source paragraph they came from. The file appears
as a card in the conversation and as a row in Work.

**Verified:** a proposal with recalled claims exported to .docx, both claim
hyperlinks resolving to bookmarks present in `word/document.xml`; and the same
document generated over HTTP, listed and downloaded through the dev proxy. The
document half and the Work half both hold.

**The gap, precisely.** `POST /artifacts/generate` is the seam and it works —
it is what a capability would call. What does not exist is the capability: chat
goes through `CapabilityRouter` / `IntentBasedRouter.INTENT_MAP`, and producing
a document from natural language means registering a runtime there, adding an
intent, and emitting a file-card event on the stream. Deliberately not
half-wired this session. Note also that routing is keyword-based, so
`INTENT_MAP` will match "proposal" by word rather than by meaning until
embeddings land.

### Session 5 — Settings → Tools, the pack catalogue
Each pack shows risk tier (generative / mutative / egressive), data policy, and
honest grading against this machine — greyed out where unavailable, with the
reason stated. Only packs that exist or are genuinely next; a catalogue of forty
things we will never build is a promise accumulating.

### M7 — Ingest
**The one v1 scope item with nothing built.** Docling. Folder in, facts out.

**Failures must be loud.** A file that produced nothing appears in Knowledge with
a reason and a retry, and is mentioned in the conversation the first time it
matters. Silent ingestion failure is the most likely reason a user concludes the
product doesn't know their material and leaves.

### M8 — Memory scope
Every fact carries `global` or `project:<id>`, **and `origin`** — the two land
together because they add fields to the same rows and doing them separately means
two migrations. **Flip `Artifact.indexed` to `True` here.**

**Do this before the alpha.** Retrofitting scope onto facts that lack it means
guessing for everything already stored. It is also the multiplayer boundary.

### M9 / M9a — The business layer and obligation extraction
The universal job: invoice → receipts → expenses → how is the business doing.
Then the keystone: dates and commitments pulled from documents, surfaced before
they lapse, **every obligation showing its source clause and correctable**.

**Acceptance:** generate an invoice with 30-day terms; on day 31 Zaram says the
payment is late, shows the clause it read that from, and has the follow-up
drafted. Correct a wrongly-extracted date and watch the reminder move.

### M9c — Read-only MCP: Unreal and Blender
Inspect, list, report. No writes, so no undo or sandbox needed — which is why it
ships in v1 and scoped writes do not. **Epic's plugin binds `127.0.0.1:8000`, so
the backend must stay on 8420.**

### M10 — Confirm-before-send, editable
The dialog shows the literal outbound text, the destination and the reason.
Recalled facts are removable chips, editable inline, edits written through as
supersessions.

### M11 — Packaging
**The real blocker.** A stranger cannot install this. See Open questions above —
code signing has the longest lead time and cannot be compressed later.

**Acceptance:** a Windows machine that has never seen the repo runs one installer
and reaches a cited answer from its own files in under ten minutes.

### M12 — Alpha
Ten to fifteen people, one segment. Onboard individually, watch, do not help.
Ask at intake: hours spent on admin last month, and what is past due — those
answers become the missing line in `docs/PITCH.md`.

**Acceptance:** the day-30 number. 5+ of 15 weekly → build the paid tier.
2–4 → the job is wrong. 0–1 → the thesis is wrong, learned in six weeks.

---

## Known broken

**27 failing tests**, unchanged and pre-existing:

- 13 in `test_streaming_conversation`, `test_alpha10c_acceptance`, `test_kernel_flow`
- 14 in voice — these skip on a base install, so CI sees 13

Record any change to that number. A stable failure count everyone stops looking
at is how a real regression hides.

Also broken, found and not fixed: `services/speech_manager.py` imports a module
that was deleted. Nothing imports `SpeechManager`, so nothing breaks today.
