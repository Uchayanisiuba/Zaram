# Handover — 18 August 2026

Paste the block below into a new session. It is written to be read cold.

The previous handover (17 August) is superseded. Read *What changed* at the
bottom before assuming anything from an older session still holds.

---

```
You are continuing work on Zaram (C:\Zaram), on branch Zaram-V0.1.

READ FIRST, IN THIS ORDER
  1. CLAUDE.md — the contract. Rules, scope, vocabulary. Authority on rules.
  2. docs/HANDOVER.md — "What changed on 18 August", below the block.
  3. docs/MILESTONES.md — "Current state — 18 August 2026" at the top.
  4. docs/UI-SPEC.md — the interface.

BEFORE RUNNING ANYTHING
  - pytest as `backend\venv\Scripts\python.exe -m pytest` from the repo root.
    Bare `python` is a broken shim that reports phantom failures.
  - STOP ANY RUNNING BACKEND BEFORE THE PYTHON SUITE. A live backend holds the
    SQLite lock on the real spine.db and the suite stalls on
    test_memory_scope_api instead of failing. Measured: ~3m clean, 34m with a
    backend up. It looks exactly like a slow test and it is not.
  - STOP ZARAM BEFORE THE ELECTRON SUITE. electron/main.js takes a
    single-instance lock, so the two bootstrap tests spawn an instance that
    quits immediately and assert against an empty log. Two failures that look
    like a regression and are not.
  - `npm run check:all` runs lint, typecheck, four guards, the payload check
    and all three suites. It passes. If it does not, that is a regression.
  - Frontend dev server binds IPv6 and pins 5173 with strictPort — use
    localhost:5173, and expect a named failure rather than a drift to 5174.

THE CREDENTIAL TRAP — this cost more time than any bug this session
  The desktop app MINTS A FRESH API SECRET EVERY LAUNCH and passes it to its
  renderer over IPC. So:
  - A browser tab at localhost:5173 401s on everything, and the interface
    correctly reports "Zaram engine not running" about a perfectly healthy
    backend. Nothing is broken. Test in the Electron window.
  - curl against 8420 needs -H "X-Zaram-Auth: $(cat backend/api-secret)", and
    that file only matches when the backend was started STANDALONE
    (`cd backend && venv/Scripts/python.exe main.py`). Against the Electron
    app's backend the file is stale and every curl 401s.
  - To drive the real UI in a browser: run the backend standalone, not via
    Electron. To exercise tray / shortcuts / ambient / packaging: run Electron.
  - Whatever is on 8420 may be stale code — it does not hot-reload. Restart it
    after backend edits, and check build.commit_short before believing it.

TWO ELECTRON MAIN PROCESSES
  `npm run dev` runs a 46-line desktop/src/main/index.ts; the packaged app runs
  the 429-line electron/main.js. Everything in the latter — tray, global
  shortcuts, backend launcher, static server, ambient surface — is never
  exercised in development, which is how a boot crash reached a shipped build.
  Run the real one: `node_modules/.bin/electron electron/main.js`.

MEASURED STATE (18 August, every number from a run)
  backend 2184 passed / 0 failed / 102 skipped · frontend 178 · Electron 48 ·
  typecheck clean · lint passes · guards pass.
  HEAD 3d9db72, working tree clean.
  16 COMMITS AHEAD OF origin/Zaram-V0.1 AND NOT PUSHED. Ask before pushing.

THE THREE THINGS THAT MATTER MOST
  1. The installer is BUILT and UNVERIFIED on a clean machine —
     dist-electron/Zaram-0.1.0-x64.exe. Four separate reasons it could never
     have started are fixed. Only a machine that has never seen this repo can
     prove it, and that is the maintainer's action, not yours. Do not claim
     packaging is done. That build PREDATES everything below — rebuild before
     testing any of it installed.
  2. Knowledge domains narrow recall, and /chat cannot ask inside one yet.
     The scope works and is proven at the retriever; the conversation has no
     picker, so nothing in the chat path passes `only_ids`. Configurable, not
     yet usable from a question. This is item 1 below.
  3. core/pairing.py — the credential a second DEVICE needs — is complete,
     tested and uncalled. The API itself has authentication.

WHAT TO BUILD, IN ORDER
  1. Let a question be asked inside a knowledge domain. Small: `only_ids` is
     already a parameter on MemoryRuntimeImpl.retrieve, and
     knowledge/domain_recall.py::describe already writes the phrase a reply
     ends with ("answered from your Investing domain"). Needs a picker in the
     conversation and the reply saying which domain it read from. Rule:
     disabled capabilities are visible, not silent — a question answered from
     one domain did not look at the rest, and must say so.
  2. The session/memory split — the structural fix rule 7d actually needs.
     The door check in ExecutionEngine._carries_new_information is a heuristic
     standing in for it and says so in its own docstring.
  3. Obligations wired into ingest. Still the differentiator.
  4. The ambient surface's selection capture. ASK THE MAINTAINER FIRST:
     synthesised Ctrl+C, clipboard-only, or UI Automation. Each carries a
     different privacy cost and it is their call, not a default to pick.

KNOWN OPEN GAPS, DELIBERATELY
  - /chat cannot ask inside a domain. Item 1 above.
  - The orb's colours. Speaking and listening are 29 degrees apart in hue
    (emerald against cyan — the pair that alternates fastest in a voice
    exchange), and idle and thinking are the same two hues with dominance
    swapped, so "is it working?" is carried by rate alone. All five states sit
    inside a 111 degree arc. Proposed fix: stop using hue as the state channel
    — cyan and violet already mean local and cloud — and let motion character
    carry state instead. Inward ripple for listening, outward pulse for
    speaking, churn for thinking, near-still for idle. NEEDS A GPU MEASUREMENT
    FIRST: a shader would run permanently beside a resident model and that cost
    is unmeasured. Not started.
  - Ctrl+S and Ctrl+O are still swallowed by the orb debug shortcuts, which
    force an orb state by hand. Same bug class as the Ctrl+C defect that was
    fixed: useShortcuts calls preventDefault() on every match outside a text
    field, so it deletes Save and Open rather than shadowing them.
  - /character has routes, tests, and no interface. A user cannot name it yet.
  - relevance: 0.0 on every web citation chip while being cited. Observed, not
    investigated. Suspected ranking-versus-deciding again, in the reporting
    layer this time.
  - knowledge/retrieval.py::_hybrid blends vector*0.7 + bm25*0.3 and truncates
    on the blend — the bug class fixed elsewhere. Check it is reachable first;
    this repo has a habit of hiding dead code that looks live.
  - The uninstaller zips raw SQLite rather than calling the real exporter.

TRAPS THIS CODEBASE HAS PAID FOR REPEATEDLY
  - A feature's tests can all pass while the feature cannot happen. Twelve
    complete, tested, unreachable modules have been found, and eleven dead orb
    components were deleted this session. Before believing a feature works,
    check something calls it and a route serves it.
  - THIS APPLIES TO YOUR OWN ANALYSIS. A written assessment this session
    claimed the orb's core was painted with the cloud accent at rest. True of
    OrbCore's source; false on screen, because OrbCore never mounted. Config
    was read and assumed to render.
  - An empty set is not an absent one. frozenset() is falsy, so `if only_ids`
    widens a domain holding nothing to the entire Spine. Use `is not None`
    wherever "none selected" and "nothing matches" are different answers.
  - An operation correct for a whole source is wrong for part of one.
    "Replace this source's rows" is right for a folder scan and destroyed an
    earlier drop's rows — and with them the fact ids rule 4 needs.
  - A boundary enforced per code path has a hole per code path. Scope and
    domain filters both live at ONE point in runtimes/memory/retrieval.py,
    after every strategy, because _vector_search bypasses the store's filters.
  - A blocklist fails open. Require positive evidence instead.
  - A score built for ranking is not a score for deciding. Membership,
    ordering and citation are three questions; never merge them.
  - Never render an invented value.
  - A test can assert a rule violation and pass for months.
  - Verify by seeing it work, not by a passing suite.
```

