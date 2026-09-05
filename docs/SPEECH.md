# Speech — what speaks, when, and who may stop it

The contract for voice output. Read with `CLAUDE.md` (the rules) and
`docs/MILESTONES.md` (what is done). Where this file and the code disagree, the
code wins and this file is wrong — say so.

Written 19 August 2026, after the maintainer asked three questions the codebase
could answer and no document could.

---

## The two modes, and why there is no third

| Renderer | On a reply | How the user asks |
|---|---|---|
| **Orb** (landing default) | Silent | A **Speak** button under each reply |
| **Avatar** (character) | Speaks automatically, sentence by sentence | Nothing to press |

`CLAUDE.md`: *"Speech follows the renderer: avatar selected, replies speak; orb,
silent unless asked."* One decision the user already made by choosing a face, so
it needs no second setting — rule 7h, *never make the user choose in advance*.

**Where each half lives.** `chatStore.sendMessage` reads
`useEmbodimentStore.getState().renderer === 'avatar'` **once**, at send, and
holds that answer for the whole reply: a renderer change mid-reply would
otherwise leave a queue open with nothing to close it, or start speaking a reply
whose first half was never queued. `SpeakButton` renders **only** when the
renderer is `orb`, because a button offering to do what just happened reads as a
bug.

**The toggle is in Settings**, not on the landing. The landing panel that used to
carry it was labelled "EMBODIMENT SPIKE — NOT SHIPPED UI" and was shipping; it
was removed on 18 August.

---

## Which voice speaks

**Kokoro-82M, and only Kokoro** — Apache 2.0, CPU, under 2.5 GB, 54 voices. The
reasoning for excluding every better-sounding alternative is in `CLAUDE.md` under
the dependency stack: licence, VRAM, platform coverage. It has not changed.

The default is **`am_michael`** — American English, male. Kokoro ids read `<language><gender>_<name>`, so the
second character is the claim, and `test_voice_resolution.py` asserts on that
convention rather than on the literal: swapping in another male voice keeps it
green, swapping in a female one does not. That is what let the default move
four times across 3–4 September 2026 — `am_michael` → `bm_fable` → `am_onyx` →
`am_michael` — with one constant edited each time and no test rewritten to
match a name.

**The first character is a claim too, and it is the one that nearly shipped
wrong.** `lang_code` was a separately written `"a"`; `DEFAULT_LANG_CODE` is now
derived from `DEFAULT_VOICE`, so a British voice can never again be phonemised
by the American front end. See `voice/config.py`, which also records why the
brightness measurements taken that day are worth keeping and were not what
decided the choice.

**It is decided in exactly one place**, `backend/voice/config.py`. It used to be
spelled in six, which is how they drifted apart. A scan test fails the suite if
any live module spells a default voice instead of importing the constant.

### Resolution order

`main._resolve_voice(requested, persona)`:

1. **What this request asked for.** A per-utterance override still wins.
2. **What the user chose in Settings** (`user_settings.voice`). Their standing
   answer.
3. **The tone preset's voice** — but only if the request named a preset that is
   not the default one.
4. **`DEFAULT_VOICE`**.

**Step 3 is narrow on purpose.** Every request carries `persona="zaram_prime"`
whether or not anybody picked it, so resolving the preset before the setting
would mean the preset nobody chose silently outranked the only voice the user
did. Both voice request models take `DEFAULT_PERSONA` *by reference*, and a test
asserts that coupling, because the day they drift is the day this returns.

**The defect this order was written against:** `user_settings.voice` was written
by the character pane, read back by `GET /character`, rendered in Settings — and
consulted by nothing. A control that stored, round-tripped and displayed, with no
effect on any sound.

---

## When it speaks: alongside the text, not after it

**Speech keeps pace with the text; it never waits for the reply.** Synthesis
starts on the first sentence that will not change again, while the model is still
writing the next. Measured 14 August: speech began **16.6 s before** generation
finished on one reply, and the gap grows with length.

