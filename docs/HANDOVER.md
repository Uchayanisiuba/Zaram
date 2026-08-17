# Handover — 17 August 2026

Paste the block below into a new session. It is written to be read cold.

The previous handover (16 August) is superseded. Read *What changed* at the
bottom before assuming anything from an older session still holds.

---

```
You are continuing work on Zaram (C:\Zaram), on branch Zaram-V0.1.

READ FIRST, IN THIS ORDER
  1. CLAUDE.md — the contract. Rules, scope, vocabulary. Authority on rules.
  2. docs/MILESTONES.md — "Current state" at the top.
  3. docs/UI-SPEC.md — the interface.

BEFORE RUNNING ANYTHING
  - pytest as `backend\venv\Scripts\python.exe -m pytest` from the repo root.
    Bare `python` is a broken shim that reports phantom failures.
  - **Stop any running backend before running the suite.** A live backend holds
    the SQLite lock on the real spine.db and the suite stalls on
    test_memory_scope_api for half an hour instead of failing. Measured: 3m20s
    with no backend, 34m with one.
  - `npm run check:all` runs lint, typecheck, four guards, payload check and
    all three suites. It passes.
  - The API now REQUIRES A CREDENTIAL. Any curl against 8420 needs
    `-H "X-Zaram-Auth: $(cat backend/api-secret)"` or it answers 401.
  - Frontend dev server binds IPv6 — use localhost:5173, not 127.0.0.1.
  - Whatever is on port 8420 may be stale. Check build.commit_short.

MEASURED STATE (17 August, every number from a run)
  backend 2120 passed / 0 failed / 102 skipped · frontend 158 · Electron 48 ·
  typecheck clean · lint passes · guards pass. Working tree clean, branch
  pushed to origin/Zaram-V0.1.

THE THREE THINGS THAT MATTER MOST
  1. The installer is BUILT and UNVERIFIED on a clean machine.
     dist-electron/Zaram-0.1.0-x64.exe. Four separate reasons it could never
     have worked are now fixed. Only a machine that has never seen this repo
     can prove it, and that is the maintainer's action, not yours.
  2. The API has authentication now, but core/pairing.py — the credential a
     second DEVICE needs — is still complete, tested and uncalled.
  3. Ingestion by drop/paste/upload has a SERVICE LAYER AND NO ROUTES. It is
     committed and labelled unreachable on purpose. Routes + drop zone next.

WHAT TO BUILD, IN ORDER
  1. Ingestion routes + the Knowledge drop zone. The service layer is in
     backend/ingest/service_api.py (save_upload, save_text,
     stream_ingest_paths) and nothing calls it.
  2. Knowledge domains, scoping retrieval.
  3. The session/memory split — the structural fix behind rule 7d. The door
     check is a heuristic patching its absence and says so in its docstring.
  4. Obligations wired into ingest. Still the differentiator.
  5. The ambient surface's selection capture. NEEDS A DECISION FROM THE
     MAINTAINER FIRST: synthesised Ctrl+C, clipboard-only, or UI Automation.
     Each has a different privacy cost and it is their call.

TRAPS THIS CODEBASE HAS PAID FOR REPEATEDLY
  - A feature's tests can all pass while the feature cannot happen. Eleven
    complete, tested, unreachable modules have now been found. Before
    believing a feature works, check something calls it and a route serves it.
  - A blocklist fails open. Two defects this session were "reject the known
    bad shapes" where the fix was "require positive evidence".
  - A score built for ranking is not a score for deciding.
  - Never render an invented value.
  - Verify by seeing it work, not by a passing suite.
  - A test can assert a rule violation and pass for months. One demanded that
    a question be stored as a fact.
```

---

## What changed on 17 August

### Reliability of web search — the session's main thread

The maintainer reported unreliable answers about the world. Four separate
defects, each measured:

| Defect | Symptom | Fix |
|---|---|---|
| Semantic router bypassed `needs_search` | "Who is the current president" → Joe Biden, no sources. Routed `conversation` at **0.022** confidence, and `classify` returns the moment the semantic path answers | Union the two signals — a question can be conversational *and* need current facts |
| 300-char snippets were the whole evidence base | Prominent questions right, regional ones wrong. The model was handed three sentences that did not contain the answer and filled the gap | `deep_read.py` fetches the top three pages in parallel |
| Cloud model silently removed the search step | "Latest in AI" answered from a training cutoff. `search_applies_to` was a blanket local/cloud switch | Recency outranks the economy — no model knows last week |
| Prompt told the model to name its sources | "You mentioned a few sources… Let's review them:" followed by a bibliography. Every fact correct, nothing answered | Answer directly; markers are emitted, not suppressed |

