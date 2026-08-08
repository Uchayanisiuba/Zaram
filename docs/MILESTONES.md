# Zaram — Milestones

Ordered. Each has an acceptance criterion phrased as something you can *see*, not
something that passes. "Tests green" is not done; "I ran it and watched X happen" is.

Read with `CLAUDE.md` (the contract) and `docs/UI-SPEC.md` (the interface).

**This file is the handoff.** A new session should be able to read it and know
where the work stands without being told. Keep the Current state block below
accurate — it is the first thing anyone reads.

---

## Current state — 8 August 2026

**Suite: 0 failures.** 1152/27 → 1263/0 on a full dev install. The 27 were not
one thing; see "What the 27 actually were". Run pytest **from the repo root** —
the `--ignore` lines in `pyproject.toml` are rootdir-relative, and running it
from `backend/` aborts collection on a truncated `test_kernel.py`.

**M7 is done and driven for real.** `backend/ingest/` — parser interface, light
parsers, quality floor, loud failures. Verified against a real folder: an
invoice indexed, an image-only scan reported with its reason and the OCR
remedy, an encrypted .docx reported as password-protected, then a cited recall
naming the source document.

**Recall was broken and is now measured.** The eval harness found, on its first
run, that hybrid retrieval was ranking on stopword overlap — an unrelated
question outscored a genuinely relevant document. Fixed in three places. See
"What the recall eval found" — this is the most consequential thing in this
entry.

**Docling is now an optional extra**, decided by measuring 1,080 real files.
CLAUDE.md's dependency table is updated; the reasoning is recorded there.

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

### What the recall eval found — read this one

**Hybrid retrieval was ranking on stopword overlap.** Recall is the moat, it
had never been measured end to end, and the eval failed within minutes of
existing. Three bugs, in three different places, all pointing the same way:

1. **`HybridMemoryRetriever` ran keyword search *beside* vector search in
   HYBRID mode and kept whichever scored higher** (`retrieval.py`). Keyword
   scoring split on whitespace with no stopword filter, so *"What is the
   capital of France?"* overlapped a Harbour Lane project brief on `is`, `the`
   and `of` — three of six terms, a score of 0.5 — while the true cosine
   similarity was **0.226**. The max won. An unrelated document was cited with
   a number that looked like a similarity and was not.
2. **`HybridMemoryIndex` blended `0.7 * vector + 0.3 * keyword`**, which capped
   any document matching on meaning alone at 0.7 of its true score. A genuinely
   relevant note scoring **0.599** under bge-m3 arrived as **0.407** and was
   dropped by the 0.42 floor. Keyword now *boosts* into the headroom above the
   semantic score and can never dilute it.
3. **Stopwords scored at all**, in both places, with two hand-maintained
   tokenizers that disagreed — `France?` was a term and `is` was a good one.
   One shared `content_tokens()` now.

**Before: the populations were inverted** — genuinely related documents bottomed
out at 0.407 while unrelated ones reached 0.493, a margin of **−0.086**. No
threshold could separate them, so no value of `MIN_RECALL_SCORE` was correct.
**After: +0.080**, related min 0.469 against unrelated max 0.389, with 0.42
sitting in the gap. `test_recall_eval.py` prints that margin on every run, so a
narrowing one is visible before a user feels it.

**`MIN_RECALL_SCORE = 0.42` was not "chosen by feel"** — that claim was wrong.
It was measured, with the distribution recorded in its docstring and asserted by
`test_recall_relevance.py`. What was wrong is subtler and worse: it was measured
*through* the distortion above, on a two-fact Spine. It held there and collapsed
at five documents. It is now validated against real embeddings on a deliberately
confusable corpus.

**`bge-reranker-v2-m3` cannot be wired through Ollama.** Both `/api/embed` and
`/api/generate` terminate llama-server with a stack-buffer overrun
(`0xc0000409`). It is not merely unreferenced — it is unusable by this route, so
CLAUDE.md's ~1.8 GB "embeddings and reranker resident" arithmetic is fiction
until a different route exists. Decide it deliberately; do not assume the model
being pulled means it works.

### What the 27 actually were — the count was four separate bugs

The previous entry said "13 = one stale test double, 14 = voice, out of scope".
Both halves were wrong, and the second was the more misleading.

- **The stale `FakeLLM` was real but was only the top layer.** Fixing the
  signature moved the failure one level down: `test_streaming_conversation` and
  the voice integration module were written against a `ConversationManager`
  that took a `VoiceManager` and yielded `audio` events. Sprint Alpha.6
  replaced that with the event bus. **Half those tests could never have passed
  again**, whatever was done to the fake. They now test what the manager
  actually promises; the audio assertions went back to the voice stack.
