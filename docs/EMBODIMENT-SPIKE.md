# The embodiment toggle — spike scope

**Report, not built.** Two questions answered against the code, then what the
spike would actually cost. Investigated 8 August 2026.

---

## The constraint, first

**The avatar embodies which model is answering and what it is doing.** Local
versus cloud, thinking versus idle, speaking. The orb's job with more bandwidth.

Not a personality. Not a name. Not a relationship. This is the line that decides
every later argument, so it goes in the spec before any code: the moment the
avatar has a name, users form a relationship with a status indicator, and every
routing decision it displays becomes a thing *she* did rather than a thing the
system did. Zaram's whole claim is that the machine is legible. A character that
invites projection is the opposite of legible.

Concretely, that rules out: idle animations that read as personality (looking
around, fidgeting, reacting to being watched), any name or pronoun in the UI,
emotional expressions not derived from system state, and voice lines. It rules
*in*: the same four-to-six states the orb has, rendered with a face instead of a
glow.

---

## Question 1 — can the TTS path emit phoneme timings?

**Yes, and better than hoped: Kokoro already computes them. Zaram throws them
away.**

Measured on this machine, `kokoro==0.9.4`, `misaki==0.9.4`:

```
text        phonemes           start     end
Your        jˌʊɹ               0.275   0.425
day         dˈA                0.425   0.650
rate        ɹˈAt               0.650   0.925
for         fɔɹ                0.925   1.050
Harbour     hˈɑɹbəɹ            1.050   1.400
Lane        lˈAn               1.400   1.975
```

### Where they come from

Two stages, and the important one is the second:

1. **`misaki.en.G2P`** returns `(phoneme_string, [MToken])`. `MToken` carries
   `text`, `phonemes`, `start_ts`, `end_ts` — but **the timestamps are `None` at
   this stage.** G2P knows *what* sounds, not *when*. The queued brief's
   assumption that phonemes exist before the audio is right; the assumption that
   durations do is not. Durations are a model output.
2. **`KModel` returns `pred_dur`**, a per-token frame-duration tensor, alongside
   the audio. `KPipeline.join_timestamps(tokens, pred_dur)` walks it and fills
   `start_ts` / `end_ts`. Frames convert at 600 samples per frame against a
   24 kHz rate — 40 frames per second.

So timings arrive *with* the audio rather than before it, from the same forward
pass. **Cost is zero**: `pred_dur` is already computed and discarded. Nothing
extra runs, no second model, no spectral analysis.

### Why Zaram does not have them today

`voice/providers/kokoro.py:243`:

```python
for _graphemes, _phonemes, audio in pipeline(text, voice=voice):
    chunks.append(audio)
```

`KPipeline.Result` supports tuple-unpacking for backwards compatibility, and
this call site uses it — so `tokens` and `pred_dur`, which are only reachable as
attributes, are discarded before anyone could want them. The phonemes are
captured into `_phonemes` and dropped too.

**The change is to stop discarding, not to compute anything.** Iterate results
as objects, keep `result.tokens`, carry them on `AudioResult` beside the path
and duration.

### Granularity, and the one real gap

`tokens` are **word**-level. Visemes want phoneme-level. `pred_dur` is
per-*phoneme-token* underneath, so finer timings are derivable — `join_timestamps`
already walks that array and simply aggregates to word boundaries. A
phoneme-level variant is arithmetic on data we already have, not new inference.

Worth measuring before committing: whether word-level visemes look acceptable.
At ~3 phonemes per word and 150 wpm, word-level gives roughly 2.5 mouth shapes
per second, which will read as mushy. Assume phoneme-level is needed.

### Mapping to VRM

IPA → the five VRM presets is a lookup table, and it is lossy by design — 40-odd
English phonemes onto `aa ih ou ee oh`. That is the standard trade and it looks
fine, because a mouth moving plausibly in time beats a mouth moving accurately
out of time.

The sample file's blendshapes are confirmed present, which removes the usual
first-day failure.

### Verdict

**Take the phoneme path. Do not build the wawa-lipsync fallback in the spike.**

The fallback is for audio Zaram did not generate, and today Zaram generates all
of it. Building both paths in an afternoon spike means neither gets tested
properly. Add it when there is audio from elsewhere — and note that the
interface below makes that a second implementation rather than a rewrite.

One caveat worth stating plainly: **this couples lip sync to Kokoro.** CLAUDE.md
says keep TTS behind an interface so the choice is replaceable. So the timings
cross the boundary as a plain structure — `[(phoneme, start, end)]` — not as
Kokoro's `MToken`. A future engine that cannot produce them returns an empty
list and the renderer falls back to amplitude, which is exactly the seam the
fallback would slot into.

---

## Question 2 — is the embodiment layer a clean seam?

**Mostly yes. Three things need changing, and none is structural.**

### What is already right

