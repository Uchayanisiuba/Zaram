# Handover — 19 August 2026

Paste the block below into a new session. It is written to be read cold.

The previous handover (18 August) is superseded. Read *What changed* at the
bottom before assuming anything from an older session still holds.

---

```
You are continuing work on Zaram (C:\Zaram), on branch Zaram-V0.1.

READ FIRST, IN THIS ORDER
  1. CLAUDE.md — the contract. Rules, scope, vocabulary. Authority on rules.
  2. docs/HANDOVER.md — "What changed on 19 August", below the block.
  3. docs/MILESTONES.md — "Current state — 19 August 2026" at the top.
  4. docs/UI-SPEC.md — the interface.

WHY THIS CODEBASE IS THE WAY IT IS — read this before judging any of it
  **Zaram was partly built with Kilo Code and Trae.** The maintainer said so on
  18 August and it explains the single dominant failure mode: complete,
  well-commented, fully-tested subsystems that *nothing calls*. Fifteen found so
  far. Those tools produce a plausible whole and cannot check that anything
  reaches it, and the tests they write assert the scaffolding rather than the
  contract — which is why "tests green" has repeatedly meant nothing here.
  Assume unreachable until you have seen the caller. This is not pessimism, it
  is the base rate.

BEFORE RUNNING ANYTHING
  - pytest as `backend\venv\Scripts\python.exe -m pytest` from the repo root.
    Bare `python` is a broken shim (it fails with "install path was not found").
  - STOP ANY RUNNING BACKEND BEFORE THE PYTHON SUITE. A live backend holds the
    SQLite lock on the real spine.db and the suite stalls rather than failing.
  - STOP ZARAM BEFORE THE ELECTRON SUITE. electron/main.js takes a
    single-instance lock, so two bootstrap tests assert against an empty log.
  - **OLLAMA CHANGES THE TEST COUNT AND THE RUNTIME.** With Ollama running the
    suite takes ~4 minutes; with it down, ~20, because every provider probe
    waits for a timeout. It also changes which code paths execute — see the
    boot crash below. Say which condition you measured in.
  - `npm run check:all` runs lint, typecheck, guards, the reachability report,
    the payload check and all three suites.

THE CREDENTIAL TRAP — still the most confusing thing in the repo
  The desktop app MINTS A FRESH API SECRET EVERY LAUNCH and passes it to its
  renderer over IPC. So:
  - A browser tab at localhost:5173 401s on everything if the backend was
    started BY ELECTRON, and the interface correctly reports "Zaram engine not
    running" about a healthy backend.
  - curl against 8420 needs -H "X-Zaram-Auth: $(cat backend/api-secret)", and
    that file only matches when the backend was started STANDALONE
    (`cd backend && venv/Scripts/python.exe main.py`).
  - **To drive the real UI in a browser: start the backend STANDALONE first,
    then the Vite dev server.** Verified working on 18 August — /health returned
    200 from the page with zero 401s. Order matters: Vite bakes the secret in at
    boot.
  - Whatever is on 8420 may be stale code — it does not hot-reload. Check
    build.commit_short before believing it.

TWO ELECTRON MAIN PROCESSES
  `npm run dev` runs a 46-line desktop/src/main/index.ts; the packaged app runs
  the 429-line electron/main.js. Everything in the latter — tray, global
  shortcuts, backend launcher, static server, ambient surface — is never
  exercised in development. Run the real one:
  `node_modules/.bin/electron electron/main.js`.

MEASURED STATE (19 August, every number from a run)
  backend 2207 passed / 0 failed / 95 skipped, WITH OLLAMA DOWN (21m43s) ·
  frontend 198 · Electron 48 ·
  typecheck clean · lint passes · guards pass.
  HEAD 61d6e36, working tree clean, everything pushed to origin/Zaram-V0.1.

  **The old "2184 passed / 0 failed" baseline was measured with Ollama UP and
  is not the number a clean machine produces.** Measured with Ollama down on
  18 August it was 1 failed / 53 errors, all from one crash — see below.

THE THREE THINGS THAT MATTER MOST
  1. The installer is BUILT and UNVERIFIED on a clean machine. That build now
     predates ingestion routes, domains, the character pane, the boot-crash fix
     and everything else. REBUILD BEFORE TESTING. Only the maintainer can run
     it on a machine that has never seen this repo.
  2. core/untrusted.py — the prompt-injection defence — is called by NOTHING.
     Provenance, may_instruct and scan are complete, tested and attached to no
     code path. Obligation extraction must not ship without it. Task 21.
  3. backend/orchestrator/ is 1,261 lines imported by nothing, no tests. It
     blocks the modality work. THE MAINTAINER MUST DECIDE: delete, or revive as
     the routing engine. Do not build on it before that answer.

WHAT TO BUILD, IN ORDER
  1. Triage the reachability report — `npm run check:reachability`. 25 modules
     and 4 routes. Each is wire / allowlist-with-a-reason / delete. This is
     where the remaining unknown risk is concentrated before an alpha.
  2. Wire core/untrusted.py (task 21). Security, and a prerequisite for
     obligations.
  3. Conversation persistence, as the session/memory split (task 3). The
     largest felt gap in daily use: there is NO conversation history at all —
     no conversations.db, no route, no UI, and the session buffer dies with the
     process. Close Zaram and yesterday is gone.
     GUARDRAIL, enforce by test: the conversation store is readable by the user
     and INVISIBLE to recall. Never retrieved, never embedded, never cited.
     CLAUDE.md rejects L0 because persisting raw dialogue made Zaram quote its
     own replies — that is a recall failure, not a storage one.
  4. The egress data class (task 4) — must land before any image can leave.
  5. Modality as a gate (task 5) — BLOCKED on the orchestrator decision.

KNOWN OPEN GAPS, DELIBERATELY
  - The domain PICKER's rendering is unverified. The backend path is proven
    live (POST /chat with domain_ids emitted the domain notice), but with no
    model installed the conversation shows the first-run gate instead of the
    composer, so no composer control renders at all. Re-check with a model.
  - The date in the system prompt is unverified live for the same reason —
    it needs a model to generate an answer.
  - The orb's colours. Speaking and listening are 29 degrees apart in hue, and
    idle and thinking are the same two hues with dominance swapped. Proposed
    fix: let motion character carry state instead. NEEDS A GPU MEASUREMENT
    FIRST. Not started.
  - The uninstaller zips raw SQLite rather than calling the real exporter.
  - Obligations are not wired into ingest.

TRAPS THIS CODEBASE HAS PAID FOR REPEATEDLY
  - A feature's tests can all pass while the feature cannot happen. Fifteen
    found. `npm run check:reachability` now reports two of the shapes.
  - THE GUARD IS NOT COMPLETE AND SAYS SO. It catches unimported modules and
    routes with no frontend caller. It does NOT catch a dead branch inside a
    live function, an unused export, or a component mounted that should not be.
    Three of the six found on 18 August were invisible to it.
  - THIS APPLIES TO YOUR OWN ANALYSIS AND YOUR OWN TOOLS. On 18 August I wrote
    a wrong claim into CLAUDE.md from my own note instead of the code, and the
    reachability guard's first run reported 183 dead modules that were all
    alive. Check your instrument before reading its output.
  - A test can be named for a guarantee it does not check. The shortcut guard
    was called "leaves Copy, Paste, Cut, Save and Select All to the operating
    system" and tested c/v/x/a/z — no S. Ctrl+S was being deleted for weeks.
  - An environment condition can hide a crash completely. The boot crash below
    only fires when models are discovered and ALL are unselectable, which never
    happens with Ollama up and never fails to happen on a stranger's machine.
  - An empty set is not an absent one. frozenset() is falsy; use `is not None`.
  - A blocklist fails open. Require positive evidence instead.
  - A score built for ranking is not a score for deciding. Membership,
    ordering and citation are three questions; never merge them.
  - Never render an invented value.
  - Verify by seeing it work, not by a passing suite.
```