---

## What changed on 18 August

Sixteen commits. Two features, five defects, one deletion — and one wrong claim
of my own, corrected below because it is the most useful thing here.

### Ingestion by drop, paste and upload

`backend/ingest/service_api.py` had carried `save_upload`, `save_text` and
`stream_ingest_paths` — complete, commented, called by nothing. Two routes close
it:

| Route | Body | Notes |
|---|---|---|
| `POST /ingest/upload` | multipart, repeated `files` | Bytes written **before** the stream starts; a `StreamingResponse` body runs after the request is gone |
| `POST /ingest/text` | `{text, name}` | Written as a `.txt` and read by the same parser, so there is one chunker and one grader |

Both stream the NDJSON the folder scan already emits, and `consume()` in
`ingestClient.ts` is the single reader for all three ways in — a second event
shape would be a second set of split-chunk bugs.

Knowledge gained a drop zone, a *Choose files* button and a paste handler. Rule
7h shapes the paste: files on the clipboard go straight in, because the user
copied a file and there is nothing to decide; text is **offered**, with the real
text shown back and a 40-character floor, since a short paste is far more often
a path meant for the folder field.

A dropped **folder** resolves its real filesystem path and goes to the folder
route the text field already uses. `desktopPathOf` is the single place that knows
how to ask, so Electron 32 removing `File.path` changes one function.