Two failures this rules out, both worse than the delay they avoid:

* **Waiting for the whole reply** — silence that scales with how much there is to
  say.
* **Releasing a sentence that can still be merged into** — puts a pause where the
  text has none, and a listener hears that as a fault rather than as latency.

### Why not word by word

Asked for by the maintainer, 19 August 2026. It is **not** what is built, and
`CLAUDE.md` rules it out in the same paragraph that requires the streaming:
*"Word-by-word is not the goal and would be worse — a clause is the smallest unit
with prosody."*

The reason is not implementation cost. Kokoro synthesises an utterance and gives
it prosody: pitch contour, stress, and the falling tone that ends a statement.
Synthesising *"The"*, then *"harbour"*, then *"lane"* produces three utterances
each carrying the intonation of a complete sentence — the flat, clipped delivery
of a station announcement. It is also slower in wall-clock terms, because each
call carries fixed overhead and there would be one per word rather than one per
clause.

**What the request almost certainly wants is already true**: the voice runs
*alongside* the text as it appears, rather than starting when the text finishes.
If per-word delivery is still wanted after hearing the current behaviour, that is
a maintainer decision to overturn the rule, and it belongs in `CLAUDE.md` before
it belongs in code.

### Citation markers are grounding, not language

`[M1]` and `[S2]` reach neither a reader nor a synthesiser. Stripping happens on
**accumulated** text, because a marker arrives split across tokens, and in **one
function with all callers** — there were three, and the one that had been missed
was the one that spoke.

---

## Interrupting it

**Both routes work, and both are required.**

* **By typing.** The composer calls `bargeIn()` on `onChange` — deliberately on
  change rather than on focus, because clicking into the composer to read it back
  is not an interruption, and stopping there would make speech feel fragile
  instead of responsive.
* **By microphone.** `MicButton` calls `bargeIn()` before `start()`. Here it is a
  **correctness** requirement rather than a courtesy: the microphone would
  otherwise record Zaram's own voice from the speakers and transcribe it back as
  if the user had said it.

`bargeIn()` is cheap when nothing is speaking, so callers may fire it on every
keystroke without checking first. A caller that has to ask "is it speaking?"
first is a caller that will eventually get the answer wrong.

**Generation counters, not flags.** `stop()` and each new `speak()` bump a
counter that every async step checks, so a stopped utterance cannot have its
audio interleaved by an older one's callbacks.

---

## Lip sync, and the state that drives it

The chain, in order:

1. Kokoro returns **word timings with the word's full phoneme string**
   (`{text, phonemes, start_s, end_s}`).
2. `lib/visemes.ts` maps IPA onto the five VRM mouth shapes (`aa ih ou ee oh`,
   plus `sil`), longest-match-first so diphthongs and affricates are not split.
   Lossy by design.
3. A word's phonemes are distributed **evenly** across its span. An
   approximation, and named as one — per-phoneme timings are derivable from
   `pred_dur` but that is a backend change.
4. `VrmAvatar` scrubs the track against **`audio.currentTime`**, never an elapsed
   counter: the two diverge the moment audio buffers or the tab is backgrounded,
   and a mouth drifting out of sync is worse than one that does not move.
5. Shapes ease rather than snap (~15 Hz). Blend shapes switched instantly read as
   a puppet.

**Speech owns the `speaking` state, and chat activity may not overwrite it.**
That is `lib/orbActivity.ts`, and it exists because of a defect worth
remembering: `ChatSurface` wrote `idle` the moment generation finished, and
speech had already set `speaking` and was still playing. Speech outlives the
stream *by design*, so that `idle` landed on top of `speaking` on **every reply**
— and the avatar, which opens its mouth only in `speaking`, sat shut through the
whole answer.

Nothing looked broken, which is why it lasted. The rim light is the same cyan for
`thinking` and for `speaking`, so the only renderer that could show the
difference was the mouth, and a still mouth reads as "lip sync is unfinished"
rather than as a state bug. The viseme code, its tests and `check:visemes` were
green and correct throughout.

