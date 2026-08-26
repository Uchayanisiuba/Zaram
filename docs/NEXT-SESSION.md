# Next session — start here

A prompt and a state snapshot. Rewritten 26 August 2026 at the end of the
attachments, images and desktop-launch session.

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
>   committed.** `git log --oneline -8` is the list.
> - Nothing is running. Ollama may or may not be up — check, because it
>   changes what the suite executes and how long it takes.
>
> How this repository fails, so you can recognise it:
>
> - **Nineteen** complete, tested, unreachable subsystems have been found. The
>   nineteenth was `/vision/analyze`: a finished streaming endpoint, called by
>   nothing, hardcoding a model that is not installed. **Assume unreachable
>   until you have seen the caller.**
> - A green suite has meant nothing on at least seven occasions. Before you
>   trust a new test, disable the thing it tests and watch it go red — and then
>   read *which* tests survived. Five of mine passed with the feature disabled
>   this session, across two separate mutation runs.
> - Verify against the code, not the documentation. **`CLAUDE.md` is currently
>   wrong about the modality gate** — it says nothing gates, and the gate has
>   been in `select_model_for_task` for some time. When the two disagree the
>   code wins, and say so.
> - Say which environment you measured in, and **check the GPU before trusting
>   any timing**. See the VRAM note below; it is the likeliest explanation for
>   the long-standing suite-timing mystery.
>
> Environment specifics that have each cost time:
>
> - Python is `backend/venv/Scripts/python.exe`. There are two other
>   interpreters here and both have been launched by accident; a bare `python`
>   on PATH is broken.
> - Run tests from `backend/`. Scripts outside it need
>   `PYTHONPATH=C:/Zaram/backend`, and `PYTHONIOENCODING=utf-8` or printing a
>   document will die on cp1252.
> - `curl http://127.0.0.1:8420/health` returning **401** is success. The auth
>   header is `X-Zaram-Auth`, not `X-Zaram-Client`, which is enforced nowhere.
> - **`gh` is not installed.**
> - **Do not read a command's exit code through a pipe.**
> - **Bash heredocs mangle escape sequences.** `\x89PNG` and `\u2014` both came
>   out wrong this session and cost two rounds each. Write the patch to a file
>   with the Write tool and run it with Python. This is in the handoff for the
>   third time; believe it.
>
> Start on item 1 under "What to do next" unless I say otherwise. Before
> reporting anything as working, run it and watch it happen.

---

## Read this before you install or launch anything

`docs/RUNNING.md` is the full version. **The launch bugs it documented are
fixed as of this session** — see MILESTONES — but the two structural traps
remain:

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

**A cold boot takes ~2.5 minutes and that is expected now.** The launcher waits
240s and logs its state transitions, so `desktop.log` will say
`Backend state: starting` → `available` → `Loading renderer`. If you see
`error.html` instead, read the log rather than guessing — that is what it is
for now.

**Electron mints the API secret per launch and never exposes it.** To drive the
backend by hand instead, run it yourself with a known secret:

```bash
cd backend && ZARAM_API_SECRET=dev-secret ZARAM_DATA_DIR=/some/scratch venv/Scripts/python.exe main.py
```

```bash
curl -s -H 'X-Zaram-Auth: dev-secret' http://127.0.0.1:8420/chat/attachments?session_id=probe
```

Use `ZARAM_DATA_DIR` for anything that writes. It is what keeps a test run away
from the real Spine — and note that without it `data_dir()` resolves to
`C:\Zaram\backend`, which is correct and is also how a module this session
deleted its own source directory.

---

## The VRAM finding, which may explain the suite-timing mystery

**An ordinary Windows desktop holds ~8.8 GB of this 12 GB card.** Measured with
`nvidia-smi --query-compute-apps` on 26 August: Explorer, Edge, WebView2,
WhatsApp, PhoneExperienceHost, SearchHost and the start menu, with **no model
loaded at all**.

That leaves ~3.4 GB. `gemma4:12b` needs 7.5 GB, so it **spills to CPU** —
measured at 1.8 GB of 8.95 GB resident, with the rest on the processor. Any
test that performs a real inference then runs at CPU speed.

The backend suite hung at 51% twice in that state and completed in **4:51**
once the model was unloaded and the card was quieter. CLAUDE.md records an
unexplained 2:53-versus-20:46 split and blames provider-probe timeouts. **This
is a better candidate**, and it is cheap to check: read `nvidia-smi` before
quoting a duration.