### Two defects the routes exposed

**A second drop deleted the first.** `record_outcomes` replaces a source's rows
wholesale — right for a folder scan, wrong for a drop, since every drop lands in
one shared uploads directory. `fact_ids` live on those rows, so the user would
press *"Forget this folder and everything Zaram learned from it"*, be told it
worked, and every fact from every earlier drop would stay in the Spine, still
recallable, unreachable. `merge_outcomes` records per path.

**Withdrawing uploads left the documents on disk.** The facts went, the rows
went, the copies stayed — four had to be deleted by hand after one verification.
Now three conditions guard the delete: the outcome belongs to the withdrawn
source, that source *is* the uploads directory, and the stored path **resolves
inside it**. The third is not a formality — an outcome's `path` is stored data,
and following it to a delete without checking where it lands is how "Zaram
deleted my file" happens. A staged source asks before deleting; a scanned folder
is never touched and is not asked about.

### Knowledge domains

A named retrieval scope over the user's own sources. `domain_recall.py` resolves
domain → sources → outcomes → fact ids, and `MemoryQuery.only_ids` narrows recall
to that set — enforced at the same single point as rule 7i's scope, with a test
that fakes a vector hit to prove it did not get its own hole.

Many-to-many and never a tree; a required one-line description because routing
reads it; one memory, many domains, so deleting a domain deletes a lens and not
facts. Withdrawing a source unlinks it from every domain that held it.

Verified live: a domain created through the interface resolved to exactly **one
reachable fact out of a 13-record Spine**.

**It is not wired into `/chat`.** See item 1.

### The interface said the engine was down while it answered 200

`installApiCredential` resolved Vite's build-time value first and asked the
desktop host only if that was empty. Both exist at once when the real
`electron/main.js` loads the Vite dev server, and they disagree. The stale one
won and everything 401'd. Zero 401s after. See THE CREDENTIAL TRAP above — this
is the single most confusing behaviour in the repo, and it is now correct rather
than fixed.

### Ctrl+C was deleting Copy, not shadowing it

`useShortcuts` calls `preventDefault()` on every match outside a text field, and
Toggle Chat was bound to Ctrl+C — so Copy did not work on any of the six
surfaces, including the three whose whole job is showing facts and citations.
Now **Alt+C**, matched on physical position because macOS Option is a compose
key: ⌥C emits `key: "ç"`, so a chord compared on `event.key` would have been
printed on the keycap and never fired.

### The orb, and a wrong claim of mine

`UI-SPEC` requires a `prefers-reduced-motion` gate and `LivingOrb` had none
across seven infinite animations. Fixed, with colour still transitioning —
reduced motion means less movement, not less information.

The restlessness was arithmetic: ten particles ran at `3.5 + p.delay`, ten
distinct periods, so the field never repeated. Every live idle period is now a
multiple of 4s and the composite repeats every **8s** instead of never. The pulse
is unchanged for anyone who has not asked for less motion.

**Eleven of fifteen orb components were imported by nothing, and are deleted** —
464 lines. Before deleting them I wrote an assessment claiming the orb's core was
painted with the cloud accent at rest. That is true of `OrbCore`'s source and
false on screen, because `OrbCore` never mounted. I read config and assumed it
rendered — this repository's signature failure, committed against its own
analysis rather than against a feature. `settle`/`settleAll` went with them
rather than becoming two dead functions in place of eleven dead components.

Two colour findings stand and are unfixed; see the gap list.

### Also landed

One `SurfaceHeader` for all six surfaces, replacing six copies that had drifted
to `pb-3` against `pb-4` with Project's title in the wrong typeface. The Zaram
mark on the landing, quiet and inert — `ZaramMark` argues it should be absent,
and that argument shaped it rather than excluding it. `useIsReducedMotion`
returning a real boolean instead of `boolean | null`.