- **The 14 "voice, out of scope" failures were not voice.** Five were
  `test_kokoro_provider` asserting that discovery populates `_voices`, which
  stopped happening when `voice_discovery_enabled` was deliberately defaulted
  **off** — real discovery contacts huggingface.co at startup and rule 7g
  forbids that before consent. Nine more were the ConversationManager problem
  above. "Out of scope" was the label that stopped anyone reading them.
- **Two were a live NameError.** `main.py` used `SEARCH_MARKER` without
  importing it — a real crash on the web-search path, latent only because
  search is default-deny.
- **One asserted a rule violation.** `test_alpha10c_acceptance` required
  `/chat` to trigger a search; search has since moved behind `chat_router` and
  become default-deny, so the test demanded that a question reach the internet.

The lesson is the one this file already recorded and then fell for anyway: a
stable failure count everyone stops looking at is how a real regression hides.
The specific trap was the *taxonomy* — "13 core, 14 voice" made 27 feel
understood. Nobody had run them individually.

### Still open from the last audit

**Test the seams, not just the components.** Unchanged and still true. Every
real bug found by driving the live kernel passed unit tests. `test_ingest.py`
and `test_recall_eval.py` are the first two acceptance-shaped tests; the
end-to-end recall demo still has no test that boots the real kernel.

**`--ignore` in `pyproject.toml` is rootdir-relative.** Running pytest from
`backend/` aborts the whole suite on `test_kernel.py`, which is committed
truncated mid-expression (ends at line 18, `SyntaxError: '(' was never
closed`). It is a manual smoke script from early kernel work, not a test.
Delete it or rename it `manual_*.py` — the ignore line is a workaround for a
file nobody wants.

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

### Providers and data policy

**OpenRouter is registered only when `OPENROUTER_API_KEY` is set**, and its
models carry `data_policy=None` — unknown — except the `:free` tier, which is
stated as `LOGGED_AND_TRAINED_ON`. Nothing it returns is
`selectable_by_default`, so Zaram never routes there on its own initiative.

This came out of an audit that proposed registering OpenRouter with
`YOUR_KEY_NO_TRAINING`. That one line would have made every model it returns
auto-selectable, **including the free tier that is free precisely because
prompts are logged** — a privacy guarantee displayed over the opposite
behaviour. `test_openrouter_policy.py` asserts the *absence* of that claim so
it cannot come back quietly.

The asymmetry worth remembering: **we can sometimes prove a model logs; we can
never prove one does not.** Free tier is stated, everything else is None.

**`backend/config.json` is deleted.** Nothing read it — not the backend, not
the frontend, not Electron. It declared `ENABLE_WEB_SEARCH: true` beside a
product whose default is deny, plus model names and a `SYSTEM_PROMPT`
instructing the model to cite web URLs. All inert, all misleading to the next
reader. Web search is gated by `ZARAM_WEB_SEARCH` in the environment, read at
call time by `planner.web_search_enabled()`.

### Open questions

- **How does recall behave as the Spine grows?** The eval runs on five
  documents. The failure mode it exposed — an unrelated document creeping over
  the floor — gets *more* likely with more material, because the maximum
  unrelated score is a maximum over a larger set. A fixed threshold may not
  survive a thousand documents even now that the scoring is honest. Measuring
  that needs the eval run at 10, 100 and 1,000 documents and the margin
  plotted; the harness already prints the number. **This is the argument for a
  reranker**, and the reranker route through Ollama is broken — so the answer
  is probably a cross-encoder loaded directly, which changes the residency
  arithmetic. Do not defer this past M8.
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

## The agreed path to alpha

Decided 7 August 2026, after an audit of what actually stands between here and
a 15-person retention test.

**~~Do these first~~ ✅ → ~~M7~~ ✅ → M8 → M9/M9a → cloud engine + M10 as one
unit → M11 + first run → M12.**

**Next, and it is small: render the ingest outcomes in Knowledge.** M7's service
returns a reason, a remedy and a progress callback per file, and nothing draws
them. Until that lands the failures are recorded rather than loud, which is the
half of M7 that actually protects the user.

**Cut from the alpha path**, not from the product: **M9c** (Unreal/Blender is a
different wedge on a different day, orthogonal to freelancers) and **Session 5**
(CLAUDE.md: build two packs by hand before building the pack system — a
catalogue with no packs is a promise accumulating). Both stay in this file
below; neither is next.

**Local *and* cloud, decided deliberately.** An earlier proposal to make the
alpha local-only was overruled: both capabilities ship. That keeps M10 in
scope and adds one thing that is missing entirely — see below.

