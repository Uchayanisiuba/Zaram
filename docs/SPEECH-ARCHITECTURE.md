# Zaram — speech response architecture

> ## North star, set by the maintainer 15 August 2026
>
> **Speech follows the text without lag. The user never waits. Zaram processes
> and responds as fast as it can, and the user can interrupt it — by typing or
> by microphone — at any moment.**
>
> Everything below is measured against that. Where the current design falls
> short of it, that is said rather than explained away.
>
> **Barge-in is built** (15 August): typing in the composer or pressing the
> microphone stops speech immediately. The microphone case is a correctness
> requirement, not a courtesy — without it the mic records Zaram's own voice
> from the speakers and transcribes it back as if the user had said it.


A description of how Zaram speaks, written to be handed to another model for
critique. Everything below is read from the running code, not from memory, and
every number is measured rather than estimated.

## What Zaram is, briefly

A local-first memory and control layer for people who use more than one AI. It
runs on the user's own machine, indexes their documents into a local knowledge
base, and routes chat to local models (Ollama) or to cloud providers the user
has brought their own key for. A 3D VRM avatar can replace the status orb; when
the avatar is showing, replies are spoken.

## Hard constraints (these are not negotiable, so please work inside them)

1. **The product never pays for inference.** The user brings their own key or
   their own model. No feature may require a per-token cost we bear. This rules
   out cloud TTS APIs as the default path.
2. **Speech must not compete with the local LLM for VRAM.** A 12 GB card holds
   the chat model (~8 GB) plus embeddings (0.66 GB, measured). TTS therefore
   runs on **CPU**.
3. **Must work on Apple Silicon and AMD**, not just NVIDIA.
4. **Permissive licence only.** No AGPL, no non-commercial weights.
5. **Local only.** Cloud speech recognition is prohibited outright and enforced
   by a build-time check — Chrome's `webkitSpeechRecognition` streams the user's
   *audio* to Google, which no logging gate can see.

Those five are why the engine is **Kokoro-82M** (Apache 2.0, ~2.5 GB, CPU, 54
voices) and not something that sounds better. Alternatives were evaluated and
each failed on licence, VRAM, or platform coverage.

## The measured problem

Kokoro on CPU runs at roughly **real time**:

| Input | Audio produced | Wall clock |
|---|---|---|
| "Hi." | 1.25 s | 3.4 s |
| 30-word passage | — | 8.2 s |

So synthesising a whole reply before playing any of it costs the user
approximately the entire duration of the reply before they hear the first word.
For a 60-second answer that is a minute of silence.

## The architecture

### Output path (text → speech), end to end

```
model streams tokens
   │
   ▼
chatStore accumulates reply text
   │  (on every token)
   ▼
stripCitationMarkers()            ← removes [M1] / [S2] grounding markers
   │
   ▼
utterances.ts  ── splits into sentences; only sentences that
   │               CANNOT CHANGE AGAIN are released
   ▼
UtteranceQueue (async, grows under its consumer)
   │
   ▼
play loop:  synthesise piece N+1  ──while──▶  play piece N
   │                                          (one ahead, never two)
   ▼
POST /voice/synthesize  →  { audio_url, timings }
   │
   ├── fetch the .wav → Blob → HTMLAudioElement
   └── timings: Kokoro's word-level spans, each with its phoneme string
                     │
                     ▼
              visemes.ts — IPA → 5 VRM mouth shapes
                     │
                     ▼
              VrmAvatar reads audio.currentTime every frame
              and scrubs the viseme track
```

### The key design decisions

**Speech keeps pace with the text; it never waits for the reply.** Synthesis
starts on the first sentence that will not change again, while the model is
still writing the next. Measured on a real reply: first synthesis at 35.8 s
against a stream that closed at 52.4 s — **speech began 16.6 s before generation
finished**, and the gap grows with reply length.

**Time-to-first-sound stops scaling with reply length.** That is the property
that makes it feel immediate. It does not make synthesis faster — nothing can —
it stops the user waiting for work whose output they will not need for another
ten seconds.

**Sentence, not word.** Word-by-word would be worse: a clause is the smallest
unit with prosody. Releasing a sentence that could still be merged into puts a
pause where the text has none, and a listener hears that as a fault rather than
as latency.

**Two guards on the splitter, both learned from failures:**
- *Never split inside a number.* "£1,470.50" broken after "1,470." is spoken as
  two utterances with a pause in the middle. The figure on an invoice is exactly
  what must not be garbled. There is a decimal-point check and a short
  abbreviation list (`Mr.`, `e.g.`, initials).
- *Never emit a chunk too small to be worth a request.* Below **24 characters**
  the round trip and model call cost more than the audio they buy, so short
  pieces merge forward. Above **240 characters** (~10 s of speech) a clause
  boundary is used instead, because one long chunk reintroduces the original
  delay.

**One piece of lookahead, not two.** Two would synthesise work that a `stop()`
is about to discard, and Kokoro is the scarce resource.

**The lip-sync clock is `audio.currentTime`, not an elapsed counter.** The two
diverge the moment audio buffers or the tab is backgrounded, and a mouth
drifting out of sync is worse than one that does not move.

**Viseme mapping is lossy by design** — ~40 English phonemes onto five VRM
shapes (`aa ih ou ee oh` plus silence). A mouth moving plausibly in time beats a
mouth moving accurately out of time.

**Timings arrive with the audio, never before it.** Kokoro's G2P returns
phonemes with null timestamps; the durations are only known after synthesis. So
there is no "timings first, audio second" sequence to build against — one
request returns both.

**Speech follows the renderer.** Avatar selected → replies speak. Orb → silent
unless asked. One decision the user already made by choosing a face, so it needs
no second setting.

