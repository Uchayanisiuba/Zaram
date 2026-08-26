# Next session — start here

A prompt and a state snapshot. Rewritten 26 August 2026 at the end of the
documents, search-labelling and obligations session.

**This file is a pointer, not a second handoff.** `docs/MILESTONES.md` Current
state is the handoff and stays the authority on status; `CLAUDE.md` stays the
authority on rules. If this file disagrees with either, they win and this file
is stale — say so and fix it.

---

## The prompt

Paste this into a new session:

> Read `CLAUDE.md`, then `docs/MILESTONES.md` Current state — 26 August — then
> this file. For anything touching voice read `docs/SPEECH.md`; before
> launching the app read `docs/RUNNING.md`, which has four failure modes that
> each look like something else.
>
> State you are inheriting:
>
> - Branch `Zaram-V0.1`. **The working tree is clean and everything is
>   committed.** Ten commits landed on 26 August; `git log --oneline -10` is
>   the list.
> - Nothing is running. Ollama may or may not be up — check, because it
>   changes what the suite executes and how long it takes.
>
> How this repository fails, so you can recognise it:
>
> - **Eighteen** complete, tested, unreachable subsystems have been found. The
>   seventeenth was bitemporal memory: the field is written, persisted and
>   exported, and `valid_time.py` — which queries it — is imported by nothing
>   but its own test. The eighteenth was obligation extraction, wired this
>   session. **Assume unreachable until you have seen the caller.**
> - A green suite has meant nothing on at least seven occasions. Before you
>   trust a new test, disable the thing it tests and watch it go red — and then
>   read *which* tests survived. Three of mine passed with the feature disabled
>   because they iterated an empty list and asserted nothing.
> - Verify against the code, not the documentation. When the two disagree the
>   code wins, and say so.
> - Say which environment you measured in. The backend suite has taken 2:53 and
>   20:43 on this machine with Ollama up in both cases, unexplained.
>
> Environment specifics that have each cost time:
>
> - Python is `backend/venv/Scripts/python.exe`. There are two other
>   interpreters here and both have been launched by accident; a bare `python`
>   on PATH is broken and reports a missing install path.
> - Run tests from `backend/`. Scripts outside it need
>   `PYTHONPATH=C:/Zaram/backend`, and `PYTHONIOENCODING=utf-8` or printing a
>   document will die on cp1252.
> - `curl http://127.0.0.1:8420/health` returning **401** is success. The auth
>   header is `X-Zaram-Auth`, not `X-Zaram-Client`, which is a label enforced
>   nowhere.
> - **`gh` is not installed**, so anything needing the GitHub CLI must be
>   handed back rather than attempted.
> - **Do not read a command's exit code through a pipe.**
> - Bash heredocs choke on document content containing backticks and
>   apostrophes. Write the file with the Write tool and splice it in with a
>   short Python script instead of fighting the quoting.
>
> Start on item 1 under "What to do next" unless I say otherwise. Before
> reporting anything as working, run it and watch it happen.

---

## Read this before you install or launch anything

`docs/RUNNING.md` is the full version. The two that bite hardest:

**There are two virtualenvs and two Electron trees.** Both pairs are internally
consistent, so no guard sees either.

| | ships / working | the other one |
|---|---|---|
| Python | `backend/venv` | `C:\Zaram\.venv` — also complete |
| Electron | `electron/main.js` | `desktop/src/main/index.ts` |

Launch, from the repo root, with Vite already listening on 5173:

```bash
env -u ELECTRON_RUN_AS_NODE ZARAM_PYTHON="C:/Zaram/backend/venv/Scripts/python.exe" node_modules/.bin/electron electron/main.js
```

`ELECTRON_RUN_AS_NODE` must be **deleted, never blanked**; Electron tests for
its presence.

To drive the backend directly instead — which is how the search and obligation
work was verified — start it with a known secret and call it with that header:

```bash
cd backend && ZARAM_API_SECRET=dev-secret venv/Scripts/python.exe main.py
```

```bash
curl -s -H 'X-Zaram-Auth: dev-secret' http://127.0.0.1:8420/obligations
```

---

## What is uncommitted right now

**Nothing.** The tree is clean.

---

## Decisions taken this session

* **Documents are structured, and markdown is the input form.** `Heading`,
  `BulletList`, `TableBlock`, `PageBreak`, `RichText` in
  `artifacts/contracts.py`; `artifacts/markdown_blocks.py` converts. `str` and
  `Claim` are unchanged, so every older caller works untouched.
* **Model variance is absorbed by the adapter, not by requiring a better
  model.** A format contract in the prompt removes most of it; the adapter
  handles the rest. Documents do **not** need cloud models — that was never a
  capability failure.
* **The licence file exists**: source-available, all rights reserved.
* **`origin_of` defaults to *local record*, never *web*.** Calling a web page a
  local record understates a source; the reverse is a false claim of
  provenance, which is rule 2.
* **Do not repeat the bitemporality claim** until something calls
  `in_force_at`. See MILESTONES, the seventeenth.
* **"Comparable to state of the art" is unsupported in either direction** and
  should not be claimed. The LoCoMo/LongMemEval benchmark CLAUDE.md asks for
  has never been run.

---

## What to do next

1. **Give obligations a surface.** The backend is done — extracted on ingest,
   stored, correctable, and reachable over HTTP — and **nothing on screen shows
   any of it**, which is the same "reachable only from Python" state the
   package was in yesterday, moved one layer up. `GET /obligations` returns the
   commitments and the open questions together; both need showing. CLAUDE.md's
   constraint is the design brief: *Zaram surfaces obligations in context and
   drafts the response — it is not a calendar and must not become one.* Every
   obligation shows its source clause and is correctable; **never silently
   create a commitment.**