Two consequences worth thinking about:

* The **30.3 tok/s "fully resident"** figure for `gemma4:12b` was measured on a
  quiet machine. On a working desktop it is not resident and the number does
  not hold.
* `ProviderManager.resident_budget_bytes` subtracts the embedder and a KV
  reserve from *total* VRAM. It does not subtract the desktop, and on this
  machine the desktop is the largest single consumer. The residency gate is
  therefore optimistic by several gigabytes in exactly the case that matters.

---

## What is uncommitted right now

**Nothing.** The tree is clean.

---

## Decisions taken this session

* **Attachments are working state, never the Spine (rule 7d).** A file dropped
  into a conversation is parsed, used, and *offered* — `Keep` adds it to
  Knowledge, and nothing does so on the user's behalf.
* **Chips persist across messages.** An attached file belongs to the
  conversation, not to one message. The backend scopes attachments by session
  for exactly this.
* **The reply always says how much of a file it read**, including when it read
  all of it. A disclosure that appears only on the lossy path teaches the user
  that silence means "all of it".
* **Images are a separate kind, not a document with no text.** They never enter
  the prompt block, never spend the character budget, and are never excerpted.
* **An image is refused rather than sent to a cloud provider.** Rule 7j: a chat
  message is ~2 KB and a photograph is megabytes of something far more
  personal, and connecting a provider for text is not consent to send it one.
  Refused rather than stripped, because an answer built with the picture
  quietly removed is the same failure the local gate exists to stop.
* **A capability check must never turn "unmeasured" into a claim.** The vision
  check read an unscanned catalogue and told the user their machine could not
  read images. Every uncertainty now proceeds; only "models were found and none
  can see" refuses.
* **The model installer will follow LM Studio's experience.** The maintainer
  asked for this directly on 26 August, having heard the argument against
  copying the browser. It is their call and it is now the brief. See item 2.
* **`qwen3.8:27b` earns nothing and should be deleted.** Identical capability
  list to `gemma4:12b` (completion, vision, tools, thinking), 17 GB against
  7.6 GB, 1.85 tok/s against 30.3. The registry has no lighter build — all 12
  tags are 27B and the smallest is the q4_K_M already installed. Not deleted,
  because that is the maintainer's 17 GB to remove.

---

## What to do next

1. **The recall disclosure — item 4 of the LM Studio list, and the last piece
   of it.** Attachments already say what was read; recall does not.
   `ExecutionEngine.MAX_RECALL = 6` keeps the six most relevant facts *above
   the floor* and silently drops the rest, so an answer can be missing
   something the Spine holds with nothing said. **Disclose only when facts were
   actually dropped** — `len(above_floor) > MAX_RECALL` — which is rule 7h's
   moment of doubt. A notice on every message is the tax that rule forbids, and
   it is a different case from attachments, where the user just handed over a
   file and is owed an account of it. Emit it as a `notice` event with a new
   `kind`; `NoticeCard` needs a tone for it or it draws an amber warning
   triangle over something routine.

2. **The model installer, with the LM Studio experience.** The maintainer has
   asked for this specifically. **Settle the scope with them first** — search
   and browse, download progress, compatibility badges, or all three — because
   that is the difference between an afternoon and a week.
   What exists: hardware detection, `resident_budget_bytes`, `ModelInfo`,
   discovery across Ollama and LM Studio, and `providers/catalogue.py` as a
   working template for a dated, honestly-graded local manifest.
   What does not: **the VRAM-tiered model manifest CLAUDE.md specifies does not
   exist** — `vram_tier` and `recommended_models` appear nowhere, and
   `model_catalog.py` only stores models discovery already found. And there is
   **no pull path at all**; `/api/pull` appears nowhere outside the venv.
   The thing only Zaram can say: *"7.6 GB, fits your card, about 30 words a
   second"* beside *"17 GB, does not fit, about one word a second"* — graded
   against measured hardware rather than a spec sheet. Read the VRAM note
   above first: the honest number must subtract the desktop.
   Constraints: never block on a download, state the size before the click,
   log the pull like any other egress, and keep filenames and quant suffixes
   out of the primary path.

3. **The FTS5 work, step 1.** Unchanged and still queued. Membership is the
   union of each retriever's top-K, ordering is RRF, citation stays on measured
   relevance. **The delete path is the part that matters** — rule 4 promises
   that correcting a fact changes the answers, and a lexical index not kept in
   sync breaks that silently.

