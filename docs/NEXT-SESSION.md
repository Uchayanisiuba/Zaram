# Next session — start here

A prompt and a state snapshot. Written 19 August 2026 at the end of the model
routing, web search and packaging session.

**This file is a pointer, not a second handoff.** `docs/MILESTONES.md` Current
state is the handoff and stays the authority on status; `CLAUDE.md` stays the
authority on rules. If this file disagrees with either, they win and this file
is stale — say so and fix it.

---

## The prompt

Paste this into a new session:

> Read `CLAUDE.md`, then `docs/MILESTONES.md` Current state, then
> `docs/NEXT-SESSION.md`. For anything touching voice read `docs/SPEECH.md`;
> before launching the app read `docs/RUNNING.md`, which has four failure modes
> that each look like something else.
>
> State you are inheriting:
>
> - Five commits are pushed on branch `Zaram-V0.1` (PR #2, open, base `main`).
> - Three logical commits sit uncommitted in the working tree: a web search
>   fix, a rewritten README, and the two handoff documents. The files for each
>   are listed below.
> - Zaram may still be running from the previous session. It holds port 8420
>   and a single-instance lock, and a stale instance will not have rescanned
>   models.
>
> How this repository fails, so you can recognise it:
>
> - **Sixteen** complete, tested, unreachable subsystems have been found. The
>   sixteenth was web search: every layer reported success and the results were
>   discarded in the seam between two steps. Assume unreachable until you have
>   seen the caller.
> - A green suite has meant nothing on at least six occasions. Before you trust
>   a new test, disable the thing it tests and watch it go red.
> - Verify against the code, not the documentation. When the two disagree the
>   code wins, and say so. The README was understating a shipped feature this
>   week; a status page that understates is the same defect as one that
>   overstates.
> - Say which environment you measured in. The backend suite takes ~4 minutes
>   with Ollama up and ~20 with it down, and it executes different code.
>
> Environment specifics that have each cost time:
>
> - Python is `backend/venv/Scripts/python.exe`. There are two other
>   interpreters on this machine and both have been launched by accident.
> - Launch with the command below, Vite on 5173 first. Delete
>   `ELECTRON_RUN_AS_NODE`, never blank it.
> - `curl http://127.0.0.1:8420/health` returning **401** is success.
> - **`gh` is not installed**, so anything needing the GitHub CLI must be
>   handed back rather than attempted.
> - **Do not read a command's exit code through a pipe.** `ollama pull … | tail`
>   reported success for a pull that had failed, and it was believed.
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

A third Python appeared this session: the instance running before the restart
had been launched with `AppData\Local\Programs\Python\Python311\python.exe`,
i.e. with `ZARAM_PYTHON` unset. Set it.

Launch, from the repo root, with Vite already listening on 5173:

```bash
env -u ELECTRON_RUN_AS_NODE \
    ZARAM_PYTHON="C:/Zaram/backend/venv/Scripts/python.exe" \
    node_modules/.bin/electron electron/main.js
```

Success looks like `curl http://127.0.0.1:8420/health` returning **401** — the
per-launch secret is enforced and you do not have it. A 200 means the guard is
off. `ELECTRON_RUN_AS_NODE` must be **deleted, never blanked**; Electron tests
for its presence.

---

## What is uncommitted right now

Two logical commits, independent of each other.

**1. Web search reaches the model.** The fix described at the top of
`MILESTONES.md` Current state.

* `backend/core/search_context.py` — **new**. `format_search_results`,
  `search_prompt`, `result_count`. Moved out of `main.py` because the engine is
  its only consumer and `main` imports from `core`, never the reverse.
* `backend/core/execution_engine.py` — injects the search output into the
  `reasoning.generate` step; emits a notice when a search returns nothing.
* `backend/main.py` — dead `_format_search_results` and its now-unused
  `SEARCH_MARKER` import removed.
* `backend/tests/test_search_reaches_the_model.py` — **new**, 18 tests, six of
  which drive the real engine and assert on the prompt the model was handed.
* `backend/tests/test_alpha10c_acceptance.py` — two imports repointed.

**2. The README, rewritten.** Adds *Who this is for* and *Why this is hard to
copy*, both previously absent; re-verifies the Status section against the code;
and states the licence decision below.

**3. These two documents** — this file and the new Current state entry in
`docs/MILESTONES.md`. They travel together with whichever commit lands last.

---

## Decisions taken this session

* **`gemma4:12b` is the daily driver.** `qwen3:14b` was rejected: 9.3 GB fails
  the ~9.1 GB residency budget it was chosen to satisfy.
* **`qwen3.8:27b` is background-tier only**, at a measured 1.45 tok/s.
* **The repository is source-available, all rights reserved — not open
  source.** Reading and auditing are welcome; copying, modifying and
  redistributing are not granted. This reverses the README's earlier line that
  an OSI licence was required before public release, and the reconciliation is
  that the concern underneath that line was *auditability*, which readable
  source satisfies without forkability.
* **Do not revive `backend/orchestrator/`.** The live replacement now exists,
  and that package still contains the merged gate/ranking bug.

---

## What to do next

**This list is from 19 August and has been overtaken.** `docs/MILESTONES.md`
Current state — 26 August — is the handoff and is the authority. What follows
is kept because most of it is still open; items struck as DONE are recorded so
nobody re-does them.

0. **~~Ask the running Zaram something the weights cannot know.~~ DONE,
   26 August.** Run twice against a real DuckDuckGo result and a real local
   model. It worked, and it found two further defects that no test could have:
   the search block was labelling the user's own Spine records as internet
   results, and five of six "sources" on a news question were local. Both
   fixed. See MILESTONES Current state.

0b. **~~Write the `LICENSE` file.~~ DONE, 26 August.** Source-available, all
   rights reserved, matching the README section it was drawn from.

1. **Wire obligation extraction.** Promoted to first because it is now
   unambiguously the largest gap between built and reachable.
   `backend/obligations/` — `contracts.py` and `extract.py` — is imported by
   **nothing but its own test file**, which makes it the eighteenth complete,
   tested, unreachable subsystem. Its CLAUDE.md precondition is satisfied:
   `untrusted.py` is wired into `core/execution_engine.py` and
   `test_untrusted_reaches_recall.py` asserts the seam rather than the module.
   The extractor already carries the source sentence for every clause, which is
   what rule 2 and "every obligation shows its source clause" require. What is
   missing is a caller, a surface, and the correction path. **Never silently
   create a commitment.**
2. **Run the app and watch the mouth move.** Carried over untouched from the
   previous handoff. Nothing from the voice session has been seen in the
   product. Speech on the Speak button in orb mode, speech automatic and
   streaming in avatar mode, visemes moving with it.
3. **Listen to the three WAVs and decide the Kokoro backend.** `a-torch`,
   `b-onnx-fp32`, `c-onnx-fp16`. If b is indistinguishable from a bar the
   level, flip `DEFAULT_BACKEND` to `"onnx"` — the assertion in
   `test_default_backend_is_the_one_a_human_has_heard` makes that a deliberate
   edit. Human ears are the only instrument for this one.
4. **Wire obligation extraction.** Now unambiguously the next real feature: the
   extractor reads payment, deliverable, expiry and renewal clauses with the
   sentence each came from, and nothing outside its own tests imports it. It
   must not ship without `untrusted.py`, which is now wired.
5. **~~Write the `LICENSE` file.~~ DONE — see item 0b.** Original note: The decision is taken and only the README
   carries it; tools and scanners look for the file. Note that GitHub's terms
   permit viewing and forking *within GitHub* for any public repo — that cannot
   be prevented while the repo is public, only the use of what is copied.
6. **Fix the GitHub repo description.** It reads *"Multi-Ai Operating system
   for domain experts"*. `AI operating system` is on CLAUDE.md's retired
   vocabulary list, and "domain experts" narrows to a segment the vision
   widened away from on 16 August. Suggested: *"The memory and control layer
   for people who use more than one AI. Runs on your machine, cites its
   sources, and logs every byte that leaves."* Needs the GitHub settings page —
   **`gh` is not installed on this machine**, so it cannot be done from a
   session.
7. **Conversation persistence, as the session/memory split.** There is no
   history at all — close Zaram and yesterday is gone. Guardrail, enforced by
   test: readable by the user, invisible to recall (rule 7d).
8. **`KPipeline.load_voice` is an ungated download.** It fetches a `.pt` at
   synthesis time with nothing asked and nothing logged. The ONNX path routes
   the same fetch through the gate; the torch path still does not.
9. **Reconcile the two Electron trees and the two venvs.** Triage decisions
   nobody has taken, invisible to every guard because each side is internally
   consistent.
10. **Delete `backend/orchestrator/`.** 1,261 lines, no importers, no tests,
    and it contains the membership-versus-ranking bug ready to be revived.
11. **Rebuild the installer and run it on a machine that has never seen this
    repo.** Still the actual blocker.

---

## Two loose ends nobody has explained

* **The egress gate reports "7 host policies"; `backend/egress-policy.json`
  holds 35.** Observed at boot on 19 August. There is no second policy file
  anywhere on disk — checked. Either the count means something other than
  hosts, or there is a store nobody knows about. It sits under rule 5, so it is
  worth an hour.
* **The suite skip count went from 24 to 27** in the run after the search fix,
  which added no skips. The likely cause is that Zaram was running and holding
  resources during that run — CLAUDE.md's own warning that the suite *executes
  different code* depending on conditions. Confirm with `pytest -rs` rather
  than assuming; a silently skipping suite has already cost this repository
  once, and it reads exactly like passing.

---

## Open questions for the maintainer

* **Is `qwen2.5-coder:14b` still worth keeping?** `gemma4:12b` scores 72 on
  LiveCodeBench (vendor-reported); the entire Qwen2.5-Coder generation was
  scoring in the low thirties on that benchmark's earlier versions. Version
  differences make the subtraction unrigorous, but if the general model is
  better at code then the `code` intent added this session routes to the
  *worse* model **and pays a full swap to do it** — 7.6 GB and 9.0 GB cannot be
  co-resident in ~9.1 GB. The test is three real coding questions from this
  repo, judged by a human. If gemma4 wins, drop the coder and delete the
  specialisation mapping.
* **Should Zaram expose an MCP server?** Kilo Code, Cline, Claude Code and
  Cursor are all MCP *clients*. Exposing `recall`, `search_spine` and
  `get_provenance` read-only would let the agents people already use read from
  the Spine — most of the value of "Zaram has agents" without building one,
  without opening the mutative tier, and without adopting a framework whose own
  memory abstraction would compete with the product. Prerequisite: the API
  secret, which now exists.
* **`en_core_web_sm` in the base install.** Unchanged and still open. misaki
  downloads it at runtime when absent — unlogged and ungated — so the pin looks
  deliberate; its *location* is still wrong, since spaCy is not in base.
* **Word-by-word speech.** Unchanged. CLAUDE.md rules it out — *"a clause is
  the smallest unit with prosody"* — and what is built already speaks alongside
  the streaming text rather than after it.

---

## What this session learned about the instruments

**The search layer was healthy and the product was broken.** Every diagnostic a
person would reach for — the toggle, the package, the egress policy, the host
gate, the log — reported success, because each of them *was* succeeding. The
failure was in a seam between two components, which is the one place no
component's own tests look. `check:reachability` cannot see it either: both
sides are live, and the missing thing is a line that was never written.

**A test that passes proves nothing until you have seen it fail.**
`_format_search_results` carried two green tests for its entire unreachable
life. The fix's tests were verified by disabling the fix and watching them go
red, which took two minutes and is the difference between a guard and a
decoration.

**Re-verify a status page against the code before believing its gaps.** The
README's headline gap — no API authentication — had been closed by work nobody
had updated it for. A status section that understates a project is the same
defect as one that overstates it, which that file already says about itself.
