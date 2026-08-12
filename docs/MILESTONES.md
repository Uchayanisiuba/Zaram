# Zaram — Milestones

Ordered. Each has an acceptance criterion phrased as something you can *see*, not
something that passes. "Tests green" is not done; "I ran it and watched X happen" is.

Read with `CLAUDE.md` (the contract) and `docs/UI-SPEC.md` (the interface).

**This file is the handoff.** A new session should be able to read it and know
where the work stands without being told. Keep the Current state block below
accurate — it is the first thing anyone reads.

---

## Current state — 12 August 2026

> ### The session is committed, on `Zaram-V0.1`, unpushed.
>
> Committed in coherent pieces, re-verified green before staging rather than on
> the previous session's word. Read the two "found by running it" sections below
> before debugging anything, because four of the defects fixed here were
> invisible to a passing suite.
>
> **M10 is finished and cloud generation now sends**, after a person says it
> may. **M11 has an installer**: `Zaram-0.1.0-x64.exe`, 186 MB, plus a portable
> build — the NSIS step had never once completed, because an unset signing
> variable killed it after packaging had already succeeded. `Zaram.exe` launches
> its own bundled Python and reaches `kernel: online`.
>
> **The only thing left in M11 is running it somewhere that has never seen this
> repo**, which cannot be done from here.
>
> Suites, measured 12 August: **1647 backend passed / 0 failed**, 76 skipped,
> 3m29s. **103 frontend** across 14 files. **30 Electron**. Every skip names its
> reason — the voice and mic extras are absent from this shell and the scale
> eval is opt-in behind `ZARAM_SCALE_EVAL=1`. An earlier note here read "1714 /
> 9 skipped" against the same 1723 collected: the same suite on a machine that
> had the extras installed. **Read the skip count as a fact about the
> environment, not the code**, and `-rs` prints why.

### The lesson this session kept teaching

**A feature's tests can all pass while the feature cannot happen.** It happened
twice, in unrelated places, and both times the only thing that could see it was
starting the product and asking it to do the thing.

Confirm-before-send was complete: the gate blocked, the question appeared, an
approval released the thread, an edit reached the wire — all asserted. It could
not work. `ChatRouter._kernel_stream` was an `async def` generator driving the
engine's *synchronous* generator with a plain `for`, so every blocking step ran
on the event loop thread. When the gate blocked on its confirm hook the whole
backend stopped answering, `/egress/pending` could not be served, the dialog
could never appear, and the only reachable outcome was a two-minute timeout with
`/health` dead throughout. The gate, the confirmations, the engine and the
endpoints were each correct in isolation and still are. **The defect lived in
the seam.**

The second: the packaged installer would have shipped `spine.db` and
`egress.db`. Every unit test was green. Nothing tests what a glob matches.

Both are now covered — `backend/tests/test_confirm_does_not_freeze.py` and
`scripts/check-installer-payload.mjs` — and both were verified by reintroducing
the defect and watching the new test fail.

### M10 — confirm before send, done and driven

`GET /egress/pending`, `GET /egress/pending/{id}`, `POST /egress/pending/{id}`
taking `{approved, body}`. Answering something already decided is a 404, so a
double-click cannot approve a second send. `get_pending()` / `set_pending()` sit
beside `get_gate()`; the bootstrapper wires
`gate.set_confirm(lambda r: get_pending().ask(r))` — **resolved per call, not
bound once**, or a later `set_pending` leaves the gate asking a store nothing is
watching. `cancel_all()` runs first at shutdown, before anything awaits.

`ConfirmSendDialog` is mounted in the shell on every surface, because a tool can
reach the network from anywhere. It polls at 1s while something is in flight and
renders nothing otherwise. Recalled facts become removable chips by **parsing
the outbound body** for the engine's `[M1] (date) …` lines — parsed rather than
handed over, so the chips cannot drift from the text they describe. A body it
cannot parse gets the plain decision and **no chips**, never invented ones.

**Verified against a running product.** A fake OpenAI-compatible provider on the
LAN address (non-loopback, so the gate treats it as egress), a real cloud-routed
chat, the dialog on screen with three genuinely recalled facts. Struck the one
holding the day rate, approved, and compared all three: preview, append-only
log, and what arrived at the destination — **byte-identical at 1650 bytes, and
the struck fact in none of them.**

Two more defects fell out of that run:

* **The log said the user refused when nobody was asked.** A timeout was
  recorded as "you chose not to send this" — a permanent, tamper-evident record
  of a decision that never happened. `EgressRequest.refusal_reason` now carries
  the truth: nobody answered, Zaram was shutting down, or it could not ask.
* **Discovery asked for `/v1/v1/models`.** The engine normalises a trailing
  `/v1`; the discoverer did not. Given `ZARAM_OPENAI_ENDPOINT` written the way
  providers print it, discovery 404s, no cloud model is known, and routing
  silently sends every message local. Chat still works, which is what makes it
  hard to notice.

A guard sits under the freeze: asked from the event-loop thread, the confirm
hook refuses in milliseconds and says why, rather than freezing the server that
would have answered it. **The call site is fixed; the guard is so the next one
costs a refusal instead of the product.**

**One clause of M10 was deliberately not built.** The acceptance line asks for
edits "written through as supersessions". Striking a fact in the dialog changes
*that request only*. "Do not send my day rate to this provider" and "this fact
is wrong" are different statements, and writing one through as the other would
delete a correct fact at the exact moment the user is being careful. Reasoning
in the M10 section below.

### The API was published to the network

`main.py` bound `0.0.0.0` — every interface — and `backendLauncher.js` launches
the packaged app through exactly that path. **No endpoint has authentication.**
On any café, hotel or shared-office network, anyone reaching port 8420 could
read the whole Spine through `/memory`, read the egress log, set a host to
`allow` through `/egress/policy`, and approve a pending confirmation.

Now `LISTEN_HOST = "127.0.0.1"`, **not configurable** — a setting that reopened
it would be set once while debugging and never unset, and the failure is silent
because everything keeps working. Verified live: loopback answers, the LAN
address refuses, `netstat` shows `127.0.0.1:8420`.

**How it happened is the more useful half.** `test/backendLauncher.test.js`
asserted the launcher passed `--host 127.0.0.1`. The launcher changed to run
`main.py`, the test started failing, and **nothing in this repo ran it** — there
was no script wired to `test/`. Twenty-six Electron tests existed, two were
failing, and the failing one encoded the loopback guarantee.

`npm test` now runs them and both failures are fixed. The second was
`staticServer`, whose fake returned `arrayBuffer()` from when the proxy
buffered; the proxy streams now, because `/chat` emits tokens as they are
generated. **Production code was correct in both cases** — the tests had rotted
where nobody could see them. The replacement assertion grades the *property*
rather than the argument list, so it survives either launcher shape.

### M11 — packaging

**The installer had never been buildable.** electron-builder exited before
packaging anything, on missing `name` and `version` in `package.json` and on
`electron` / `electron-builder` sitting in `dependencies`. All fixed.
`build:desktop:portable` also never returned to the repo root after
`cd desktop`.

**What it would have shipped is the finding that matters.** The config included
the backend as one glob with four exclusions:

* `!backend/.venv` does not match `backend/venv`, which is what the directory is
  actually called here. **376 MB**, plus 61 MB of `audio_cache` and
  `audio_output`.
* Nothing excluded `spine.db`, `egress.db` (with its `-wal` and `-shm` sidecars,
  which hold the most recent writes), `artifacts.db`, `projects.db`,
  `egress-policy.json`, or `backend/generated/`. **The maintainer's memory,
  their record of everything that has ever left the machine, their invoices, and
  their per-host privacy rules — all on disk today, all matching the glob.**

The backend is now included by **allow-list**. That is the opposite polarity to
`pyproject.toml`'s argument about test collection, and deliberately: a stale
exclusion there collects an extra test, while a missing exclusion here publishes
private data. Two checks hold it — `scripts/check-installer-payload.mjs` runs
inside `build:desktop` with the real `minimatch` and exits non-zero, and
`backend/tests/test_installer_payload.py` catches a bad edit in the suite long
before anyone builds.

**Python is bundled and the packaged app runs.** `resolvePythonCommand` resolves
`ZARAM_PYTHON` → bundled runtime → dev venv, and **PATH is deliberately not a
fallback**: finding a stranger's Python 3.9 is worse than finding none, because
it fails later and reads as a broken product. The runtime is found via
`resourcesPath` when packaged, since the backend is inside `app.asar` and an
archived file cannot be executed.

**Relocatable CPython, not PyInstaller — the product already decided this.**
`backend/ingest/quality.py` tells the user "pip install zaram[ingest]". Voice,
mic and OCR are extras installed after the product is running, on its own
instruction, and **you cannot pip install into a frozen bundle.**

CPython 3.11.9 from python-build-standalone, SHA-256 verified, base
requirements only. **401 MB runtime, 679 MB unpacked app.**
`dist-electron/win-unpacked/Zaram.exe` launches
`resources/runtime/python.exe` — confirmed by process path — reaching
`kernel: online` in about five seconds, with voice degrading exactly as
designed: *"Kokoro package unavailable … (speech disabled, chat unaffected)"*.
The asar carries 323 backend entries, 271 of them `.py`, and **no database, no
venv, no generated document, no policy file and no tests** — verified by listing
the archive, not by trusting the payload checker.

**Dev tooling is out of the base install: 83.5 MB, measured.** An earlier note
guessed "probably 30–40 MB" and was under by more than half — mypy alone is
42.1 MB, ruff 32.9 MB. Now `backend/requirements-dev.txt`.

**Jinja2 stays where it is.** Not a leftover: spaCy and torch both require it
unconditionally. Answered from declared metadata, which is trustworthy in that
direction — a package *declaring* a dependency is evidence; nothing declaring
one is not, which is the misaki/spaCy trap.

**The installer icon was one clone away from being wrong.** `electron-builder.yml`
names no icon at all — electron-builder finds `build/icon.ico` by convention —
and `/build/` was gitignored. On this machine the icon is present because the
brand generator wrote it here; on a fresh clone there is none, and the build
does not fail, it just produces an installer wearing the default Electron icon.
`build/icon.ico` is now tracked, for the same reason the brand PNGs under
`frontend/public/` are: **the build must not depend on someone having run the
generator first.** This is the same class as the two above — a check that
passes locally and means nothing anywhere else — and it sits on the one path
that matters, which is a stranger installing this.

**The frontend suite had no way to run it.** 14 vitest files, 103 tests, vitest
in `devDependencies`, and no `test` script anywhere pointing at them: reachable
only by knowing to type `npx vitest run`. Exactly the shape of the Electron
`test/` directory that hid a failing loopback assertion for who knows how long.
`npm test` at the root now runs both JS suites, and `npm run test:backend`
encodes the venv interpreter so the wrong-`python` trap costs nothing.

**The installer exists.** `Zaram-0.1.0-x64.exe`, **186 MB**, NSIS, plus
`Zaram-Portable-0.1.0-x64.exe` beside it — from 679 MB unpacked, most of which
is the 410 MB Python runtime. Built unsigned, which `check:signing` permits for
a development build and refuses under `ZARAM_RELEASE=1`.

**Why it had never been built is the finding.** `electron-builder.yml` set
`certificateSubjectName: "${env.ZARAM_SIGN_SUBJECT}"`, with a comment claiming
an unset variable resolves to empty and signing is skipped. It resolves to
nothing of the kind — the literal reaches the signer, which looks for a
certificate by that name and fails:

```
⨯ Cannot find certificate ${env.ZARAM_SIGN_SUBJECT}, all certs:
```

So **no machine without a code-signing certificate could produce an installer**,
which is every machine today. What hid it is *where* it fails: packaging
succeeds, `win-unpacked` is written, `Zaram.exe` starts — and the build dies
afterwards, signing the *uninstaller*. Both earlier statements were true at
once and nobody connected them.

`scripts/build-installer.mjs` injects the subject only when there is one, which
YAML cannot express, and `check:signing` now refuses any `${env.}` macro in the
config. **That check runs before the development-build exit, unlike every other
check in the file** — every one of them was release-only, which is exactly how
the setting that made an unsigned build impossible was never examined on an
unsigned build. A check that only runs where the defect isn't is not a check.

The installed tree was verified directly rather than through the payload globs:
no `.db`, no `-wal` or `-shm` sidecar, no `egress-policy.json`, no venv, no
generated documents, and nothing matching inside `app.asar`.

**Still missing from M11's acceptance:** a run on a machine that has never seen
this repo. That is now the whole of it, and it is the one part that cannot be
done from here.

### Code signing — decided, prepared, not purchased

`docs/CODE-SIGNING.md` is the runbook. **OV, and not EV later either.**

An earlier version of that document said EV buys immediate SmartScreen
reputation. **That is false**, and it is worth recording as false because it is
the most repeated code-signing advice there is. Microsoft, checked 12 August:
*"EV certificates no longer bypass SmartScreen … Paying a premium for EV solely
to avoid SmartScreen warnings is no longer justified."* Their table gives OV and
EV the same first-download behaviour: a warning until reputation accrues. What
signing buys is **your name in that warning**, and the ability to accumulate
reputation at all — unsigned starts from zero every version, forever.

**Microsoft Artifact Signing is ruled out on geography, not merit.** It is the
better architecture — ~$10/month, no token, HSM-backed, CI-native, and it would
keep the key off the dev machine. But Public Trust certificates are limited to a
listed set of countries, and **individual developers must be in the US or
Canada.** Nigeria is on neither list. Re-check before public beta; the list has
grown before.

Two things that raise the stakes beyond a click-through: **Smart App Control on
Windows 11 blocks unsigned executables outright**, on all executables rather
than only downloaded ones; and **modifying a file after signing breaks the
signature**, which matters for the bundled runtime — post-processing happens
before signing, never after.

The repo is ready. `electron-builder.yml` names the identity by environment
variable and never names a key. Timestamping is configured, because without it
every signature dies with the certificate *including on machines where it is
already installed*. `scripts/check-signing.mjs` fails a release that is
unsigned, that signs from a key file, or that has no timestamp server.
`.gitignore` carries certificate patterns.

### Brand

**Tagline: "One memory. Every model."** Settled. Not yet placed — it belongs in
`README.md` and `docs/PITCH.md`, not the app chrome.