**Cloud is not just a provider setting. `OpenAICompatibleEngine` does not
exist.** `runtimes/models/engines/` holds `base_engine.py` and
`ollama_engine.py` and nothing else. The provider layer *discovers*
OpenAI-compatible endpoints and OpenRouter, but nothing can generate through
them, so the v1 scope line "chat routed to at least two providers (one cloud,
one local)" is **not met**. Two local models satisfies the recall demo; it does
not satisfy that line.

**M10 ships in the same commit as the cloud engine, not after it.** Rule 8 is
narrower than it looks: `test_outbound_query_invariant.py` enforces that Spine
content never reaches a *search query*, because recalled facts live in
`system_prompt` and the search path never reads it. But `system_prompt` is
exactly what a generation call sends. Today it only reaches `OllamaEngine` on
localhost, so it is not egress. **The moment a cloud engine exists,
`system_prompt` becomes egress and it contains Spine content by design.**
CLAUDE.md intends that — "carries project context into the cloud request" —
immediately followed by "showing the user exactly what leaves before it does".
So M10 is the enforcement point for the only path that sends memory
off-device, not a dialog bolted on later. Cloud generation without it is rule 5
with the safety removed. It needs a test in the same shape as the existing
invariant: recalled facts reaching a cloud engine must pass the gate *and* the
confirmation, structurally.

**Cloud lands after the wedge, not before it.** M10's dialog shows recalled
facts as removable chips, and that can only be tested honestly against a Spine
with real material in it. Built before M7 and M9, it is built against an empty
store and the interaction problems surface during the alpha.

**Start now, in parallel, because it is not coding work:** Windows code
signing and the Nigerian sole-trader business verification. Longest lead time
of anything here and it cannot be compressed later.

**Worth one afternoon, soon:** actually run the recall demo end to end and
record it — ask model A, ask model B later, get a cited answer, delete the
fact, watch the answer change, open the log. Every piece exists and it has
never been demonstrated. It is the closest-to-done, least-verified asset in the
repo, and a break in it should be found before M7 buries it under new code.

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

### M7 — Ingest ✅
`backend/ingest/` — a parser interface, four light parsers, a measured quality
floor, and an outcome for every file rather than only the ones that worked.

**Verified against a real folder**, not just tests: an invoice indexed and
recalled by a question about its day rate (0.492, cited by filename); an
image-only scan reported as *"2 pages produced only 1 character (0.5 per page).
It is probably a scan with a little text on top"* with the OCR remedy and its
size; an encrypted `.docx` reported as password-protected **without** falsely
offering OCR, since no parser opens those.

**Docling is an optional extra, decided by measurement.** It costs 321 MB of
wheels (torch, opencv, transformers, rapidocr, scipy) against a 267 MB base —
more than doubling the installer that the packaging milestone cut by 81%.
Probed against 1,080 real files: the light parsers read **50 of 54 PDFs**; the
four they cannot are image-only scans. `docling-slim` alone is a mirage — 40 MB
that parses nothing, because every format backend lives in the `standard` extra
that pulls torch.

`PyPDF2` was in `requirements.txt` and imported by nothing; replaced by `pypdf`
(0.4 MB), verified by removal plus a green suite rather than by metadata.

**The quality floor is measured, and the interesting half is where it *isn't*
set.** Zero characters is unambiguous — four files, all image-only scans, no
false positive possible. The band above zero is not: of twelve PDFs under 200
chars/page, those between 98 and 190 are *legitimately sparse* — a pitch deck
at 98.6, a cast sheet at 186.8. A floor at 200 looks reasonable and would tell
a user their own pitch deck was unreadable. The floor is **50 chars/page**, the
only place the two populations separate, and it **warns rather than rejects**:
sparse content is still indexed, because rejecting it would make the floor a
second, quieter way to lose a file.

**Not built:** the Knowledge surface does not yet show any of this. The service
returns per-file outcomes with reasons, remedies and progress callbacks — the
data is there and nothing renders it. That is the next piece, and it is what
makes the failures actually loud rather than merely recorded.

**Failures must be loud.** A file that produced nothing appears in Knowledge
with a reason and a retry, and is mentioned in the conversation the first time
it matters. Silent ingestion failure is the most likely reason a user concludes
the product doesn't know their material and leaves.

**"Extracted almost nothing" is a failure, not a success.** A scanned PDF that
yields three garbled words will silently degrade every answer that touches it,
and it is *worse* than a hard failure because nothing signals it. The quality
floor sits beside the error path: a file that parsed cleanly but produced
almost no text lands in Knowledge with a reason and a retry, exactly like one
that could not be opened. Decide the floor from measurement (characters per
page, or extracted length against file size), not from a guessed constant, and
record how it was chosen.

**Rule 7c: no ingestion path may route documents off-device.** Managed parsing
APIs are prohibited. This is the exact trade the product refuses.