**Egress consequence of deep-read**: reading a search result means fetching a
host the *search engine* chose, which the user cannot pre-allow. The first
attempt keyed the exemption off `source="internet.deep_read"` — a string the
caller supplies about itself, which is `X-Zaram-Client` again. `SearchReadGrant`
carries the exact URLs instead: GET only, no body, and it is consulted *after*
the policy so an explicit user denial still wins.

### Custody

**The API had no authentication at all.** Any process on the machine could read
the whole Spine. `ZARAM_API_SECRET` wins and packaged builds use only that —
minted per launch by the desktop host, passed to the backend in the spawn
environment and to the renderer over IPC, never in a command line. A file under
`data_dir()` is the development fallback and is documented as weaker.

Measured: `GET /memory` **401** without, **200** with.

Two follow-on defects, both found by running it: `matches()` returns early for
an absent header so the credential was never resolved and the dev file was
never written — a deadlock; and the file was not gitignored.

### The packaged app could never have started

Three separate reasons, all fixed, none visible from a checkout:

1. **322 backend `.py` files sealed inside `app.asar`** with no `asarUnpack`.
2. **`windows._mainWindow` does not exist** — threw inside `bootstrap()`, whose
   only handler logs. Everything after it never ran, including
   `backend.start()`. The shipped app never started its backend at all.
3. **The packaged proxy carried 10 of 21 prefixes.** `/egress`, `/export`,
   `/artifacts`, `/providers`, `/projects`, `/routing` all returned **200 and
   index.html**. The egress log and the exporter — rules 3 and 7 — were
   unreachable in the only build a stranger runs.

`test/packagedBackend.test.js` now inspects a real build from outside the
checkout, in plain Node, because Electron's patched `fs` is what hid it.

### Memory hygiene — rule 7d

The Spine held the user's own prompts as durable facts: "Say the single word:
ping", "Reply with exactly: OK", "WHars your name". The door check was a
blocklist and failed open. Now requires positive evidence a message asserts
something.

`GET /memory/traffic` reviews what got in before the fix. It proposes and never
applies — removal is `DELETE /memory/{id}`, by the user. **9 records were
deleted with the maintainer's explicit authorisation on 17 August**; the Spine
now holds 13 and reports 0 traffic.

### Also landed

- **The ambient surface** — global hotkey (`CommandOrControl+Shift+Space`) and
  a screen-edge handle. Verified running: hotkey registered, panel warm at
  640×420 hidden, handle 6px. Invoked, never passive, asserted at source level.
- **Citations open.** `SourcePanel` only handled `memory:` URLs, so every web
  citation dead-ended at "not a stored memory".
- **Structured extraction** — invoices, spreadsheets and decks from the
  conversation, refusing rather than inventing.
- The character (name/manner/voice), Spine export, one data directory, the
  DNS-rebinding `Host` guard, lint repair.

### Still open, deliberately

- **`/character` has routes and no interface.** A user cannot name it yet.
- **`core/pairing.py`** has no caller.
- **Ingestion service layer has no routes.**
- **`knowledge/retrieval.py::_hybrid`** blends and truncates on the blend — the
  bug class fixed elsewhere. Check reachability before spending time.
- **The uninstaller zips raw SQLite** rather than calling the real exporter.
- **`relevance: 0.0` on web citation chips.** Every web source reports 0.0
  while being cited. Not investigated; suspected to be the same
  ranking-vs-deciding confusion, in the reporting layer this time.
- **Two Electron main processes.** `npm run dev` runs a 46-line
  `desktop/src/main/index.ts`; the packaged app runs the 429-line
  `electron/main.js`. Everything in the latter — tray, shortcuts, backend
  launcher, static server, ambient surface — is never exercised in
  development. This is how the boot crash survived. Run the shipped one with
  `node_modules/.bin/electron electron/main.js`.
