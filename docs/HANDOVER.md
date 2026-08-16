# Handover — 16 August 2026

Paste the block below into a new session. It is written to be read cold.

The direction changed materially this session. `CLAUDE.md` was updated rather than
left to drift, so it remains the authority — but read the *What changed* section
at the bottom of this file before assuming anything from an older session still holds.

---

```
You are continuing work on Zaram (C:\Zaram), on branch Zaram-V0.1.

READ FIRST, IN THIS ORDER
  1. CLAUDE.md — the contract. Rules, scope, vocabulary. Authority on rules.
     Several rules CHANGED on 16 August. Read the embodiment section, rule 7g,
     the new rule 7j, "Custody, not only consent", and "The daily driver comes
     first" — all are new or reversed.
  2. docs/MILESTONES.md — "Current state — 16 August 2026" at the top.
  3. docs/UI-SPEC.md — the interface.

BEFORE RUNNING ANYTHING
  - Run pytest as `backend\venv\Scripts\python.exe -m pytest` from the repo root.
    Bare `python` on PATH is a broken shim and reports phantom failures.
  - Whatever is on port 8420 is probably stale. Confirm build.commit_short
    matches `git rev-parse --short HEAD` before believing any response.
  - The frontend dev server is on 5173 and binds IPv6 — use `localhost:5173`,
    not `127.0.0.1:5173`, or it will look down when it is up.
  - `npm run check:all` at the root now runs lint, typecheck, guards, payload
    check and both suites. It passes. If it does not, that is a regression.

MEASURED STATE (16 August, every number from a run)
  backend 2013 passed / 0 failed / 100 skipped · frontend 158 across 20 files ·
  Electron 48 · typecheck clean · lint passes · all four build guards pass ·
  the tree is committed, in thirteen pieces.

  AN INSTALLER EXISTS: dist-electron/Zaram-0.1.0-x64.exe, 186 MB. Rebuild with
  `npm run build:desktop -- --config.win.signAndEditExecutable=false` — the
  flag avoids an electron-builder symlink-privilege failure at the very end.

THE THREE THINGS THAT MATTER MOST
  1. NOTHING IN THIS REPO HAD EVER RUN electron/main.js — the file every
     installed copy runs. `npm run dev` starts a DIFFERENT main process
     (desktop/src/main, 46 lines, no tray/shortcuts/backend launcher/static
     server). The shipped one is 429 lines and reached only through
     electron-builder's extraMetadata.main. Its bootstrap was throwing on
     `windows._mainWindow` — a property WindowManager has never had — so
     backend.start() never ran and the app sat on a splash for ever. Fixed,
     and test/bootstrap.test.js now launches the real main process. Merging
     the two mains is the structural fix and has not been done.
  2. The local API still has NO AUTHENTICATION. A Host-header guard refuses
     DNS rebinding, so a web page cannot reach it. Any local process still can.
     A per-launch secret from the Electron host is the remaining half.
  3. The direction is DAILY DRIVER FIRST. The ambient surface now exists —
     hotkey and edge handle, invoked never passive — but it does nothing with
     what is on the screen. That decision is next.

WHAT TO BUILD, IN ORDER
  1. Run the installer on a machine that has never seen this repo. It is built;
     three separate reasons it could not have worked are now fixed.
  2. Decide how the ambient surface reads a selection — synthesised copy,
     clipboard, or UI Automation — then build it. Read CLAUDE.md's "ambient
     surface" section first: INVOKED, never passive, at any accuracy.
  3. The launch secret for the local API.
  4. A Settings panel for the character. GET/POST /character are served and
     nothing calls them.
  5. Free-tier keys in first run, with the data cost stated on the offer.
  6. Ingestion by drop, paste and upload — the parsers exist, the Knowledge
     surface cannot reach them.
  7. Knowledge domains, scoping retrieval.
  8. Deep-read for web search — the model still only sees 300-char snippets.
  9. Obligations wired into ingest.

TRAPS SPECIFIC TO THE BUILD
  - `npm run build:desktop` used to overwrite the repo's own package.json,
    leaving it with dependencies and nothing else. Caused by
    `directories.app: .`, now removed. If every `npm run` starts reporting
    "Missing script", that is what happened — `git checkout package.json`.
  - A backend prefix missing from electron/config.js's apiProxyPrefixes is not
    a 404 in a packaged build. It is a 200 with index.html.

TRAPS THIS CODEBASE HAS PAID FOR REPEATEDLY
  - A feature's tests can all pass while the feature cannot happen. Eight
    complete, tested, unreachable modules have been found. Before believing a
    feature works, check something calls it and a route serves it.
  - A score built for ranking is not a score for deciding. Membership,
    ordering and citation are three questions. Never merge them.
  - Never render an invented value. A constant standing in for a measurement
    reaches the UI and becomes a lie.
  - Verify by seeing it work, not by a passing suite.
```

