# Known failures — classified by contract

**Current: 0 failing. See `docs/MILESTONES.md` for the count — it is measured
every session and was 1293 when this line was first written.**

Run from the repo root. Not from `backend/`.

**A test count without its condition is not a measurement — 19 August 2026.**
The suite runs in roughly 4 minutes with Ollama up and roughly 20 with it down,
because every provider probe waits for a timeout. More importantly it executes
*different code*: a crash that stopped the backend booting hid for two weeks
behind a green suite, because its branch only runs when models are discovered
and every one is unselectable — which never happens with Ollama running and
always happens on a machine that has never had it. The passing number was
honest and answered a question nobody had asked.

So this file no longer restates a total that drifts. When you record a count,
record whether Ollama was running.

---

## Why this file exists

For four milestones the suite sat at 27 failures under a two-line summary:

> **13** — one stale test double, core.
> **14** — voice, out of scope.

Both numbers were right. Both labels were wrong, and the labels are what
mattered. When they were finally taken apart, the 27 were **four unrelated
bugs**, two of them live in shipped code:

| What the label said | What it was |
|---|---|
| 13, one stale test double | A stale double **and**, underneath it, 10 tests written against a `ConversationManager` architecture deleted in Sprint Alpha.6 |
| 14, voice, out of scope | 5 tests broken by `voice_discovery_enabled` being deliberately defaulted **off** for rule 7g, 9 more that were the ConversationManager problem, and **0** that were about voice |
| — | A live `NameError` in `main.py`: `SEARCH_MARKER` used without importing it |
| — | A test *requiring* `/chat` to reach the internet, against a default-deny product |

The grouping was the failure. "13 core, 14 voice" made 27 feel understood, so
nobody ran them individually. A failure filed under a plausible label is more
dangerous than an unexplained one, because the label ends the investigation.

**This is now in `CLAUDE.md`'s working agreement:** a failure is out of scope
only if the *code it exercises* is out of scope. Where a test lives says
nothing about what it tests.

---

## How to classify a failure

Ask what contract the test exercises, then ask whether that contract is in
scope. Never ask which directory it is in.

| Class | Meaning | Action |
|---|---|---|
| **Live defect** | The contract is in scope and the code is wrong | Fix the code |
| **Stale contract** | The contract no longer exists — the code was deliberately changed and the test was not | Rewrite against the real contract, or **delete**. Never leave failing |
| **Wrong assertion** | The contract exists; the test asserts something else, or asserts nothing | Fix the test |
| **Missing dependency** | The contract is in scope but needs something absent (Ollama, a model, an optional extra) | `skipif` with the install command in the reason. Never a bare failure |
| **Out of scope** | **The code under test** is out of scope for v1 | Record here with the date it can be revisited |

A failing test is never left in place. It either gets fixed or it gets deleted,
because a permanent failure is a permanent invitation to stop reading.

---

## The 27, taken apart

Resolved 7–8 August 2026. Kept because the taxonomy is the lesson.

### Live defects — 3

**`main.py` used `SEARCH_MARKER` without importing it.** A real `NameError` on
the web-search path, latent only because search is default-deny. Two tests in
`test_alpha10c_acceptance` were reporting it and were filed under "core".
*Fixed: import added.*

**`HybridMemoryRetriever` ranked on stopword overlap.** Not part of the 27 —
found by the recall eval built afterwards — but the same shape. Keyword search
ran beside vector search and the higher score won, with no stopword filter, so
*"What is the capital of France?"* beat a true cosine of 0.226 with a 0.5
overlap on `is`, `the`, `of`. *Fixed; see `docs/MILESTONES.md`.*

**`CrossDocumentLinker.get_links()` could only ever return empty.** Nothing
called `record_link`, so the public accessor was dead. Found by making a
vacuous test assert something. *Fixed: `link_objects` now records.*

### Stale contract — 10