4. **Settle whether `qwen2.5-coder:14b` earns its swap.** `INTENT_SPECIALISATION`
   maps exactly one intent, so that entry is the only thing that can trigger a
   model swap. Needs three real coding questions judged by a human.

5. **Make `_rank_key` ask the question its docstring claims** — a residency term
   read from `/api/ps`, as a preference and never a gate. The VRAM finding
   above makes this worth more than it looked: a model that "fits" on paper is
   spilling to CPU in practice.

6. **The markdown preamble case.** A model that opens with "Sure! Here's the
   statement of work:" leaves a stray paragraph. Small, and the last known
   model-variance gap.

7. **Document kinds** — proposal, report, meeting notes, letter, CV. Presets
   over structure that already exists.

8. **Conversation persistence, as the session/memory split.** Still no history.
   Guardrail, enforced by test: readable by the user, invisible to recall
   (rule 7d). **Chat organisation waits on this** — folders for conversations
   that vanish on restart organise nothing.

9. **`KPipeline.load_voice` is an ungated download.** Fetches a `.pt` at
   synthesis time with nothing asked and nothing logged. Rules 3 and 7g.

10. **Delete `backend/orchestrator/`.** 1,261 lines, no importers, no tests, and
    it contains the membership-versus-ranking bug ready to be revived —
    `scoring.py` records a *missing required capability* as a warning and ranks
    the candidate anyway, which is the modality gate inverted. Pure subtraction.

11. **Reconcile the two Electron trees and the two venvs.** Triage nobody has
    done, invisible to every guard because each side is internally consistent.

12. **Rebuild the installer and run it on a machine that has never seen this
    repo.** Still the actual blocker.

---

## Open questions for the maintainer

* **Does `Return` send a message?** It did not fire in a Playwright-driven test
  and the button was used instead. Not investigated, so it may be an artefact
  of synthetic key events — but if it is real it is an obvious daily
  irritation. Ten minutes to check by hand.
* **Should `conversation`-type memories be in `knowledge.search` results at
  all?** Unchanged. They are labelled honestly now, but labelling is not the
  same as deciding they belong.
* **Is `qwen3.8:27b` worth keeping installed?** Answered by measurement this
  session: no unique capability, sixteen times slower, 17 GB. The deletion is
  the maintainer's to run.
* **The suite timing.** See the VRAM note. This is the first concrete
  candidate; confirming it is an hour's work and would settle a question every
  measurement in this repository depends on.
* **`test_an_engine_failure_becomes_an_error_event_and_still_terminates` is
  flaky.** Fails under load, passes alone. The log shows the error *was* caught
  and printed, so the event races the consumer's completion — a real defect in
  the legacy `ConversationManager` path, not a test bug.
* **`en_core_web_sm` in the base install.** Unchanged and still open.
* **Should Zaram expose an MCP server?** Unchanged.

---

## What this session learned about the instruments

**A recursive delete rooted at a configured path has a blast radius somebody
else chooses.** `AttachmentStore` swept its scratch directory with
`shutil.rmtree`, `data_dir()` resolves to `C:\Zaram\backend` in a checkout, the
directory was called `attachments` — and importing `main.py` deleted the
package's own source. The rename to `chat-attachments` stops that route; the
real fix is that the sweep now unlinks only files it created and never removes
a directory.

**A swallowed exception is worse than a crash, and a launcher that logs no
state transitions cannot be debugged.** `broadcastViewport` was declared inside
`if (loadedDesktop && desktopRuntime)` and called outside it, so every backend
status change threw `ReferenceError` into a bare `catch (_) {}`. It was found
only after adding the logging that should always have been there.

**Check the GPU before trusting a timing.** Two suite hangs, both VRAM.

**A test fixture that stops exercising its branch is how a test starts proving
nothing.** A 40-clause fixture fitted inside the budget, so two tests asserting
the excerpt path were grading the full one. The fixture now asserts its own
size before the tests that depend on it.

**Two sources of truth for one fact, in the file whose purpose is that there be
one.** `test_llm_engine_contract` hardcoded `CANONICAL_PARAMETERS` beside an
assertion message naming `base_engine.LLMEngine` as the authority. Adding a
parameter to the protocol and to every implementation failed all four engines
against a contract they satisfied. It now reads the protocol.

**Mutation testing found five assertion-free tests across two runs**, including
one where the id under test was also `attachments[0]`, so the assertion held
however the component behaved. Counting failures is not enough — read *which*
tests survived.