**Markers are stripped once, in one function, for all callers.** `[M1]` and
`[S2]` reach neither a reader nor a synthesiser. There were three callers of
that idea once and the one that had been missed was the one that spoke them
aloud.

## Known weaknesses (I am not asking you to discover these — I am asking whether the fixes are right)

1. **Per-phoneme timings are approximated.** Kokoro exposes *word-level* spans
   with the word's full phoneme string. `pred_dur` is per-phoneme-token
   underneath and `join_timestamps` merely aggregates to word boundaries, so
   real per-phoneme timings are derivable — but that is a backend change not yet
   made. Today a word's phonemes are distributed **evenly** across its span. At
   ~3 phonemes per word and 150 wpm that gives roughly 7–8 mouth shapes per
   second against the ~2.5 that word-level-only would give.

2. **A chunk-streaming endpoint exists and is unused.** `/voice/stream` returns
   SSE chunks from the engine; the client uses `/voice/synthesize` per sentence
   instead. So chunking is decided **client-side by punctuation** rather than
   engine-side by audio frames.

3. **Every utterance is a separate model call.** No warm pipeline across pieces.

4. ~~**No barge-in.**~~ **Built 15 August.** Typing or pressing the microphone
   stops speech immediately. What it still cannot do is *resume* mid-utterance —
   the unit of playback is a sentence, so an interruption discards the current
   one rather than pausing inside it.

5. **No prosody or emphasis control.** Plain text in, one voice out.

6. **The splitter is heuristic** — regex plus a deliberately short abbreviation
   list. A long list was judged "a different kind of wrong"; the cost of a miss
   is a slightly early pause rather than a mangled number.

## My own answers to the three questions, for you to disagree with

Written before sending this out, so the disagreement is visible rather than
absorbed.

**1. Is sentence-level client-side chunking the right layer?** *Yes, for this
engine, and it would be wrong for a different one.* Kokoro is not a streaming
model — it synthesises a whole utterance and returns a whole waveform, so
`/voice/stream`'s SSE chunks are chunks of *a finished clip*, not audio frames
emitted as the model produces them. Moving chunking backend-side would therefore
change where the split is decided without changing when the first sound arrives,
which is the only number that matters. It would also cost the one thing the
client is uniquely able to do: decide *"will this sentence change?"* against
text that is still arriving, which the backend cannot know because it receives
one utterance at a time. **The layer follows the engine.** If Kokoro were
replaced by a genuinely frame-streaming model, this inverts and the client
should become a dumb player.

**2. Are per-phoneme timings worth extracting?** *Probably not yet, and the
measurement to decide is cheap.* Even distribution already yields ~7–8 shapes
per second. Human speech averages ~12–14 phonemes per second, so the current
approximation is roughly half rate — but the error is *within* a word, bounded
by word duration (~400 ms), and the mouth is ~40 px tall at the rendered size.
The honest test is a side-by-side recording at 320 px, not an argument.
`CLAUDE.md` has a scar exactly here: pointer-tracking gaze had passing unit
tests, a confirmed `lookAt` rig, and did not visibly work, because the fringe
covered the eyes at the rendered size. **The deciding evidence is two videos,
not a duration table.**

**3. How do you do barge-in on a queue of clips?** *Built, and simpler than a
live stream.* A generation counter is bumped, every async step checks it and
bails, the queue is released so the loop is not blocked waiting on it, and the
current `HTMLAudioElement` is paused. A queue is *easier* to interrupt than a
stream — there is no half-received buffer to discard and no connection to tear
down; the worst case is one already-synthesised clip thrown away. What a queue
cannot do is resume mid-utterance, because the unit of playback is a sentence.
Whether resume matters is a question about people, not architecture.

## What I would like your view on

Please be concrete and stay inside the five constraints above. Vague advice to
"use a streaming TTS model" is not useful unless it is CPU-viable, permissively
licensed and cross-platform.

1. **Is sentence-level client-side chunking the right layer?** Or should the
   backend stream audio frames and the client just play them? What does each buy
   and cost, specifically, given synthesis is ~1× real time on CPU?

2. **Is one-piece lookahead the right depth?** Under what conditions would two
   or three be better, and how would I detect that from measurements rather than
   feel?

3. **Is extracting per-phoneme timings from `pred_dur` worth the backend
   change**, or is even distribution across a word visually indistinguishable at
   a 320 px avatar? What would you measure to decide?

4. **How would you handle barge-in** on a design where audio is a queue of
   pre-synthesised clips rather than a live stream?

5. **Sentence segmentation**: is a heuristic splitter the right call for
   *streaming* text, where you must decide "will this sentence change?" before
   seeing the next token? Is there a better formulation of that decision?

6. **What breaks first at scale** — a 2,000-word reply, a reply full of code
   blocks and tables, a language other than English?

7. **Anything structurally wrong** that I have described as working. Assume I
   would rather hear it now.

## For reference, the concrete numbers again

| Quantity | Value | How known |
|---|---|---|
| Kokoro CPU throughput | ~1× real time | measured, 10 Aug 2026 |
| "Hi." → audio | 1.25 s audio in 3.4 s | measured |
| 30-word passage | 8.2 s | measured |
| Speech head start on a real reply | 16.6 s | measured, 14 Aug 2026 |
| Minimum utterance | 24 characters | tuned |
| Maximum utterance | 240 characters (~10 s) | tuned |
| Viseme shapes/sec, current | ~7–8 | derived from ~3 phonemes/word at 150 wpm |
| Viseme shapes/sec, word-level only | ~2.5 | derived |
| Lookahead depth | 1 piece | design |
| Embedding model resident | 0.66 GB | measured, nvidia-smi |
| Chat model resident | 8.08 GB (gemma4:12b) | measured, Ollama /api/ps |
| Kokoro package size | ~905 MB extra | measured |
