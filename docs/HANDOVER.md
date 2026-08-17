# Handover — 18 August 2026

Paste the block below into a new session. It is written to be read cold.

The previous handover (17 August) is superseded. Read *What changed* at the
bottom before assuming anything from an older session still holds.

---

```
You are continuing work on Zaram (C:\Zaram), on branch Zaram-V0.1.

READ FIRST, IN THIS ORDER
  1. CLAUDE.md — the contract. Rules, scope, vocabulary. Authority on rules.
  2. docs/HANDOVER.md — "What changed on 18 August".
  3. docs/MILESTONES.md — "Current state — 18 August 2026" at the top.
  4. docs/UI-SPEC.md — the interface.

BEFORE RUNNING ANYTHING
  - pytest as `backend\venv\Scripts\python.exe -m pytest` from the repo root.
    Bare `python` is a broken shim that reports phantom failures.
  - STOP ANY RUNNING BACKEND BEFORE RUNNING THE SUITE. A live backend holds
    the SQLite lock on the real spine.db and the suite stalls on
    test_memory_scope_api instead of failing. Measured: ~4m with no backend,
    34m with one. It looks exactly like a slow test and it is not.
  - THE API REQUIRES A CREDENTIAL. Any curl against 8420 needs
    -H "X-Zaram-Auth: $(cat backend/api-secret)" or it answers 401.
  - `npm run check:all` runs lint, typecheck, four guards, the payload check
    and all three suites. It passes. If it does not, that is a regression.
  - Frontend dev server binds IPv6 AND pins 5173 with strictPort — use
    localhost:5173, and expect a named failure rather than a drift to 5174.
  - Whatever is on port 8420 may be stale. Check build.commit_short against
    `git rev-parse --short HEAD` before believing any response.
  - THERE ARE TWO ELECTRON MAIN PROCESSES. `npm run dev` runs a 46-line
    desktop/src/main/index.ts; the packaged app runs the 429-line
    electron/main.js. Everything in the latter — tray, global shortcuts,
    backend launcher, static server, ambient surface — is never exercised in
    development, which is how a boot crash reached a shipped build. Run the
    real one with `node_modules/.bin/electron electron/main.js`.

MEASURED STATE (18 August, every number from a run)
  backend 2146 passed / 0 failed / 102 skipped · frontend 178 · Electron 48 ·
  typecheck clean · lint passes · guards pass.
  Run the Electron suite with NO ZARAM RUNNING. electron/main.js takes a
  single-instance lock, so the two bootstrap tests spawn an instance that
  quits instantly and assert against an empty log. Looks like a regression.

THE THREE THINGS THAT MATTER MOST
  1. The installer is BUILT and UNVERIFIED on a clean machine —
     dist-electron/Zaram-0.1.0-x64.exe. Four separate reasons it could never
     have started are now fixed. Only a machine that has never seen this repo
     can prove it, and that is the maintainer's action, not yours. Do not
     claim packaging is done. NOTE: that build predates the ingestion routes,
     so drop and paste are not in it — rebuild before testing them installed.
  2. Documents can be dropped, pasted and uploaded into Knowledge, and
     withdrawing a staged source now deletes the copies Zaram made after asking
     first. Both halves were verified in the running product, not by the suite.
     THE DESKTOP APP MINTS A FRESH API CREDENTIAL EVERY LAUNCH. A browser tab
     at localhost:5173 therefore 401s on everything and the interface reports
     "Zaram engine not running" about a healthy backend. That is correct
     behaviour in a tab and it cost the most time this session — test in the
     Electron window, launched with node_modules/.bin/electron electron/main.js.
  3. core/pairing.py — the credential a second DEVICE needs — is complete,
     tested and uncalled. The API itself has authentication.

WHAT TO BUILD, IN ORDER
  1. Knowledge domains, scoping retrieval.
  2. The session/memory split — the structural fix rule 7d actually needs.
     The door check in ExecutionEngine._carries_new_information is a heuristic
     standing in for it and says so in its own docstring.
  3. Obligations wired into ingest. Still the differentiator.
  4. The ambient surface's selection capture. ASK THE MAINTAINER FIRST:
     synthesised Ctrl+C, clipboard-only, or UI Automation. Each carries a
     different privacy cost and it is their call, not a default to pick.

KNOWN OPEN GAPS, DELIBERATELY
  - The orb's colours: speaking and listening are 29 degrees apart in hue, and
    idle and thinking are the same two hues with dominance swapped. All five
    states sit in a 111 degree arc. Proposed fix is to stop using hue as the
    state channel, since cyan and violet already mean local and cloud, and let
    motion character carry state. Not started.
  - Ctrl+S and Ctrl+O are still swallowed by the orb debug shortcuts, the same
    bug class as the Ctrl+C one that was fixed.
  - /character has routes, tests, and no interface. A user cannot name it yet.
  - relevance: 0.0 on every web citation chip while being cited. Observed,
    not investigated. Suspected to be ranking-versus-deciding again, in the
    reporting layer this time.
  - knowledge/retrieval.py::_hybrid blends vector*0.7 + bm25*0.3 and truncates
    on the blend — the bug class fixed elsewhere. Check it is reachable first.
  - The uninstaller zips raw SQLite rather than calling the real exporter.

TRAPS THIS CODEBASE HAS PAID FOR REPEATEDLY
  - A feature's tests can all pass while the feature cannot happen. Twelve
    complete, tested, unreachable modules have now been found. Before
    believing a feature works, check something calls it and a route serves it.
  - A blocklist fails open. Require positive evidence instead.
  - A score built for ranking is not a score for deciding. Membership,
    ordering and citation are three questions; never merge them.
  - An operation that is correct for a whole source is wrong for part of one.
    "Replace this source's rows" is right for a folder scan and destroyed an
    earlier drop's rows — and with them the fact ids rule 4 needs.
  - Never render an invented value.
  - A test can assert a rule violation and pass for months.
  - Verify by seeing it work, not by a passing suite.
```

