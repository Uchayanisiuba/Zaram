# Zaram — Milestones

Ordered. Each has an acceptance criterion phrased as something you can *see*, not
something that passes. "Tests green" is not done; "I ran it and watched X happen" is.

Read with `CLAUDE.md` (the contract) and `docs/UI-SPEC.md` (the interface).

---

## Done

### M0 — Recall loop ✅
Spine on SQLite with `bge-m3` embeddings. Facts stored, retrieved, injected with
citation markers, provenance events emitted.

**Verified:** a fact stored by `gemma3` in one session was recalled correctly by
`llama3.2` in a separate session, with provenance. No model could have known it.

### M1 — Egress log ✅
Append-only hash-chained log in its own database. Per-host policy, default deny.
All outbound calls routed through one gate. `test_egress_chokepoint.py` fails the
build on any direct HTTP call outside `core/egress/`.

**Verified:** the guard catches a reintroduced direct call and a stale exemption.

### M2 — Provider layer ✅
`backend/providers/` connected, renamed from `garage/`. Model metadata carries a
data policy with no default value — unknown is `None`, never a guarantee.
`select_default_model()` refuses rather than choosing something unlabelled.

**Verified:** booted against real Ollama, 10 models discovered and labelled,
default selected, `ModelsRuntime` reports it.

### M3 — Frontend integration ✅ (built, unverified)
`chatClient.ts` does `POST /chat`, parses NDJSON, handles JSON split across chunks
and multi-byte characters split mid-character. `ChatSurface` renders sources live
and settled. `SourcePanel` exists. `memoryClient` and `egressClient` wired.

**Not yet verified by running it.** That is M4.

---

## Next

### M4 — Verify the integration
Not build — verify. Run the UI against a live backend and report findings.

**Acceptance:** a screen recording or a written walkthrough showing: ask a question,
see a cited answer, click a citation, open the source, correct a fact, watch the
answer change, open Activity and see what left.

**Report specifically on:** how stream events arrive and parse, what happens when the
backend is unreachable, what happens on an error mid-stream, and whether stop
actually aborts the request rather than hiding the stream.

### M5 — VRAM detection
`_vram_bytes()` reads only through `torch.cuda`, so on this machine VRAM is unknown,
the residency budget is `None`, and the fit gate is skipped. The unit tests pin a
fake profile, so they pass while the real path stays inert.

**Acceptance:** on the dev machine, `select_default_model()` refuses a 9GB model
when a smaller one fits, and the log says why. Non-CUDA paths still report
`unknown`, never a false number.

### M6 — Shell cleanup
19 frontend surfaces exist; most are retired names — Agent, Browser, Build, Code,
Calendar, Project, Research, ImageGeneration. That is the six-workspace shell against
a four-item spec.

**Acceptance:** the rail renders Work · Memory · Knowledge · Activity plus Settings.
Everything else moved to `legacy/`, unlinked, bundle size drops.

### M7 — Ingest
The one v1 scope item with nothing built. Docling for parsing. Folder in, facts out.

**Acceptance:** point Zaram at a real messy folder — scanned PDFs, .docx, .xlsx —
and ask a question answered from it, with a citation to the right file.

**Failures must be loud.** A file that produced nothing appears in Knowledge with a
reason and a retry, and is mentioned in the conversation the first time it matters:
*"I couldn't read scan-04.pdf — it's an image with no text layer."* Silent ingestion
failure is the most likely reason a user concludes the product doesn't know their
material and leaves.

### M8 — Memory scope
Every fact carries `global` or `project:<id>`. Default to current project. Promote to
global on evidence — a fact recalled across three projects prompts once.

**Acceptance:** two projects exist; a fact from one does not surface in the other;
a global preference surfaces in both; the Memory filter shows
*This project · All projects · About me*.

**Do this before the alpha.** Retrofitting scope onto facts that lack it means
guessing at scope for everything already stored. It is also the multiplayer boundary,
so the permission model comes free.

### M9 — Generative documents and the Work surface
HTML is the source of truth. Generate HTML, convert: WeasyPrint to PDF, second export
to .docx. python-docx, openpyxl, matplotlib, Mermaid.

Generated files go to a dedicated output directory. The write path has **no delete or
overwrite capability at all** — a name collision increments or asks. Safety is
structural, not promised.

**Acceptance:** ask a question, say "write that up as a proposal", get a .docx where
claims link back to the source paragraph they came from. The file appears as a card in
the conversation and in Work, with the conversation that produced it.

### M10 — Confirm-before-send, editable
The dialog shows the literal outbound text, the destination and the reason. Recalled
facts are removable chips, editable inline, with edits written through as
supersessions. The user can add context retrieval missed. The outbound text updates
live as they edit.

**Acceptance:** trigger a cloud call, see exactly what will leave, correct a wrong
fact in the dialog, watch the outbound text change, send, and find the correction
persisted in Memory afterwards.

This is a learning mechanism as much as a safety control — it is the one moment where
correcting a fact has an immediate payoff, which is why it is where the Spine actually
becomes accurate.

### M11 — Packaging
**The real blocker.** A stranger cannot install this. Every feature added before this
widens the gap between what the product does and what anyone can experience.
`electron-builder.yml` exists — check its state before assuming greenfield.

**Acceptance:** a Windows machine that has never seen the repo runs one installer and
reaches a cited answer from its own files in under ten minutes. Detect existing Ollama
models rather than asking for a download. Never block on a 7GB pull.

### M12 — Alpha
Ten programmers, one segment. Onboard individually, watch them use it, do not help.

**Acceptance:** the day-30 number. 5+ of 15 still using it weekly — build the paid
tier. 2–4 — the job is wrong, interview those users. 0–1 — the thesis is wrong,
learned in six weeks rather than two years.

Closing question, instead of "would you pay for this":
**"If I turned this off tomorrow, what would you do?"**

---

## After the alpha

Unreal read-only inspection. Then scoped Unreal writes with dry-run and undo. Then
Blender. Then the document editor (TipTap over HTML) and Univer for sheets and slides.
Then the pack abstraction — extracted from two hand-built packs, never designed ahead
of them.

Web search returns only after per-source consent exists. Sequence is fixed: egress log
→ per-source policy → search as its first governed source.

---

## Known broken

27 failing tests, unchanged and pre-existing: 13 in `test_streaming_conversation`,
`test_alpha10c_acceptance`, `test_kernel_flow`; 14 in voice. Voice is out of scope.
Record any change to that number — a stable failure count everyone stops looking at is
how a real regression hides.