`test_streaming_conversation` (10 tests) and `voice/tests/test_voice_conversation_integration`
(9 tests) drove a `ConversationManager` that took a `VoiceManager` and yielded
`audio` events. Sprint Alpha.6 replaced that with the event bus: the manager
publishes `conversation:sentence_ready` and the Speech runtime decides whether
to speak.

The stale `FakeLLM` signature hid this. Fixing the double moved the failure one
layer down, to tests asserting an architecture that had not existed for
milestones — they could never have passed again.

*Resolved:* `test_streaming_conversation` rewritten against what the manager
actually promises; the audio assertions returned to the voice stack where they
can run. One shared `FakeLLM` in `tests/llm_doubles.py`, held to the contract by
`test_llm_engine_contract.py`.

### Wrong assertion — 3

**`test_alpha10c_acceptance` required `/chat` to trigger a search.** Search moved
behind `chat_router` (which the test mocks, so the count could only be zero) and
became default-deny. The test demanded a rule violation. *Inverted: it now
asserts nothing leaves.*

**`test_invalidate` stored an object and called `invalidate`, asserting nothing.**
It also used content too short to chunk, so it invalidated an object with
nothing stored against it — it would have passed against an empty store and a
no-op implementation. *Fixed: asserts the chunks go, and that its neighbour's
do not.*

**`test_cross_document_links_created` stored two documents and asserted nothing.**
Fixing it exposed the live defect above. *Fixed.*

### Missing dependency — 5

`voice/tests/test_kokoro_provider` asserted that discovery populates `_voices`.
It stopped doing so when `voice_discovery_enabled` was deliberately defaulted
**off** — real discovery contacts huggingface.co at startup, which rule 7g
forbids before consent, and `test_egress_chokepoint` asserts that default.

These were the five filed hardest under "voice, out of scope". They were about
a privacy decision, not about voice. *Fixed: the tests enable the flag
explicitly against an injected `FakeDiscoverer`, so they reach no network.*

### Out of scope — 0

None of the 27. The label was applied to 14 tests and fitted none of them.

---

## Deleted rather than left failing

- **`backend/test_kernel.py`** — a manual smoke script committed truncated
  mid-expression (`SyntaxError: '(' was never closed`), zero test functions.
  It survived only because `pyproject.toml` ignored it by path, and that ignore
  is rootdir-relative, so running pytest from `backend/` aborted collection of
  the entire suite. The workaround was worse than the file.
- **`backend/services/speech_manager.py`** — imported `implementations.kokoro_tts`,
  deleted long ago. Unimportable, imported by nothing.
- **Three more smoke scripts** (`test_models_runtime.py`,
  `test_execution_engine.py`, `core/test_execution_engine.py`) — zero test
  functions, `asyncio.run(main())` at import time, matching `test_*.py` by
  accident. Renamed `manual_*.py`. **All four `--ignore` lines are gone from
  `pyproject.toml`.**

---

## Tests that skip, and why that is fine

A skip is honest when the reason names what is missing and how to get it. A
skip that hides an in-scope contract is not.

| Suite | Needs | Reason given |
|---|---|---|
| `test_recall_eval.py` (end-to-end half) | Ollama + `bge-m3` on loopback | Similarity over the hash fallback is arbitrary rather than merely worse, so a green run against it would be a lie. `ollama pull bge-m3` |
| Voice suites | The 905 MB voice extra | Install command in the reason |
| PDF export | GTK native libraries on Windows | `export.formats()` reports it unavailable with a per-platform remedy |

---

## The trap to watch for next

**A stable failure count that everyone stops reading.** That is what happened,
and this file's own numbers can become it. Two guards:

1. Any change to the count is recorded here with the *contract* affected, not
   the module.
2. Vacuous tests count as failures for this purpose. A test that asserts
   nothing reports coverage it does not have, and both bugs above were hiding
   behind exactly that. `grep` for test functions with no `assert` and no
   `pytest.raises` — it takes seconds and it found two live defects.