---

## What changed on 18 August

### Ingestion by drop, paste and upload — the routes exist now

`backend/ingest/service_api.py` had carried `save_upload`, `save_text` and
`stream_ingest_paths` — complete, commented, called by nothing. Two routes
close it:

| Route | Body | Notes |
|---|---|---|
| `POST /ingest/upload` | multipart, repeated `files` | Bytes written **before** the stream starts; a `StreamingResponse` body runs after the request is gone |
| `POST /ingest/text` | `{text, name}` | Written as a `.txt` and read by the same parser, so there is one chunker and one grader |

Both stream the NDJSON the folder scan already emits. A second event shape
would be a second set of split-chunk bugs, and `consume()` in `ingestClient.ts`
is now the single reader for all three ways in.

Uploads land in one `uploads` directory under `data_dir()`, so they are one
source with one policy — rule 5 asks about a *place* once, not once per file.

### The defect this found: a second drop deleted the first

`record_outcomes` replaces a source's rows wholesale. That is right for a
folder scan, which saw every file in its source. Every drop lands in the same
shared uploads directory, so the second drop deleted the first drop's row —
and `fact_ids` live on that row.

The consequence is a rule 4 failure, not an inconvenience: the user presses
*"Forget this folder and everything Zaram learned from it"*, is told it worked,
and every fact from every earlier drop stays in the Spine, still recallable,
with nothing anywhere able to reach it.

`merge_outcomes` records per *path*. Re-reading one file still replaces its own
row, so "what is wrong now" holds per file; every other row survives with its
fact ids. Found by the second assertion of a route test — two files kept, one
file listed.

A refused upload is now **all or none** for the same reason: nine saved files
and a 413 on the tenth would leave bytes nothing records, nothing can cite and
no deletion can reach.

### Verified in the running product

Live backend, `localhost:5173`, through the interface rather than by curl:

- a file **dropped** onto Knowledge → indexed, listed with its character count
- a **paste** → the offer appeared with the real text shown back, was named
  *client minutes*, and became `client minutes.txt`, 108 characters, indexed
- a **folder** dropped → *"A folder can't be dropped in yet — put its path in
  the field below and press Index"*, nothing indexed
- four documents under one `uploads` source, reporting **Local only**
- *Forget this folder* → the Spine went from 17 records back to **13**, its
  state before the session, and the source row disappeared

That last step is the merge fix demonstrated: the three earlier drops' facts
came out, which is exactly what the bug would have prevented.

### The gap it opened, and it is deliberate