`LivingOrb` reads exactly one thing: `useOrbStore().orbState` — `idle |
thinking | speaking | listening`. Its props are **purely presentational**
(`px`, `size`, `emphasis`, `pulseAmplitude`, `coreDotScale`). It has no
knowledge of chat, routing, memory or transport.

That is the definition of an adapter over a status store, and it means a
`VrmAdapter` reading the same store genuinely could sit beside it without either
knowing the other exists. The stores are already split the right way:
`orbStore` (activity), `sessionStatusStore` (which model, local or cloud),
`systemStore` (the machine). The state the avatar needs is already assembled and
already has one home.

### What needs changing

**1. `orbState` has no `local`/`cloud`, and the spike wants four expressions
including those.**

Locality lives in `sessionStatusStore.locality`, activity lives in
`orbStore.orbState`. They are correctly separate — they change at different
rates for different reasons, and that separation was a deliberate fix. So an
adapter should *derive* an embodiment state from both rather than either store
growing a field that duplicates the other:

```ts
type EmbodimentState =
  | 'idle' | 'thinking' | 'speaking' | 'listening'
  | 'local' | 'cloud' | 'swapping'
```

Derived in one hook — `useEmbodimentState()` — that both adapters consume. That
hook is the seam, and it is what stops the VRM adapter reaching into three
stores and slowly acquiring opinions about routing.

**2. `swapping` does not exist anywhere.** CLAUDE.md: *"a route that requires a
swap must be visible in the orb's state. An invisible swap reads as a broken
product."* Neither the orb nor the store has it. **The orb is missing a state
the spec requires**, and the avatar would inherit that gap. Worth adding to the
orb first, in the same shape, so the toggle is switching between two renderers
of the same vocabulary rather than one renderer with more states than the other.

**3. Four mount sites, none of them behind a chooser.** `Landing`, `OrbStatus`,
`CommandDock`, and a legacy surface all import `LivingOrb` directly. A toggle
means an `<Embodiment />` component that picks a renderer, and those call sites
switching to it. Mechanical, but it is four files, and `OrbStatus` is the
return-to-conversation control — breaking it strands the user in a workspace.

### What must not happen

The VRM adapter must not import from `LivingOrb`, and `LivingOrb` must not learn
that another renderer exists. Both read `useEmbodimentState()` and nothing else.
If a shared behaviour constant is needed, it moves next to the hook rather than
one adapter importing the other's `ORB_BEHAVIOUR`.

---

## What the spike costs

Afternoon-sized, in this order:

| step | why first |
|---|---|
| `useEmbodimentState()` + `swapping` on the orb | The seam, and a real spec gap. Both adapters need it before either exists. |
| `<Embodiment />` chooser + persisted toggle, orb-only | Proves the switch with one renderer. Nothing can break yet. |
| Three.js canvas + `@pixiv/three-vrm`, load and **log every blendshape name** | The named requirement, and it is the right one: a missing viseme is silently indistinguishable from a code bug. |
| Four expressions from `useEmbodimentState()` | The actual product claim. Ship-or-bin decision point. |
| Keep `result.tokens` through the TTS path | Backend, independent of the renderer, testable on its own. |
| Phoneme→viseme table, driven by timings | Last, because it is the only part that is merely nice. |

### Costs to confirm before starting

- **Bundle.** `three` plus `@pixiv/three-vrm` is roughly 600 KB–1 MB gzipped.
  Not a base-install problem — it is frontend, not a wheel — but it is real, and
  the packaging discipline that refused 321 MB for OCR should at least look at
  it. Lazy-load the adapter so orb users never fetch it.
- **VRAM and GPU.** `docs/UI-SPEC.md` currently says of the constellation:
  *"No 3D, no force-directed layout, no bloom or glow — the machine is running
  local inference and GPU budget is not free."* A VRM renderer is 3D on the
  landing state, permanently. That is not a contradiction the spike gets to
  ignore: **measure the frame cost against a resident 9 GB model before this
  becomes a default**, and keep it opt-in regardless.
- **Licence.** `@pixiv/three-vrm` MIT, `three` MIT, VRM an open format. Clean.
  The sample avatar is a VRoid export and is gitignored — worth confirming its
  licence permits redistribution before any avatar ships in an installer.

---

## Open question for the spec

**Does the toggle belong on the landing state or in Settings?**

The queued brief says landing. That makes it discoverable, and it is where the
thing being toggled lives. Against it: the landing is the calmest surface in the
product and a renderer switch is a preference, not an action — and CLAUDE.md's
navigation argument is that things which hold nothing do not earn a place.

A middle reading: the toggle lives in Settings, and the landing gets nothing.
Someone who wants an avatar will look for it once; someone who does not should
never see the control. Worth deciding before the spike, because it changes
whether `<Embodiment />` needs to animate between renderers or merely pick one
at mount.