---

## What changed on 16 August, in brief

Read this if you are picking the project up and an older document contradicts you.

### Rules that changed

| Rule | Was | Now |
|---|---|---|
| Embodiment | "not a personality: no name, no pronoun" | A user may name it, style it, voice it, bring their own VRM. It may never deny what it is when asked. Enforced by test. |
| 7g | No network call before consent, including update checks | Update checks asked once at first run, default yes. An unpatchable product holding contracts is not the safe option. Telemetry still prohibited. |
| 7j (new) | — | Connecting a provider *is* per-item consent for its host. Confirm-before-send is once per destination and data class, not per request. |
| Audience | "the wedge is freelancers" | Universal base, verticals as packs. The freelance layer is the *first pack*, not the wedge. |

### New sections in `CLAUDE.md`

- **Custody, not only consent** — the DNS rebinding hole, what the `Host` guard
  does and does not fix, `X-Zaram-Client` is a label not a credential, and
  `core/paths.py` owning the data directory.
- **The daily driver comes first** — five of eight daily jobs are already
  local-solvable; free API tiers are the bridge and are rule 1 as written;
  driving the consumer web apps is prohibited.
- **The ambient surface** — global hotkey and screen-edge handle, modelled on
  Superhuman Go, with the opposite data model. **Invoked, never passive.**
- **Business model** — give personalisation away, charge for continuity
  (encrypted sync across the user's own devices). Cost of goods is ~zero, which
  is what makes an uncapped free tier permanent. No avatar marketplace; no voice
  cloning.
- **Knowledge domains** — a retrieval scope, many-to-many, described, shareable.
  No seventh node. One memory, many domains.

### Code that landed

| What | Where | Tests |
|---|---|---|
| asar unpack + safe backend resolution | `electron/backend/backendLauncher.js`, `electron-builder.yml`, `scripts/check-installer-payload.mjs` | 4, guard mutation-tested |
| One data directory | `backend/core/paths.py` + six stores | 10 |
| Search relevance, RRF, diversity, temporality | `backend/runtimes/internet/relevance.py` | 24 |
| DNS rebinding guard | `backend/main.py` | 9 |
| Spine export (rule 7, was unreachable) | `GET /export`, `/export/manifest`, Settings | reuses `test_export.py` |
| The character — name, manner, voice | `core/identity.py`, `core/user_settings.py`, `GET/POST /character` | 21 |
| Lint config repair | `frontend/eslint.config.js` | lint passes |
| Structured extraction — invoice, spreadsheet, deck | `backend/artifacts/extract.py`, `runtimes/documents/runtime.py`, `ollama_engine.read_structured` | `test_structured_documents.py`, `test_extraction_across_models.py` |
| The shipped main process boots at all | `electron/main.js` | `test/bootstrap.test.js`, mutation-tested |
| Packaged origin proxies every backend prefix | `electron/config.js`, `check-proxy-covers-backend.mjs` | 2 in `staticServer.test.js`, guard mutation-tested |
| A build is inspected, from outside the checkout | — | `test/packagedBackend.test.js`, mutation-tested |
| The ambient surface — hotkey and edge handle | `electron/native/ambient.js`, `frontend/src/surfaces/` | 7 in `test/ambient.test.js` |

### Numbers worth not re-deriving

- Junk GitHub repo on an election query: relevance **0.052**, dropped. The
  correct Reuters article: **0.448**, cited. Floor **0.18**.
- Packaged spawn with `cwd` inside `app.asar`: **ENOENT**. Same exe, real cwd:
  **exit 0**.
- DNS rebinding without the `Host` guard: **200 and the whole Spine**. With it:
  **400**.
- Lint: **157 warnings → 0**, and all 157 were false — core ESLint rules running
  on TypeScript with no plugin.

### Still open, deliberately

- `GET/POST /character` are served and no interface calls them. A user cannot
  name it until Settings can — found at commit time, not left to be discovered.
- Obligations extract but nothing calls them. Still the differentiator.
- `core/pairing.py` (device pairing) has no caller but its own test.
- `knowledge/retrieval.py::_hybrid` blends `vector * 0.7 + bm25 * 0.3` and
  truncates on the blend — the same bug class fixed elsewhere, not yet fixed
  there. Check whether it is reachable before spending time on it.
- The uninstaller zips raw SQLite rather than calling the real exporter. The
  wording was corrected; a CLI exporter would be the proper fix.
