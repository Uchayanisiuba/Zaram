# The embodiment toggle — spike scope

**Report, not built.** Two questions answered against the code, then what the
spike would actually cost. Investigated 8 August 2026.

---

## The constraint, first

**The avatar embodies what the system is doing.** Thinking versus idle,
listening, speaking, swapping. The orb's job with more bandwidth.

**Narrowed 13 August 2026: it does not embody which model answered.** The
original line here read "which model is answering and what it is doing", and
`local` / `cloud` were two of the seven states. Both are gone, for two reasons.

*The two renderers disagreed about what they report, and that was found by
checking rather than by reasoning.* `LivingOrb` reads `orbStore.orbState`
directly and has **never rendered locality at all**. So the claim in the seam
section below — that both renderers read one derived state — was half true: the
derivation existed and only one consumer ever saw it. The avatar was the sole
renderer reporting where an answer came from, which means the same status told
the user different things depending on a toggle.

Where locality *is* reported is `OrbStatusLabel`, in words: "Local only",
"Local · can send", "Cloud enabled". Its own comment records why three labels
rather than two — permitting a single search host once flipped the indicator to
"Cloud enabled" while every answer was still generated on the machine, and *"on
the one indicator whose entire job is to be trusted, that is the worst thing to
be wrong about."* A rim colour cannot draw that line, so the colour and the
label could only ever have agreed by luck.

**The gap this leaves, stated rather than papered over.** That label is behind
`{chat && …}` in `Landing.tsx` — deliberately, because *"at rest the landing is
meant to be quiet"* — so at rest nothing reports locality. The avatar surfaced
`local` / `cloud` **only** at rest, which is precisely when the label is
absent, so the two were complementary rather than redundant and this removal
does lose that. It was already the situation on the orb path, and the fix, if
it is wanted, is one condition in `Landing.tsx` rather than a colour on a face.
CLAUDE.md's line that *"the Orb shows system state (idle / thinking / local /
cloud)"* does not match `OrbState`, which has never held the last two.

*A face that reports where an answer came from is read as a someone.* The
constraint below is that this is a status indicator rather than a personality.
Rendering a routing decision as an expression is the first step to "she used the
cloud", which is precisely the projection this document was written to prevent.
The pressure to cross that line arrives from anything that sells or personalises
characters, which is why the narrowing is recorded rather than merely done.

Attaching an avatar to an **agent** is the direction that replaces it — an agent
is a thing with a job, and a face standing for one is not a claim about
infrastructure. Not designed, not scheduled; agents are out of scope until v1
ships, and they get no menu item when they arrive.

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

### The shipped avatar is also the mascot — 15 August 2026

A helmeted robot with a dot-matrix LED face. It is the default avatar and the
product's mascot, and the second of those is a collision with the line above
worth stating rather than glossing: the reference art smiles, and a smile is not
a system state.

**It resolves because mascot and renderer are two jobs, and only one of them is
governed here.** The rule says the *status indicator* may not be a someone. It
does not say the product may not have key art. So the character smiles on the
site, the installer, the README and the icon; inside the product its rest face
is `sil`, a flat line. Same asset, two contexts, and the split costs nothing —
a smiling render sells just as well when the running app is honest.

The pressure this document predicted — *"from anything that sells or
personalises characters"* — is now arriving from the product's own marketing
rather than from an avatar store, which is the harder direction to refuse.
Hence writing it down.

### A screen face is not a blendshape face

The LED panel is driven by VRM 1.0 `textureTransformBinds`, which slide a UV
window across a sprite atlas, rather than by morph targets. `@pixiv/three-vrm`
implements them (`VRMExpressionTextureTransformBind`), so the driver's shape is
unchanged — `setValue('aa', 1)` still selects a mouth. What changes is how the
value behaves, and both differences were read off `applyWeight` rather than
assumed:

- **Weights are binary.** `applyWeight` scales the UV delta linearly, so a
  fractional weight lands *between* two atlas cells and renders a sliced
  composite of both. The eased mouth lerp in `VrmAvatar.tsx` is correct for
  morph rigs and wrong for this one.
- **One expression per material.** Binds are additive (`offset.add`), so two
  simultaneous non-zero mouth expressions sum into a cell that does not exist.

The two paths are told apart by **bind type**, never by which avatar is loaded.
Special-casing the bundled character would break bring-your-own on the first
sprite-faced VRM a user supplies, which is the whole reason `vrmSafety.ts`
exists.

Eyes and mouth are **separate materials** so blinking stays independent of
speech; a single combined atlas would need a cell per combination. The face
panel is the only thing the sprite touches — black base colour, atlas on
`emissiveMap`, two quads on the visor, full 0–1 UVs with cell selection done
entirely by `repeat` and `offset`.

State stays on the **rim light**, not on the face. Moving it to the character's
ear rings was considered and not built: the rim already works, needs no
geometry, and reads on any VRM. The face's colour is therefore a constant
(`--face-led`, `#818cf8`) and asserts nothing — see `docs/UI-SPEC.md` for why it
is neither accent, and specifically why it is not violet.

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

**1. ~~`orbState` has no `local`/`cloud`, and the spike wants four expressions
including those.~~ Withdrawn 13 August 2026 — the avatar does not report
locality, so there is nothing to derive.**

The original plan derived an embodiment state from `orbStore.orbState`
(activity) and `sessionStatusStore.locality` (where the answer came from),
because those two are correctly separate stores and neither should grow a field
duplicating the other. That derivation was built and has now been removed with
the states it existed to produce.

What is left is the orb's activity vocabulary, and it is the **same type** rather
than a copy of it:

```ts
export type EmbodimentState = OrbState
// 'idle' | 'thinking' | 'speaking' | 'listening' | 'swapping'
```