`speaking` is now set at the moment a clip **starts playing** — not when the
queue opens, which claimed sound seconds before any existed.

### If the avatar is not the sample one

`AvatarSample_Z.vrm` is morph-rigged, and the eased lerp above is correct for it.
**A character with a screen face is not.** `CLAUDE.md` records that a dot-matrix
face is driven by `textureTransformBinds`, where weights must be **binary** and
exactly **one expression per material** may be non-zero — a fractional weight
lands between atlas cells, and two binds sum into a cell that does not exist.

**That path is not implemented.** The driver applies fractional weights to all
five visemes unconditionally. The two paths must be told apart by **bind type**,
never by which avatar happens to be loaded, or bring-your-own breaks. This is the
first thing to build if a screen-faced character ships.

---

## Installing it

Speech output is an optional extra. Two installs, same engine:
`backend/requirements-voice.txt` (**905 MB**, torch) or
`backend/requirements-voice-onnx.txt` (**243 MB**, onnxruntime — see the
ONNX section above for what that trades). Listening is separate and
far smaller: `zaram[mic]`, 81 MB measured. Split because someone who wants Zaram
to talk should not have to buy a microphone stack.

**The size is not optional in the message.** Naming a fix without naming its cost
is not a choice somebody on a metered connection can make. `speechStore` exports
`SPEECH_NOT_INSTALLED` so the test asserts the same string the user sees, and the
assertions are on the *properties* — a command, a number — so rephrasing stays
free and hollowing it out does not.

**Cloud speech recognition is prohibited outright**, not governed.
`webkitSpeechRecognition` streams the user's *audio* to Google, where no gate can
see or log it. `check-no-cloud-speech.mjs` asserts on every build that no live
module names the API and no live module imports from `legacy/`.

### Which interpreter gets the extras — 19 August 2026

**Installing the extra is only half the instruction; the other half is *into
which venv*, and this repository has two.** `backend/venv` is the working one.
`C:\Zaram\.venv` also exists and is a second complete environment — fastapi,
uvicorn, kokoro, torch, spaCy.

They were identical but for the mic extra: `av`, `ctranslate2`,
`faster-whisper` and `onnxruntime` were in the root `.venv` and absent from
`backend/venv`. So **which interpreter launched decided whether Zaram could
listen**, and `docs/RUNNING.md` told you to point `ZARAM_PYTHON` at the half
that could not. That is why every test in `tests/test_speech_roundtrip.py`
skipped for a whole session while the speaking half worked fine.

Both now carry both extras, which closes the symptom and leaves the cause. The
launcher trap is written up in `docs/RUNNING.md`; reconciling the two venvs is
a triage decision nobody has taken.

### What the 905 MB actually is

**Kokoro is lightweight. Its runtime is not, and the two get confused.**
Measured on disk in `backend/venv`, 19 August 2026:

| | on disk |
|---|---|
| `kokoro` package | **~1 MB** — a thin wrapper |
| Kokoro-82M weights (HF cache) | 315 MB |
| **torch** | **494 MB** |
| transformers | 96 MB |
| spaCy + thinc + blis | 125 MB |
| misaki | 15 MB |

The 82M parameters really are small. What costs the 905 MB is **torch**, which
Kokoro happens to be written against, plus the spaCy stack `misaki` reaches for
grapheme-to-phoneme. Against a 267 MB base that is roughly a quadrupling of the
installer, which is the 81% packaging reduction undone — so the extra stays an
extra.

Two figures were taken with different instruments and agree: summing file
lengths gives torch 494 MB, `du` gives 528 MB because it counts allocated
blocks. Same conclusion either way.

### The ONNX backend — measured, built and tested, 19 August 2026

