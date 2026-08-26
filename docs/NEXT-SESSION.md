# Next session — start here

A prompt and a state snapshot. Rewritten 26 August 2026 at the end of the
obligations-surface session.

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
>   committed.**
> - Nothing is running. Ollama may or may not be up — check, because it
>   changes what the suite executes and how long it takes.
>
> How this repository fails, so you can recognise it:
>
> - **Eighteen** complete, tested, unreachable subsystems have been found.
>   Obligations were the eighteenth and are now wired all the way to the
>   screen. Bitemporal memory is still the seventeenth and is still unreached.
>   **Assume unreachable until you have seen the caller.**
> - A green suite has meant nothing on at least seven occasions. Before you
>   trust a new test, disable the thing it tests and watch it go red — and then
>   read *which* tests survived, by name. A count is not enough.
> - **Run the guards before believing the code.** `npm run check:proxy` had
>   been failing since the obligations routes landed and nobody ran it, so the
>   first thing the new client got back was Vite's `index.html`.
> - Verify against the code, not the documentation. When the two disagree the
>   code wins, and say so.
> - Say which environment you measured in. The backend suite has taken 2:53 and
>   20:43 on this machine with Ollama up in both cases, unexplained.
>
> Environment specifics that have each cost time:
>
> - Python is `backend/venv/Scripts/python.exe`. There are two other
>   interpreters here and both have been launched by accident; a bare `python`
>   on PATH is broken and reports a missing install path.
> - Run tests from `backend/`. Scripts outside it need
>   `PYTHONPATH=C:/Zaram/backend`, and `PYTHONIOENCODING=utf-8` or printing a
>   document will die on cp1252.
> - `curl http://127.0.0.1:8420/health` returning **401** is success. The auth
>   header is `X-Zaram-Auth`, not `X-Zaram-Client`, which is a label enforced
>   nowhere.
> - **Vite binds `localhost`, not `127.0.0.1`.** `curl 127.0.0.1:5173` gets
>   nothing while the server is up and healthy, which reads as a dead server.
> - **The backend does not finish starting with Ollama down.** It logged three
>   provider-discovery failures and then sat on `Waiting for application
>   startup` indefinitely; with Ollama up it was listening in about a minute.
>   Whether that is a hang or merely very slow is unmeasured — but it is the
>   condition a stranger installs into.
> - **`gh` is not installed**, so anything needing the GitHub CLI must be
>   handed back rather than attempted.
> - **Do not read a command's exit code through a pipe.**
> - Bash heredocs choke on document content containing backticks and
>   apostrophes. Write the file with the Write tool and splice it in with a
>   short Python script instead of fighting the quoting.
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

Launch, from the repo root, with Vite already listening on 5173:

```bash
env -u ELECTRON_RUN_AS_NODE ZARAM_PYTHON="C:/Zaram/backend/venv/Scripts/python.exe" node_modules/.bin/electron electron/main.js
```

`ELECTRON_RUN_AS_NODE` must be **deleted, never blanked**; Electron tests for
its presence.

To drive the backend directly instead — which is how the obligations surface
was verified — start it with a known secret and a scratch data directory, and
give Vite the same secret:

```bash
cd backend && ZARAM_API_SECRET=dev-secret ZARAM_DATA_DIR=/some/scratch venv/Scripts/python.exe main.py
```

```bash
cd frontend && ZARAM_API_SECRET=dev-secret npx vite --port 5173 --strictPort
```

Then reach it at `http://localhost:5173` — **not** `127.0.0.1`.

For a screenshot, use system Edge rather than downloading a browser, and force
the click: the landing nodes orbit, so Playwright's stability check never
settles on them.

```js
const browser = await chromium.launch({ channel: 'msedge' });
await page.getByRole('button', { name: 'Memory', exact: true }).click({ force: true });
```

---

## What is uncommitted right now

**Nothing.** The tree is clean.

---

## Decisions taken this session

* **Commitments is a view inside Memory, not a seventh node.** Six is the
  count, a pack adds no screens, and an obligation is a derived correctable
  claim with provenance — which is Memory's contract rather than Knowledge's.