Forgetting the uploads source leaves **Zaram's copies of the documents on
disk**. Four files had to be deleted by hand after the verification above.

For a scanned folder, not deleting is correct — those are the user's originals.
For uploads it is not: the file is a copy Zaram made, and the button promises
"everything Zaram learned from it". Fixing it means deleting document files, so
it is not a change to make quietly in passing. It is the first item in the list.

### Interface

`KnowledgeWorkspace` gained the drop target, a *Choose files* button and a
paste handler on the surface. Shaped by rule 7h: files on the clipboard go
straight in, because the user copied a file and there is nothing to decide;
text is **offered**, with the real text shown back and a 40-character floor,
because a short paste is far more often a path meant for the folder field. The
paste listener ignores inputs, textareas and contenteditable, so pasting a path
into the folder field does not also offer to index the path.

### The interface reported the engine down while it answered 200

`installApiCredential` resolved Vite's build-time value first and consulted the
desktop host only when that was empty. Both are present at once in the case
nobody had run — the real `electron/main.js` loading the Vite dev server — and
they disagree: `main.js` mints a fresh secret per launch and passes it over IPC,
while Vite baked in whatever `backend/api-secret` held at boot, a file the
backend stops writing once `ZARAM_API_SECRET` is set. The stale one won.

Measured: **401 on everything** before, **zero 401s** after. The bridge is
authoritative because the process on the other end minted the value.

**A browser tab still shows this, and correctly** — it has no host to ask. This
is now the most expensive misunderstanding in the repo; test in the Electron
window.

### Ctrl+C was deleting Copy, not shadowing it

`useShortcuts` calls `preventDefault()` on every match outside a text field, and
Toggle Chat was bound to Ctrl+C — so Copy did not work on any of the six
surfaces, including the three whose whole job is showing facts and citations
someone would want to copy. Now **Alt+C**.

Alt chords match on physical position, because macOS Option is a compose key:
⌥C emits `key: "ç"`, so a chord compared on `event.key` would have been printed
on the keycap and never fired — the Ctrl+K/Win+K defect the matcher already
carries a comment about, arriving by a second route. The test helper was
synthesising an idealised event and would have passed either way; it now emits
what the platform's keyboard emits.

`Ctrl+S` and `Ctrl+O` remain claimed by the orb debug shortcuts. Same bug class,
left for a decision.

### The orb: reduced motion, and periods that could never resolve

`UI-SPEC` requires the gate and `LivingOrb` had none across seven infinite
animations. Colour still transitions under reduced motion — less movement, not
less information — and resting poses are the value each loop pauses at, so the
listening ring holds at 0.7 rather than the array's 0.

The busy feeling was arithmetic, not speed: ten particles ran at
`3.5 + p.delay`, ten distinct periods, so the field drifted through every phase
relationship and never repeated. One 8s period with staggered delays looks the
same and settles. Every live idle period is now a multiple of 4s and the
composite repeats every **8s** instead of never. `ring1Duration` and
`ring2Duration` were deleted — set in all five states and read by nothing.

**Eleven of fifteen orb components were imported by nothing, and are deleted**
— 464 lines. This had produced a wrong finding in a written assessment: "the
core of the orb is the cloud accent at rest" is true of `OrbCore`'s source and
false on screen, because `OrbCore` never mounted. Config was read and assumed to
render — the trap this file has warned about for two sessions, walked into while
writing about it. `settle` and `settleAll` went with them rather than becoming
two dead functions in place of eleven dead components.

Two colour findings stand, both in `STATE_CONFIG`, which does render: speaking
and listening are **29° apart** in hue, and idle and thinking are the same two
hues with dominance swapped. Proposed fix under the orb entry in `MILESTONES`.

### Also landed

One `SurfaceHeader` for all six surfaces, replacing six copies that had drifted
to `pb-3` against `pb-4` with Project's title in the wrong typeface. The Zaram
mark on the landing, quiet and inert. `useIsReducedMotion` returning a real
boolean.

### Still open from 17 August, unchanged

`/character` has no interface · `core/pairing.py` has no caller ·
`knowledge/retrieval.py::_hybrid` truncates on a blend · `relevance: 0.0` on
web citation chips · the uninstaller zips raw SQLite · two Electron main
processes.