**Kokoro now runs on onnxruntime as well as on torch, and the choice is one
config field.** `KokoroConfig.backend` is `"torch"` or `"onnx"`;
`ZARAM_VOICE_BACKEND` overrides it. Both build through the seam
`_default_pipeline_factory` already had, both are called `pipeline(text,
voice=...)`, and both yield results carrying `.audio` and `.tokens` — so
`KokoroProvider._run_synthesis` is unchanged and cannot tell which one it got.
That is what `VoiceProvider` was for.

**What it saves, measured rather than projected: 662 MB.**

| dropped | | added | |
|---|---|---|---|
| torch | 528 MB | onnxruntime | 45 MB |
| transformers | 109 MB | onnx | 48 MB |
| sympy | 79 MB | | |
| networkx | 19 MB | | |
| tokenizers, safetensors, mpmath, kokoro, functorch, torchgen | 20 MB | | |

The earlier estimate here was ~590 MB and was low, because torch drags sympy and
networkx behind it and nobody had counted them. `backend/requirements-voice-onnx.txt`
is the install; a clean virtualenv built from it comes to 476 MB of
site-packages, against which the same machine's torch install is 755 MB of
dropped packages alone.

**The blocker was word timings, and it was real.** This file already said the
constraint that decides any TTS swap is not size — an engine that cannot emit
timings costs the viseme chain. Measured on the community export:

```
INPUTS:   input_ids [1, seq]  style [1, 256]  speed [1]
OUTPUTS:  waveform  [1, num_samples]
```

`pred_dur` is not there. A naive swap would have shipped a smaller installer and
a shut mouth, one session after the shut mouth was fixed.