---

## What changed on 19 August

Seven commits. Five features and defects closed, one crash that stopped the
backend booting, one build guard — and two corrections of my own work, which
are the most useful entries here.

### The backend could not start on a machine without Ollama

`models_runtime.py` read `m.id for m in rejected` while
`rejected_default_candidates()` returns `list[tuple[ModelInfo, str]]`. The
`AttributeError` escaped through kernel boot: **53 tests errored at app startup**
and the traceback named a logging line rather than the model layer.

It is an installer-class defect. The branch runs only when models are
discovered and *every one* is unselectable — a machine with no Ollama, which is
every machine a stranger installs this on.

**Why two weeks of green suites sat on top of it.** The *producer* is tested
twice and both tests unpack the tuple correctly, so the type was never in
doubt. The *consumer* had no test at all, and the branch does not execute with
Ollama up. Nothing was hidden by cleverness; it was hidden by an environment
condition no previous run happened to be in.

The function's own docstring had promised since 4 August that "every failure
here returns None… must degrade rather than take chat down with it", and the
`try` covered its first two statements only. The guarantee now wraps the whole
body, split into `_choose_model_inner` so a later edit cannot append past it.
The reason the log was discarding is restored, too — it asserted "data policy"
for every rejection, so a VRAM exclusion was reported as a privacy decision.