The mark was **traced** from `Logo_Image/`, not eyeballed: threshold the hero
glyph, follow the boundary, reduce with Ramer-Douglas-Peucker. Each plane came
down to six and eight corners, which is itself the check that the trace found
real geometry. It corrected three things an earlier reconstruction had wrong —
the mark is **1.31:1, not square**; it is **two interlocking planes, not three
slabs**, and the diagonal gap between them is its whole character; and the
gradient ends in **cyan (#4BADE6), not blue**.

`scripts/build-brand-assets.py` emits SVG, PNG and a seven-size `.ico` from one
definition, so the favicon, app icon and installer icon cannot drift into being
three logos. The top-left of every workspace is now the rounded app-icon tile,
51px, **icon only** — it returns to the landing with the conversation closed,
which keeps the orb's single meaning as the way *in*.

Previews write to `Logo_Image/`, never `frontend/public/` — everything under
`public/` is built into `dist` and shipped.

### Before you run anything

The short list. *Read this before debugging anything*, further down, has the
restart command and the longer catalogue — including why a run under the wrong
interpreter reports 54 failures that all look like product defects.

**Run the suite as `.venv\Scripts\python.exe -m pytest`.** Bare `python` on PATH
is a broken shim that reports a missing install path — this costs the first ten
minutes of a session that does not know it.

**Measure the suite with nothing else running.** A run that reported 435s
against a normal 245s produced one failure in
`test_measure_exemplar_separation`; it passes alone with a wide margin and
passed two clean runs after. That test is a `measure` test against a live local
model, which is the class most sensitive to a loaded machine. **Not hardened,
deliberately** — loosening a measurement to survive contention is how it stops
measuring.

**Whatever is on 8420 is stale.** Restarting it is step one of testing anything.
Confirm `build.commit_short` matches `git rev-parse --short HEAD` before
believing a single response.

**Building the installer needs a privilege this shell does not have.**
electron-builder extracts its `winCodeSign` cache using symlinks, which requires
Developer Mode or elevation; without it the build fails on two irrelevant
*darwin* `.dylib` links and the error names 7-Zip rather than the privilege.
**`--config.win.signAndEditExecutable=false` gets past it** — at the cost of the
exe's icon and version metadata, which is also the step that applies
`build/icon.ico`. The icon and the signature arrive together or not at all.

**GNU tar cannot extract to a Windows absolute path.** It reads `C:\…` as
`host:path` and tries SSH. Git for Windows puts GNU tar on PATH while Windows
ships bsdtar, so *which tar answers* decides whether a build works. Use relative
paths.

### What is next

1. **Run the installer on a machine that has never seen this repo.** The
   installer itself now exists — `dist-electron/Zaram-0.1.0-x64.exe`, 186 MB —
   and its payload has been checked against the built tree, so what that run
   tests is install, first launch and the bundled interpreter finding itself
   under a different path. Take the portable build too; it isolates whether a
   failure is NSIS or the app. **Nothing else in M11 is unknown.**
2. **Obligation extraction (M9a) — the extractor exists; nothing calls it yet.**
   `backend/obligations/` reads payment, deliverable, expiry and renewal
   clauses with the sentence each came from, resolves `net 30` against an issue
   date, and returns a *question* rather than a commitment when it cannot
   honestly resolve one — an ambiguous `03/04/2026`, a relative term with no
   anchor, a date that does not exist. 28 tests.

   What remains is everything around it: nothing calls it on ingest, there is
   no store, no surface, and no reminder. The acceptance line — day 31, Zaram
   says the payment is late, shows the clause, and has the follow-up drafted —
   is not met and cannot be until obligations persist. Direction is deliberately
   `UNKNOWN` until a caller supplies it, and the caller that knows is the ingest
   path, via rule 7b's origin.

   One bug worth carrying forward: the sentence splitter cut `£2,400.00` at the
   decimal point, so precise figures extracted nothing while round ones worked.
   It failed on realistic input and passed on tidy examples, which is why the
   suite now holds a whole scruffy invoice rather than only single sentences.
3. **The business base layer** — invoices exist; quotes, receipt capture,
   expense categorisation and the monthly picture do not. Largest remaining
   volume of v1 work and the most likely to be underestimated.
4. **Cloud's Settings surface and the three tiers of control.** The key comes
   from the environment today. The recommended shape is Electron `safeStorage`
   (DPAPI on Windows) with the key passed to the Python child as an environment
   variable — which is what the backend already reads, so no backend change.
   **Never expose an endpoint that returns a key**, given the local API has no
   authentication.
5. **The avatar.** Seven states, closed set, from `useEmbodimentState`: idle,
   local, cloud, thinking, listening, speaking, swapping. Six mouth visemes —
   `sil aa ee ih oh ou` — from `src/lib/visemes.ts`. Eyes are state-derived
   only, no gaze. The acceptance test is two states side by side in a screenshot
   at the size they will actually render.

**Blocked on the maintainer, and only this:** buying the OV certificate. Every
day it is not begun adds a day to the end.

### Documents as templates — agreed 12 August

Asked for on 12 August — upload an existing invoice or letterhead and have
Zaram produce new documents that look like the company's own. Agreed the same
day, including the cut below.

**The shape that is worth building, and the part that is not.** Exact layout
cloning is refused, for the reason that already excluded an embedded office
engine: reproducing an arbitrary `.docx` means reimplementing Word's layout,
and a PDF carries no structure to reproduce at all. The failure mode is the
specific one that matters — a *near* miss. A document 90% in the house style
is worse than one obviously Zaram's, because the client notices the wrong font
on something carrying their letterhead.

What users want decomposes into three things that are reliable: **identity**
(logo, trading name, address, accent colour), **boilerplate** (terms, footer,
bank details, numbering scheme) and **conventions** (standard terms, currency).

**The second and third are facts, not formatting**, and that is what makes this
cheap: they belong in the Spine with provenance and scope, correctable under
rule 4, rather than in a template store. Which means uploading three past
invoices does not merely style new ones — it teaches Zaram the business.
CLAUDE.md already promises Zaram "knows the client's rate, their terms, and
that they pay late"; this is how that is true on day one instead of day ninety.
It is the onboarding path for the business layer, not a formatting feature.

`Letterhead` and `render_document` are the seam, and HTML-as-source-of-truth
means a style profile is CSS variables plus masthead content. No new pipeline.

Conditions, if it is built: a review step before first use — never silently
adopt an extracted identity; refusal rather than approximation when a logo
cannot be extracted cleanly; fonts matched to a bundled family **and said so**,
since remote fonts are banned and embedding a licensed one is a licensing
question; and per-project templates, which `scope` already allows. An uploaded
template is a source in Knowledge under the per-source policy like any other.

**The layout-cloning cut is accepted.** Everything above depends on it.

### Two ideas worth taking from outside

Read against an external memory-architecture proposal, 12 August. Most of it
was already here under rules with recorded failures behind them, and four
parts contradict things this repo has measured — a mandatory reranker (bought
nothing at 1,000 documents, and `bge-reranker-v2-m3` cannot run through Ollama
at all), a raw-dialogue experience log (rule 7d inverted), a merged
relevance-and-trust score (the blend-versus-threshold bug, three times), and a
graph database (a stranger cannot install it). Two parts are better than what
exists:

* **Supersession.** Storing an old belief and a new one and letting retrieval
  choose is how contradictions accumulate silently. The correction should mark
  the old superseded. This is already a known gap: M10's acceptance asked for
  edits "written through as supersessions" and it was deliberately not built.
* **Ingest is an unguarded path into memory.** The rule that a tool description
  is third-party text applies equally to a document that becomes a fact. This
  matters now that obligations are extracted from documents: a hostile PDF is a
  way to plant a commitment in someone's week. Nothing retrieved or ingested
  may widen what the system will act on without the user seeing it.

### What changed, in one screen

Read the sections further down for the reasoning; this is the index.

| | |
|---|---|
| **Cloud engine** | `OpenAICompatibleEngine`, no new dependency, **no HTTP client of its own** — `EgressGate.stream_lines` carries the bytes. Recorded deviation from CLAUDE.md's LiteLLM entry, with reasons, reversible behind `LLMEngine`. |
| **Cloud routing** | `RoutedEngine` picks local or cloud per message by the model's **declared locality**, never by name — `gpt-oss` runs on Ollama. Every unknown routes local; `HYBRID` counts as remote. |
| **Confirm-before-send** | The confirmation may *edit* the outbound text, and the gate now reads the body back after the check so the edit reaches the wire and the log identically. **Answerable as of 12 August** — endpoints, dialog, and the event-loop fix that made delivering the question possible at all. |
| **Chat streams off the loop** | Both `ChatRouter` paths iterate the engine's synchronous generator in a worker thread. Previously any blocking step froze the whole backend; with a confirm hook in the path that made the feature unreachable rather than merely slow. |
| **Loopback only** | The API bound `0.0.0.0` with no authentication on any endpoint — the Spine, the egress log and the policy were readable by anyone on the same network. Now `127.0.0.1`, not configurable. The test that would have caught it existed and had never been run. |
| **Installer payload** | Included by allow-list, not denylist. A denylist was shipping 437 MB of venv and scratch **plus `spine.db`, `egress.db`, the artifacts and projects databases, the privacy policy and the generated invoices.** Two gates hold it — one in the suite, one in the build. |
| **Python in the installer** | Relocatable CPython 3.11.9, SHA-256 verified, 401 MB. PyInstaller ruled out because the product tells users to `pip install zaram[ingest]` and you cannot pip into a frozen bundle. **`Zaram.exe` packaged and starting its own backend for the first time.** |
| **Electron tests run** | `npm test` wired to `test/`, which held 26 tests nobody had ever run and two failures. Both were stale tests over correct production code — and one of them encoded the loopback binding. |
| **Frontend tests run** | Same shape, found later: 103 vitest tests across 14 files with no script pointing at them. `npm test` now runs both JS suites; `test:backend` encodes the venv interpreter. |
| **Installer icon** | `electron-builder.yml` names no icon and `/build/` was ignored, so a fresh clone would have built an installer with the default Electron icon and no error. `build/icon.ico` is tracked now. |
| **The installer exists** | 186 MB NSIS plus a portable build. It had never been buildable without a code-signing certificate: `${env.ZARAM_SIGN_SUBJECT}` does not resolve to empty when unset, and the literal killed the build while signing the uninstaller — after packaging had already succeeded, which is why "packaged" and "no installer" were both true and never connected. |
| **Code signing** | OV, prepared, not purchased. **EV buys nothing** — Microsoft's own docs say it no longer bypasses SmartScreen. Artifact Signing unavailable in Nigeria. Identity by env var, timestamping mandatory, release gate refuses unsigned. |
| **Brand** | Mark traced from the source image rather than eyeballed — it is 1.31:1, two interlocking planes, gradient ending in cyan. One generator emits SVG, PNG and a seven-size `.ico`. Top-left app icon returns home. |
| **Project adoption** | `harbour` and `northwind` existed on files but were not projects, and assignment validation had made that a one-way door. Adopt keeps the id exactly; generation is validated so no new ghosts arrive. |
| **Recall at scale** | Measured at 10/100/1,000: margin +0.131 → +0.108 → **+0.106**, 5/5 recalled at rank 1, zero false citations. The curve saturates. Reranker stays unbought. |
| **Shortcuts** | Every chord was dead on Windows — the matcher waited for the Win key while the overlay advertised Ctrl. |
| **Invoices / formats** | Decimal money, terms → due date from one number, refusal rather than invention. `.html`, `.txt`, `.csv`, `.pptx` added; slides are headings, not a second pipeline. |
| **Speech** | Time-to-first-sound 9.9s → 2.5s, no longer scaling with reply length. |
| **Landing** | Orbit nodes drag and spring back to their live slot. One Settings in the rail, not two; 440px → 260px. |

### Read this before debugging anything

**Check which build is answering.**

```
curl -s localhost:8420/health | jq .build
```

It reports the commit and uptime. A backend started at 06:32 on 10 August served
that port for the rest of the day while two *already fixed* bugs — the audio 404
and recall firing on a greeting — were reported as live and re-diagnosed against
it. Both fixes had been correct the whole time. **Windows lets a second uvicorn
bind `0.0.0.0:8420` beside a `127.0.0.1:8420` without an error, and the older
process wins for loopback.** A backend with no `build` field at all predates
this commit and is stale by definition.

Proven rather than assumed, same input to both, same second:

```
port 8420 ('Hello') -> 3 source events     (the stale process)
port 8425 ('Hello') -> 0 source events     (current code)
```

**It happened again on 10 August and cost the same way.** A backend from 06:32
was still serving 8420 at 19:00 with **no `build` field at all** — it predated
the stamp. Restarting it is what made the new routes reachable. To restart:

```
powershell -Command "Get-NetTCPConnection -LocalPort 8420 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"
```

then `backend/start.bat`, and confirm `build.commit_short` before testing.

**The venv is `C:\Zaram\.venv`, and bare `python` on PATH is a broken shim** —
it exits with "the install path was not found". Use
`C:\Zaram\.venv\Scripts\python.exe` for every pytest run. `py` is also
unreliable here.

**Run pytest from the repo root**, with `.venv/Scripts/python.exe` — not with
whatever `python` resolves to. `--ignore` in `pyproject.toml` is rootdir-relative
so running from `backend/` aborts the whole suite, and the system Python 3.11
has pytest but not the dev install, where the suite reports 54 failures that all
look like product defects and none of which are.

Live measurements against a local model carry a `measure` marker and skip when
Ollama is absent. `pytest -m measure` re-runs every one of them — do that when an
embedding model changes, because several recorded numbers are calibrated to
bge-m3 and do not transfer.

**Run it with `.venv/Scripts/python.exe`, not with whatever `python` resolves
to.** The system Python 3.11 on this machine has pytest but not the dev install,
and the suite reports **54 failures** there — python-docx, openpyxl and the rest
are missing, so ingest reports "Nothing installed can read this file" and twenty
artifact tests fail on exporters that are not there. Every one of them looks
like a product defect and none of them is. Recorded because it cost twenty
minutes: a suite that fails differently depending on which interpreter found it
is not telling you about the code.

One run on 9 August took **36m25s** and has never reproduced; the two runs
since were 2m19s and 1m19s. Three wrong explanations were offered for it
before measurement (live DuckDuckGo calls in the suite — real, but 2.8s;
`pytest-randomly` — not installed; a first-use HuggingFace download — cache
untouched). Recorded so nobody spends another hour on it: **it is not
reproducible and it is not understood.** If it returns, run with
`--durations=25` first.

### Project is the sixth node — decided 10 August 2026

**The navigation is now six: Work · Project · Memory · Knowledge · Activity ·
Settings.** Maintainer's decision, and it reverses an argument I made against it
in the same conversation, so both halves are recorded.

The case against: a project only groups artifacts, and a grouping of artifacts
is a filter inside Work rather than a surface — the same test that cut Canvas
and Plugins.

**Why that was wrong: rule 7i.** Project scope applies to *facts*, not only
files. `project:<id>` is a field on the Spine, the queued plan object carries
the same scope, and Knowledge sources carry it too. A project spans Work, Memory
and Knowledge at once, and a filter living inside Work cannot own something that
scopes Memory.

The precedent the maintainer named is the right one: **Memory and Knowledge are
similar and are not the same**, which is why they are two nodes and not one.
Project stands in that relation to Work — adjacent, overlapping, distinct.

It also passes "does it hold something real?" more clearly than Work does. A
project holds a type (which activates a pack), its scoped facts, its assigned
artifacts, and eventually its plan with decisions taken and rejected.

**Bounded, and the bounds are the point.** No folder tree, no subfolders, no
nesting — one level. Work is the output; Project is the organisation of it.
Deleting a project asks what happens to the facts and files inside, never one
button. `CLAUDE.md` and `docs/UI-SPEC.md` are updated.

**Also declined in the same conversation: sub-apps inside Work for file
editing.** Already settled in the dependency stack — OnlyOffice is AGPL,
LibreOffice headless is hundreds of megabytes, both are separate services.
Zaram generates; users edit in what they already have. The narrow defensible
version, post-v1 and unpromised, is that HTML is the source of truth for every
generated document, so *editing Zaram's own generated HTML before export* needs
no embedded editor. That is a preview that accepts edits, not a word processor.

### Documents are laid out for paper now — and it was never the model

The report was that generated PDFs and Word files "lack design, have no header,
and would not pass as a document anyone deals with in 2026", and the suspicion
was that the local LLM was the limit. **It was not.** The model writes the
words. Every visual property came from eight lines of CSS at the bottom of
`artifacts/html.py`:

```css
body{font:14px/1.6 Georgia,serif;max-width:44em;margin:3em auto;color:#111}
```

`max-width` and `margin:auto` are screen conventions on something destined for
paper, and there was **no `@page` rule anywhere** — so no paper size, no print
margins, no page numbers, no running foot, no letterhead. A larger model would
have written better prose on the same unstyled page.

Now: A4 with document margins, "page N of M", a real type scale, a ruled
masthead, an optional metadata block, and the print rules that are invisible
when they work — `orphans`, `widows`, `break-after` on headings, `break-inside`
on tables. One stylesheet with `@media screen` / `@media print`, because the
same string is the preview *and* the WeasyPrint input and two templates would
drift. No web fonts: a generated document is opened on machines Zaram does not
control, so a linked font would make it phone home from a stranger's laptop.

**Tables are set the way printed documents set them.** The old rules boxed every
cell in a 1px grid, which is a spreadsheet convention. Three details separate a
document from a table dump: `tabular-nums` so a money column aligns on the
decimal, `thead{display:table-header-group}` so headings repeat on every page,
and `break-inside:avoid` on rows so a line item is never cut in half.

**Branding.** `Letterhead` carries a name, free-form lines and a logo. The logo
is **embedded as a data URI, never linked** — `export/pdf.py` calls WeasyPrint
with no `base_url`, so a path cannot resolve. SVG is refused with a reason: it
can carry `<image href="https://…">` and no scanner sees inside a data URI.

**Sources and claims are no longer printed into the document.** An invoice goes
to a client, and the client has no use for `memory:55b6` at the foot of it. This
does not weaken rule 2 — rule 2 is traceability, and its operational test
(`test_provenance_invariant.py`) is about the *stream*. The anchors stay in the
markup and on `Artifact.claims`; the preview renders provenance as chrome around
the document, the same relationship `CitationPanel` has to a reply.
`include_provenance=True` turns it back on for a research brief or a proposal,
where citation is part of the genre.

### Where branding is captured — decided, not yet built

Global scope, captured in chat, offered at the moment of doubt. Rule 7i decides
it: a letterhead is about *the user*, not about the work, so it is global with a
per-project override for someone genuinely trading under two names. Rule 7e says
do not make them fill a form before their first document — drop the logo in the
composer and say "use this as my letterhead". Rule 7h says offer it the first
time a document is generated without one. **Settings is where it is visible and
editable afterwards, never the only way in.**

### Scope changed this session, deliberately

Two reversals of `CLAUDE.md` as previously written, both the maintainer's
decision. `CLAUDE.md` has been updated to match; this is the reasoning.

- **Voice is in v1, both directions.** Speech out (Kokoro) and speech in
  (faster-whisper, local), because a character that cannot speak or listen is
  a skin rather than an embodiment. **Speech follows the renderer** — avatar
  speaks, orb is silent unless asked — so it needs no second setting.
- **The 3D embodiment is in v1**, no longer a spike. Toggle on the landing for
  now; the shipped control belongs in Settings.
- Extras split: `zaram[voice]` ~905 MB speaks, `zaram[mic]` **81 MB measured**
  listens. Light installer, extras fetched **on demand after the product has
  proved itself** — not during install, which is the same blocking download
  moved earlier.

### Decided against, so it does not return as a reasonable suggestion

- **Hospitals as a segment. Cut.** The proposal was storing patient records and
  using GPT Vision to review x-rays and infer patterns across tests. That is
  diagnostic support — regulated as a medical device (FDA SaMD, EU MDR IIa+) —
  and it is already on the never-build list. It also means patient data leaving
  the device to a provider with no BAA. The defensible neighbour is medical
  *documents* for individual clinicians, never diagnosis, and not before M12.
- **Cloud speech recognition in Settings. Cut.** Probed in Electron 28.3.3
  (`electron/probe-speech-support.js`): the constructor exists, `start()` errors
  `not-allowed`. That result is **confounded** — the probe denies all
  permissions — and resolving it would mean sending real audio to Google. It
  does not matter: broken means a dead control, working means microphone audio
  leaving unlogged. Same answer from both branches.
- **A `Creative` embodiment state. Cut.** Every other state answers *what is the
  system doing*; `Creative` answers *what kind of task is this*, which is a genre
  label. Rendering it means the avatar performs a mood based on subject matter —
  the drift into personality the spike exists to prevent. Fold into `working`.
- **"Everything ChatGPT can do" as positioning.** Those are model capabilities;
  Zaram trains no models and would be permanently one release behind. The claim
  is **any model, one memory, nothing leaves without you seeing it** — which
  gets stronger as models improve. Capability arrives by routing and tools,
  never by Zaram implementing a modality.
- **An agent framework for the plan object.** ADK, LangGraph, CrewAI all ship
  their own memory and session abstraction, and memory is the product.

### What this session built

Six commits, `1ccc339..7a7bd45`, all pushed.

- **`66736fa` DuckDuckGo asks the gate.** `DDGS` opened its own socket, bypassing
  `get_gate()`, while `test_egress_chokepoint.py` exempted the module as
  *"dormant"* and `test_knowledge_runtime.py` called it for real on every run.
  The guard checked reachability **at boot**, so it passed while the suite made
  the unlogged live request. 0.67s live → 0.01s refused and logged. The three
  web-provider tests were also vacuous *and machine-dependent* — `if results:`
  asserted nothing, and whether they touched the network depended on the
  gitignored `backend/egress-policy.json`. Now driven against gate doubles:
  69 tests, 0.89s, no network.
- **`f22d06f` The embodiment spike runs.** `useEmbodimentState()` derives one
  state from `orbStore` (activity) and `sessionStatusStore` (locality) without
  either duplicating the other. Activity wins over locality, so `local`/`cloud`
  surface only at rest. `<Embodiment />` picks at mount, no crossfade, VRM lazy
  so the orb path never pays for `three`. Confirmed in `AvatarSample_Z.vrm`:
  14 expressions, **all five visemes**, humanoid rig.
- **`e5e55f0` Kokoro's phoneme timings survive.** They were discarded by tuple
  unpacking at `kokoro.py:242`; `pred_dur` comes out of the same forward pass, so
  the cost of keeping them is zero. They cross the interface as `SpeechTiming`,
  never as Kokoro's `MToken`. Offsets are absolute across chunks; `None`
  timestamps are skipped, not zeroed.
- **`576e5aa` The mouth is driven by those timings**, scrubbed against
  `audio.currentTime`. `check-visemes.mjs` asserts the mapping and was
  **mutation-tested** before being believed. `check-no-cloud-speech.mjs` bans the
  Web Speech API and asserts the `legacy/` quarantine.
- **`cfaa191` The avatar speaks its replies.** Closes the gap that mattered:
  every piece was green while the character was silent, because nothing called
  `speak()`.
- **`7a7bd45` The STT contract.** `SpeechRecogniser`, `Transcript`,
  `TranscriptSegment` — which mirrors `SpeechTiming` on purpose. `language` is
  `Optional` and never defaults to `"en"`.

Then seventeen more, `0cef961..a0d2bed`, all pushed. Each is written up in full
in the sections below.

**Voice**
- **`0cef961` The audio URL 404.** `audio_filename` crosses the connector
  boundary; `base_url` defaults to empty so the URL is relative.
- **`b7bca96` Zaram listens.** `WhisperRecogniser`, `/voice/transcribe`,
  `micStore`, `MicButton` — and `speechStore.error` finally rendered.
- **`2c4c819` A dictated amount is flagged, never corrected.** The audio says
  *naira*; Whisper said **$**.
- **`67ca372` The orb can be asked to speak.** The "unless asked" half of
  "orb, silent unless asked", which was never implemented.

**Guards and correctness**
- **`fc1fb42` Three holes in the guards.** The CSS universal selector, the
  block-comment blind spot, and exemptions that had stopped being needed.
- **`0c8cc8b` A greeting no longer pulls the user's files into the prompt.**
- **`b69b147` `/health` says which build is answering.**

**Embodiment**
- **`09e5303` The avatar's GPU cost, measured — 190 MB, not 1.5 GB.**
- **`2cbe9bb` The avatar was pixelated, and `antialias:true` was not the fix.**
- **`f2a2a16` Triangle count reported alongside VRAM.** 37,678 today.

**Documents**
- **`3d3d0a1` Laid out for paper, and carrying the user's branding.**
- **`517c3da` The client sees the document, not the working.**

**Navigation**
- **`faabf4a` Project is the sixth node** — docs only.
- **`a0d2bed` The sixth node exists in the app**, not only in the docs.

**Also** `9f22bfb` the page-load 404 (it was `/favicon.ico`), and three `docs`
commits including this file.

### Project is a real object now — and the lesson from building it

`a0d2bed`. A project used to be `SELECT DISTINCT project_id FROM artifacts`, so
it existed only once a file had been saved into it, could not be created,
renamed or deleted, and had nowhere to keep the type that activates a pack.

Both endpoints remain and answer different questions: `/artifacts/projects` is
"which projects hold files" (Work's filter, which cannot lead to an empty list),
`/projects` is "which projects exist". Conflating them was the bug.

**Deleting states what it will do and then does only that.** `contents=keep`
re-scopes facts to global — the grouping goes, the knowledge stays — and is the
default because it is recoverable. `contents=delete` is never implicit; an
unrecognised value is a 400 rather than a guess at the destructive branch. Files
are never touched and the response says so, because "the project is gone" would
otherwise read as "the files are gone". Fact counts are `-1` when the Spine
cannot answer, rendered as "an unknown number", and the destructive button is
**disabled** in that state — "0 facts" on a confirmation that then destroys
eleven is the failure the sentinel exists for.

**Renaming never moves the id**, because facts carry `project:<id>`.

**The lesson worth carrying forward: a comment describing a bug does not prevent
the bug.** `registry.ts` calls `orbitOrder` the canonical node list and warns, in
prose, that three components had each restated it and CommandPalette had
silently lost Activity as a result. That was written down and never enforced —
and `orbitOrder` ended up with **no consumers at all**. So adding Project
updated the rail, the command palette and the router while the orbit, the first
thing anyone sees, kept rendering five nodes. It was caught by taking a
screenshot, not by reading the code. `Landing.test.ts` now asserts the orbit
against `orbitOrder` for membership, order, labels and spacing.

Two more found the same way: `slugify` **stripped accents instead of folding
them** ("Ünïcodé Studio" → `n-cod-studio`, which is what a French, German or
Yorùbá business name would have become), and `/projects` was **missing from the
Vite proxy**, so every call from the frontend would have hit the dev server.

### TencentDB Agent Memory, read and mined — 11 August 2026

Reviewed at the maintainer's request. **It is not a competitor and it is not a
dependency; it is a source of two retrieval ideas Zaram should take.**

**Why it is not a competitor.** Its user is a team wiring an agent fleet, with a
control panel governing what a fleet shares. Zaram's user is one person who uses
more than one AI and wants their own continuity. The overlap is the substrate,
not the product — and `CLAUDE.md` already says the substrate is commodity and
the surfaces are not. A strong open-source local memory engine **commoditises
the layer Zaram was never going to win on while validating the thesis**. The
convergence is worth noting: SQLite plus `sqlite-vec`, zero external calls,
provenance back to raw evidence, share-versus-private governance. Four
architectural choices Zaram made independently, arrived at by a team at Tencent.

**Why it is not a dependency, despite MIT.** Node ≥ 22.16, distributed as three
Docker services. The actual blocker is that a stranger cannot install Zaram;
adding a container runtime to a Python backend moves that blocker backwards.
Licence was the gate everyone expects to fail and it passed — packaging is the
one that fails.

**Taken: rank fusion (RRF).** They fuse BM25 and vector results by rank position
rather than by blended score. This is the most valuable thing in the project for
this codebase, because merging a ranking blend with a selection or citation
threshold has cost it three times and the current defence is a discipline —
`relevance` selects, `score` orders, remember which. RRF is on no source's
scale, so there is no magnitude that *could* be compared against a cosine floor.
It converts a rule someone must remember into one that cannot be broken. Taken
for ordering only.

**Taken: real lexical retrieval, fused rather than averaged.** `_keyword_match`
is term overlap and its own comment records that function words score against
everything. The argument is not tidiness — it is **rule 9's documented
failure**. "Write that up as a proposal" retrieves nothing because five
referential words resemble nothing; but a client name or a reference number is
precisely what a lexical index finds and a dense embedding misses. This is the
one retrieval change with a known failure already waiting for it.

**Corrected from the first read of this project.** I described their tiered
retrieval as a membership gate and warned it would reintroduce the rank-43
defect. Reading the design, that was wrong: L2/L3 are a *fast context bootstrap*
and specific-fact queries fall back to BM25 + vector + RRF over L1 and L0. It is
two-phase, not a gate. The caution survives in a narrower form — if a bootstrap
answers and the fallback never runs, tier decided membership after all — but the
architecture as built does not make that mistake.

**Rejected: the four tiers.** L1 atom / L2 scenario / L3 persona is Zaram's
scope field with more machinery. Rule 7i already argues one field on one store
is better: facts move, recall needs both at once, and the correction loop stays
uniform. Their pyramid would buy nothing and cost that.

**Rejected: L0.** Persisting raw dialogue is rule 7d inverted, and 7d was
written from a specific failure — duplicate citations and Zaram quoting its own
replies. They keep L0 for verification; Zaram keeps provenance, which is the
same guarantee without the store.

**Deferred: symbolic short-term memory.** Compressing intermediate tool logs is
genuinely applicable — the execution engine runs multi-step plans and those logs
are the bloat this targets — and it touches **session state only**, so rule 7d
is untouched and nothing changes about what enters the Spine. Worth prototyping;
not started.

**Their numbers are a hypothesis.** 61% fewer tokens and +50% task success come
from secondary write-ups. `CLAUDE.md` says benchmark against LoCoMo /
LongMemEval, not by feel, and this codebase has already been burned by an eval
that graded itself and by a corpus whose filler answered the question. Those
figures get measured on Zaram's own harness or they do not count.

### Assignment exists — a project can be filled

`PATCH /artifacts/{id}` and `POST /memory/{record_id}/scope`, wired into the
Project and Memory surfaces. This closes **item 7** and makes **item 8**
testable: a file and a fact can now be put into a project after the fact, which
is the only way project scope was ever going to be exercised on real data.

**Assignment lives in Project, not Work.** `CLAUDE.md` splits them — Work
browses and previews, Project creates, names, types, assigns, moves and deletes
— so a project row expands to show what is in it, with a picker for what is not.
Adding a file that already belongs somewhere says **"Move here"** and names
where it currently lives, because a file has one project and a button reading
"Add" would look like a copy while quietly emptying somewhere else.

**The destination is validated, and that is the whole point.** An unchecked
write lets a typo create a project that exists only as a string on one row:
absent from `/projects`, so unnameable, undeletable, and able to collect facts
under a scope nothing points at — rule 4 broken by a spelling mistake. This is
the same ghost the `/projects` ÷ `/artifacts/projects` split was made to kill,
approached from the other end.

**`null` and `""` are different instructions** on both routes. Omitted means
*the caller said nothing* and is a 400; empty means *take it out*, and restores
the value a file is born with rather than inventing a third state.
`assignment.test.ts` asserts the client actually sends `""`, because every
ordinary instinct — dropping falsy fields, `|| undefined` — collapses the two,
and the only symptom is that **Remove silently stops working** while everything
else looks fine.

**`scope` was missing from both memory serializers.** A fact could be scoped to
a project and there was no way to see that it was: rule 7i's field existed and
was invisible from outside the backend. Now on `/memory` and `/memory/{id}`, as
one field — the surface derives the project id from it rather than being handed
a second spelling that can disagree.

**The artifacts store's mutation guard was counting instead of naming.**
`test_no_sql_deletes_or_blanket_updates` asserted `count("UPDATE ARTIFACTS")
== 1`, so a second named mutation failed it even though the class docstring
asks for exactly that ("adding a second has to be a deliberate act"). It now
asserts an allow-list of mutable columns and one column per statement. A count
says *how many* named mutations exist and not *which*, so swapping a safe one
for a dangerous one left it green — the number was never the property worth
guarding.

**A test that passed alone and failed in the suite.** The fact fixture drove
`asyncio.get_event_loop().run_until_complete`; by the time the full run reaches
it another module has closed the thread's loop and it raises rather than making
one. Now `async def` and awaited. A test that only passes in isolation gets
blamed on the suite.

**Driven in the browser, on the real Spine**: created a project, added a file
(0 → 1 file), removed it (back to 0), moved one in from another project, moved
a fact in (0 → 1 fact) and watched Work's filter follow. Everything touched was
put back — the fact to global, the file to its original id, the test project
deleted.

**Left open, and found by that restore.** Existing artifacts carry `project_id`
strings for projects that were never objects — `harbour`, `northwind`. Project
cannot see them, and validation now makes them a **one-way door**: a file can
leave such a group and can never go back, because the destination does not
exist. Restoring the file needed a direct store write. Someone with existing
work therefore opens Project to an empty screen while Work shows their files
grouped, which reads as two products. The fix is an adoption path — Project
listing artifact-only ids as "not a project yet", or a backfill at startup —
and it is a migration decision, so it was flagged rather than guessed at.

### Two Settings buttons, and a rail twice as wide as its own labels

Both reported by the maintainer from a screenshot, which is twice now that the
navigation's defects have been caught by looking rather than by reading.

**Settings was in `surfaceOrder` *and* pinned at the foot**, so the rail drew
the same destination twice, three rows apart — which reads as two different
places. The node list has now drifted three times in three distinct shapes:
CommandPalette silently **lost** Activity, the landing orbit silently **missed**
Project, and the rail silently **doubled** Settings. A
`Record<WorkspaceId, …>` catches the first, `Landing.test.ts` catches the
second, and neither catches the third — a Record proves every node has an entry
and says nothing about how many times it is rendered. `LeftRail.test.tsx` now
renders the rail and asserts each node appears exactly once.

The list is still derived, minus one named id. A derivation with a deliberate
omission is not a restatement: a seventh node still arrives on its own.

**The rail defaulted to 440px** to hold labels that need about 210 — a band of
empty rail as wide as the content beside it, on the surface `UI-SPEC.md` says
density matters most. Now 260, still draggable.

**The migration is the part that nearly shipped broken.** A persisted width
beats a constant, so lowering the default reaches nobody who has opened the app
before — the change lands and the rail stays wide, looking like an edit that did
not take. The first attempt was `from < 1`, which read correct and did nothing,
and the browser said so: still 440 after a reload. Two facts, both checked
rather than assumed:

- zustand gates migration on `typeof stored.version === 'number'`, so an entry
  with **no version key is never migrated at all** — it is loaded as-is and
  `migrate` is not called.
- every entry zustand itself wrote carries `version: 0`, because that is the
  default when the option is absent. So real users migrate, and the version-less
  case is unreachable through the normal path.

The comment in the code originally claimed the opposite, and asserting the wrong
reason for a real behaviour is how the next person inherits a false model of it.

### Every keyboard shortcut was dead on Windows, and the interface said otherwise

The same lesson again, one file over. `chordTokens` and `matches` both read
`keys.meta`, and they disagreed about what it meant. The renderer treated it as
*the platform's primary modifier* and printed **Ctrl** on Windows. The matcher
took it literally and required `event.metaKey` — the physical Windows key, which
the OS claims before the page sees it.

So the help overlay listed fourteen shortcuts, every chord correctly labelled,
and **not one of them fired**: not Ctrl K, not Ctrl 1–7, not the orb states.
Nothing threw, nothing logged, and the keycap was a claim about the system the
system did not honour — which is rule "never render invented values" in its
quietest form, because the value here was a promise rather than a number.

**`meta` now means the platform's primary chord key, and that is written down
where both halves read it.** On Windows `meta` and `ctrl` collapse onto Ctrl,
exactly as the label says; holding the Windows key is a non-match rather than a
forgiven near-miss, so Win+K does not open the palette.

`registry.test.ts` is the enforcement, and it is the shape worth copying: for
every shortcut, on both platforms, it **synthesises the exact event the rendered
chord describes and requires the matcher to accept it**. A label and a matcher
agreeing is not something a type can express. Reverting the fix fails it with
`nav.landing is shown as "Ctrl 1" and does not respond to it` — checked, not
assumed, because a test written after the fix has never seen the bug.

Driven in the browser afterwards: Ctrl K opens the palette, Ctrl 2 and Ctrl 3
land on Work and Project, `?` opens the overlay and all fourteen chords read
`Ctrl …`. The one remaining restatement, `components/palette/CommandPalette.tsx`
with its own `metaKey || ctrlKey` listener, has no importers — it is not the
palette the shell renders.

Mac glyphs are gone from the live frontend and from `UI-SPEC.md`. TopNav derives
its `Search (Ctrl K)` label from the registry instead of spelling it out.
`src/legacy/` and `figma-assets/` still contain `⌘` and were left alone: the
first is quarantined and unreachable, the second is imported design source
rather than shipped UI.

### The avatar costs ~190 MB of VRAM, not the invented 1.5 GB

`backend/tests/test_avatar_vram_budget.py` weighs `AvatarSample_Z.vrm` by
parsing the glTF container — a VRM *is* glTF 2.0, so no VRM library is needed
and none was added — and computing what the GPU actually holds:

| | |
|---|---|
| File on disk | 16.4 MB |
| Textures, 27 images, decoded RGBA8 + mipmaps | **182.5 MB** |
| Geometry, vertex and index buffers | **7.5 MB** |
| **Texture + geometry VRAM** | **189.9 MB** |

Six 2048×2048 textures at 22.4 MB each are 134 MB of the 182. **The file size is
not the footprint** and is out by a factor of twelve: textures ship compressed
and land decoded at four bytes a pixel, plus a third again for mipmaps. A test
asserts that direction so the mistake cannot be made quietly.

**Against the budget this is nothing.** `CLAUDE.md` reserves ~9.1 GB on the
12 GB card for a chat model; 190 MB is 2% of it, and the gaps between installed
model sizes are 1–3 GB. The avatar cannot change which model fits. The "~1.5 GB"
that appeared in conversation was wrong by eight times, in the direction that
would have killed the feature.

**Corroborated live, and the live instrument is the weaker one.** Toggled
orb↔avatar three times on the RTX 3060 at 1280×720 in a real browser, reading
total board memory with `nvidia-smi`: deltas of **189, 433 and 122 MiB**. Same
order of magnitude, nothing near 1.5 GB, and memory returned *below* its
starting point afterwards — so nothing leaks per cycle. But a 3.5× spread is
what total-board memory is worth on a shared desktop, which is why the asset
arithmetic is the number and this is only its check. GPU utilisation went 25% →
31% with the avatar rendering.

Two things this deliberately does **not** include: the framebuffer and depth
buffer, and three.js's own allocations. Those scale with the viewport and the
renderer rather than with the model, so they do not move when the avatar is
swapped — and a ceiling can only protect the half that moves. Also confirmed by
reading the live page: **the orb landing creates no canvas at all**
(`document.querySelectorAll('canvas').length === 0`), so the orb path genuinely
pays nothing for `three`.

The ceiling is set at 512 MB. It is a budget decision, not a measurement, and
raising it means re-checking that it still cannot change which model fits.

**`AvatarSample_Z.vrm` is a placeholder and 190 MB is its number, not the
product's.** The intent as of 10 August is to replace it with a humanoid robot
with an LED face carrying five or six textures. What carries across the swap is
the per-texture arithmetic, not the total: **22.4 MB per 2048×2048 map, 5.6 MB
per 1024×1024**. Six of the first is 134 MB and six of the second is 34 MB, so
the intended asset lands well inside the ceiling either way — and the thing to
watch is texture *dimensions*, never texture count. This is why the figure is
recomputed by a test on every run instead of written down here.

### The avatar was pixelated, and `antialias: true` was not the fix

Two settings, both wrong in the way that is hardest to see: the code already
looked like it handled the problem.

**The render buffer was 320×320.** `setPixelRatio(Math.min(dpr, 2))` capped a
high DPR — correctly — but had no floor, so on an ordinary 1× display the entire
head rendered into 320 pixels square. Now `max(dpr, 2)` capped at 2, which
supersamples to 640×640 and resolves down. The old comment priced that as
unaffordable beside a resident local model; the arithmetic disagrees — 409,600
fragments against the 2,073,600 in one 1080p frame, a fifth of a single frame of
the screen it is drawn on. Measured: GPU utilisation over the orb went from
+6pp to +5–10pp, which is to say it did not move.

**Every texture sat at anisotropy 1**, three.js's default. Six 2048² maps on a
head a couple of hundred pixels tall is ~10× minification, sampling one texel
per fragment. Now 16, with the mipmapped min filter set alongside it — raising
one without the other is a no-op that reads as a fix.

`antialias: true` was already on and confirmed live at `SAMPLES = 4`. **MSAA
smooths silhouettes and does nothing for shading or texture sampling inside a
surface**, which is where aliasing on a face lives. The setting that looks like
the answer was the setting already applied.

**The first attempt reported `textures filtered: 0`** and its unit tests passed.
`MToonMaterial` extends `ShaderMaterial` and exposes `map` and
`shadeMultiplyTexture` as *prototype accessors* over `this.uniforms`, so
`Object.values(instance)` enumerates neither — while the test fixture, a
`MeshBasicMaterial`, held its textures as own properties and agreed with the
bug. The walk now searches uniforms too, the fixture that would have caught it
is in `VrmAvatar.test.ts`, and the count is printed at load: **71 textures at
anisotropy 16**, `render buffer: 640px for a 320px box`. The diagnostic is why
this was caught in minutes rather than shipped.

This matters more after the asset swap, not less: an emissive LED dot grid
aliases harder than skin.

### The page-load 404 was the favicon nobody declared

Open since 8 August, closed 10 August. `frontend/index.html` declared no icon
link, so every browser asked for `/favicon.ico` by default — and nothing serves
it, because `public/` holds `favicon.svg`, unreferenced.

It survived two days because of where it does *not* appear: a favicon request is
in neither the console nor `performance.getEntriesByType('resource')`, so both
places anyone looks were empty while the request was real. It was found by
reading the HTML, not by watching the network. `curl` settles it —
`/favicon.ico` 404, `/favicon.svg` 200.

**Two more defects in the same file, same cause.** The title was literally
`<!-- figma:title -->` and `lang` was `<!-- figma:lang -->`: an unfinished Figma
export still rendering its own placeholders. The browser tab said
`<!-- figma:title -->`. `lang` is not cosmetic — a screen reader takes its
pronunciation from it.

All three are guarded by `frontend/src/index-html.test.ts`, mutation-checked
against the pre-fix file. This is the one file nothing else covers — not
imported, not type-checked, not rendered by any component test — and it is also
the file the next Figma export overwrites, which is why the placeholders get a
test and not just a fix.

### The avatar was silent because every audio URL 404'd

`cfaa191` shipped "the avatar speaks its replies" and it has been silent ever
since. Synthesis succeeded, the response looked correct, and `audio_url`
pointed at a file that never existed:

- `AudioCache.generate_filename()` writes `{voice}_{sha256[:16]}.wav` —
  `af_heart_05322cae55732340.wav`
- `runtimes/speech/runtime.py` built the URL from `result.audio_id`, which is
  the **request** id — `tts-f68ca98d.wav`

Two naming schemes that could never agree. `new Audio(url)` failed, `speechStore`
set `'The audio could not be played.'` — **and nothing in the UI rendered that
field**, so the only symptom was silence.

**Found by a human saying "I didn't hear it", then curling the endpoint.** No
test covered the seam: the provider tests assert a file is written, the runtime
tests assert a URL is returned, and nothing asked whether they were the same
file. That is the sixth instance of this codebase's signature failure — a
contract with two implementations where the tests exercise the one the product
does not run.

**Fixes:**

- `SynthesisResult.audio_filename` carries the real filename across the
  connector boundary — the one place that knows both sides, exactly as it
  already does for `timings`.
- `base_url` defaulted to a hardcoded `http://127.0.0.1:8420` that nothing ever
  overrode. Now `""`, making the URL **relative**: the backend port is
  configurable, an absolute URL bypasses the Vite proxy and turns audio into a
  cross-origin fetch, and a packaged build has no reason to hardcode loopback.
- `speechStore.error` is rendered in the composer beside the mic's line.
- `/voice/stream` has the identical defect, is called by nothing, and is
  **marked KNOWN WRONG in place** rather than migrated — fixing it needs the
  same field on `AudioChunk`. It must not be wired up as-is.
- `test_the_returned_audio_url_names_a_file_that_exists` is the missing seam
  test.

**Verified live:** `POST /voice/synthesize` → `200 audio/wav, 124844 bytes`.
Warm synthesis is 1.6s; the first call is ~12.7s because that is when the model
loads (lazily, since the boot-egress fix below).

### The guards had holes — all three, and one was covering a bug in itself

Asked to make the guards trustworthy before adding any parallelism, on the
grounds that every parallel worker is safe exactly to the degree the guards
catch what it cannot see.

**`check-no-remote-assets.mjs` — two defects, both found by writing its
self-test.**

1. `COMMENT_OR_DOC = /^\s*(?:\/\/|\*|\/\*|#|<!--)/` treated any line *starting
   with* `*` as a comment and skipped it. `*` is also the CSS universal
   selector, so `* { background: url('https://cdn.example/x.png') }` was
   **silently ignored** in every stylesheet and CSS-in-JS template literal.
   Confirmed by mutation: with the old heuristic restored the fixture yields
   **0 findings** where it should yield 1. That is the dangerous direction —
   missing a real request rather than flagging prose.
2. Every finding was **double-reported**, because the patterns overlap
   (`@import url(…)` matches both the `@import` rule and the generic `url()`;
   `<img src=…>` matches both markup and JSX). The "N remote asset
   reference(s)" headline was twice the truth. Now deduped on where the scheme
   sits in the file, so two URLs on one line stay two findings.

**`test_egress_chokepoint.py` — a third hole**, beyond the two already recorded
below. The staleness test only asks whether the exempted *file* exists. An
entry for a file that no longer imports a network library keeps its waiver
forever and silently covers whatever is added back. Two such entries existed;
**one of them had been granted to paper over a bug in the scanner itself** (a
relative `from .kokoro import …` read as the PyPI `kokoro`). An exemption
granted to quiet a false positive outlives the false positive.
`test_no_exemption_is_unnecessary` now fails on any entry that imports nothing.

**`check-visemes.mjs` needed nothing** — it asserts real behaviour against a
clear oracle and was already mutation-tested.

**Both scanners now self-test before scanning** — 9 fixtures each, run by
`npm run build`, each case observed failing against a deliberately broken
scanner. The general rule this session kept re-learning: **a guard whose logic
changed and was believed on inspection is a guard nobody has verified.**

### Workflow: the parallelism question, answered

Asked twice how to parallelise Zaram's development, against two detailed
multi-agent proposals (an Opus/Sonnet/Haiku tier hierarchy, then a Kilo agent
roster). Recorded because it will otherwise be re-asked.

**Parallelism is not the bottleneck, and unpaid-for parallelism makes this
codebase worse.** The signature failure is cross-boundary — six instances now.
Every defect found on 10 August was found by leaving the assigned scope: a
startup log read while serving a URL, an endpoint curled outside the task, a
test failing for a reason that needed thinking about. A reviewer handed
SPEC + PLAN + DIFF passes all three, because each diff *was* correct against
its spec. More parallel workers means more boundaries.

**So: guards first, hierarchy second.** Parallelism is affordable in proportion
to what the guards catch — which is why they were fixed before anything else.

- **Split by subsystem, not by role.** Splitting by job (explorer / tester /
  reviewer) puts every agent in the same files. Packaging, ingest, voice, and
  the frontend surfaces are independent; the queued architecture (project
  record → plan object → plan in recall) is a strict chain and does not
  parallelise at all.
- **`.kilo/worktrees/` already contains stale divergent copies** using
  `backend/garage/`, renamed at M2. That is the parallelism failure mode
  already present in this repo. Delete or refresh before adding more.
- **Start the long-lead items now.** Code signing and Nigerian sole-trader
  business verification are weeks of *waiting*, not weeks of work. They block
  nothing and nothing blocks them; every day unstarted is a day on the end.
- **Kilo is not needed yet.** Worktrees plus a merge gate cover it. Adopt it
  after two features have run SPEC → IMPLEMENT → REVIEW by hand — CLAUDE.md's
  own rule about not building the pack system before two packs exist.
- **`docs/MILESTONES.md` stays the single status file.** A second
  `CURRENT_STATE.md` is precisely the "two lists, one goes stale unread"
  failure this file already names.

### The backend contacted huggingface.co on every boot, unlogged

Found by reading a startup log while bringing the app up to test the
microphone, and it is the most serious thing in this entry. Rule 3 says every
byte that leaves is logged. This left, and was not.

**The mechanism, and it is a pattern this codebase has now hit five times: a
flag deliberately turned off, and another path doing the thing anyway.**
`KokoroConfig.load_model_eagerly` is `False`. `KokoroProvider.initialize()`
ends with `self._last_health = await self.health_check()`. And
`health_check()` called `_ensure_pipeline()` **unconditionally** — so reporting
health is how the model got loaded, KPipeline resolved through
`huggingface_hub`, and the fetch happened before any policy had been consulted.
A health check that changes what it is measuring is not a health check.

**Three guard defects let it hide**, all in `test_egress_chokepoint.py`, and
all now fixed:

1. **Dormancy was checked by grepping one file for a dotted path.** The
   bootstrapper does not name `runtimes.speech.connectors.kokoro`; it imports
   `runtimes.speech.runtime`, which does. The check asked whether the
   bootstrapper *names* a module when the question is whether it *reaches* one.
   `_reachable_from_boot()` now walks the import graph, following relative
   imports, and is deliberately over-approximate — an import inside a function
   body counts. On the first run it caught **three** false dormancy claims, not
   one.
2. **A relative import was read as a third-party package.**
   `from .kokoro import KokoroProvider` in `voice/providers/__init__.py` has
   `node.module == "kokoro"`, so the scan flagged the PyPI `kokoro` — and the
   module had been given a standing exemption to silence it. **An exemption
   granted to quiet a scanner bug is a hole that outlives the bug**, because
   nothing revisits it once the noise stops. `node.level` is now checked.
3. **Two exemptions named modules that import no network library at all.** The
   staleness test only asks whether the *file* exists, so an entry that has
   stopped being necessary looks identical to one that is load-bearing.

**The fixes.** `health_check(*, probe_model=False)` no longer loads anything by
default, and `test_health_check_does_not_load_the_model` is the guard.
`_ensure_pipeline()` now does what `voice/stt/whisper.py` does: try the cache
offline first — via `HF_HUB_OFFLINE`, since `KPipeline` has no
`local_files_only` — and ask the gate only when weights are genuinely absent.
`runtimes/internet/runtime.py` had a second ungated `DDGS` and got the
`66736fa` treatment. Both moved to `NETWORK_LIBRARY_GATED`.

`available` also changed meaning for Kokoro, deliberately: it is now "the engine
is installed and can write its output", **not** "the weights are here" —
establishing the second requires loading them. That is asymmetric with
`WhisperRecogniser.is_available()`, which does require a loaded model, and the
asymmetry is the honest one: listening decides whether to *offer a button*, so
it must know before the user presses; speaking follows a reply that has already
arrived, so resolving weights on first use costs a delay rather than a dead
control.

**Verified by restarting the server**: four HuggingFace and torch lines in the
boot log before, **zero** after.

### Speech is measured now — and dictated figures cannot be trusted

`backend/tests/test_speech_roundtrip.py`, seven tests, with two committed
fixtures under `backend/tests/fixtures/`. Kokoro speaks a sentence, it is
encoded to Opus-in-WebM — the container `MediaRecorder` produces — and Whisper
transcribes it. The listening half runs on the fixtures, so it needs
`zaram[mic]` and nothing else: **no torch, no spaCy, no 905 MB**.

Observed, live, through the real route over HTTP:

```
said:  My day rate for Harbour Lane is four hundred and twenty five thousand naira.
heard: My day rate for Harbor Lane is 425,000 Nira.
heard: My day rate for Harbor Lane is 400 and 25,000 Nira.
heard: My day rate for Harbor Lane is $400,000 and $25,000.
```

One sentence, one voice, one model, three transcripts. Two findings, and the
second is much the worse.

- **The figure is unstable.** "four hundred and twenty five thousand" parses as
  one number or two, depending on the run.
- **The currency is invented.** The audio says *naira*. The third transcript
  says **$**, twice, unhedged. A Nigerian day rate rendered as dollars is wrong
  by a factor of about fifteen hundred, in the direction that looks reasonable
  on an invoice, and nothing downstream can detect it because `$400,000` is a
  well-formed amount.

**So: speech is for prose. Amounts get typed, or get confirmed.** That is a
constraint on M9/M9a rather than a bug to fix in the recogniser, and it is
exactly what rule 9 exists for — the number leaves the building. Recorded as
`test_a_dictated_figure_is_not_guaranteed`, which asserts only that *some*
digits survive, because that is the strongest true statement available. Whether
`small` fixes the currency is worth measuring before the business layer ships.

**Where the variance lives, traced rather than assumed.** Kokoro's waveform is
not byte-identical between calls. Whisper on a *fixed* clip inside one process
is exact — three runs, one string — which is what located it. Across processes
it is not: `cpu_threads=0` lets CTranslate2 size its own pool from machine load,
and floating-point reduction order follows thread count. The test is named
`test_transcription_is_deterministic_within_one_process` for that reason; the
shorter name would assert something false while passing.

**Measured while doing it:** the mic extra is 61.7 MB of *new* wheels here
(av 27.6, ctranslate2 19.2, onnxruntime 13.8, faster-whisper 1.1) on top of what
the voice extra already brought — consistent with the 81 MB from-scratch figure.
Whisper `base` weights are **141 MB on disk**, not the 145 MB carried in from
the packaging notes; corrected everywhere.

### Zaram listens — the engine, the route, and the one moment it can leave

`voice/stt/whisper.py`, `POST /voice/transcribe`, `stores/micStore.ts`,
`components/chat/MicButton.tsx`. `zaram[mic]` pins in
`backend/requirements-mic.txt`.

**The chokepoint entry landed before the provider did**, which was the whole
point of putting it first: `faster_whisper` is in `NETWORK_LIBRARIES` because
`WhisperModel("base")` resolves through `huggingface_hub` and downloads 141 MB
without asking anyone.

**`NETWORK_LIBRARY_EXEMPT` is now two lists, and the split fixed a live
falsehood.** Every entry claimed to be justified by dormancy, and the
DuckDuckGo one had not been since `66736fa` — it is gated, not dormant, and
`test_..._not_reachable_at_boot` was therefore asking it the wrong question.
Had the bootstrapper ever imported it, a correctly-gated module would have
failed a test that could only be silenced by weakening the guard.

- `NETWORK_LIBRARY_DORMANT` — unreachable, checked against the bootstrapper.
- `NETWORK_LIBRARY_GATED` — reachable, and **asserted in the AST** to call
  `get_gate()` and to name `EgressDenied`. Prose in the reason column survives
  the deletion of the code it describes; a parametrised test does not.

**How the weights are governed, and why the order matters.** Offline first
(`local_files_only=True`), which is the ordinary case after the first run and
touches nothing. Only on absence does it ask the gate about
`huggingface.co/Systran/faster-whisper-base`, and under default deny the library
is never constructed. Asking unconditionally would log a decision about a
request that was never going to happen, and **a log full of entries for traffic
that did not occur is worth less than no log.**

**A refusal is the ordinary answer here, not an error**, so it reads like one:
the reason names the host and the size, the route returns 503 carrying it
unedited, and the composer renders it as written. Only `tiny` (75 MB) and `base`
(141 MB) have measured sizes; anything else says *"size not recorded"* rather
than inventing a number, and a test asserts that.

**Deliberate departures, both recorded so they are decisions rather than
drift:**

- **The button is press-to-start / press-to-stop, not hold-to-talk.** Holding is
  a pointer gesture: a keyboard or screen-reader user activating a button gets
  one event, not a down and an up. A control that is *both* asks the user to
  discover which gesture they performed. Same reasoning that gave the collapsed
  left-rail buttons real accessible names.
- **The transcript lands in the composer as editable text and is never sent.**
  A recogniser that mishears and then submits has spoken for the user.
- **`vad_filter` is on.** Whisper hallucinates on silence and push-to-talk audio
  is mostly silence, so this is rule 9 one surface earlier: invented words in
  the user's own input box.
- **The microphone is released on every exit path**, including the failures,
  and that is what `micStore.test.ts` spends three of its twelve tests on. The
  browser's recording indicator is the only sight the user has of Zaram
  listening, and nothing in the UI would reveal a leaked track.

**`check-no-cloud-speech.mjs` was flagging prose, and now has a self-test.** It
strips `//` comments but never tracked block comments, so a module explaining
*why* it does thirty lines of `MediaRecorder` plumbing instead of three lines of
the banned API was reported as a finding — the check disagreeing with its own
docstring, which promises that comments may discuss the API by name. Block
tracking is deliberately conservative (an opener must start the line), because
between "flag a comment" and "miss a use" only one of those errors matters.

Changing a guard and then reading it is not testing it, so the mutation cases
are checked in rather than run once in a scratchpad: `npm run check:speech` now
runs nine fixtures first, including *code after a block comment closes* and *an
unterminated block comment must not swallow the rest of the file*. Both were
observed to fail against a deliberately broken tracker. `check-visemes.mjs` was
mutation-tested before being believed; this is the same debt paid the same way.

### How the commit split actually went

Seven commits, not the six sketched here beforehand, and in a different order.
The plan put the shortcut fix first and folded invoices and formats together;
the dependency graph did not allow it.

**`artifacts/html.py` imports `.invoice` at module scope, and
`test_invoice_api.py` generates with `fmt: "html"` — an exporter that did not
exist yet.** So the exporters had to land before invoices, and invoices before
slides, because `render_deck` lives in the same module as `render_invoice`. The
real order was: formats → invoices → slides → project and memory scope → speech
→ shortcuts and rail → orbit drag → docs.

`backend/main.py` was touched by three of them, not two. It was split by
writing each intermediate state as *the final file with the later commits'
blocks removed* — never by retyping, which would produce a fourth version of
the code that can disagree with the one that was tested. Each state was
compiled and its own tests run before the commit was made.

Worth keeping for next time: **the split is a review.** Reading the tree one
commit at a time is what surfaced the `kind: "deck"` 500 — the branch and the
model that fed it were written in the same session and never read against each
other.

### Do these first

Worst first. Nothing is broken. **Restart the backend before testing anything** —
see the build-stamp note at the top; a stale process cost two rounds on
10 August.

1. **Speech now plays promptly and lip-syncs — the remaining unknowns moved.**
   The maintainer's *"I've never heard Zaram respond with speech"* was answered
   on 11 August in part: the avatar was driven in a browser, `orbState` reached
   `speaking`, 31 viseme cues were live, and the mouth was caught open
   mid-word. **What is still unconfirmed is a human hearing it through a real
   output device** — every check so far reads `audio.currentTime` advancing,
   which is not the same as sound leaving a speaker.

   Two new items from that work:
   - **Synthesis runs at roughly real time on CPU (RTF ≈ 1.0).** Chunking hides
     the first sentence's cost, but there is *no headroom*: a reply of many
     short sentences can out-run synthesis and pause mid-way. Fixing that
     properly means Kokoro on the GPU, which is the VRAM decision `CLAUDE.md`
     deliberately took. Kokoro-82M is ~0.3 GB against a ~9.1 GB chat budget —
     worth revisiting now there is a number.
   - **`/voice/stream` is still known-broken and unused.** It builds the audio
     URL from the request id; the comment in `main.py` says it must not be
     wired up in that state. The chunking fix went through `/voice/synthesize`
     instead, so this is untouched and still a trap.

   The standing list below is unchanged for the input half:

   Both directions work against
   real audio at the API level — Kokoro synthesises, the URL serves
   `200 audio/wav`, Opus-in-WebM decodes, Whisper transcribes, the weight
   download was refused and then permitted and observed. What remains untested
   is the browser at both ends: `MediaRecorder` with a live input device, and
   `<audio>` playback with a live output device. The specific unknowns:
   - whether Chromium's muxer produces something PyAV decodes. The fixtures are
     Opus-in-WebM written by `av`, not by Chromium, so the *format* is exercised
     and the *producer* is not.
   - whether `vad_filter` handles real room noise. It is proven on synthetic
     silence, which is the easy case; a fan and a street are not.
   - whether autoplay policy blocks the reply audio. `speechStore` handles it
     and now renders the reason, but it has never fired.
   - ~~speech only plays when the toggle is `avatar` and nothing says so.~~
     Closed by `67ca372`: a **Speak** button on each reply when the orb is the
     renderer. The remaining unknown is whether it works against a real output
     device.
2. ~~**Speech must not write figures.**~~ Decided and enforced, 10 August:
   **confirmed, not typed-only**. `backend/voice/stt/figures.py` flags any
   amount, currency or number in a transcript and `/voice/transcribe` returns
   it; the composer renders an amber caution naming the observed failure. It
   **never corrects** — rewriting `$` to `₦` is guessing intent from unreliable
   audio. Still open: whether Whisper `small` fixes the currency, worth
   measuring before M9/M9a.
3. **The citation UI's `web` half has never been rendered with real data.**
   Unchanged from 8 August. Built against a shape the backend can emit and has
   not, because search is default-deny. **Do not treat that path as verified.**
4. ~~**The avatar's GPU cost is unmeasured.**~~ **Measured: ~190 MB.** See
   below. What remains is not measurement but the decision it unblocks — the
   warning copy, and whether `docs/UI-SPEC.md`'s ban on 3D on the landing
   survives a number this small.
5. **`Artifact.indexed` interaction with project scope is unexamined.**
5b. **Pointer-tracking gaze was built and removed on 11 August.** Not on
   principle — because it did not visibly work, and the reason is the lesson:
   the maths had unit tests and the `.vrm` was confirmed to carry a `lookAt`
   bone rig, and **neither is evidence that an eye moved on screen.** The
   asset's fringe covers the eyes at 320px, which was noted at the time and
   then not checked. `lib/gaze.ts` and its tests are deleted; if it returns it
   returns with a screenshot showing two different eye positions.
5c. **`RECENT_CONTEXTS` in `LeftRail.tsx` is invented data** — "zaram-core
   v0.4.2", "Vector store sync", "Agent: code-review", with timestamps. It
   renders on every workspace and violates "never render invented values".
   Flagged 10 August, left alone because removing it versus wiring it to real
   data is a product decision nobody has taken.
6. ~~**One unexplained 404 on every page load.**~~ Closed, 10 August: it was
   `/favicon.ico`. See below.
7. ~~**Project exists but nothing can be moved into it yet.**~~ Closed,
   10 August. Files and facts both move, from Project and from Memory. See
   below.
7b. ~~**Projects that exist only on artifacts cannot be adopted.**~~ Closed,
   11 August. Project lists them under "not projects yet" with an **Adopt**
   action; `GET /projects/unclaimed` finds them and `POST /projects/{id}/adopt`
   claims one, keeping the id exactly. The startup-backfill alternative was
   rejected: it would invent a name and a type nobody chose, and the type is
   rule 7e's one genuine exception — it activates a pack and cannot be inferred
   from behaviour. Adoption **is** the creation moment, so it is where the
   question is asked.

   The second half matters as much and is easy to forget: **generation was
   validated too.** `PATCH /artifacts/{id}` checked its destination and
   `POST /artifacts/generate` did not, so a file could be *born* into a project
   it was then forbidden from moving into. That asymmetry is how `harbour` and
   `northwind` arrived. Adoption without it would keep refilling the list it
   had just emptied.

   Verified against the real database on this machine: both ghosts listed with
   their counts, `harbour` adopted through the UI as "Harbour Lane"/business
   with its file intact, then reverted with `DELETE /projects/harbour?contents=keep`
   so the maintainer picks the real name and type. Chat's `project_id` is still
   unvalidated and deliberately so — refusing a message because of a stale
   selection is worse than a ghost scope, now that ghost scopes are reclaimable.
8. **The whole project-scope path is still barely exercised on real data.**
   `spine.db` held **zero** `project:*` facts before this session. One fact was
   scoped, observed and moved back during verification, so the path is *proven*
   — but proven once, by hand, is not the same as exercised. Rule 7i's project
   half still has not run in anger.

### The road to alpha — asked for 11 August, one fork still open

Four steps, and the first costs no code.

**0. Code signing, starting now, in parallel.** The longest-lead item and the
only one here that *cannot be compressed later*. Windows business verification
as a Nigerian sole trader is an unknown that needs a real answer before M11
finishes, not after. Unsigned, SmartScreen warns on a product whose entire
claim is trustworthiness — the alpha's day-30 number would be measuring the
warning rather than the product. Paperwork and waiting; every day not started
is a day added to the end.

**1. M9a, obligation extraction.** The half the alpha measures. Needed under
every branch below, so it is never wasted work.

**2. The cloud engine + M10, as one commit.** This is the step that will be
argued down, and the argument is wrong. `runtimes/models/engines/` contains
**only `ollama_engine.py`** — there is no cloud chat, and "chat routed to at
least two providers (one cloud, one local)" is a failing v1 scope line.

The tempting shortcut is a local-only alpha. It fails on **recruitment**, not
on capability: every tester would need Ollama and adequate VRAM, which filters
fifteen freelancers down to the technical ones — and `CLAUDE.md` says plainly
that the target user is not technical. A day-30 number from fifteen people who
can configure Ollama measures a different market than the one being aimed at,
so six weeks buys a number nobody can act on. M10 ships in the same commit
because rule 8 gets teeth the moment a cloud engine exists.

**Decided by the maintainer, 11 August: cloud is in v1**, on exactly that
ground — "people without a graphics card and low hardware".

> **Step 2a — the engine, landed 11 August.**
> `OpenAICompatibleEngine` exists, satisfies `LLMEngine`, and is covered by
> `test_cloud_generation_invariant.py`. It has **no HTTP client**: the body is
> built and handed to `EgressGate.stream_lines`, which is new and is the gate
> growing the one shape it lacked. The first draft did own a client —
> `check` then `requests.post` — and `test_egress_chokepoint.py` rejected it on
> the first run, correctly. The remedy the scan demands was the right one.
>
> **No LiteLLM**, deviating from `CLAUDE.md`'s dependency table and recorded in
> the module rather than done quietly. `/v1/chat/completions` is already the
> lingua franca — OpenAI, OpenRouter, Groq, Together, DeepSeek, Mistral, vLLM,
> llama.cpp, LM Studio — and OpenRouter fronts Anthropic and Gemini. So the
> whole surface is one POST and an SSE parser with no new dependency, against a
> library that would enlarge the installer packaging cut by 81% *and* need an
> exemption from the chokepoint scan, since it brings its own client. Reversible:
> nothing above `LLMEngine` knows what is inside.
>
> **Step 2b — wired, 11 August.** `RoutedEngine` satisfies `LLMEngine` and
> sits where the single engine used to, so `ModelsService` and everything above
> it are unchanged. It delegates per message on the model's **declared
> locality**, read from what discovery recorded — never from the shape of the
> name. `gpt-oss` runs on Ollama, so a router matching `"gpt"` would send a
> local model's system prompt, recalled facts included, to a cloud provider.
>
> **Every unknown routes local**, and the asymmetry is the argument: guessing
> local costs a possibly-worse answer, guessing cloud costs the user's
> documents leaving on a lookup that failed. `HYBRID` counts as remote for the
> same reason — a maybe has to be treated as a yes. The gate would still refuse
> an unapproved host, but a design that leans on its last line of defence for
> ordinary behaviour has one line of defence.
>
> Configuration reuses the variables the provider layer already reads —
> `ZARAM_OPENAI_ENDPOINT` + `ZARAM_OPENAI_KEY`, or `OPENROUTER_API_KEY` — so a
> key configured once is *discovered and callable* rather than producing a
> catalogue of models that cannot be reached. No network call at construction
> (rule 7g): a key is validated by being used, at which point the gate has
> already logged and asked. **With no key, the engine is the local one
> unchanged**, so nothing about the previous behaviour depends on this path.
>
> Cloud requested with no key configured **says so** rather than answering
> quietly from a small local model — "disabled capabilities are visible, not
> silent", applied to model choice.
>
> Still missing at this layer: a **Settings surface**, so today the key comes
> from the environment; and `CLAUDE.md`'s three tiers of control
> (*Prefer local · Auto · Prefer cloud*) — there is a router, not yet a
> preference the user can express.
>
> **Step 2c — M10's dialog.** Until it exists the gate has no confirmation
> handler, and a gate with no handler *refuses*. That is the designed resting
> state and it is asserted: cloud generation is wired, tested, and declines to
> send. Shipping it half-done fails closed.

**3. M11 packaging + guided first run.** Acceptance unchanged. Three decisions
are already queued inside it — GTK for WeasyPrint, dev tooling in the base
install, and whether Jinja2 is a real transitive dependency.

**~~The gate nobody has scheduled.~~ Run 11 August, and it passes.** Recall had
only ever been evaluated on five documents; it is now measured at 10, 100 and
1,000. The margin narrows and then flattens — **+0.131, +0.108, +0.106** — with
5/5 targets recalled at rank 1 and zero false citations at every size. Full
numbers and the caveat are in Open questions.

**This does not clear the alpha, it clears one hypothesis.** The synthetic
corpus has four templates and ten client names, so it stops adding *kinds* of
document long before a real folder does — which is the most likely reason the
curve flattens. The measurement to want is the same one on real material, and
the honest place to get it is the alpha itself: `test_recall_eval.py` prints
the margin on every run, so a narrowing gap is visible before a user feels it.
**Watch that number during M12 rather than treating this as settled.**

**Paced out of the alpha, not cut — decided by the maintainer, 11 August.**
The distinction is the whole point and the wording of an earlier draft was
wrong: **none of these is dropped.** They keep their place in v1 and each has a
named re-entry point, because a thing "cut" quietly stops being anyone's
problem, and three of these are things the product has promised.

Each is *off the alpha's critical path* only, and none costs anything today,
because none is built or on by default.

- **M9c, read-only MCP for Unreal and Blender.** Not started. **Re-enters after
  M12 intake**, and the alpha itself decides how fast: if a tester's segment is
  3D rather than admin, it moves up. It is one of two v1 verticals and stays
  there — `CLAUDE.md`'s integration tests still pass for it.
- **Web search.** Already default-deny in code and needs no change:
  `planner.web_search_enabled()` reads `ZARAM_WEB_SEARCH` at call time and is
  off unless explicitly set. **Re-enters on its stated sequence, unchanged** —
  egress log, then per-source policy, then search as their first governed
  source. Both prerequisites exist, so this is nearer than its position
  suggests; the alpha simply does not need it to produce a day-30 number.
  Verified 11 August rather than assumed: the `config.json` that once declared
  `ENABLE_WEB_SEARCH: true` beside a default-deny product is deleted.
- **Image and video generation.** Post-v1 already. **Re-enters when the cloud
  engine lands**, which is step 2 — so this is paced behind a step the alpha
  may well include, not behind the alpha. The shape is settled: Zaram ships no
  weights ever, routes to a provider, logs the egress, carries project context.

**Ordering, set by the maintainer 11 August: M9a goes last**, after the cloud
engine, packaging and the recall-at-scale gate. That does not shorten the path
— the alpha cannot start without obligation extraction, since it is the half
the alpha measures — but it attacks the *stated* blocker earlier, and it means
M9a is built against a packaged product rather than a dev tree. The cost to
watch: it is the least-understood piece, and discovering a problem in it last
is the expensive way to discover one.

**~~Still open~~ — answered 11 August: the alpha waits for the cloud engine**,
and the maintainer's reason is the one that matters more than the
recommendation above: *"Zaram is local first, but v1 should come with cloud, so
people without a graphics card and low hardware"*. Local-first is not
local-only, and the constraint was never capability — it was who can run it.

**What is genuinely still open**, and neither blocks the next session:

* **Where the API key is captured.** It comes from the environment today, which
  is fine for a developer and useless for the freelancer the cloud path exists
  to serve. Settings is the obvious home; nobody has designed it.
* **The three tiers of control** — *Prefer local · Auto · Prefer cloud*. There
  is a router; there is no preference the user can express, so today the model
  chosen per message is the only lever.

### Next, in the order I would take them

Not a queue anyone has committed to — a recommendation, with the reasoning, so
the next session can disagree cheaply.

**Superseded for the alpha by "The road to alpha" above**, which the maintainer
set on 11 August: the cuts are decided and M9a goes last. The list below is
kept because the *reasoning* per item is still the best record of why each
thing is worth doing — read it for the why, and take the order from the road.

**Re-ordered 11 August**: the maintainer asked for the business layer directly
("work on the invoice and other types of document"), so item 1 is now partly
built — invoices generate, and `.docx`/`.xlsx`/`.pdf`/`.md`/`.html`/`.txt`/
`.csv`/`.pptx`/`.png` all export. **What M9 still needs is obligation
extraction**, which is the half that was never started and the half the alpha
measures. The invoice was deliberately built first so obligations have real
terms to read rather than fixtures written to make them pass.

1. **Obligation extraction — M9a, and the half M9 is still missing.** The
   invoice half landed on 11 August, and it landed as a **refusal surface**
   exactly as this item argued: `invoice.py` raises `InvoiceIncomplete` rather
   than defaulting a price, a quantity or a line, and the route returns it as a
   400 the caller can act on. That is rule 9 working where it does the most
   damage.

   What remains is the keystone: **dates and commitments pulled out of
   documents and surfaced before they lapse, each showing its source clause and
   correctable.** The due date is already derived from `terms_days` and carried
   on the record, and the terms sentence is printed on the page — so the seed
   and its evidence both exist. Acceptance is unchanged: on day 31 Zaram says
   the payment is late, shows the clause it read that from, and has the
   follow-up drafted; correcting a wrongly-extracted date moves the reminder.

   A quote template is the second pack example and is still worth building by
   hand — *build two packs by hand before building the pack system*.
2. **The preview panel with page navigation.** Asked for directly. Much cheaper
   now that documents have real pages — the HTML *is* the paginated document, so
   this renders what exists rather than reimplementing pagination. The pattern
   to copy is a scroll container of page-sized sheets, not a PDF viewer.
3. ~~**Assignment**~~ — done, 10 August. ~~Its successor is **item 7b**~~ —
   also done, 11 August. Project adopts the groups that existed only as strings
   on artifacts, and generation now validates its `project_id` so no more
   arrive. See item 7b for what was decided and what was deliberately left.
3b. **Rank fusion and lexical retrieval**, from the TencentDB review above.
   Small, and it is the only change on this list that attacks a *documented*
   failure rather than adding capability: rule 9's invented "Project Phoenix"
   is a rare-token problem, and rare tokens are what a lexical index finds and
   an embedding misses. RRF is the safe way to combine the two here, because it
   cannot be compared against a citation floor by accident — which is the
   mistake this codebase has now made three times.
4. **Packaging.** `CLAUDE.md` still calls this *the actual blocker*: "a stranger
   cannot install this… capability is not what stands between the current state
   and a 15-person retention test." Nothing this session moved it. If the next
   milestone is real users rather than more capability, this is the honest
   answer and it should jump the queue.

### Asked for, and deliberately not built

- **TencentDB Agent Memory as a dependency.** MIT, so not a licence question —
  a packaging one. Node ≥22.16 as three Docker services against a Python
  backend whose stated blocker is that a stranger cannot install it. Its ideas
  were taken; its code was not. See the review above.
- **The four-tier memory pyramid.** L1/L2/L3 is Zaram's `global` /
  `project:<id>` scope field with more machinery, and rule 7i already argues one
  field on one store is the better shape. L0 is rule 7d inverted and is refused
  outright.
- **Pointer-tracking gaze.** Built and removed the same day — see item 5b. The
  argument for it still stands; the verification did not.
- **Running the user's apps from a repo inside Zaram.** Splits in two. Rendering
  generated or simple web content in a **sandboxed frame** is v1-feasible and is
  the same technology as the document preview. Executing code from a repository
  is arbitrary execution on the user's machine — queued step 5, "tier-gated,
  post-v1", and rule 6 says tools confirm before acting. It needs a sandbox
  story before anyone touches it.
- **Folder trees inside Project.** One level of grouping, permanently. A
  hierarchy competes with scope, provenance and recall; if a tree is needed to
  find your own work then recall has failed and the tree hides that.
- **Sub-apps inside Work for editing.** See the note above — settled on licence
  and size grounds, with the narrow HTML-editing version recorded for post-v1.

### Queued — the architecture discussed, not started

In build order. Steps 1–3 are weeks and step 3 is where a to-do list becomes
Zaram.

1. **A project record.** There is none — `/artifacts/projects` derives the list
   by collecting distinct `project_id`s off artifacts, so a project is an
   emergent label rather than an object. Everything below needs one, and its
   creation is the only honest moment to choose a **type** (business, coding,
   MCP, 3D), which activates a pack.
2. **A durable plan object in the Spine**, scoped `project:<id>` — steps, state,
   decisions taken **and rejected**. A plan is an obligation you owe yourself,
   so it is M9a's object with `origin = authored` rather than a new subsystem.
   **Naming collision to settle first:** `RoutingPlan` and `PlanState` already
   exist and are ephemeral — a `RoutingPlan` decides which model answers one
   message. The durable user-facing object should be "Plan"; rename the internal
   one while it is still internal.
3. **Plan carried into recall** — the current step is context, and the Spine is
   already provider-neutral, so this works across models for free.
4. **Outcome and drift** — recorded from conversation, never from autonomy.
   Never infer a plan step and assert it: a plan that quietly decides you
   committed to something breaks the rule that a missed deadline is worse than
   no reminder.
5. **Execution** — tier-gated, post-v1. Per-project agent config should be a
   **tool-tier grant**, not a list of agents: "may things be changed in this
   project" is answerable at creation; "which agents may run" is not.

Also queued: **the consistent mind is unbuilt and will not emerge from recall.**
Consistency comes from constraining inputs and outputs — schema-constrained
generation where shape matters, one provider-neutral system prompt carrying
global-scope style facts, few-shot from outputs the user accepted. Transport is
solved by LiteLLM; behaviour is solved by nobody. Mine Letta, Aider's
`CONVENTIONS.md`, Continue.dev, Instructor/Outlines for patterns — never adopt
as architecture, and verify every licence at adoption. It needs an eval, built
as carefully as the recall eval, or it is a claim in a pitch deck.

### The local model is not the centre of truth — the Spine is

Decided 10 August 2026, in conversation, and written here because it is the
shape of the consistent mind above and the question will otherwise be re-asked
every time someone notices how much a cloud turn costs.

**The proposal.** Make a resident local model the centre of truth: it holds
context across sessions, projects and chats, recalls fast, stays consistent, and
keeps the cloud models in line — so a session uploads almost nothing and spends
almost no tokens.

**The half that is right, and it is the more important half.** Sending recalled
*facts* instead of transcripts is the whole economic argument for this product,
and it compounds per turn. `MAX_RECALL` is 6. That is the difference between
carrying a project's history into every message and carrying six sentences.

**The half that is wrong.** Truth must live in records, not in weights. Rule 2 —
every recalled fact carries provenance — is only enforceable when a fact is a
row with a source. A model *is* the hallucination the Spine exists to remove, so
promoting it to the authority reintroduces the failure and removes the ability
to detect it: an answer from weights cannot be corrected, deleted, or traced,
which takes rules 2 and 4 with it. **The model is a renderer of the Spine, never
a copy of it.**

**What the local model can be trusted with — one test: is the output checkable
against a source?**

| Job | Checkable | Verdict |
|---|---|---|
| Routing | deterministic, no generation | already built, embeddings |
| Query rewriting for recall | against what it retrieves | yes |
| Schema-constrained extraction (obligations, invoice fields) | against the source clause | yes — and it is M9a |
| Session → fact compaction | against the transcript | yes |
| Open-ended reasoning and drafting | no | route it |

A local model **supervising** a cloud model fails that test and is rejected:
it is a second thing that can hallucinate, holding no ground truth the Spine
does not already hold. Where a check is genuinely possible it should be a
lookup — does every claim trace to a source — not an inference. That is rule 2
and rule 9, which already exist, rather than a new subsystem.

**Two consequences worth designing for now.**

- **Prompt-cache order.** A recall block that varies every turn sits in front of
  the stable text and busts the provider's prefix cache, so the token saving is
  paid back as a lost cache discount. The payload wants **stable prefix first**
  (the provider-neutral system prompt, global-scope style facts, project
  constants) and **varying recall after it**. This is a constraint on the
  consistent mind's system prompt, not a separate piece of work — and it is
  measurable, so it belongs in that eval.
- **Do not put the local model on the critical path of every request.** Rule 1
  means the user brings their own model, so on a 6 GB machine that model is
  small. If every request must pass through it, Zaram's quality is gated by the
  user's GPU in a way *any model, one memory, nothing leaves without you seeing
  it* does not promise. The **Spine** is what belongs on the critical path: it
  is deterministic and needs no accelerator at all.

### Two inert features became real, and both were inert for the same reason

`apply_decay` and the citation floor were each written, tested, green, and
never actually reached the thing they were about. The pattern is worth naming
because it has now happened four times in this codebase: **a contract with two
implementations, where the tests exercise the one the product does not run.**

- `access_count` incremented on `InMemoryMemoryStore` and not on SQLite.
- `apply_decay` read `store._records` — a private dict only
  `InMemoryMemoryStore` has. On SQLite `hasattr` was simply false, the id list
  came out empty, and every pass reported a clean run over zero records. No
  error, no warning, nothing decayed, ever.
- The citation threshold was compared against the ranking blend rather than
  the similarity.
- And now: the *shortlist selection* was made on the ranking blend too.

`test_decay_runs.py` is parameterised over both stores for exactly this
reason. Never test one without the other.

### Closed on 8 August

- ~~**Nothing calls `beginModelSwap`.**~~ ✅ Now a *pre-flight* check, below.
- ~~**Nothing sets a project scope.**~~ ✅ M8 is real, below.
- ~~**Citation UI at step 3 of 5.**~~ ✅ Steps 3–5 done and driven in a browser.
- ~~**The eval's filler answered its own questions.**~~ ✅ Fixed, and guarded by
  a test that runs in the default suite.

The live thread list is in **Do these first** at the top of this file, not here.
Two lists of what to do next is how one of them goes stale unread.

### The swap is announced before it happens, not during

`ProviderManager.swap_preflight(model)` asks Ollama `/api/ps` what is
**actually resident right now** and decides before generation starts. The orb
gets a `model_load` stream event ahead of any token.

"Before" is the whole point. A spinner appearing once the machine has already
stalled is not visibility — by then the user has spent the seconds and drawn
their own conclusion about why Zaram is slow.

**Four outcomes, because the remedies differ**, and a boolean would hide that:

| kind | means | remedy |
|---|---|---|
| `resident` | already loaded | nothing said |
| `load` | fits alongside what is there | a cold start; passes on its own |
| `swap` | something resident must be evicted | recurring, it is a model assignment the user can change in Settings |
| `oversized` | bigger than the whole budget | a hardware fact no setting changes |

Plus a fifth answer that is not an outcome: **`None`, for "cannot tell"** — no
accelerator, unreadable VRAM, unreachable Ollama, unknown model. Nothing is
announced then. Announcing a swap that does not happen trains the user to
ignore the indicator, which costs more than staying quiet.

**Verified live**, with gemma3 actually loaded on the dev machine:

```
resident now: {'gemma3:latest': 2.84 GB}
  gemma3:latest       -> resident
  qwen3:latest        -> load
  qwen2.5-coder:14b   -> swap, evicts ['gemma3:latest']
```

**Two defects found only by running it against the real provider layer**, both
invisible to the unit tests:

- **Three spellings of one model name are in play** — the catalog id is
  provider-prefixed (`ollama:gemma3:latest`), `/api/ps` and the chat path use
  the provider-native name (`gemma3:latest`), and a config file may use the
  bare name (`gemma3`). Comparing ids alone matched none of them, so
  `swap_preflight` returned `None` for *every model on the machine* while the
  tests passed — the fakes happened to be keyed the same way as `/api/ps`. It
  failed the right way, silently rather than falsely, and it failed completely.
  `TestTheRealCatalogShape` now uses discovery's actual shape.
- **A model too big for the whole card was reported as a `swap` evicting
  nothing.** Not a swap — nothing displaced would make room, and an indicator
  that names nothing evicted cannot explain itself. That is what `oversized`
  is for, and it was found by a test asserting the embedder was excluded, which
  it correctly was; the empty `evicts` was the real defect underneath.

### M8 is real — project scope reaches the Spine

`ChatRequest.project_id` → `ChatRouter.route` → `ExecutionEngine.execute` →
recall scoped to `project:<id>` plus global, and capture written under it.
`ProjectScopePicker` sits under the chat input, sourced from
`/artifacts/projects`.

**Verified with real embeddings**, not just tests:

```
scope='project:harbour'  'My Harbour Lane day rate is 425,000 naira.'
scope='global'           'I prefer short emails.'
recall inside harbour -> project:harbour | ... | relevance 0.593
```

`None` and `global` are deliberately different instructions. As a *recall*
filter `None` means every scope — right when the user is not inside a project,
where `global` would hide their own project material from them. Capture
converts `None` to `global` separately.

**Found by driving it:** `/artifacts/projects` returns `[{id, count}]`, not
`[string]`. The picker assumed the simpler shape, rendered an object as a React
child, and **took the entire conversation surface down** — a blank page after
clicking the orb. The same drift that made `sampleArtifacts.ts` disagree with
the backend model, and the reason the artifacts client uses backend field names
directly rather than through a mapping layer.

### Citation UI — steps 3, 4 and 5, driven in a browser

`CitationChips.tsx` (chips + summary line) and `CitationPanel.tsx` (grouped by
egress). `frontend/scripts/drive-citations.mjs` is re-runnable.

Observed, against a live backend:

```
summary line: "4 sources · nothing left this device · 2 recalled, not cited"
chips: numbered, cyan rgb(120,220,240) — the local colour
panel:  nothing left this device
        1  My day rate for Harbour Lane is 425,000 naira.   relevance 1.00
        2  My day rate for Harbour Lane Studio is 425,000…  relevance 0.95
        3  My day rate for Ashgrove Films is 750,000 naira. relevance 0.77
        Recalled but not cited — read, and not what carried the answer
        INVOICE FROM BILL TO … · 0.50    INVOICE Services … · 0.48
Escape closes: true
empty state on "capital of France": true
```

**`MIN_CITATION_SCORE = 0.55` is visibly doing its job** — cited at 0.77–1.00,
recalled-and-not-cited at 0.47–0.50, with the gap shown rather than hidden.
That is the "cited versus *used*" problem from the last session, closed.

**A defect driving found:** the panel printed a memory's text twice — once as
the title, once as the excerpt. The guard compared them for equality, and they
are never equal because the title truncates at 120 characters and the excerpt
at 400. It reads as a bug in recall rather than in layout. Now compared on the
prefix, and skipped entirely for `memory`, whose title *is* the fact.

### Rule 7e now runs — daily, plus once shortly after boot

`runtimes/memory/maintenance.py`. `SpineMaintenance` calls `apply_decay()` and
`promotion_candidates()` on one pass, wired into the backend lifespan and
stopped cleanly on shutdown. `GET /memory/maintenance` reports what the last
pass did.

**Why that schedule, and it is not a guess.** Every threshold in `DecayConfig`
is expressed in whole days — a 90-day half life, `age_days > 30`,
`age_days > 7` — so a pass more often than daily cannot change a single
outcome. Daily is the finest interval the rules can distinguish. Daily *alone*
would not be enough, though: Zaram is a desktop app, and someone who opens it
for an hour each morning never reaches a 24-hour timer. The startup pass (60s
in, clear of the first question) is what makes it real for how the product is
actually used. Both are overridable by env for testing, and nothing in the
product sets them.

**Verified against a live server, not just tests:** booted on 8422, waited for
the pass, `GET /memory/maintenance` returned
`{"decay":{"boosted":14,"total_records":14,...}}` — fourteen real records in a
real SQLite Spine. Before the fix that pass reported zero records and did
nothing, silently.

**Promotion proposes and never promotes** (rule 6). The endpoint returns
candidates with their content and `recalled_in` evidence; promoting is a
separate call the user makes. Note that it will return **nothing** until
something sets a project scope — see "Do these first" item 2.

**One thing to watch.** Decay *boosts* `importance`, and importance carries
weight 0.20 in the ranking blend — see below. Now that decay actually runs,
frequently-accessed facts will climb the ordering over time. That is intended,
but it is a feedback loop that has never been able to operate before, and its
effect on recall quality has not been measured over any real span of time.

### The reranker question is closed — 5/5 at 1,000 documents

```
[1000 docs] recalled in top-6: 5/5 answerable targets
[1000 docs] target ranks by relevance: [1, 1, 1, 1, 1] — deepest 1, headroom 5
[1000 docs] blend-driven exclusion: none
[1000 docs] false citations: 0/18 (0%) at floor 0.42
[1000 docs] related_min 0.517 - unrelated_max 0.410 = +0.106
[1000 docs] mean recall latency: 673 ms
```

**Every answerable target is now the single most relevant document in a
thousand.** Two changes got there and neither was a purchase: selection moved
onto relevance, and the eval's corpus stopped answering its own questions.

**The margin reads lower — +0.106 against the +0.179 recorded before — and that
is not a regression.** `related_min` was 0.589 only because the document
scoring 0.517 was being excluded from the shortlist entirely and so never
entered the sample. Recalling it correctly put a real 0.517 into the population
that had been silently missing from it. The old number was flattering because
of the defect. This one is honest, and 0.42 still sits inside it with room.

**Worth watching:** +0.106 is a narrower gap than the headline used to suggest,
and `test_recall_eval.py` prints it on every run for exactly that reason. If it
narrows further as real corpora grow, *that* is when the reranker question
reopens — on evidence about scoring, which is what a cross-encoder actually
fixes, rather than on a miss count that turned out to be about something else.

### The ranking fix, and what the eval got wrong

**Instruction for this session was "fix the depth, not the ranking". The
measurement says depth was never the problem, so this is a deliberate
departure — recorded here with the numbers that forced it.** No reranker was
bought; the change is cheaper than raising depth, not more expensive.

At 1,000 documents the eval reported one miss and diagnosed it as displacement
at rank 7 — a shortlist too narrow. Widening the shortlist did not fix it, and
looking at *why* found something worse. For *"How should I write to clients?"*
the target sat at **rank 43 with relevance 0.599 — the highest similarity
anywhere in the eval** — behind 42 documents it out-scores on relevance.

The arithmetic makes that inevitable rather than unlucky:

| signal | weight | realistic range | swing |
|---|---|---|---|
| semantic | 0.35 | 0.30–0.60 | **~0.10** |
| importance | 0.20 | 0.0–1.0 | 0.20 |
| recency | 0.15 | 0.0–1.0 | 0.15 |
| access | 0.10 | 0.0–1.0 | 0.10 |
| keyword | 0.10 | 0.0–1.0 | 0.10 |
| session | 0.10 | 0 or 1 | 0.10 |

Similarity contributes a swing of about **0.10** against **0.55** for
everything else, because cosines live in a narrow band while the other factors
are normalised across their full range. **Non-relevance signals outweigh
relevance roughly four and a half to one**, so on a corpus of near-identical
invoices the blend decides almost everything.

**The fix is selection by relevance, ordering by the blend.** `rank()` now
picks the top `max_results` by similarity and *then* sorts those by the blend;
`_recall` does the same before its cut. Ordering inside the shortlist by the
blend is right and stays — a pinned, recent, frequently-used fact should be
shown first among equally relevant ones. What must not happen is a document
being *excluded* on anything but relevance.

This is the same lesson the citation floor already taught, one step earlier in
the pipeline. The floor was moved off `score` and onto `relevance` because
ordering and permission are different questions. **Membership of the shortlist
is a third question, and it belongs with relevance too.**

**Where exactly the loss happened, traced rather than assumed.** The index
already returns its top `max_results` *by cosine*, so the candidate pool was
never the problem — `_vector_search` takes `indexed[:max_results]` off a
similarity-ordered list. The pool of 25 genuinely contained the best document.
It was the **final 25 → 5 cut in `_recall`** that threw it away, because that
cut took the first five of whatever order retrieval returned, and that order is
the blend. So the fix that matters is three lines in `_recall`; the matching
change in `rank()` guards the same mistake against the keyword path, which
merges its own candidates into the pool and can displace on the blend before the
engine ever sees them.

`MAX_RECALL` 5 → **6**, and it is no longer also the citation count —
`MIN_CITATION_SCORE` decides that separately, so widening what the model can
use no longer widens what the user is asked to check.

**Two of the eval's own tests were measuring the wrong list**, which is why
this took three runs to see. They read the raw blend-ordered results and then
asserted things about the shortlist; those are different lists, and reading the
second while reasoning about the first is what made an ordering defect look
like a depth defect for a whole cycle. `_engine_shortlist()` now mirrors
`_recall` exactly and the tests assert against that.

**And a diagnostic that agreed with me was wrong.** A stability check compared
two consecutive top-10 slices, passed, and proved nothing — the instability
lives at the shortlist boundary among documents whose scores differ in the
third decimal, not in the top ten where the gaps are wide. Rewritten to track
the target's own rank across six repeats, it showed retrieval is in fact
perfectly deterministic (`[54, 54, 54, 54, 54, 54]`). The earlier
disagreement between two tests was the ordering change, not non-determinism.

### The eval was grading itself, and had been for three cycles

The last residual miss was not a product defect at all. `_filler()` drew
deliverables from a list containing **"title sequence"**, and emitted them in a
brief template carrying a duration and a date — the same shape as the expected
answer to *"How long is the title sequence?"*. Counted: **64 of 995 filler
documents answered that question exactly as well as the target did**, for
different clients, and the question names no client.

Ranking the expected document 54th out of 65 equally valid answers is *correct
retrieval*. The eval had been reporting it as a recall miss and inviting a
reranker to fix it.

`_SVC2` no longer contains "title sequence" — the filler is still the same
*shape* of document, which is what makes it a useful distractor, it simply no
longer answers the question being graded. `TestTheCorpusIsFitToMeasureWith`
enforces that, runs in the default suite, needs no Ollama, and fails with the
collision count.

**The general lesson, and it is the sharpest one here.** This file already says
a stable failure count everyone stops looking at is how a real regression hides.
This is the mirror image: *a stable failure count nobody can explain is how a
broken instrument survives.* "4 of 5 recalled" survived three measurement
cycles and nearly bought a cross-encoder, because nobody asked whether the
corpus could grade the thing it was grading. **Check the instrument before
reading the measurement.**

### Citation UI — step 2 of 5 done

`StreamEvent.source` now carries `excerpt`, `relevance`, `cited`, `number`,
`egress_id`, `bytes_sent`, `origin` and `record_id` alongside `kind`, `url`,
`title`. Keyword-only past `title`, because five optional strings in a row is
how an excerpt ends up in the url slot at one call site and nowhere else.

- **`MIN_CITATION_SCORE = 0.55`** — a second, higher cut on the same
  `relevance` field. Sits inside the observed 0.50–0.61 band from the day-rate
  reply, so the fact that carried the answer is still cited and the
  merely-adjacent ones move to the panel's quieter section.
- **Recalled-but-uncited sources are still emitted**, with `cited=False`.
  Dropping them would hide the gap between the two thresholds, and that gap is
  what makes the cut arguable rather than magic.
- **Web sources are always cited**, never thresholded. That is an egress
  disclosure, not an attribution judgement, and a relevance score is not a
  reason to stop telling someone what left their machine. `kind` is normalised
  to `web` rather than passing the provider name through — the UI colours by
  egress, and a chip saying "tavily" makes the user learn a vocabulary to
  answer the only question that matters.
- **A fact from one of the user's files is `document`, not `memory`**, and its
  title is the filename they recognise rather than a snippet of its text.
- **Citation numbers are assigned server-side, after dedupe**, at the single
  point every source event passes through. Numbering in the emitters would
  double-count a source that recall and search both surfaced, and the user
  would see a reply citing 1, 2 and 4.

### The orb has a `swapping` state

`orbStore` (visual), `systemStore` (`OrbActivity`, the model name, and the
plain-language label), rendered by `LivingOrb`, `Aura`, `Halo` and `OrbCore`.
Dimmer and slower than every other state, in desaturated slate — every other
state animates *faster* to signal effort, and a swap is the one state where
nothing is resident and no work is being done. Cyan and violet are not spent
here because they already mean "stayed" and "left" on the orb and in citation
chips.

Set it through `systemStore.beginModelSwap(model)` / `endModelSwap()`, never
`setOrbState('swapping')` — the orb and its label are two renderings of one
fact, and setting one without the other turns the orb slate-grey while the
words still read "Local only".

**Found doing it:** the per-state variant maps in `Aura`, `Halo` and `OrbCore`
were untyped object literals, so adding a state produced no build error and
framer-motion silently animated to nothing. Now `Record<OrbState, …>` — the
same remedy M6 applied to the surface list. `LivingOrb` also declared its own
four-member copy of `OrbState` instead of importing the store's; it now
re-exports it.

### What this session settled

**The frontend has been driven.** M4's UI acceptance, outstanding for four
milestones, is met — see M4 below. Four defects came out of it that no unit
test had, including the citation threshold being compared against the wrong
number for the entire life of the product.

**The reranker question is answered: don't buy one.** `docs/RERANKER.md` has
the options and costs; `test_recall_at_scale.py` has the measurement that
decided it. The margin *holds* as the corpus grows — +0.147 at 10 documents,
+0.181 at 100, +0.179 at 1,000, with zero false citations at the floor. The one
miss at 1,000 was **displaced at rank 7 with relevance 0.517**: above the floor,
outside a top-5. A depth problem, not a scoring one, so `RECALL_CANDIDATES = 25`
and cut to `MAX_RECALL` after the floor. Costs one wider read.

Also verified there: the Ollama reranker route crashes llama-server *and* evicts
bge-m3 and gemma3 with it.

**Residency is measured and CLAUDE.md is corrected**: bge-m3 0.66 GB resident,
reranker 0 GB, KV reserve 2.58 GB, budget ~9.1 GB. The old "~1.8 GB" was wrong
in both directions. **It changed no decision**, because the fit gate never read
that constant — it computes from whichever embedder discovery found. One real
imprecision recorded: the gate uses on-disk size (1.16 GB) as a proxy for
resident VRAM (0.66 GB), which over-reserves ~0.5 GB and flips nothing between
4 and 24 GB.

**M8 is done** — see below.

**The avatar spike is scoped, not built**: `docs/EMBODIMENT-SPIKE.md`. Both
questions answered against the code.

**M7 is done and driven for real.** `backend/ingest/` — parser interface, light
parsers, quality floor, loud failures. Verified against a real folder: an
invoice indexed, an image-only scan reported with its reason and the OCR
remedy, an encrypted .docx reported as password-protected, then a cited recall
naming the source document.

**Recall was broken and is now measured.** The eval harness found, on its first
run, that hybrid retrieval was ranking on stopword overlap — an unrelated
question outscored a genuinely relevant document. Fixed in three places. See
"What the recall eval found" — this is the most consequential thing in this
entry.

**Docling is now an optional extra**, decided by measuring 1,080 real files.
CLAUDE.md's dependency table is updated; the reasoning is recorded there.

**Base install: ~317 MB.** 267 MB plus a *measured* 50 MB for the exporters
(matplotlib 31, fonttools 16, openpyxl and the rest 3). Voice remains an
optional 905 MB extra. If that 50 MB has to come back, the split is charts-only
— .docx, .md and .xlsx together are 2 MB, and matplotlib is the whole cost.

**M9b and Session 4 are committed.**
`backend/artifacts/` now has the model, the write path, the HTML layer,
`export/` (Markdown, .docx, .xlsx, PNG), `records.py` (SQLite) and
`service.py`. `main.py` serves `/artifacts`. Work reads real records and
`sampleArtifacts.ts` is deleted. **PDF is the only exporter not working**, and
it is blocked on packaging rather than on code — see Open questions.

**Verified against a live server**, not just tests: three artifacts generated
over HTTP, listed, previewed and downloaded through the Vite dev proxy on the
same path the browser uses.

**Generation is reachable from chat.** "Write that up as a proposal" routes to
`document.generate`, writes a .docx grounded in the conversation, and returns
it as a card in the transcript and a row in Work. M9b's acceptance criterion
is met.

**Routing is embedding-based.** `core/retrieval/` embeds the query with bge-m3
and compares against task exemplars. Keywords remain the fallback.

**Last commits:** semantic routing + chat-reachable generation → Work reads
real artifacts → the exporters → artifacts write path → Work surface →
dependency removals → packaging split → VRAM detection.

### The citation threshold was never applied to a similarity

The biggest single defect this session, found by driving the browser and seeing
a reply cite **five** memories — including a deploy target and an unrelated
client — for a statement the user had just made.

`MemoryRankerImpl.rank()` **overwrote** `result.score` with a blend:

```
0.35 semantic + 0.20 importance + 0.15 recency
+ 0.10 access + 0.10 keyword + 0.10 session_match
```

`ExecutionEngine` then compared that to `MIN_RECALL_SCORE = 0.42`, a threshold
measured and documented as a **cosine similarity** floor. Similarity carried a
weight of 0.35, so a fact with a true cosine of 0.20 could clear the floor on
recency and session membership alone. Every reply in the product has been
citing on that number.

`MemoryResult` now carries **two** numbers, because they answer two questions:

- `relevance` — similarity as retrieval produced it. What the citation floor is
  compared against.
- `score` — the ranking blend. Ordering only.

CLAUDE.md already draws this line for tools: *"retrieval produces a shortlist;
the model chooses; a retrieval score authorises nothing."* Citation is the same
shape — rank on whatever is useful, but decide **whether to cite** on relevance
alone.

The index was also made to return a similarity rather than a blend: keyword
overlap decides *membership* of the candidate set, and `MemoryRankerImpl`
already weights it at 0.10 for ordering, so adding it to the score double-counted
it and made the number something other than the cosine the floor was measured
against.

**Measured effect: the eval margin went from +0.080 to +0.147** — related
bottoming out at 0.517, unrelated topping out at 0.369, floor 0.42 in the gap.
Those are now raw bge-m3 cosines, which means the distribution recorded in
`MIN_RECALL_SCORE`'s docstring in April describes reality for the first time.
Verified live: the unrelated deploy-target fact is no longer cited.

**Still open, and known:** a reply about a day rate still cites five memories,
now all genuinely about day rates and payment terms (0.50–0.61). That is
cited-versus-*used*, which the queued citation-UI brief already anticipates —
"local sources are cited only when they carry the answer… use a second, higher
relevance threshold than the one that decides injection". It is a separate cut
on the same number and it is not built.

### What the recall eval found — read this one

**Hybrid retrieval was ranking on stopword overlap.** Recall is the moat, it
had never been measured end to end, and the eval failed within minutes of
existing. Three bugs, in three different places, all pointing the same way:

1. **`HybridMemoryRetriever` ran keyword search *beside* vector search in
   HYBRID mode and kept whichever scored higher** (`retrieval.py`). Keyword
   scoring split on whitespace with no stopword filter, so *"What is the
   capital of France?"* overlapped a Harbour Lane project brief on `is`, `the`
   and `of` — three of six terms, a score of 0.5 — while the true cosine
   similarity was **0.226**. The max won. An unrelated document was cited with
   a number that looked like a similarity and was not.
2. **`HybridMemoryIndex` blended `0.7 * vector + 0.3 * keyword`**, which capped
   any document matching on meaning alone at 0.7 of its true score. A genuinely
   relevant note scoring **0.599** under bge-m3 arrived as **0.407** and was
   dropped by the 0.42 floor. Keyword now *boosts* into the headroom above the
   semantic score and can never dilute it.
3. **Stopwords scored at all**, in both places, with two hand-maintained
   tokenizers that disagreed — `France?` was a term and `is` was a good one.
   One shared `content_tokens()` now.

**Before: the populations were inverted** — genuinely related documents bottomed
out at 0.407 while unrelated ones reached 0.493, a margin of **−0.086**. No
threshold could separate them, so no value of `MIN_RECALL_SCORE` was correct.
**After: +0.080**, related min 0.469 against unrelated max 0.389, with 0.42
sitting in the gap. `test_recall_eval.py` prints that margin on every run, so a
narrowing one is visible before a user feels it.

**`MIN_RECALL_SCORE = 0.42` was not "chosen by feel"** — that claim was wrong.
It was measured, with the distribution recorded in its docstring and asserted by
`test_recall_relevance.py`. What was wrong is subtler and worse: it was measured
*through* the distortion above, on a two-fact Spine. It held there and collapsed
at five documents. It is now validated against real embeddings on a deliberately
confusable corpus.

**`bge-reranker-v2-m3` cannot be wired through Ollama.** Both `/api/embed` and
`/api/generate` terminate llama-server with a stack-buffer overrun
(`0xc0000409`). It is not merely unreferenced — it is unusable by this route, so
CLAUDE.md's ~1.8 GB "embeddings and reranker resident" arithmetic is fiction
until a different route exists. Decide it deliberately; do not assume the model
being pulled means it works.

### What the 27 actually were — the count was four separate bugs

The previous entry said "13 = one stale test double, 14 = voice, out of scope".
Both halves were wrong, and the second was the more misleading.

- **The stale `FakeLLM` was real but was only the top layer.** Fixing the
  signature moved the failure one level down: `test_streaming_conversation` and
  the voice integration module were written against a `ConversationManager`
  that took a `VoiceManager` and yielded `audio` events. Sprint Alpha.6
  replaced that with the event bus. **Half those tests could never have passed
  again**, whatever was done to the fake. They now test what the manager
  actually promises; the audio assertions went back to the voice stack.
- **The 14 "voice, out of scope" failures were not voice.** Five were
  `test_kokoro_provider` asserting that discovery populates `_voices`, which
  stopped happening when `voice_discovery_enabled` was deliberately defaulted
  **off** — real discovery contacts huggingface.co at startup and rule 7g
  forbids that before consent. Nine more were the ConversationManager problem
  above. "Out of scope" was the label that stopped anyone reading them.
- **Two were a live NameError.** `main.py` used `SEARCH_MARKER` without
  importing it — a real crash on the web-search path, latent only because
  search is default-deny.
- **One asserted a rule violation.** `test_alpha10c_acceptance` required
  `/chat` to trigger a search; search has since moved behind `chat_router` and
  become default-deny, so the test demanded that a question reach the internet.

The lesson is the one this file already recorded and then fell for anyway: a
stable failure count everyone stops looking at is how a real regression hides.
The specific trap was the *taxonomy* — "13 core, 14 voice" made 27 feel
understood. Nobody had run them individually.

### Still open from the last audit

**Test the seams, not just the components.** Unchanged and still true. Every
real bug found by driving the live kernel passed unit tests. `test_ingest.py`
and `test_recall_eval.py` are the first two acceptance-shaped tests; the
end-to-end recall demo still has no test that boots the real kernel.

**`--ignore` in `pyproject.toml` is rootdir-relative.** Running pytest from
`backend/` aborts the whole suite on `test_kernel.py`, which is committed
truncated mid-expression (ends at line 18, `SyntaxError: '(' was never
closed`). It is a manual smoke script from early kernel work, not a test.
Delete it or rename it `manual_*.py` — the ignore line is a workaround for a
file nobody wants.

### Decisions taken that are not yet obvious from the code

- **An externally edited file returns as a new artifact**, origin
  `user_document`, never as an update to the generated one. We cannot verify
  which claims survived a Word edit, and letting unverified text inherit
  citations is the product failing in miniature. **The UI must say this** when
  it happens — silent lossiness is the same class of problem as silent
  ingestion failure. Not yet built.
- **`Artifact.indexed` defaults to `False`**, against rule 7b's default-on. The
  deprioritisation that makes default-on safe needs origin *on facts*, which
  lands with M8. Until then, not indexing is safer than indexing unranked.
  **Flip it in the M8 commit.** This is a known, time-boxed gap.
- **Collisions increment by default** (`proposal-2.docx`); asking is the escape
  hatch when the bounded retry exhausts.
- **`Claim.source_revision` and `verified_at` exist and are unused.** Staleness
  detection is not built; the fields are there so adding it later does not mean
  migrating every artifact.
- **Claims reach Word as bookmarks, not as attributes.** `data-zaram-claim`
  does not survive export — Word discards unknown markup — so each claim is a
  real internal hyperlink to a real bookmark on its Sources entry. Clicking a
  sentence in Word jumps to the source, with Zaram not running. The
  machine-readable mapping stays on `Artifact.claims`, independently. Word
  drops a bookmark whose name has a hyphen or exceeds 40 characters *silently*,
  rendering every link as dead text, so `_bookmark_name` is asserted by test
  rather than trusted.
- **The .xlsx exporter refuses to guess.** "₦425,000" becomes the number
  425000; "50%" and "2026-07-02" stay text. 50% is 0.5 to Excel and 50 to a
  naive strip, and writing the wrong one into a cell that feeds a formula is
  the failure the module exists to prevent. Text is visibly unfinished; a wrong
  number is invisibly wrong.
- **Charts always ship their data table, and it cannot be turned off.** Three
  of the eight categorical slots fall below 3:1 contrast on white, which
  obligates relief. The table is that relief, so the picture is never the only
  copy of the numbers. A ninth series is refused rather than given an invented
  hue.
- **Unavailability is a return value, not an exception.** `export.formats()`
  lists every format with whether it runs here and why not. An `ImportError`
  surfaced as "PDF failed" tells a user nothing actionable and reads as a bug
  in Zaram rather than a missing system library.
- **Two artifact stores, on purpose.** `store.py` holds files and cannot unmake
  them; `records.py` holds records and has no general `update` and no `delete`
  — one named method for the one field the user controls
  (`set_remember_override`). The module this replaced had an `update()` that
  `setattr`'d anything passed to it. A second mutation has to be a second named
  method, which is a conversation rather than a keyword argument nobody
  reviews.
- **The file is written before the record, always.** The reverse ordering makes
  Work show a row for a document that does not exist. This ordering, on
  failure, leaves a file the user has and Work has not listed — under-claiming,
  which is visible and recoverable. Over-claiming is neither.
- **`remember_override` is three-valued.** `None` (undecided, a default may
  still apply), `True`, `False` (a refusal, which a default may not override).
- **Work shows project *ids*, not names.** There is no project-name store, and
  turning `harbour` into "Harbour Lane Studio" would be a value nobody entered.
  The sample data had names because it was invented.
- **The preview is an iframe of the stored HTML**, sandboxed with no
  permissions. HTML is the source of truth, so the preview *is* what the file
  was rendered from — not a second rendering that can disagree with it.

### Routing and generation

`core/retrieval/` is **one index with two decision rules**, built that way so
MCP tool selection lands on it rather than beside it. Routing needs a decision
(one winner, above a floor, with the margin over the runner-up as confidence);
tool selection needs a shortlist (top-k, no floor). `search()` ranks and stops;
both rules sit on top as thin functions.

For MCP, what already holds: namespaces with independent drop/re-register (a
server disconnects, its tools stop being offered), a content-hash embedding
cache (a reconnect re-registering 200 unchanged descriptions costs nothing),
and a dimension lock (cosine across two embedders is meaningless, not weaker,
so the index refuses). **What must never change: a retrieval score authorises
nothing.** A tool description is third-party text and can be written to sit
near every query; retrieval produces a shortlist, the model chooses, the risk
tier gate still runs.

**Keywords remain the fallback and should stay.** The embedder degrades to a
hash backend when Ollama is unreachable, and similarity over hash vectors is
arbitrary rather than merely worse. The router reports that and hands back.

Four bugs stood between "every piece works" and "the feature works", and all
four were only visible end to end:

1. **The reasoning step got the literal prompt.** Asked to "write that up as a
   proposal" with no framing, the model described its own operating protocol
   and that text became the file. The planner now derives a writing
   instruction; the *user's* words still reach the runtime, which reads them
   for "spreadsheet" or "invoice".
2. **Recall could not resolve "that".** Similarity against five referential
   words retrieves nothing, and the model invented a whole client — one run
   produced a confident document about a "Project Phoenix" with the real
   client's name and day rate nowhere in it. Fixed with an **ephemeral session
   buffer on the engine** (rule 7d: session state and the Spine are separate
   stores). `_remember` deliberately stores the user's words as a fact and not
   the exchange, which is right for memory and leaves nothing that can answer
   "what is 'that'".
3. **The card lacked `exists`.** The `/artifacts` listing had it and the card
   did not, so a card for a file written a second earlier said "file not found
   where it was written".
4. **The title printed two or three times**, and Markdown `**` reached the
   .docx as literal asterisks.

**Charts from chat are refused, deliberately.** A chart is a claim about
numbers and the runtime has prose; inventing figures to plot would be worse
than refusing, and quietly returning a document nobody asked for would be too.
The refusal names what is missing and offers what works. A real chart path
arrives with the business layer, where figures come from invoices.

### Providers and data policy

**OpenRouter is registered only when `OPENROUTER_API_KEY` is set**, and its
models carry `data_policy=None` — unknown — except the `:free` tier, which is
stated as `LOGGED_AND_TRAINED_ON`. Nothing it returns is
`selectable_by_default`, so Zaram never routes there on its own initiative.

This came out of an audit that proposed registering OpenRouter with
`YOUR_KEY_NO_TRAINING`. That one line would have made every model it returns
auto-selectable, **including the free tier that is free precisely because
prompts are logged** — a privacy guarantee displayed over the opposite
behaviour. `test_openrouter_policy.py` asserts the *absence* of that claim so
it cannot come back quietly.

The asymmetry worth remembering: **we can sometimes prove a model logs; we can
never prove one does not.** Free tier is stated, everything else is None.

**`backend/config.json` is deleted.** Nothing read it — not the backend, not
the frontend, not Electron. It declared `ENABLE_WEB_SEARCH: true` beside a
product whose default is deny, plus model names and a `SYSTEM_PROMPT`
instructing the model to cite web URLs. All inert, all misleading to the next
reader. Web search is gated by `ZARAM_WEB_SEARCH` in the environment, read at
call time by `planner.web_search_enabled()`.

### Open questions

- ~~**How does recall behave as the Spine grows?**~~ **Measured 11 August
  2026, at all three sizes. The floor holds and the reranker stays unbought.**

  | docs | `related_min` | `unrelated_max` | margin | recalled | false citations | latency |
  |---|---|---|---|---|---|---|
  | 10 | 0.517 | 0.386 | **+0.131** | 5/5 | 0/18 | 41 ms |
  | 100 | 0.517 | 0.409 | **+0.108** | 5/5 | 0/18 | 65 ms |
  | 1,000 | 0.517 | 0.410 | **+0.106** | 5/5 | 0/18 | 285 ms |

  The structural worry was right in its mechanism and wrong in its size.
  `related_min` does not move at all — it is a cosine between two fixed vectors
  and corpus size cannot touch it. All movement is on `unrelated_max`, exactly
  as predicted. But the curve **saturates**: 10→100 cost +0.023, 100→1,000 cost
  **+0.001**. A linear reading of the first two points predicts 0.432 at a
  thousand and a crossed floor; the real answer was 0.410. Every answerable
  target returns at **rank 1**, headroom 5 on a shortlist of 6.

  **Read this as bounded, not settled.** `_filler` draws from four templates
  and ten client names, so a thousand synthetic documents hold a few hundred
  distinct texts and no new vocabulary — which is the most likely reason
  `unrelated_max` flattens. You stop adding *kinds* of document and only add
  instances. A thousand real documents have far more variety and the maximum
  may keep climbing. This shows the floor survives **this corpus** at scale.
  It is the same "check the corpus before reading its numbers" rule that cost
  three measurement cycles, applied to its own result.

  **The margin metric was hardened in the same pass.** Both populations are now
  read at full corpus depth rather than at `SHORTLIST`. The exclusion bias was
  already diagnosed and fixed at the *selection* end — see `docs/RERANKER.md`,
  "Which number is real: +0.106, not +0.179" — but the measurement still
  depended on that fix holding: at shortlist depth, a crowded-out target stops
  contributing and the reported margin *improves*. Measured both ways at 10 and
  100: identical, because the bias is inactive. Inactive is not absent, and
  `test_every_target_contributes_to_the_margin_however_it_ranked` is the guard.
  At 1,000 the unrelated population went from 18 samples to 3,000 and
  `unrelated_max` did not move.

  **What would reopen it:** the margin narrowing on a *real* corpus, or targets
  falling below the floor rather than being ordered badly. Both are scoring
  failures and both are what a cross-encoder buys. Neither has been observed.
- ~~**Dev tooling still ships in the base install.**~~ **Split, 12 August:
  `backend/requirements-dev.txt`. 83.5 MB measured** — the "probably 30–40 MB"
  guess was under by more than half, because mypy is 42.1 MB and ruff 32.9 MB
  on their own. `wheel` was never in base. The exclusive transitive packages
  went with them; `typing_extensions` stayed, since twenty-odd runtime packages
  require it. **Not yet proven by a clean install** — see the next item.
- **A base install has never been built and run.** The split above is
  reasoned from declared dependencies and a source scan, which is good evidence
  and is not the evidence this project accepts for a dependency claim. The
  check is a fresh venv with `requirements.txt` alone that boots the backend and
  reaches a cited answer. `tabulate` is the one entry riding on the weaker
  argument: nothing declares it and nothing imports it, which is exactly the
  reading that once recommended deleting spaCy.
- ~~**Jinja2 is declared in the *voice* extra and used by nothing.**~~
  **Answered 12 August: it is a real transitive dependency and stays.** spaCy
  and torch both require it *unconditionally* — not behind an extra. No removal
  experiment was needed, because the metadata is trustworthy in this direction:
  a package **declaring** a dependency is evidence it needs one. The unreliable
  direction is the absence of a declaration, which is the misaki/spaCy trap.
- **WeasyPrint on Windows needs native GTK libraries**, which is a packaging
  decision rather than a `pip install`. This is the only part of M9b not
  working. The exporter is written and the format reports itself unavailable
  with the reason and a per-platform remedy, so the gap is visible rather than
  silent — but a Windows user cannot produce a PDF until the installer carries
  the MSYS2 GTK runtime. **Decide this in the packaging spike, not before**:
  the alternative is ReportLab, which would mean a second document pipeline
  and breaks "HTML is the source of truth". Markdown and .docx work on every
  machine, so nobody is blocked from getting a file out meanwhile.
- **Code signing** is the long-lead packaging item. Windows business
  verification as a Nigerian sole trader needs investigating now, in parallel.
  Unsigned costs Zaram more than a typical app: SmartScreen's warning appears on
  a product whose entire claim is trustworthiness.
- **`speech.tts` is reachable from the chat path** while voice is out of scope.

---

## Done

### M0 — Recall loop ✅
Spine on SQLite with `bge-m3` embeddings. Facts stored, retrieved, injected with
citation markers, provenance events emitted.

**Verified:** a fact stored in one session was recalled in a separate session
with provenance.

### M1 — Egress log ✅
Append-only hash-chained log, per-host policy, default deny, all outbound calls
through one gate. `test_egress_chokepoint.py` fails the build on any direct HTTP
call outside `core/egress/`, and on a stale exemption naming a deleted file.

### M2 — Provider layer ✅
`backend/providers/` connected, renamed from `garage/`. Model metadata carries a
data policy with no default value — unknown is `None`, never a guarantee.
`select_default_model()` refuses rather than choosing something unlabelled, and
reports *why* each candidate was refused.

**Verified:** booted against real Ollama, 10 models discovered and labelled.

### M3 — Frontend integration ✅
`chatClient.ts` does `POST /chat`, parses NDJSON, handles JSON split across
chunks and multi-byte characters split mid-character.

### M4 — Verify the integration ✅ (the UI half, finally)
**Driven in a real browser, 8 August 2026.** Outstanding for four milestones
because the Playwright browser install kept failing here. The MCP server wants a
chromium build that will not download on this connection; the package already in
`frontend/node_modules` has one, so `frontend/scripts/drive-*.mjs` uses that
with an explicit `executablePath`. Re-runnable.

**The recall demo works end to end, watched:** state a fact → ask about it →
cited answer carrying the right figure → click a citation → a panel showing the
fact, when it was stored, how often recalled, and Forget → correct it in Memory
→ the old value stays struck through as *"superseded Aug 8 · you corrected
this"* → ask again → **the answer changes to the corrected figure and no longer
mentions the old one** → Activity shows real bytes, blocked count and an
unbroken hash chain.

Four defects came out of driving it, none of which any unit test had:

1. **`access_count` was never incremented on the store the product runs.**
   Every fact read "Recalled 0×" forever. `InMemoryMemoryStore` incremented as
   a side effect of `get`; `SQLiteMemoryStore` had no equivalent — two
   implementations of one contract, drifted. Rule 7e's whole
   promotion-through-use mechanism is that integer, and `decay.py` forgets
   anything never accessed after 30 days, so the Spine looked entirely unused.
   Fixed as an explicit `record_access` on the protocol: **reading a fact is
   not recalling it**, or browsing Memory would make everything look
   load-bearing.
2. **The citation threshold was applied to the ranking blend, not to
   relevance.** See below — the largest of the four.
3. **Collapsed left-rail buttons had no accessible name.** The label renders
   only when the rail is expanded, so the navigation announced itself as five
   anonymous buttons and "Knowledge" was unreachable to anything finding
   controls by name. Now `aria-label` + `title` + `aria-current` always.
4. **A 404 on every page load.** Unidentified, one request, harmless-looking.
   Left as a thread to pull.

**Corrected on the way:** the orb does *not* vanish inside a workspace and the
return path is not broken. The route back is `OrbStatus` in the header, labelled
"Ask Zaram", `aria-label` ending "Open conversation." An earlier reading of this
session looked for the landing orb's `data-testid` and wrongly concluded there
were zero routes back.

**Not done:** stop/abort mid-reply is still unverified.

---

Earlier, at transport level against a live backend. Found and fixed two real
bugs:

- **`invoice` contains `voice`** — keyword matching was substring-based, so every
  invoice request routed to text-to-speech and returned a fallback with no model
  call. Also `essay`→`say`, `profile`→`file`, `research`→`search`. Now matched on
  word boundaries.
- **The requested model was logged and then discarded.** `/chat` accepted a
  model, the dispatcher logged it on the line above the call that did not pass
  it, and the engine always used its own default.

**Not done:** no UI walkthrough. The Playwright browser install failed on this
connection, so the interface has never been driven. Whether **stop** actually
aborts a request is still unverified.

### M5 — VRAM detection ✅
`_vram_bytes` read `torch.cuda.get_device_properties`, which does not exist in a
packaged build — so VRAM was `None` for every user and the residency fit gate
never ran, while its tests passed against pinned profiles. Now nvidia-smi, with
the Windows registry for AMD/Intel. **Never `Win32_VideoController.AdapterRAM`**:
uint32, saturates at 4 GB, reports 4294967295 for a 12 GB card.

**Verified on the dev machine:** RTX 3060, 12 GB detected, a 9 GB model refused
when a 5 GB one fits, with the reason logged.

### M6 — Shell cleanup ✅
Orbit carries five nodes: Work · Memory · Knowledge · Activity · Settings.
*(Six as of 10 August 2026 — Project was added; see the Current state block.)*
19 unreachable files moved to `legacy/`. **Bundle unchanged — byte-identical,
same content hash** — which is the proof they were never linked. The win was
repo clarity, not size.

Found on the way: the surface list was restated by hand in TopNav, LeftRail and
CommandPalette, and the palette had silently lost Activity. All three now derive
from `surfaceOrder` with `Record<WorkspaceId, …>` icon maps, so the compiler
names every file needing an entry.

### Packaging ✅ (the big one)
**1,436 MB → 267 MB base**, an 81% reduction, and the single most consequential
thing done for the alpha — the difference between an installer someone on
metered data will download and one they won't.

- Voice is an optional 905 MB extra. Voice tests skip with the install command in
  the reason rather than failing.
- `soundfile` was imported at module scope in the Kokoro provider, so the
  graceful-degradation path could never run — the module died three lines into
  its own imports. Now lazy.
- Removed `diffusers`, `openai-whisper`, `edge-tts`, `onnxruntime`, `accelerate`,
  then `scipy`, `numba`, `llvmlite`, `tiktoken`.
- **spaCy was nearly removed by mistake.** `pip show` reported no dependents
  because misaki reaches it at runtime without declaring it. Removing it broke
  speech. **Verify by removal and a green suite, never by metadata.**

### Session 1–2 — Orbit and Work ✅
Work added as the fifth node. The Work surface built against clearly-labelled
sample data: 20 artifacts, two projects, filter by project and type, detail panel
from the right with preview, sources and a link back to the conversation.
Download is inert and says why — a working button emitting a plausible invoice
from invented data is worse than no button, because the file outlives the screen
that explained it.

The landing hint ("Click Orb to Chat") replaced the persistent bar. **Two things
went with it:** the clickable topic line was the third route back and the only
one that named its destination, and the `local · model · N facts recalled` line
is no longer visible. `sessionStatusStore` still tracks all of it.

### Session 4 — Work reads real artifacts ✅
`sampleArtifacts.ts` is deleted. Work fetches from `/artifacts` through
`services/artifactsClient.ts`, with loading, error-with-retry and a truthful
empty state. The detail panel previews the stored HTML in a sandboxed iframe,
lists claims with their source excerpts, and downloads the real file.

The sample's shape had drifted from the backend model — `projectId` against
`project_id`, a nested `conversation` object against two flat fields, and a
`previewText` with nothing behind it. The model won, and the client uses its
field names directly rather than mapping, because a mapping layer is a second
vocabulary and a place for the two to disagree quietly.

**Download is real now.** It was inert and said why, because a working button
over invented data emits a file that outlives the screen explaining it. The
button now also distinguishes "no file" from "the file is not where it was
written" — the record can outlive the file, and 410 is a different problem from
404.

**Verified end to end against a live backend**, through the Vite dev proxy on
the browser's own path: generate → list → preview HTML with claim anchors →
download 37 kB of .docx with the right content type. Not driven in a browser —
Playwright is still unavailable here.

---

## The agreed path to alpha

Decided 7 August 2026, after an audit of what actually stands between here and
a 15-person retention test.

**~~Do these first~~ ✅ → ~~M7~~ ✅ → ~~M8~~ ✅ → ~~citation UI~~ ✅ →
M9/M9a → cloud engine + M10 as one unit → M11 + first run → M12.**

**The citation UI is done** — all five steps, driven in a browser. See the
Citations section of `docs/UI-SPEC.md` and "Queued — the citation UI" below for
the reasoning that produced it. Its `web` kind is built and unverified, and
becomes testable only when search lands behind its policy gate.

**Next on the path is M9/M9a — the business layer and obligation extraction.**
That is the wedge, and it is the first milestone since M7 whose acceptance is
about what a freelancer gets rather than about what the system does.

**Queued behind it: the avatar spike.** Afternoon-sized, not a milestone.
Scoped in `docs/EMBODIMENT-SPIKE.md`; both blocking questions are answered.

**Still true and still the blocker:** a stranger cannot install this. M11.

**Cut from the alpha path**, not from the product: **M9c** (Unreal/Blender is a
different wedge on a different day, orthogonal to freelancers) and **Session 5**
(CLAUDE.md: build two packs by hand before building the pack system — a
catalogue with no packs is a promise accumulating). Both stay in this file
below; neither is next.

**Local *and* cloud, decided deliberately.** An earlier proposal to make the
alpha local-only was overruled: both capabilities ship. That keeps M10 in
scope and adds one thing that is missing entirely — see below.

**Cloud is not just a provider setting. `OpenAICompatibleEngine` does not
exist.** `runtimes/models/engines/` holds `base_engine.py` and
`ollama_engine.py` and nothing else. The provider layer *discovers*
OpenAI-compatible endpoints and OpenRouter, but nothing can generate through
them, so the v1 scope line "chat routed to at least two providers (one cloud,
one local)" is **not met**. Two local models satisfies the recall demo; it does
not satisfy that line.

**M10 ships in the same commit as the cloud engine, not after it.** Rule 8 is
narrower than it looks: `test_outbound_query_invariant.py` enforces that Spine
content never reaches a *search query*, because recalled facts live in
`system_prompt` and the search path never reads it. But `system_prompt` is
exactly what a generation call sends. Today it only reaches `OllamaEngine` on
localhost, so it is not egress. **The moment a cloud engine exists,
`system_prompt` becomes egress and it contains Spine content by design.**
CLAUDE.md intends that — "carries project context into the cloud request" —
immediately followed by "showing the user exactly what leaves before it does".
So M10 is the enforcement point for the only path that sends memory
off-device, not a dialog bolted on later. Cloud generation without it is rule 5
with the safety removed. It needs a test in the same shape as the existing
invariant: recalled facts reaching a cloud engine must pass the gate *and* the
confirmation, structurally.

**Cloud lands after the wedge, not before it.** M10's dialog shows recalled
facts as removable chips, and that can only be tested honestly against a Spine
with real material in it. Built before M7 and M9, it is built against an empty
store and the interaction problems surface during the alpha.

**Start now, in parallel, because it is not coding work:** Windows code
signing and the Nigerian sole-trader business verification. Longest lead time
of anything here and it cannot be compressed later.

**Worth one afternoon, soon:** actually run the recall demo end to end and
record it — ask model A, ask model B later, get a cited answer, delete the
fact, watch the answer change, open the log. Every piece exists and it has
never been demonstrated. It is the closest-to-done, least-verified asset in the
repo, and a break in it should be found before M7 buries it under new code.

## Next

### M9b — Generative documents ✅
Reachable from chat as of this commit. See "Routing and generation" below for
the four bugs that stood between the pieces working and the feature working.

### M9b — the pieces (kept for the reasoning)
**Committed:** the artifact model, the write path, the HTML layer, and the
exporters — Markdown, .docx, .xlsx and PNG, verified end to end against real
output. 58 tests in `test_artifact_exporters.py`.

The write path is a property of the code, not a convention: `open(path, "xb")`
is create-or-fail atomically, there is no function named for deletion, and
`test_artifact_write_path.py` scans the module's source so the build fails on the
commit that introduces the capability rather than at runtime after a file is
gone. Path confinement gets eight traversal payloads — the *model* proposes
filenames, so `../../.ssh/config` is an input to assume.

**That guarantee now has a second gate.** The exporters return bytes and never
touch the filesystem; `ArtifactStore` stays the only writer. A source scan over
`artifacts/export/` enforces it, so adding a sixth format cannot quietly route
around the store. It matches *calls* rather than names, because `workbook.save`
and `write_pdf` both write to memory.

**Remaining:** PDF, blocked on GTK packaging (see Open questions), and the
**conversation half** — nothing generates from chat.

**Acceptance:** ask a question, say "write that up as a proposal", get a .docx
where claims link back to the source paragraph they came from. The file appears
as a card in the conversation and as a row in Work.

**Verified:** a proposal with recalled claims exported to .docx, both claim
hyperlinks resolving to bookmarks present in `word/document.xml`; and the same
document generated over HTTP, listed and downloaded through the dev proxy. The
document half and the Work half both hold.

**The gap, precisely.** `POST /artifacts/generate` is the seam and it works —
it is what a capability would call. What does not exist is the capability: chat
goes through `CapabilityRouter` / `IntentBasedRouter.INTENT_MAP`, and producing
a document from natural language means registering a runtime there, adding an
intent, and emitting a file-card event on the stream. Deliberately not
half-wired this session. Note also that routing is keyword-based, so
`INTENT_MAP` will match "proposal" by word rather than by meaning until
embeddings land.

### Session 5 — Settings → Tools, the pack catalogue
Each pack shows risk tier (generative / mutative / egressive), data policy, and
honest grading against this machine — greyed out where unavailable, with the
reason stated. Only packs that exist or are genuinely next; a catalogue of forty
things we will never build is a promise accumulating.

### M7 — Ingest ✅
`backend/ingest/` — a parser interface, four light parsers, a measured quality
floor, and an outcome for every file rather than only the ones that worked.

**Verified against a real folder**, not just tests: an invoice indexed and
recalled by a question about its day rate (0.492, cited by filename); an
image-only scan reported as *"2 pages produced only 1 character (0.5 per page).
It is probably a scan with a little text on top"* with the OCR remedy and its
size; an encrypted `.docx` reported as password-protected **without** falsely
offering OCR, since no parser opens those.

**Docling is an optional extra, decided by measurement.** It costs 321 MB of
wheels (torch, opencv, transformers, rapidocr, scipy) against a 267 MB base —
more than doubling the installer that the packaging milestone cut by 81%.
Probed against 1,080 real files: the light parsers read **50 of 54 PDFs**; the
four they cannot are image-only scans. `docling-slim` alone is a mirage — 40 MB
that parses nothing, because every format backend lives in the `standard` extra
that pulls torch.

`PyPDF2` was in `requirements.txt` and imported by nothing; replaced by `pypdf`
(0.4 MB), verified by removal plus a green suite rather than by metadata.

**The quality floor is measured, and the interesting half is where it *isn't*
set.** Zero characters is unambiguous — four files, all image-only scans, no
false positive possible. The band above zero is not: of twelve PDFs under 200
chars/page, those between 98 and 190 are *legitimately sparse* — a pitch deck
at 98.6, a cast sheet at 186.8. A floor at 200 looks reasonable and would tell
a user their own pitch deck was unreadable. The floor is **50 chars/page**, the
only place the two populations separate, and it **warns rather than rejects**:
sparse content is still indexed, because rejecting it would make the floor a
second, quieter way to lose a file.

**The Knowledge surface renders it, and this was verified in a browser.**
`ingest/records.py` persists sources and per-file outcomes; `/ingest` streams
one event per file as it is read; Knowledge lists folders with counts, a
per-source `local_only` policy toggle (rule 5, default deny), a Needs-attention
section carrying each reason and remedy, and a retry on every problem.

Driven end to end with Playwright against a real folder:

> **m7folder** — 3 indexed · 2 need attention · Local only
> **NEEDS ATTENTION · 2**
> `locked-exam.docx` — Couldn't read — *Password-protected or a legacy .doc
> renamed .docx.* — Retry
> `NDA WOTG Uche.pdf` — Almost nothing — *2 pages produced only 1 character
> (0.5 per page). It is probably a scan with a little text on top.* —
> *Reading scans needs OCR: pip install zaram[ingest] (321 MB, one time).* — Retry

**And it reaches the conversation.** A new `notice` stream event carries one
sentence into the transcript after the answer:

> *"2 files in m7folder didn't give me much to work with — locked-exam.docx
> among them. Password-protected or a legacy .doc renamed .docx. They're listed
> under Knowledge if you want to look."* → **Open Sources**

Once per scan, verified: it did not reappear on the next question. After the
answer, not before it — the user asked something, and interrupting with
housekeeping first is how a warning gets trained away. Rendered as a distinct
card, never as reply text: attributing it to the model would be putting words
in its mouth.

Progress is per file rather than a percentage, and it is real — `/ingest`
yields from a generator as each file completes. An earlier draft collected
every outcome and replayed them down the stream, which is a progress bar that
is always finished before it is shown.

**Failures must be loud.** A file that produced nothing appears in Knowledge
with a reason and a retry, and is mentioned in the conversation the first time
it matters. Silent ingestion failure is the most likely reason a user concludes
the product doesn't know their material and leaves.

**"Extracted almost nothing" is a failure, not a success.** A scanned PDF that
yields three garbled words will silently degrade every answer that touches it,
and it is *worse* than a hard failure because nothing signals it. The quality
floor sits beside the error path: a file that parsed cleanly but produced
almost no text lands in Knowledge with a reason and a retry, exactly like one
that could not be opened. Decide the floor from measurement (characters per
page, or extracted length against file size), not from a guessed constant, and
record how it was chosen.

**Rule 7c: no ingestion path may route documents off-device.** Managed parsing
APIs are prohibited. This is the exact trade the product refuses.

**Build the recall eval harness here** — see "Do these first" item 3. Ingest is
what puts real documents in the Spine, so it is the first moment an eval is
possible and the moment it becomes necessary.

**Acceptance:** point at a folder, watch it index, ask a question, get a cited
answer from a real document. Then point at a folder containing a scanned PDF
and watch Knowledge say which file gave nothing back and why. **Met at the
service level; the Knowledge half is not rendered yet.**

### M8 — Memory scope ✅
Every fact carries `scope` (`global` | `project:<id>`) and `origin`, migrated
together as planned — same rows, one migration over the user's data. Pre-M8
facts become `global`, the only honest reading: they were captured with no
project in play, and inventing one would be a value nobody entered.

**A leak was found doing it.** Scope filtering lived in the store's `query`,
which the vector path does not use — `_vector_search` asks the index for ids and
fetches records individually, so a semantic hit on another project's fact walked
straight past the filter and only the keyword path was ever scoped. Now enforced
at one chokepoint in `HybridMemoryRetriever.retrieve`: a privacy boundary with
one enforcement point per code path has one hole per code path.

**Promotion is evidence-based** (rule 7i). `recalled_in` keeps the project
*identities* rather than a count, because a count cannot answer "recalled across
three *different* projects". `promotion_candidates()` proposes and never
promotes — promotion changes what is shareable, and rule 6 says autonomy is
granted rather than assumed.

**`Artifact.indexed` is flipped to `True`**, and only once the thing that makes
it safe existed: `MemoryRankerImpl.GENERATED_PENALTY` demotes Zaram's own
restatements in the *ordering*, never in relevance. Pushing a generated fact
under the citation floor would be exclusion wearing a different hat; rule 7b
asks for tagging instead.

**Not built:** nothing sets a project scope yet. Every fact still lands
`global` in practice because no surface tells the engine which project is
active. The field, the filter, the migration and the promotion evidence are all
there — the caller is not. That is the next piece of M8 and it is small.

### M9 / M9a — The business layer and obligation extraction
The universal job: invoice → receipts → expenses → how is the business doing.
Then the keystone: dates and commitments pulled from documents, surfaced before
they lapse, **every obligation showing its source clause and correctable**.

**Acceptance:** generate an invoice with 30-day terms; on day 31 Zaram says the
payment is late, shows the clause it read that from, and has the follow-up
drafted. Correct a wrongly-extracted date and watch the reminder move.

### M9c — Read-only MCP: Unreal and Blender
Inspect, list, report. No writes, so no undo or sandbox needed — which is why it
ships in v1 and scoped writes do not. **Epic's plugin binds `127.0.0.1:8000`, so
the backend must stay on 8420.**

### M10 — Confirm-before-send, editable
The dialog shows the literal outbound text, the destination and the reason.
Recalled facts are removable chips, editable inline, edits written through as
supersessions.

**Done 12 August 2026, with one clause deliberately not implemented.**

Shipped: the literal text (behind a disclosure, so the primary view stays
legible for a non-technical user while the exact bytes remain checkable), the
destination, the reason, and recalled facts as removable chips. Removing a chip
rewrites the outbound body, and the gate logs and sends that rewritten text —
verified against a live backend by comparing preview, log and destination.

**Not implemented: "edits written through as supersessions."** Striking a fact
here changes *this request only*; the Spine is untouched. The two intents are
different and merging them destroys information. "Do not send my day rate to
this provider" is a statement about an outbound request; a supersession is a
statement that the fact is **wrong**, and it stops that fact being recalled
anywhere, permanently. Writing one through as the other would delete a correct
fact because it was once sensitive — and it would do so at the exact moment the
user is trying to be careful, which is the worst possible time to be surprised
by a side effect.

Correction already has a home that says what it means: the Memory surface, per
rule 4. If a user wants both, the honest shape is an offer *after* the send —
"you removed this from that request; should Zaram stop remembering it?" — which
is rule 7h's contextual offer rather than a hidden consequence of a button whose
label says something else. Not built, because nobody has asked for it yet.

### Queued — the citation UI
**Requested 7 August 2026. Not started. Order is fixed and each step stops for
review.**

Read `CLAUDE.md` and `docs/UI-SPEC.md` first. This **adds a section to the
spec, shows it, and only then implements it**.

**The core idea.** Zaram's sources come in three kinds and no competitor has to
make this distinction:

- `memory` — a fact from the Spine. Nothing left the device.
- `document` — a passage from an indexed file. Nothing left the device.
- `web` — bytes left, and there is an egress log entry for it.

The citation UI has to make that visible, because a citation that tells you
whether an answer cost you privacy is the product's thesis at the sentence
level.

**Not everything gets cited.** Web sources are *always* cited regardless of how
central the claim was — not for attribution, but because bytes left the machine
and anything involving egress is always visible. Local sources are cited only
when they carry the answer; the test is whether the claim would be different
without that source. Use a second, higher relevance threshold than the one that
decides injection — the retrieval score already exists, this is a separate cut
on the same number. Division of labour: **chips for what mattered, the recall
strip for what was used, the panel for everything.**

**Inline chips.** Small pill, kind icon and a number: document icon, memory
diamond, globe. **Colour encodes egress, not category** — the same cyan and
violet the orb uses for local versus cloud. Cyan for anything that stayed,
violet for anything that left. One meaning reused, so it needs no legend.
**Never render a chip that isn't clickable**: citing without linking fails the
verification task, and for this product a decorative citation is worse than
none.

**Summary line.** Below the reply, collapsed by default. Leads with the split —
"2 sources · 1 sent to the web" — because that is what someone wants at a
glance. Single-source answers skip the panel entirely and put the card inline;
a panel for one citation is overkill.

**The panel.** Right side, same anchor and pattern as fact detail — one
pattern, not two. Escape closes. Grouped by egress with a mono heading per
group: *nothing left this device* / *1,204 bytes left this device*. Numbering
matches the inline chips exactly so a chip maps to its card instantly.

Per kind:
- **document** — filename, the passage quoted with a left border, page and
  index date, open-document action.
- **memory** — the fact, its source and date, recall count, and correct /
  forget inline. This is the fastest correction path in the product and it sits
  exactly where the user is already checking.
- **web** — title, excerpt, domain, when it was sent and to whom, and a link to
  its row in Activity. **That link is the citation and the egress log being the
  same object viewed twice, and it is the thing nobody else can build.**

Below the cited sources, a quieter section listing what was recalled but not
cited — so nothing is hidden, it is just not interrupting the prose.

**The empty state is not optional.** When nothing from the user's material
contributed, say so: *"Answered from the model's own knowledge — nothing from
your files."* It is a claim about absence, which the user cannot infer from
missing chips — missing chips could equally mean we didn't bother. A visible
no-sources state is more trustworthy than confident prose with hidden
provenance.

**Backend first.** Check whether `StreamEvent.source` already carries kind,
excerpt and egress reference. It currently carries only `kind`, `url`, `title`
— so this is the first change. The frontend cannot render what isn't sent, and
inventing a kind client-side would be the fabrication rule all over again.

**Order — stop after each:**
1. ~~Write the spec section, stop, show it~~ ✅
2. ~~Backend: source events carry kind, excerpt, egress reference, relevance
   score~~ ✅ — plus `cited`, a server-assigned `number`, `origin`, `record_id`
   and `MIN_CITATION_SCORE`. See the Current state block.
3. ~~Chips and the summary line~~ ✅
4. ~~The panel~~ ✅
5. ~~The empty state~~ ✅

**All five done, 9 August 2026**, and driven with
`frontend/scripts/drive-citations.mjs`. The `web` kind is built and *unverified*
— nothing emits a web citation while search is default-deny. See "Do these
first" item 1.

### M11 — Packaging
**The real blocker.** A stranger cannot install this. See Open questions above —
code signing has the longest lead time and cannot be compressed later.

**Acceptance:** a Windows machine that has never seen the repo runs one installer
and reaches a cited answer from its own files in under ten minutes.

### M12 — Alpha
Ten to fifteen people, one segment. Onboard individually, watch, do not help.
Ask at intake: hours spent on admin last month, and what is past due — those
answers become the missing line in `docs/PITCH.md`.

**Acceptance:** the day-30 number. 5+ of 15 weekly → build the paid tier.
2–4 → the job is wrong. 0–1 → the thesis is wrong, learned in six weeks.

---

## Known broken

**Nothing.** 1703 passed, 9 skipped, 0 failures, ~4m05s from the repo root on a
full dev install, 12 August 2026. Frontend: 97 across 13 files.

**One flake seen once, and the cause is the trap at the top of this file.**
`test_measure_exemplar_separation` failed in a suite run that took **435s
against a normal 245s** — nearly double, which is contention, not code. It
passes alone with a wide margin (smallest social margin +0.220 against a
largest non-social +0.025) and passed two consecutive clean full runs
afterwards. It is a `measure` test against a live local model, which is the
class most sensitive to a loaded machine. Not hardened, deliberately: loosening
a measurement to survive a contended run is how a measurement stops measuring.
If it recurs on an idle machine, that is a real signal.

The 27 are gone
and the section explaining what they actually were is above, under "What the 27
actually were"; the method for classifying the next one is
`docs/KNOWN-FAILURES.md`.

The count in this section was stale by 271 tests and two months of runtime
before 11 August. Update it, or it stops being a signal — a number nobody
refreshes is how a real regression hides, which is the same lesson as the
stable-failure-count one above, wearing the opposite face.

Record any change to that number — but the sharper lesson from clearing them is
about *taxonomy*, not counting. "13 core, 14 voice" made 27 feel understood and
that is why nobody ran them individually for four milestones. A failure grouped
under a plausible label is more dangerous than an unexplained one.

**Skips are opt-in, not accidents.** `test_recall_eval.py`'s end-to-end half
needs Ollama with `bge-m3` on loopback — similarity over the hash fallback is
arbitrary rather than merely worse, so a green run against it would be a lie.
`test_recall_at_scale.py` additionally needs `ZARAM_SCALE_EVAL=1`, because
indexing a hundred documents takes ~45s and does not belong in a run-on-every-
change suite:

```
ZARAM_SCALE_EVAL=1 pytest backend/tests/test_recall_at_scale.py -s
ZARAM_SCALE_EVAL=1 ZARAM_SCALE_EVAL_SIZE=1000 pytest backend/tests/test_recall_at_scale.py -s
```

Written and inert, which is worse than broken because the suite is green:

- ~~**`apply_decay` is called by nothing.**~~ ✅ Fixed. `SpineMaintenance` runs
  it daily and once after boot, and the pass had a second defect underneath the
  scheduling one: it read `store._records` and so saw nothing at all on SQLite.
  Verified against a live server.
- ~~**Nothing sets a project scope.**~~ ✅ `ChatRequest.project_id` reaches the
  engine, recall is scoped, capture is scoped, and `ProjectScopePicker` sets it.
  Promotion now has evidence to accumulate.
- ~~**Nothing calls `beginModelSwap`.**~~ ✅ `swap_preflight` announces it before
  generation starts.

Still broken, found and not fixed:

- One unexplained 404 on every page load.

