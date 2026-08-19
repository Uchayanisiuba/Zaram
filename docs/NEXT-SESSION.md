# Next session — start here

A prompt and a state snapshot. Written 19 August 2026 at the end of the voice,
lip sync and speech-install session.

**This file is a pointer, not a second handoff.** `docs/MILESTONES.md` Current
state is the handoff and stays the authority on status; `CLAUDE.md` stays the
authority on rules. If this file disagrees with either, they win and this file
is stale — say so and fix it.

---

## The prompt

Paste this into a new session:

> Read `CLAUDE.md`, then `docs/MILESTONES.md` Current state, then
> `docs/NEXT-SESSION.md`. For anything touching voice, read `docs/SPEECH.md`;
> before launching the app, read `docs/RUNNING.md` — it has four failure modes
> that each look like something else, and one of them will cost you an hour.
>
> The working tree has uncommitted voice, lip sync and documentation work
> described below. Verify it against the code before building on it, because
> this repository's signature failure is complete, tested subsystems that
> nothing reaches — fifteen have been found, two more in the last two sessions.
>
> Then start on the first item under "What to do next" unless I say otherwise.
> Before reporting anything as working, run it and watch it happen. A green
> suite has meant nothing here on at least five occasions, and the most recent
> was worse than green: the entire speech acceptance suite was **skipping**,
> which reads like passing in a summary line.

---

## Read this before you install or launch anything

**There are two virtualenvs and two Electron trees.** Both pairs are internally
consistent, so no guard sees either, and both have already cost a session.

| | ships / working | the other one |
|---|---|---|
| Python | `backend/venv` | `C:\Zaram\.venv` — also complete |
| Electron | `electron/main.js` | `desktop/src/main/index.ts` |

The backend launcher resolves `ZARAM_PYTHON` → bundled runtime →
`backend/.venv` → `../.venv`, with `cwd` the backend directory. `../.venv`
**exists**, so an unset `ZARAM_PYTHON` silently starts the other interpreter
rather than failing. Both venvs now carry both speech extras, so the symptom is
gone and the cause is not. Detail in `docs/RUNNING.md`.

Launch, from the repo root, with Vite already listening on 5173:

```bash
env -u ELECTRON_RUN_AS_NODE \
    ZARAM_PYTHON="C:/Zaram/backend/venv/Scripts/python.exe" \
    node_modules/.bin/electron electron/main.js
```

---

## What is uncommitted right now

Nothing is committed from any of these sessions. **Six** logical commits are in
the working tree, and they are independent.

**1. Voice resolution** — the user's chosen voice reached no synthesis path.

* `backend/voice/config.py` — `DEFAULT_VOICE = "am_michael"`, decided here and
  nowhere else. Was `af_heart`, spelled in six places.
* `backend/main.py` — `_resolve_voice`, `DEFAULT_PERSONA`, both voice request
  models tied to it by reference, dead `ChatRequest.personality` field deleted.
* `backend/runtimes/speech/runtime.py` — imports the constant.
* `backend/tests/test_voice_resolution.py` — **new**, 12 tests.

**2. Lip sync / state ownership** — the avatar's mouth never opened.

* `frontend/src/lib/orbActivity.ts` + test — **new**. `preserveSpeaking`.
* `frontend/src/components/chat/ChatSurface.tsx` — stops clobbering it.
* `frontend/src/stores/speechStore.ts` + test — sets `speaking` when a clip
  actually plays; exports `SPEECH_NOT_INSTALLED`.

**3. The Kokoro ONNX backend** — 662 MB smaller, timings bit-identical.

* `backend/voice/providers/kokoro_onnx.py` — **new**. The pipeline, the graph
  patch that recovers `pred_dur`, and one gated fetch helper.
* `backend/voice/config.py` — `backend` and `onnx_variant`, with the
  measurements that chose their defaults written into the comments.
* `backend/voice/providers/kokoro.py` — the factory dispatches on backend.
* `backend/requirements-voice-onnx.txt` — **new**.
* `backend/voice/tests/test_kokoro_onnx_backend.py` — **new**, 11 tests
  including the differential against torch and a subprocess proof that the path
  runs with torch unimportable.
* `backend/tests/test_egress_chokepoint.py` — allow-list entry, which the
  guard's own second assertion verifies actually asks the gate.
* Three test doubles gained `**_` because the factory contract grew.

**4. Typed text.**

* `frontend/src/lib/typewriter.ts` + test — **new**, the reveal rule as a pure
  function, 12 tests.
* `frontend/src/hooks/useTypedText.ts` + test — **new**, the rAF loop around
  it. The loop must not be keyed on `text`: doing so resets its frame clock on
  every token and the reveal runs ~12x slow. The test was watched to fail
  against that fault before it was kept.
* `frontend/src/components/chat/ChatSurface.tsx` — renders the typed text.

**5. Reasoning split.**

* `backend/core/reasoning.py` — **new**. `<think>` separation that survives a
  tag arriving across token boundaries.
* `backend/core/streaming_events.py` — `REASONING` event.
* `backend/core/chat_router.py` — both streams wired through one helper.
* `backend/tests/test_reasoning_split.py` — **new**, 16 tests.
* `frontend/src/services/chatClient.ts` + test — the event, and an assertion
  that thinking never reaches the answer channel.
* `frontend/src/stores/chatStore.ts` — `streamingReasoning`, and `reasoning` on
  the committed message.
* `frontend/src/components/chat/ReasoningPanel.tsx` — **new**.