### Knowledge domains reach the conversation

`domain_ids` on `ChatRequest` resolves through `_domain_scope` to fact ids and
rides down to `retrieve(only_ids=)`. An unresolvable domain **narrows to
nothing and says so** rather than failing open to the whole Spine.

Verified against the live backend: `POST /chat` with an empty domain emitted,
before the answer, *"Nothing is indexed in your Investing domain yet, so this
answer used no facts from your files."* The picker's own rendering is **not**
verified — with no model installed the conversation shows the first-run gate
instead of the composer.

### The orb reported capability as activity

An earlier fix split the two claims apart in *words* and left both returning
`tone: 'cloud'`, which paints **amber — this product's warning colour**. So
connecting a provider lit a standing warning that never went out while every
answer was local.

Colour now follows what happened; words carry what is possible. Verified live
against a backend reporting an OpenRouter provider and `can_leave_device: true`:
label read **"Local · cloud ready"** at computed `rgb(16,185,129)` — emerald,
not amber. Read off `getComputedStyle`, which is the check the previous
session's orb assessment skipped.

### A panel saying "NOT SHIPPED UI" was shipping

`EmbodimentSpikeControls` rendered **"EMBODIMENT SPIKE — NOT SHIPPED UI"** on
the landing screen, mounted unconditionally with no dev gate. Found by driving
the running product; no test could have caught it.

Deleted, because the file asked for it — "delete this file when [the Settings
renderer toggle] lands", and it has landed. The better reason is that its
safety argument had gone stale: it writes `orbStore` directly, justified as
"tolerable *here* only because this is a bench… not a path a user reaches". It
was a path a user reaches, and writing one of those stores without the other is
how the orb desynchronises from its label.

### The character pane, and citations that told the truth

`/character` had routes, tests and **zero frontend callers**. Now a Settings
section with name, manner and voice. Verified end to end: typed
`"  Ada    Lovelace  "`, backend stored `"Ada Lovelace"`, and the input rendered
the *stored* value rather than the typed one.

Separately, every web citation chip showed `relevance: 0.0` — a field-name
mismatch in one hop. `KnowledgeRuntime` built its result with
`confidence=r.score` and never set `score`, which is the field the citation
layer renders as relevance. The larger fix in the same six lines: the memory
branch passed the **ranking blend** where the similarity was wanted.

### Two corrections of my own work

**I wrote a wrong claim into CLAUDE.md.** The modality paragraph said
"`ProviderEntry` carries no modality field today; that is the first piece of
work". Both halves were wrong. `ProviderEntry` is a *provider* record holding
no models; modality belongs on `ModelInfo`, which already has
`supports_vision` and a `ModelCategory` including `VISION`, `IMAGE` and
`VIDEO`. Written from my own note instead of from the code — this
repository's signature failure, committed against its contract document.

**The reachability guard's first run reported 183 dead modules, all alive.** It
resolved relative imports against the repo root. Fixed, then sampled five by
hand: five true positives.

### The guard

`npm run check:reachability`. Two checks, because one would not have helped —
of the six found this session, a module-import check catches exactly one. The
second checks **backend routes no frontend file calls**, which is the pattern
that actually recurs here. It states plainly what it does not cover.

Report-only in `check:all` for now; 25 findings exist and `--strict` would fail
the build today.

It found a fifteenth instance and the worst one: **`core/untrusted.py`, the
prompt-injection defence, is referenced only by its own test.** Its docstring
names the exposure it was written for — "a hostile invoice is a way to put a
deadline in someone's week, or a different bank account on their letterhead" —
and it was never attached to the features it was written for.

### Also decided

**Image generation moved into v1** by the maintainer. The shape is unchanged:
Zaram ships no image weights, routes to a provider, logs the egress. The
recorded objection is spent — it said image generation could not ship before
the cloud engine existed, and the cloud engine landed. Recorded with it: an
image is **its own consent class** under rule 7j, since a chat message is ~2KB
and an image is 1–5MB and far more personal.