2. **Wire `in_force_at` into recall — the seventeenth.**
   `runtimes/memory/valid_time.py` implements `in_force_at`, `history_of` and
   `explain` over the bitemporal fields and is imported by exactly one file:
   its own test. The field is written, persisted and exported; nothing filters
   recall by it. So Zaram can store that the day rate was £500 until June and
   £600 after, and cannot answer "what was it in May" through any live path.
   Small, and it makes a real claim true — it is the axis that distinguishes
   this memory from Mem0's.

3. **The FTS5 work, step 1.** Step 0 is done and the corpus is now trustworthy.
   The design constraint is the whole job: **membership** is the union of each
   retriever's top-K, **ordering** is RRF (`Σ 1/(k + rank)`, fused by rank
   position so no blended magnitude exists to compare against a cosine floor),
   and **citation** stays on measured relevance, untouched. The deleted
   `_hybrid` did `vector*0.7 + bm25*0.3` and truncated on the blend; doing that
   again by a new route is the thing to avoid. **The delete path is the part
   that matters** — rule 4 promises that correcting a fact changes the answers,
   and a lexical index not kept in sync breaks that silently.

4. **Settle whether `qwen2.5-coder:14b` earns its swap.** `INTENT_SPECIALISATION`
   maps exactly one intent — `CODE` — and that single entry is the only thing
   that can trigger a model swap. Measured: qwen2.5-coder 10.8 tok/s against
   gemma4 30.3, and they cannot be co-resident in ~9.1 GB. Deleting the mapping
   would remove every swap in the product. Needs three real coding questions
   judged by a human.

5. **Make `_rank_key` ask the question its docstring claims.** It orders on
   `model_fits_resident`, which is `size_bytes <= budget` — a static capacity
   check with no reference to what Ollama has loaded *right now*. Add a
   residency term read from `/api/ps`, as a **preference and never a gate**, so
   a required capability still wins.

6. **The markdown preamble case.** A model that opens with "Sure! Here's the
   statement of work:" leaves a stray paragraph. The last known model-variance
   gap; small.

7. **Document kinds** — proposal, report, meeting notes, letter, CV. Now just
   presets over structure that exists, and what actually delivers "the most
   popular docs people create with AI".

8. **Conversation persistence, as the session/memory split.** There is still no
   history — close Zaram and yesterday is gone. Guardrail, enforced by test:
   readable by the user, invisible to recall (rule 7d).

9. **`KPipeline.load_voice` is an ungated download.** It fetches a `.pt` at
   synthesis time with nothing asked and nothing logged. The ONNX path routes
   the same fetch through the gate; the torch path still does not. Rules 3
   and 7g.

10. **Delete `backend/orchestrator/`.** 1,261 lines, no importers, no tests,
    and it contains the membership-versus-ranking bug ready to be revived.
    Pure subtraction.

11. **Reconcile the two Electron trees and the two venvs.** Triage nobody has
    done, invisible to every guard because each side is internally consistent.

12. **Rebuild the installer and run it on a machine that has never seen this
    repo.** Still the actual blocker.

---

## Open questions for the maintainer

* **Should `conversation`-type memories be in `knowledge.search` results at
  all?** They are now labelled honestly — the model is told which sources are
  the user's own past remarks rather than research — but labelling is not the
  same as deciding they belong. Rule 7d says conversation is ephemeral and
  entering the Spine is a decision the system makes. Five of six sources on a
  live news question were local records, three of them near-duplicates of one
  another.
* **Is `qwen3.8:27b` worth keeping installed?** 17 GB on disk, 18.7 GB loaded
  against 12 GB of VRAM, 1.85 tok/s, 95.6 s cold load. It is background-tier by
  measurement, and nothing currently routes to it.
* **The suite timing.** 2:53 and 20:43 on the same machine, Ollama up in both,
  no stale backend. CLAUDE.md blames provider-probe timeouts for the
  4-versus-20 split; that is where to look, and it is worth an hour because
  every measurement in this repository is quoted with a condition that assumes
  it is stable.
* **`en_core_web_sm` in the base install.** Unchanged and still open. misaki
  downloads it at runtime when absent — unlogged and ungated.
* **Should Zaram expose an MCP server?** Read-only `recall`, `search_spine`,
  `get_provenance` would let Claude Code, Cursor and Cline read from the Spine.
  Prerequisite — the API secret — now exists.

---

## What this session learned about the instruments

**A test can pass by asserting nothing, and disabling the feature is how you
find out.** Three obligation tests iterated `store.open_obligations()` and
asserted per item. With the ingest seam disabled they iterated an empty list
and passed. Disabling the feature and reading *which tests survived* — not just
counting the failures — is what caught it.

**Wiring a subsystem up is how its defects are found.** The obligation
extractor had 28 green tests and could not read the commonest clause on an
invoice — the exact sentence the repo's own eval corpus uses. Nothing short of
running it against a real file would have shown that.

**Run the real model, not a fixture.** `qwen2.5-coder` wraps every answer in a
fenced block and `gemma4` never does. One line of difference collapsed a whole
document into a single code block, and no hand-written test markdown would have
produced it.

**Check the instrument before reading its output — including the half nobody
wrote.** The recall corpus guard asserted distractors do not *answer* the
questions and never asserted they are *near* them. The most product-specific
question in the eval was being graded against a corpus containing nothing like
its target, and passing.