**6. Documentation.** `docs/SPEECH.md` gained the ONNX section and lost the
"none tested" one; `docs/MILESTONES.md` Current state and this file rewritten.

Also unpushed from before: `07ef558`, `4039a8f`.

## Measured state

| | |
|---|---|
| Backend | **2326 passed / 0 failed**, 29 skipped, 11m00s, **Ollama up** |
| Frontend | **224 passed** (was 206) |
| Typecheck · lint · guards · payload | clean |
| `check:reachability` | 2 modules, 2 routes — unchanged, nothing new orphaned |
| Kokoro ONNX suite | **10 passed, 1 skipped** — the skip is named, see below |
| Speech extra | **905 MB** torch · **243 MB** onnx |

**The skip is `test_onnx_backend_speaks_with_torch_unimportable`**, and it skips
because `spacy-curated-transformers` is installed in `backend/venv`. That plugin
imports torch at module scope and spaCy loads it automatically, so torch is
reachable in this virtualenv no matter what the backend does. The claim it exists
to prove was verified instead in a clean virtualenv built from
`requirements-voice-onnx.txt`, and
`test_onnx_requirements_exclude_the_torch_plugin` keeps the contaminant out of
the shipped extra from the other side.

**Say which condition you measured in.** Ollama was **up** for these runs.

**The app was not run.** Ports 5173 and 8420 were both held by a running
instance. See the last section of `docs/MILESTONES.md` Current state.

## What to do next

1. **Run the app and watch the mouth move.** Nothing this session was seen in
   the product — the suites are green and green has meant nothing here at least
   five times. Specifically: speech on the Speak button in orb mode, speech
   automatic and streaming in avatar mode, visemes moving with it, and the typed
   cadence not lagging the voice. `docs/RUNNING.md` has the launch and the four
   traps. Stop whatever is holding 5173 and 8420 first.
2. **Listen to the three WAVs and decide the Kokoro backend.** `a-torch`,
   `b-onnx-fp32`, `c-onnx-fp16`. If b is indistinguishable from a bar the level,
   flip `DEFAULT_BACKEND` to `"onnx"` — the assertion in
   `test_default_backend_is_the_one_a_human_has_heard` is there to make that a
   deliberate edit. c should audibly degrade toward the end; if it does not, the
   correlation measurement is wrong and worth re-reading.
3. **Wire `core/untrusted.py`.** The prompt-injection defence — `Provenance`,
   `may_instruct`, `scan` — is complete, tested, and called by nothing.
   **Obligation extraction must not ship without it.** This was item 1 before the
   session was redirected, and it has not moved.
4. **Conversation persistence, as the session/memory split.** There is no
   history at all — close Zaram and yesterday is gone. Guardrail, enforced by
   test: readable by the user, invisible to recall (rule 7d).
5. **`KPipeline.load_voice` is an ungated download.** It fetches a `.pt` at
   synthesis time with nothing asked and nothing logged. The ONNX path routes
   the same fetch through the gate; the torch path still does not.
6. **Reconcile the two Electron trees, and the two venvs.** Both are triage
   decisions nobody has taken, invisible to every guard because each side is
   internally consistent.
7. **A guard for a skipping acceptance suite.** Fail the run when the speech
   roundtrip tests skip on a machine that has both extras.
8. **The maintainer's two standing decisions**, both blocking: delete or revive
   `backend/orchestrator/` (1,261 lines, no importers, no tests), and rebuild the
   installer before testing it on a clean machine.

## Open questions for the maintainer

* **`en_core_web_sm` in the base install.** Still open, but with new
  evidence pointing the other way: misaki **downloads it at runtime** when it is
  absent, observed while building the clean virtualenv — unlogged and ungated.
  So the pin at `backend/requirements.txt:45` looks deliberate rather than
  accidental. Its *location* is still wrong, since spaCy is not in base; it
  belongs in the two voice extras.
* **Word-by-word speech.** Asked for on 19 August; not built, and `CLAUDE.md`
  rules it out — *"a clause is the smallest unit with prosody"*. What is built
  already speaks *alongside* the streaming text rather than after it, which is
  probably the real intent. If per-word is still wanted after hearing it, that
  overturns a rule and belongs in `CLAUDE.md` first.
* **The screen-faced character.** If the dot-matrix robot ships, the viseme
  driver needs a `textureTransformBinds` path — binary weights, one expression
  per material — told apart by bind type, never by which avatar is loaded.
  Not implemented. `docs/SPEECH.md` has the detail.

---

## What these sessions learned about the instruments

Three defects, and **`check:reachability` was blind to all three**:

* A **settings control** that stored, round-tripped and displayed, with nothing
  downstream reading it. The route *is* called and the setting *is* read — the
  missing hop was between them.
* **Two modules importing one store** and disagreeing about who owns a field.
  Both internally consistent; the conflict exists only at runtime.
* **Two virtualenvs** differing by one extra, where which one launched decided
  whether a whole capability worked. Not a code defect at all, which is why no
  code scanner could ever have seen it.

The report already admits it misses a dead branch inside a live function, an
unused export, and a wrongly-mounted component. The cheap counter is not
another scanner. It is asking, of each control the interface offers, **whether
anything downstream reads what it stores**; of each shared field, **who owns
it**; and of each environment-dependent capability, **which environment was
actually measured**.

The oldest lesson was re-earned twice. A green suite is not evidence that
something visible happens — the viseme mapping, its unit tests and
`check:visemes` were all correct and all green while the mouth never moved. And
worse than green is **skipped**: 8 skipped and 8 passed look alike at a glance,
and only one of them means anything.
