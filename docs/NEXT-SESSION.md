# Next session — start here

A prompt and a state snapshot. Rewritten 28 August 2026 at the end of the
conversation-history, context-budget and transcript-projection session.

**This file is a pointer, not a second handoff.** `docs/MILESTONES.md` Current
state is the handoff and stays the authority on status; `CLAUDE.md` stays the
authority on rules. If this file disagrees with either, they win and this file
is stale — say so and fix it.

---

## The prompt

Paste this into a new session:

> Read `CLAUDE.md`, then `docs/MILESTONES.md` Current state, then this file.
> For anything touching voice read `docs/SPEECH.md`; before starting the app
> read `docs/RUNNING.md`, and note that launching means three processes, not
> two — Vite, Electron, and TabbyAPI on port 1234.
>
> **Everything from the last session is committed and pushed** (`Zaram-V0.1`,
> through `08788f6`). The suite is 2716 passing, 0 failing, 194 s with Ollama
> up. Frontend 298 passing.
>
> Two jobs are open and they are independent. Pick by what you can verify:
>
> 1. **See the history panel work.** It shipped without ever being rendered,
>    because port 5173 was held for the whole session. If you can get a dev
>    server, that is the cheapest real thing to do first — and this project has
>    already paid once for shipping UI that passed its tests and did not
>    visibly work (the VRM gaze).
> 2. **The per-launch API secret** — roadmap 1.4. It is the hard gate on
>    exposing the Spine over MCP, and `CLAUDE.md` says it belongs before a
>    stranger installs this.
>
> The vision decision from the previous handoff is **still open** and is
> described below. It was not touched last session.

---

## What happened

Started from one pasted error and went a long way from it. Seven commits.

### The error, and the two defects under it

    [ERROR] Ollama could not answer with gemma4:26b-a4b-it-q4_K_M:
    HTTPConnectionPool(host='127.0.0.1', port=11434):
    Read timed out. (read timeout=120)

`stream_response` used one number for two different waits: the silence before
the first token, and the gap between tokens. Ollama does not send response
headers until the first token, so that budget covered the whole model load.

Measured on this machine, `gemma4:26b-a4b-it-q4_K_M` — 18.2 GB on disk against
a 12 GB card, so 9.3 GB lands on the GPU and the rest in system RAM:

| | |
|---|---|
| cold load, empty prompt, nothing generated | **109 s** |
| first token after that, five-word prompt | **28.8 s** |
| cold load to first chunk, through the engine | **172.7 s** |
| headers arrive | with the first token, not before it |

The budget is now chosen by whether the weights are resident, asked of
`/api/ps`, rather than by whether an image is attached. The vision path is a
cold start too — of the projector — which is why it kept needing a constant of
its own.

Second defect, same story: `warm_local_model` called `warm(self._selected_model)`
and that is `None` whenever `select_default_model` declines everything
installed, which on this machine is the ordinary outcome. `warm` fell back to a
hardcoded `gemma3:latest` that is not installed here, failed at `logger.info`,
and returned False — so "warming is once per session" was quietly never
happening.

### What shipped

| Roadmap | What |
|---|---|
| 0.2 | Settings says a model is too large **before** it is chosen |
| 1.1 | Conversation history, end to end |
| 1.2 | Neutral transcript, per-provider projection, session seeding |
| 1.3 | Context budget measured from `/api/ps` |
| U.3 | UI-SPEC orb table corrected to match the code |

Plus two bug fixes that were not on any list — see below.

**Conversation history** is the foundation item. Before it, no table in any of
the seven databases held a message: closing the window lost the conversation.
`conversations.db` implements rule 7d's *"session state and long-term memory
are separate stores"* — Zaram had the second and not the first.

Decisions worth not re-litigating:

* Deleting a conversation deletes the transcript and **nothing else**, and the
  API response says so. Facts are correctable in Memory in their own right.
* Two roles, no `system`. The system prompt is recomposed per request from
  identity, character settings and the date; a stored one becomes false the
  moment the user renames the assistant.
* The title is the first thing typed — never asked, never model-generated.
* Restoring a conversation does **not** restore its citations. A citation
  claims *this* answer used *that* fact, and the fact may since have been
  corrected under rule 4.

**Context budget.** Ollama serves a default `num_ctx` whatever a model
advertises — `gemma4:12b` reports 262,144 and loads with 4,096. Unknown returns
`None`, never a guess; `context_length: 0` counts as unreadable rather than a
budget of nothing. Documents get a *share* of the input budget, calibrated so
that at Ollama's default it yields 1,843 tokens against the old flat 1,800 —
behaviour unchanged, and a 16k model now gets a proportionally larger share.

**Transcript projection.** The transcript is canonical; a provider's format is
a projection. Whole turns only — half a message attributed to a person is a
fabrication, and the model answers the truncated question. The kept transcript
never begins with a reply.

`seed_session_turns` closes the gap that makes visible: `_session_turns` dies
with the process, so a resumed conversation used to arrive with nothing in
front of it and *"write that up as a proposal"* resolved against an empty
buffer.

### Two live defects found by accident

Both surfaced while chasing what I had written off as environment noise. Both
had been hiding behind a label.