**Build the recall eval harness here** — see "Do these first" item 3. Ingest is
what puts real documents in the Spine, so it is the first moment an eval is
possible and the moment it becomes necessary.

**Acceptance:** point at a folder, watch it index, ask a question, get a cited
answer from a real document. Then point at a folder containing a scanned PDF
and watch Knowledge say which file gave nothing back and why. **Met at the
service level; the Knowledge half is not rendered yet.**

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

### Queued — the citation UI
**Requested 7 August 2026. Not started. Order is fixed and each step stops for
review.**

Read `CLAUDE.md` and `docs/UI-SPEC.md` first. This **adds a section to the
spec, shows it, and only then implements it**.

**The core idea.** Zaram's sources come in three kinds and no competitor has to
make this distinction:

- `memory` — a fact from the Spine. Nothing left the device.
- `document` — a passage from an indexed file. Nothing left the device.
- `web` — bytes left, and there is an egress log entry for it.

The citation UI has to make that visible, because a citation that tells you
whether an answer cost you privacy is the product's thesis at the sentence
level.

**Not everything gets cited.** Web sources are *always* cited regardless of how
central the claim was — not for attribution, but because bytes left the machine
and anything involving egress is always visible. Local sources are cited only
when they carry the answer; the test is whether the claim would be different
without that source. Use a second, higher relevance threshold than the one that
decides injection — the retrieval score already exists, this is a separate cut
on the same number. Division of labour: **chips for what mattered, the recall
strip for what was used, the panel for everything.**

**Inline chips.** Small pill, kind icon and a number: document icon, memory
diamond, globe. **Colour encodes egress, not category** — the same cyan and
violet the orb uses for local versus cloud. Cyan for anything that stayed,
violet for anything that left. One meaning reused, so it needs no legend.
**Never render a chip that isn't clickable**: citing without linking fails the
verification task, and for this product a decorative citation is worse than
none.

**Summary line.** Below the reply, collapsed by default. Leads with the split —
"2 sources · 1 sent to the web" — because that is what someone wants at a
glance. Single-source answers skip the panel entirely and put the card inline;
a panel for one citation is overkill.

**The panel.** Right side, same anchor and pattern as fact detail — one
pattern, not two. Escape closes. Grouped by egress with a mono heading per
group: *nothing left this device* / *1,204 bytes left this device*. Numbering
matches the inline chips exactly so a chip maps to its card instantly.

Per kind:
- **document** — filename, the passage quoted with a left border, page and
  index date, open-document action.
- **memory** — the fact, its source and date, recall count, and correct /
  forget inline. This is the fastest correction path in the product and it sits
  exactly where the user is already checking.
- **web** — title, excerpt, domain, when it was sent and to whom, and a link to
  its row in Activity. **That link is the citation and the egress log being the
  same object viewed twice, and it is the thing nobody else can build.**

Below the cited sources, a quieter section listing what was recalled but not
cited — so nothing is hidden, it is just not interrupting the prose.

**The empty state is not optional.** When nothing from the user's material
contributed, say so: *"Answered from the model's own knowledge — nothing from
your files."* It is a claim about absence, which the user cannot infer from
missing chips — missing chips could equally mean we didn't bother. A visible
no-sources state is more trustworthy than confident prose with hidden
provenance.

**Backend first.** Check whether `StreamEvent.source` already carries kind,
excerpt and egress reference. It currently carries only `kind`, `url`, `title`
— so this is the first change. The frontend cannot render what isn't sent, and
inventing a kind client-side would be the fabrication rule all over again.

**Order — stop after each:**
1. Write the spec section, stop, show it
2. Backend: source events carry kind, excerpt, egress reference, relevance score
3. Chips and the summary line
4. The panel
5. The empty state

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

**Nothing.** 1263 tests, 0 failures, ~2m from the repo root on a full dev
install. The 27 are gone and the section explaining what they actually were is
above, under "What the 27 actually were".

Record any change to that number — but the sharper lesson from clearing them is
about *taxonomy*, not counting. "13 core, 14 voice" made 27 feel understood and
that is why nobody ran them individually for four milestones. A failure grouped
under a plausible label is more dangerous than an unexplained one.

Two of the new tests need a live dependency and skip loudly without it:
`test_recall_eval.py` needs Ollama with `bge-m3` on loopback, because
similarity over the hash fallback is arbitrary rather than merely worse and a
green run against it would be a lie.

Still broken, found and not fixed:

- `services/speech_manager.py` imports a module that was deleted. Nothing
  imports `SpeechManager`, so nothing breaks today.
- `backend/test_kernel.py` is committed truncated mid-expression and is only
  survivable because `pyproject.toml` ignores it by path. See "Still open from
  the last audit".
- `bge-reranker-v2-m3` crashes llama-server through Ollama. See "What the
  recall eval found".