`useEmbodimentState()` stays even though it now returns one store's field
unchanged. It is the seam: it is what stops the VRM adapter reaching into three
stores and slowly acquiring opinions about routing, which is exactly what it
would have to do to get locality back. And the alias is deliberate — `LivingOrb`
once declared its own four-member copy of `OrbState` instead of importing the
store's, and a renderer written against a private copy of a vocabulary is how
two renderers silently diverge.

**2. ~~`swapping` does not exist anywhere.~~ ✅ Done, 8 August 2026.** It is now
in `orbStore` (visual), `systemStore` (`OrbActivity` plus the model name and the
plain-language label), and rendered by `LivingOrb`, `Aura`, `Halo` and `OrbCore`.

Two things came out of doing it that the avatar inherits:

- **The per-state variant maps were untyped object literals**, so adding a state
  produced no build error and framer-motion silently animated to nothing. They
  are now `Record<OrbState, …>` — the same remedy M6 applied to the surface
  list, and the reason a second renderer can be added without hunting for the
  maps it forgot.
- **`LivingOrb` declared its own four-member copy of `OrbState`** rather than
  importing the store's. It now re-exports the store's type. A VRM adapter
  written against a private copy of the vocabulary is exactly the drift this
  section warns about.

Set the state through `systemStore.beginModelSwap(model)` / `endModelSwap()`,
never `setOrbState('swapping')` directly — the orb and its label are two
renderings of one fact, and setting one without the other turns the orb
slate-grey while the words still read "Local only".

**Still to wire: nothing calls `beginModelSwap` yet.** The provider layer knows
what forces a swap — `ProviderManager.resident_budget_bytes` exists to avoid one
— but no runtime event announces that one is happening. That is the remaining
half, and it is backend work, not avatar work.

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
| ~~`swapping` on the orb~~ ✅ · `useEmbodimentState()` | The seam, and a real spec gap. The orb half is done; the hook is not. |
| `<Embodiment />` chooser + Settings toggle, orb-only | Proves the switch with one renderer. Nothing can break yet. Picks at mount, no crossfade. |
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

## Decided — 8 August 2026

**The toggle lives in Settings. The landing gets nothing.**

Someone who wants an avatar will look for it once; someone who does not should
never see the control. The landing is the calmest surface in the product and a
renderer switch is a preference rather than an action.

This settles the question the previous entry left open, and it settles a second
one with it: **`<Embodiment />` picks a renderer at mount and does not
crossfade.** A preference changed in Settings does not need to animate on a
surface the user is not looking at, and a crossfade between a glowing sphere and
a 3D character has no good frame in the middle. Changing the setting changes
what mounts next.

That also removes the worst version of the bundle problem. With no crossfade
there is never a moment where both renderers are live, so the lazy-loaded VRM
adapter is fetched only by people who turned it on — the orb path never pays.

### Settings states the cost, and greys out where the hardware cannot take it

The same honesty as the pack catalogue, for the same reason: a control that is
silently disabled is indistinguishable from one that is broken.

- Name the download before it happens — `three` plus `@pixiv/three-vrm`, and its
  size — the way the OCR extra names its 321 MB. Naming the fix without naming
  its cost is not a choice the user can make on a metered connection.
- Grade it against *this* machine. A VRM renderer is 3D on the landing state,
  permanently, while a local model is resident. Where the GPU cannot take it,
  the row is greyed with the reason stated, not hidden.
- Hardware detection returns unknown rather than a wrong number, so a machine
  that cannot be graded is offered the toggle with the caveat, never refused on
  a guess.

---

## Correction — timings arrive *with* the audio, not before it

Recorded here because it changes how the frontend consumes the stream, which is
not obvious from the TTS change alone.

The queued brief assumed phoneme timings could be known ahead of the audio, and
that is wrong. `misaki.en.G2P` produces phonemes with `start_ts` and `end_ts` set
to **`None`** — it knows *what* sounds, not *when*. The durations are a model
output: `KModel` returns `pred_dur` on the same forward pass that returns the
waveform, and `join_timestamps` fills the timestamps from it afterwards.

**What follows for the frontend.** There is no "timings first, audio second"
sequence to build against — no window in which the avatar could begin shaping a
word before the sound for it exists. Timings and audio are one payload from one
forward pass, so:

- the viseme track cannot start ahead of playback, and any design that assumed a
  lead-in has to go;
- a stream event carrying timings without its audio chunk is not a state the
  backend can produce, so the frontend must not have a branch for it;
- the renderer's synchronisation problem is therefore playback alignment, not
  prediction — which is the easier problem, and worth knowing before building
  the harder one.

**Cost is still zero.** `pred_dur` is already computed and already discarded at
`voice/providers/kokoro.py:243`. The change remains "stop throwing it away".

### Granularity — word-level is enough for the spike

Use Kokoro's own `pred_dur`. Skip `wawa-lipsync` entirely: it exists for audio
Zaram did not generate, and Zaram generates all of it today. Building both paths
in one afternoon means neither is tested.

Word-level timings are what `tokens` gives directly, and that is the spike's
target. Phoneme-level is **arithmetic on data already thrown away at
`kokoro.py:243`** — `pred_dur` is per-phoneme-token underneath and
`join_timestamps` merely aggregates it to word boundaries — so it is a refinement
of the same data, reachable without new inference, and it is not what decides
whether the spike is worth continuing.

The earlier note that word-level "will read as mushy" at ~2.5 shapes per second
still stands as a prediction. It is now a thing to *observe* during the spike
rather than a reason to build the finer path first: if word-level looks
acceptable, the arithmetic is never needed, and if it does not, the data for it
is already in hand.