**`ConversationManager` raced its own error path.** The worker put the error
event, then set an `error_occurred` flag, then put `llm_done`. The consumer
yielded an event and *then* checked the flag — so when the worker got ahead,
the loop broke out with the error still unread. The user got a partial reply
and no error. A failure that arrives as silence is worse than a failure,
because a truncated answer reads as a complete one.

**`ContinuousLearningPipeline` slept 1800 s holding the lock `stop()` needs.**
So `stop()` could hang for up to half an hour in the product. In the suite:

    9000.04s call  TestContinuousLearning::test_start_stop

Four lines of test. Exactly five intervals — the rounds it took `stop()` to win
the race — and **97% of a 2h35m suite run**. It had been read as "the suite is
slow". Same file after the fix: 0.60 s. Full suite: 2h35m → 3m14s.

The old test asserted the flag and not the *time*, so it passed throughout.

---

## Still open: the vision decision

**Carried forward unchanged from the previous handoff. Not touched.**

`OllamaEngine.stream_vision_response` hardcodes `"model": "qwen2.5vl:7b"`,
which is not installed here, and ignores whatever model the user chose. Vision
reaches the engine and fails at Ollama.

The right fix is the modality gate `CLAUDE.md` describes, and it is not a
one-liner:

* `ModelInfo.supports_vision` exists and Ollama discovery populates it from
  `/api/show`. It is a 0..1 ranking score, not a gate — `capabilities.py` maps
  `ModelCategory.IMAGE` to `Capability.VISION: 1.0`, the same value a model
  that *reads* images gets, so "can see" and "can draw" are one number.
* Modality is a **precondition**, never a ranking. It filters the candidate
  set; similarity orders what survives.
* `gemma4:26b-a4b` is vision-capable and installed. Selecting it for a vision
  request is the outcome to aim for.
* The `orchestrator/` package has **zero importers** and its `scoring.py`
  records a missing required capability as a *warning* and ranks the candidate
  anyway. Do not build the gate on it. Delete it instead.

Do not paper over it by pulling `qwen2.5vl:7b`.

---

## Not verified

**The history panel has never been rendered.** Port 5173 was held by another
process for the entire session, and `vite.config.js` sets `strictPort: true`
while the backend's CORS allow-list names that exact origin — so it could not
be moved. The panel compiles, `conversationsClient` has 12 tests, and the proxy
hole that would have broken it is fixed. None of that is a screenshot.

Found while investigating it: **`/conversations` was missing from both proxy
lists**, Vite's and Electron's. A missing prefix does not 404 — both servers
fall through to the SPA handler and answer `index.html` with a 200, so the
client hands HTML to `response.json()` and reports a syntax error naming
neither the route nor the proxy. `npm run check:proxy` now reports 20 prefixes
covered, development and packaged.

---

## Process notes, all of them mine

Three instrument misreads in one session, the same shape each time — inferring
from a proxy signal when a direct measurement was one call away.

1. **GPU utilisation read as Ollama activity.** TabbyAPI is running and holds
   VRAM. `nvidia-smi` is not an Ollama activity monitor on a machine with two
   inference servers. `/api/ps` is.
2. **`TaskStop` believed to have killed processes that were still running.**
   Two orphaned full-suite runs kept executing and competing while I started
   more. Check the process list with command lines; do not assume.
3. **A suite believed hung because I piped its output through `tail`.** Nothing
   appears until completion. Write test output straight to a file.

And one that cost a live `NameError`: an edit script asserting on two
replacements aborted on the second, silently discarding the first. **Do not use
assert-then-write edit scripts for multi-part changes** — the failure mode is
silent partial application.

The thing that actually found the 2h35m problem was `pytest --durations`. It
should have been the first move, not the fifth.

---

## Roadmap

Published as an artifact — 25 tasks in dependency order, with the measurement
or CLAUDE.md rule each rests on:

<https://claude.ai/code/artifact/b5c802a5-0701-43c1-aff1-5f9835ffbc65>

Phase 0 (day one: free-tier first run, import ChatGPT/Claude history) is the
gate everything else waits behind — a new user with no GPU and no key currently
gets nothing. Phase 1 is now four-fifths done; **1.4, the per-launch API
secret, is the remaining one** and it gates 4.1.

One entry in that artifact was withdrawn as my error: I claimed
`docs/KNOWN-FAILURES.md` was stale. It is not — its first line reads
"Current: 0 failing", and the 27 failures appear in the past tense as the
reason the file exists.

---

## Machine state

Unchanged from the last handoff, and worth restating because it shapes what is
testable here:

* Ollama holds `gemma4:26b-a4b-it-q4_K_M` (18.2 GB) and `bge-m3`. The chat
  model **does not fit** — the resident budget on a 12 GB card is ~9.1 GB — so
  it runs half on the processor and every reply is slow. This is now said in
  Settings before it is chosen.
* `select_default_model` therefore returns `None`, which is correct and is the
  ordinary path on this machine. Any code assuming a default model exists will
  be exercised here.
* TabbyAPI serves Qwen3.8-27B EXL3 on `127.0.0.1:1234`, discovered as
  "LM Studio" and routed by `LocalDispatchEngine`.
* **Say which environment you measured in.** The suite is ~194 s with Ollama
  up. With it down it is far longer *and executes different code*.