* **The source clause is in the collapsed row.** A clause behind a disclosure
  is a clause nobody opens.
* **The questions are rendered above the commitments.** A document read
  incompletely must not look cleanly read.
* **A correction body is assembled field by field, never spread.** The clause
  is the evidence, and evidence the interface can rewrite is not evidence.
* **Extraction was not amended in passing.** Two real defects were found and
  measured and left for a session of their own; see item 1.

---

## What to do next

1. **The two extraction defects the surface exposed.** Both measured against
   `extract_obligations` directly, both visible on screen now.

   *A real deadline dropped with no obligation and no question.* `The first
   round of concepts is due by 14 September 2026.` yields **nothing**:
   `_COMMITMENT` passes, the date is unambiguous, and `_classify` returns
   `None` because no word names a payment, deliverable, expiry or renewal. It
   is this morning's fix arriving through the other gate, and it fails the same
   way — silently.

   *A newline shreds a sentence.* `_TERMINATOR` is `[.!?;](?!\d)|[\r\n]+`, so a
   soft wrap ends a clause and the fragment is what gets shown as the evidence:
   `"delivered by 2 October 2026."`, and a renewal clause cut at `"at the
   then"`. Wrapped text is the normal case for plaintext and PDF extraction.
   The newline cannot simply stop being a boundary — a headed list has no
   punctuation and nothing else to split on. The distinguishing rule is whether
   the wrap lands mid-sentence, and it is a heuristic that needs its own tests.

2. **A way to dismiss a question.** There is no route for it, so a clause the
   user cannot date sits in *Needs a date* forever — a permanent item nobody
   can clear, which is the shape of the engagement mechanic the product
   forbids. `POST /obligations/questions/{id}/dismiss`, stored rather than
   deleted, the same reasoning a dismissed obligation already follows. Small,
   and it finishes the surface honestly.

3. **Wire `in_force_at` into recall — the seventeenth.**
   `runtimes/memory/valid_time.py` implements `in_force_at`, `history_of` and
   `explain` over the bitemporal fields and is imported by exactly one file:
   its own test. So Zaram can store that the day rate was £500 until June and
   £600 after, and cannot answer "what was it in May" through any live path.
   Small, and it makes a real claim true — it is the axis that distinguishes
   this memory from Mem0's.

4. **The FTS5 work, step 1.** Step 0 is done and the corpus is trustworthy.
   The design constraint is the whole job: **membership** is the union of each
   retriever's top-K, **ordering** is RRF (`Σ 1/(k + rank)`, fused by rank
   position so no blended magnitude exists to compare against a cosine floor),
   and **citation** stays on measured relevance, untouched. The deleted
   `_hybrid` did `vector*0.7 + bm25*0.3` and truncated on the blend; doing that
   again by a new route is the thing to avoid. **The delete path is the part
   that matters** — rule 4 promises that correcting a fact changes the answers,
   and a lexical index not kept in sync breaks that silently.

5. **Settle whether `qwen2.5-coder:14b` earns its swap.** `INTENT_SPECIALISATION`
   maps exactly one intent — `CODE` — and that single entry is the only thing
   that can trigger a model swap. Measured: qwen2.5-coder 10.8 tok/s against
   gemma4 30.3, and they cannot be co-resident in ~9.1 GB. Deleting the mapping
   would remove every swap in the product. Needs three real coding questions
   judged by a human.

6. **Make `_rank_key` ask the question its docstring claims.** It orders on
   `model_fits_resident`, which is `size_bytes <= budget` — a static capacity
   check with no reference to what Ollama has loaded *right now*. Add a
   residency term read from `/api/ps`, as a **preference and never a gate**, so
   a required capability still wins.

7. **The markdown preamble case.** A model that opens with "Sure! Here's the
   statement of work:" leaves a stray paragraph. The last known model-variance
   gap; small.

8. **Document kinds** — proposal, report, meeting notes, letter, CV. Now just
   presets over structure that exists, and what actually delivers "the most
   popular docs people create with AI".