**It is still computed, just never wired to an output.** Walking back from the
encoder's `CumSum` recovers `KModel.forward` line for line — `duration_proj →
Sigmoid → ReduceSum → Div(speed) → Round → Clip → Cast → Gather` — so
`/encoder/Gather_output_0` *is* `pred_dur`. Adding an existing internal tensor to
`graph.output` is local surgery on a file already on disk: no re-export from
torch, no second set of weights, nothing for anyone to host. Done once, cached
under the Hugging Face cache, and **refused loudly** if the tensor is absent,
because arriving at empty timings by accident is precisely how lip sync dies
without anything going red.

**Against the torch reference, five sentences, `am_michael`:**

| | |
|---|---|
| word timings | **bit-identical** — 0.000000 s drift, same words, same order |
| audio length | identical, to the sample |
| magnitude spectra | correlate at 0.984 |
| level | ONNX is **~3 dB louder** — best-fit gain 1.4385, sd 0.0155 |

The gain is stable across sentence lengths and flat across the spectrum, which
reads as an iSTFT normalisation convention in the export rather than lost
precision. It is deliberately **not** corrected by a constant in code: the number
is measured on one voice and has no derivation, and an unexplained scalar on the
audio path is the same class of mistake as a ranking blend used as a threshold.
What *is* in code is a full-scale guard, because `soundfile` clips silently past
±1.0 and clipping is the one difference a listener would hear as a fault rather
than as a level.

**fp16 was measured and rejected.** It is half the download and it is not
equivalent: correlation against torch starts at 0.963 and falls to **0.601** by
the end of a five-second sentence, per-window gain swinging 1.43 to 0.86. That is
error accumulating through the decoder — the sinusoidal source generator's
`CumSum` is the obvious place for it, since a running total in half precision
over a hundred thousand samples loses the low bits, and in an excitation
generator lost low bits are phase. The shape of that defect is the worst
available: invisible in a short test, audible at the end of a long reply. fp32
holds 0.960 over the same final second. The integer variants are smaller again
and are rejected for the older reason — Kokoro's back half is a vocoder, and int8
there buzzes rather than degrading gracefully.

**The default is still torch, deliberately.** Every objective measure says the
two are equivalent and one says they differ by 3 dB, and nobody has *heard* them
side by side. CLAUDE.md's fifth integration test is that the maintainer can judge
whether output is good; no measurement above is that judgement. A test asserts
the default so flipping it trips a named assertion rather than sliding through in
a diff.

**Proven torch-free in a clean virtualenv**, not inferred from a dependency
graph. With torch, `kokoro` and `spacy-curated-transformers` all absent, the
backend synthesised 4.25 s with 11 timed words and `torch` never entered
`sys.modules`.

**One trap found on the way, and it is not obvious.** spaCy loads plugin entry
points from whatever happens to be installed, `spacy-curated-transformers` is
such a plugin, and it imports torch at module scope — so one contaminated
virtualenv drags 494 MB back in through a package nobody asked for, and spaCy
raises rather than skipping a plugin it cannot import. It is in no requirements
file and `test_onnx_requirements_exclude_the_torch_plugin` keeps it out of this
one. Same shape as the misaki/spaCy lesson already in CLAUDE.md, with the edge
running the other way: metadata cannot see it, because the dependency is
expressed as an entry point rather than as a requirement.

**Egress.** Every fetch the ONNX path makes — graph, voices, vocabulary — goes
through one helper that tries the cache offline first and asks the gate only when
there is genuinely something to download. That matters more here than in the
torch provider: voices load lazily at *synthesis* time, from inside `__call__`,
which is outside the window `_ensure_pipeline` wraps. **The torch path still has
that hole**: `KPipeline.load_voice` calls `hf_hub_download` on first use of a
voice, with nothing asked and nothing logged.

### What is still open

* **Nobody has listened.** That is the only thing between the ONNX backend and
  being the default, and it is one A/B away.
* **`onnx` is 48 MB for one graph patch** that runs once. Patching at build time,
  or shipping the patched graph, would take the saving from 662 MB to ~710.
* **misaki fetches `en_core_web_sm` at runtime** if it is absent — observed while
  building the clean virtualenv, unlogged and ungated. This is probably why
  `backend/requirements.txt:45` pins that model into the *base* install, which
  `docs/NEXT-SESSION.md` had recorded as an unexplained defect. The pin looks
  deliberate; its *location* is still wrong, since spaCy is not in base.
* **Piper and espeak-ng** remain unevaluated and are now much less interesting:
  the size argument for them was 905 MB, and it is 243.

## How this was verified

Not by the suite. Driven in a browser with Playwright against the system Edge,
avatar mode, a real reply from a local model:

* **Auto-speech**: `POST /voice/synthesize` fired with nothing clicked.
* **The voice**: the fetched clip was `am_michael_*.wav`.
* **Playback**: `currentTime` advanced 0 → 8.1 s, `paused` false throughout,
  `play()` never rejected.
* **Streaming**: four clips played in sequence as the reply arrived.
* **Lip sync, before the fix**: mouth shut in all 40 frames.
* **Lip sync, after**: mouth wide open at frame 3, closed at frame 7.

That last pair is the standard the pointer-gaze failure set — *"if it returns, it
returns with a screenshot"*. A `lookAt` rig and green unit tests were not evidence
that an eye moved, and green viseme tests were not evidence that a mouth did.

### The acceptance suite now runs, where it used to skip — 19 August 2026

`tests/test_speech_roundtrip.py` is the half the browser cannot show: that
Kokoro and Whisper agree about the audio between them. It skips itself unless
**both** extras are installed and **both** weight caches are present, and it
had been skipping silently — 8 skipped reads much like 8 passed in a summary
line, which is how the listening half went a session unverified.

With `backend/venv` completed it runs: **45 passed** across the roundtrip,
voice-resolution and recogniser suites, and **59 passed** in `voice/tests/`.
The roundtrip tests also skip when the recogniser reports itself unavailable,
so the fact that they *ran* is the evidence that the mic button will be
offered rather than greyed out.

**A skip is not a pass, and a suite that skips everything is not a green
suite.** Worth a guard that fails when the speech acceptance tests skip on a
machine that has both extras — otherwise the next silent skip costs another
session.
