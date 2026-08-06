# Zaram — Milestones

Ordered. Each has an acceptance criterion phrased as something you can *see*, not
something that passes. "Tests green" is not done; "I ran it and watched X happen" is.

Read with `CLAUDE.md` (the contract) and `docs/UI-SPEC.md` (the interface).

**This file is the handoff.** A new session should be able to read it and know
where the work stands without being told. Keep the Current state block below
accurate — it is the first thing anyone reads.

---

## Current state — 6 August 2026

**Suite:** 1033 collected · 1006 passed · **27 failed** on a full dev install.
On a base install (no voice extra): 951 passed · **13 failed** · 52 skipped, in
~20s. The 27 are pre-existing and listed under Known broken.

**Base install: 267 MB.** Down from 1,436 MB. Voice is an optional 905 MB extra.

**In flight: M9b, first half committed.** `backend/artifacts/` has the model, the
write path and the HTML layer. Exporters are not written — see the milestone.

**Last commits:** artifacts write path → Work surface → dependency removals →
packaging split → VRAM detection → shell/orbit work.

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

### Open questions

- **Dev tooling still ships in the base install** — mypy, ruff, pytest,
  pip-licenses, wheel. Probably 30–40 MB. Same split-verify-measure method as
  the voice extra. Belongs in the packaging spike.
- **WeasyPrint on Windows needs native GTK libraries**, which is a packaging
  decision rather than a `pip install`. Blocks PDF export. openpyxl and
  matplotlib are simply not installed yet.
- **Code signing** is the long-lead packaging item. Windows business
  verification as a Nigerian sole trader needs investigating now, in parallel.
  Unsigned costs Zaram more than a typical app: SmartScreen's warning appears on
  a product whose entire claim is trustworthiness.
- **Routing is keyword-based, not embedding-based.** CLAUDE.md specifies
  embeddings. It degrades on phrasing rather than meaning.
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

---

## Next

### M9b — Generative documents (in flight)
**Committed:** the artifact model, the write path, the HTML layer.

The write path is a property of the code, not a convention: `open(path, "xb")`
is create-or-fail atomically, there is no function named for deletion, and
`test_artifact_write_path.py` scans the module's source so the build fails on the
commit that introduces the capability rather than at runtime after a file is
gone. Path confinement gets eight traversal payloads — the *model* proposes
filenames, so `../../.ssh/config` is an input to assume.

**Remaining:** the exporters. python-docx and jinja2 are installed; openpyxl,
matplotlib and WeasyPrint are not, and WeasyPrint needs native GTK on Windows.

**Acceptance:** ask a question, say "write that up as a proposal", get a .docx
where claims link back to the source paragraph they came from. The file appears
as a card in the conversation and as a row in Work.

### Session 4 — Wire Work to real artifacts
Replace `frontend/src/data/sampleArtifacts.ts` with real records. The `Artifact`
shape there is a first draft of the backend model; divergence is a bug in the
sample. Delete the sample module in the same commit.

**Acceptance:** generate something and find it in both the conversation and Work.

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