9. **Conversation persistence, as the session/memory split.** There is still no
   history — close Zaram and yesterday is gone. Guardrail, enforced by test:
   readable by the user, invisible to recall (rule 7d).

10. **`KPipeline.load_voice` is an ungated download.** It fetches a `.pt` at
    synthesis time with nothing asked and nothing logged. The ONNX path routes
    the same fetch through the gate; the torch path still does not. Rules 3
    and 7g.

11. **Delete `backend/orchestrator/`.** 1,261 lines, no importers, no tests,
    and it contains the membership-versus-ranking bug ready to be revived.
    Pure subtraction.

12. **Reconcile the two Electron trees and the two venvs.** Triage nobody has
    done, invisible to every guard because each side is internally consistent.

13. **Rebuild the installer and run it on a machine that has never seen this
    repo.** Still the actual blocker.

---

## Open questions for the maintainer

* **Where should obligations be surfaced *in context*, as opposed to browsed?**
  The Commitments view is the browsing half and it is done. `CLAUDE.md`'s
  acceptance criterion is the other half — *"on day 31 Zaram says the payment
  is late, shows the clause it read that from, and has the follow-up
  drafted"* — and that is Zaram speaking first, which nothing in the product
  does yet. It is also the one place the no-engagement-mechanics rule and the
  reason-to-open-it argument point in opposite directions, so it wants a
  decision rather than an implementation.
* **Should `conversation`-type memories be in `knowledge.search` results at
  all?** They are now labelled honestly — the model is told which sources are
  the user's own past remarks rather than research — but labelling is not the
  same as deciding they belong. Rule 7d says conversation is ephemeral and
  entering the Spine is a decision the system makes.
* **Is `qwen3.8:27b` worth keeping installed?** 17 GB on disk, 18.7 GB loaded
  against 12 GB of VRAM, 1.85 tok/s, 95.6 s cold load. It is background-tier by
  measurement, and nothing currently routes to it.
* **The suite timing.** 2:53 and 20:43 on the same machine, Ollama up in both,
  no stale backend. CLAUDE.md blames provider-probe timeouts for the
  4-versus-20 split; that is where to look, and it is worth an hour because
  every measurement in this repository is quoted with a condition that assumes
  it is stable.
* **`en_core_web_sm` in the base install.** Unchanged and still open. misaki
  downloads it at runtime when absent — unlogged and ungated.
* **Should Zaram expose an MCP server?** Read-only `recall`, `search_spine`,
  `get_provenance` would let Claude Code, Cursor and Cline read from the Spine.
  Prerequisite — the API secret — now exists.

---

## What this session learned about the instruments

**A guard nobody runs is a guard that does not exist.** `check:proxy` had been
failing since the obligations routes landed. It names both lists, says what the
symptom looks like, and had been sitting there red — and the symptom, when it
arrived, was a JSON parse error naming neither the route nor the proxy, exactly
as its own message predicts.

**Check the instrument before reading its output — again.** The mutation
harness written to prove these tests were worth trusting passed two test paths
as a single argv string, ran **zero** tests, and printed nine confident
`GREEN — NOTHING CAUGHT IT` lines. A tool built to find wrong things is not
exempt from being wrong, and a result that is *uniformly* alarming deserves the
same suspicion as one that is uniformly reassuring.

**A partial disable proves nothing.** Removing only `obligationsClient.ts` made
`check:reachability` report one unreached obligation route instead of six,
because the component beside it still contained the identifiers the guard
matches on. The real measurement needed the whole change reverted. Its path
matching is loose enough that `GET /obligations/{obligation_id}` — which has no
client function at all — is no longer reported.

**Assert the property, not the type.** `correctObligation` was typed so a
`source_clause` could not be passed, and spread the caller's object into the
request body anyway. The test that found it passed a plain object through a
cast, which is what a future call site will look like.

**Wiring a subsystem up is how its defects are found — twice over now.** The
obligation extractor had 28 green tests this morning and could not read the
commonest clause on an invoice. It has more now, and it drops a plainly worded
deliverable deadline and cites half a sentence whenever a document is wrapped.
Neither was visible until a person could look at the output.
