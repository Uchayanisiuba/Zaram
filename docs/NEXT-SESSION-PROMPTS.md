# Next session — handoff

Rewritten 3 September 2026, then **updated the same day once tasks 1 and 2 were
built**. `docs/AVATAR-EMBODIMENT.md` holds the avatar detail;
`docs/MILESTONES.md` remains the product-wide handoff.

---

## What happened on 3 September — read this before the task sections below

**Tasks 1 and 2 are built.** The sections that follow are the *brief*, kept
because the decisions in them are still the decisions. This section is the
state.

### An image has been generated, and nothing left the device

The thing the previous handoff said had never happened. Measured on the RTX
3060, torch 2.13.0+cu126, diffusers 0.40.0, `sd_xl_base_1.0.safetensors`:
`backend/tests/test_local_image_generation.py -m measure`, **6 passed in
8m54s**, with the SDXL Hugging Face cache **deleted** and `socket.connect`
raising for the whole load and sample.

### The offline guard did not work, and the first test could not have noticed

`from_single_file` loads weights from the file it is given and resolves the
pipeline's *component configuration* separately — the two CLIP tokenizers, the
scheduler, the UNet and VAE shapes. Left alone it fetches those from the Hub.

Setting `HF_HUB_OFFLINE=1` around the load **does nothing**: `huggingface_hub`
reads that variable once, at import, into `constants.HF_HUB_OFFLINE`, and
`import diffusers` has already done it. Measured — 3.2 MB written into
`~/.cache/huggingface` during a run the suite reported as passing.

It was found by looking at the cache directory, not by the test, because the
test asserted the loader had *restored the environment variable it borrowed* —
which is true of a guard that never applied. That is the assertion-free test
this repository has been bitten by before. **The replacement blocks sockets.**

Two fixes, and the second is the one that matters: the constant is set
directly, and the configuration is resolved from a directory on this machine
passed as `config=`, so there is nothing to fetch even if the guard lifted. A
missing config **refuses and names the 3 MB** rather than repairing itself over
the network.

**Where the config lives:** `backend/models/image/sdxl-config/` (gitignored, 3.1
MB, copied out of the HF cache), or `ZARAM_IMAGE_PIPELINE_CONFIG`. The
checkpoint is `ZARAM_IMAGE_CHECKPOINT`, or any `*.safetensors` in
`backend/models/image/`. On this machine the checkpoint is still at
`C:/ai-models/sdxl/`, so the env var is how the measured runs found it.

### The Download button has been broken since 28 August

The previous handoff said `.docx`/`.pptx`/`.xlsx` "download from the panel
today". They do not. `RequireApiSecret` authenticates every request, the
credential is attached by a wrapper around `fetch`, and **an `<a href download>`
is not a fetch** — nor is an `<img src>`. Measured: no header returns 401.

Fixed in all three places — the card, the preview panel and Work — as
fetch → object URL → synthesised click, with the failure now rendered instead
of silently doing nothing. `useArtifactImage` does the same for thumbnails.

### `backend/media/` — the open question is answered: **beside it, not through it**

Its own source says `MediaProvider` is *"intentionally stripped of any
modality-specific method"*, so it has **no execute path at all** — registering
there means inventing one from imagination for a single caller. It also
duplicates locality, health and provider selection, which have live homes with
live tests. An image is an artifact, so it goes down the path documents already
go down. Reasoning is recorded at the top of `imaging/contracts.py`.

`backend/media/` remains unreachable. Nothing in this work made that worse and
nothing made it better.

### What was built

| | |
|---|---|
| `backend/imaging/` | `ImageProvider`, `ImageRequest`, `ImageProgress`, `SdxlProvider` |
| `backend/runtimes/images/` | `ImagesRuntime`, registered in `bootstrapper.py` |
| `ArtifactKind.IMAGE` | `render_image`, `create_image`, `.png` via the existing `ChartExporter` |
| `ModelInfo.emits_image` | derived from `output_modalities`, gates `select_model_for_task` |
| `IntentType.IMAGE` | exemplars, keyword phrases, `_NEVER_DEGRADE` |
| `ArtifactGrid` | one card, 2×2, grouped by consecutive run |
| `ImageProgressCard` | percentage and step count |
| Work | thumbnail grid when a listing is all pictures |

### Three decisions worth not re-arguing

**Progress is a direct callback, not an event-bus event.** It was the bus
first, and **nothing subscribed** — the dispatcher blocks on the coroutine, so
the one thing that could have forwarded the events was not running while they
were sent. A complete, tested, unreachable channel. A callback cannot reach
that state: if nobody passes one, nothing is reported and no code pretends
otherwise.

**`image.generate` is in `_NEVER_DEGRADE`.** `_drop_unavailable_steps` turns a
misroute into an ordinary reply, which is right for `tool.terminal` and
catastrophic here — dropped, "draw me a logo" falls through to
`reasoning.generate` and returns a confident paragraph about a picture that was
never made. Rule 9's silent form.

**"Pick one to keep" opens it; it does not delete the others.** `ArtifactStore`
has no delete capability by design and CLAUDE.md puts removing a file with the
operating system. All four stay in the output folder and in Work. A button that
looked like it discarded files and did not would be worse than none.

### The suite is green, and it takes half an hour

**2 failed, 3141 passed, 20 skipped, 29m22s, with Ollama up.** Both failures
were caused by this work and both are fixed; the suite was re-run green on
those files.

The first was cosmetic: `ChartExporter`'s "png is only meaningful for a chart"
stopped being true when the image kind started using the same exporter, and a
test matched the old wording.

**The second was the egress chokepoint doing its job**, and it is worth
knowing about. `imaging/local_sdxl.py` imports `huggingface_hub` — a network
library — which the gate cannot see. It is exempt, but under a *new* category
rather than an existing one, because neither existing one is honest about it:
it is not dormant (it runs on every image request) and it is not gated (it
makes no request to gate). `NETWORK_LIBRARY_DISARMED` is for a module that
imports a network library **in order to switch its network off**, and
`test_disarmed_exemptions_actually_disarm_the_library` asserts the effective
form of the guard — that `huggingface_hub.constants` is touched, not merely the
environment variable. A test that accepted the variable would be the same test
that let the original bug through, so that one was checked against a source
that only sets the variable and it fails as it should.

**Half an hour is the number, not four minutes.** `CLAUDE.md` quotes ~4 minutes
with Ollama up; the real figure on this machine is 29m22s, and the tail is the
voice tests loading torch models. A run that looks hung at twenty minutes is
not hung — it is in `voice/`. `pytest -q` buffers everything through a pipe, so
there is no partial output to reassure you either.

### The one thing not verified: **the browser**

Everything above is measured or covered by tests, including the full backend
path — `test_a_drawn_image_reaches_the_conversation.py` asserts the real event
stream carries progress, then an artifact, with no marker line reaching the
reader and no language model asked anything.

**Nothing has been looked at on screen.** Vite was not running and Electron
held 8420 with the pre-change backend, and stopping the maintainer's running
app was not worth doing unasked. So the React rendering — the grid, the bar
filling, the panel opening itself — is typechecked and unit-tested and
**unwatched**. The avatar lesson applies exactly: unit tests plus a confirmed
rig is not evidence that anything moved on screen.

**Do this first next session:** restart the app so the backend carries the
images runtime, ask for a picture, and watch. `?faceDebug=1` and the stale-module
trap in Traps below still apply.

### Not built, and deliberately

The first-run **offer** to install a model — the refusal names the reason, the
fix and its size, but there is no download flow. **Prompt expansion from project
memory.** The **cloud** image provider. All three are the "proposed user
experience" section below rather than the four-item list, which is done.

---

## Task 1 — artifact display

Four changes, requested by the maintainer 3 September. Two carry decisions that
were taken deliberately and should not be re-opened without a reason.

### 1.1 A batch is one card with a grid, not many cards

A request that produces several images returns **one** `ArtifactCard` holding a
2×2 grid, and the user picks the one to keep. Four cards for one request floods
the conversation, and three of them are about to be discarded.

### 1.2 The panel opens itself — but only for a deliberate request

**Decided: auto-open only when the artifact was the point of the request.** Ask
for an image and the panel opens as soon as it is ready. An artifact produced
incidentally by a reply does *not* seize the screen — an overlay arriving
unbidden mid-conversation is an interruption, not a convenience.

The overlay already exists and needs no new surface: `ArtifactCard` opens
`ArtifactPreview`, which sits over the orb with the background blurred, the same
treatment `CitationPanel` and `CodePreviewPanel` use. Its own comment gives the
reason — *"one way to bring something forward is a thing users learn once."*

### 1.3 A progress bar for image generation

**Decided: percentage and step count, never time remaining.** Time-remaining is a
guess until several steps have run, and a confident wrong number is worse than no
number — the same discipline `vram_bytes` keeps by returning `None` rather than
`0`, and `locality_of` by refusing to say "local" for a model it cannot place.

The reasoning for having it at all is the maintainer's and it is the right one:
**with code you watch it being written, so the wait is legible.** An image is
silent for its whole duration unless something reports it. SDXL emits a callback
per denoising step, so percentage is a real measurement, not a spinner. The card
appears immediately and reports steps in place; the orb reports `swapping` then
working.

### 1.4 Download from the panel

**Largely already built** — verify rather than rebuild.
`ArtifactPreview.tsx:193` already renders an anchor on `downloadUrl(artifact.id)`
with a Download icon, and there is already a fallback for kinds with no preview
reading *"Download it and open it in the app that owns it."* So `.docx`,
`.pptx`, `.xlsx` download from the panel today.

What is unverified: that an **image** kind routes through the same path and
renders inline rather than falling into that no-preview fallback. That is the
work — a kind that previews, not a second download button.

### Also worth doing while in there

Images want a **grid in Work**, not the list documents get. Same store, same
artifacts, different density; a page of thumbnails is browsable in a way a page
of filenames is not, and Work's job is exactly that.

**Do not build**: a lightbox gallery, an image editor, a canvas, or an Images
node. `CLAUDE.md` already declined sub-apps for editing, and images are output —
output is Work.

---

## Task 2 — image generation, Zaram side

**The machine is ready. Zaram cannot use it yet.**

### What is installed and verified

| | |
|---|---|
| `C:/ai-models/sdxl/sd_xl_base_1.0.safetensors` | 6.94 GB, **verified** — 2,515 tensors, internal offset table matches file size exactly |
| `backend/venv` torch | **2.13.0+cu126**, CUDA 12.6, `is_available() True`, RTX 3060, 11.79 GB free |
| `backend/venv` diffusers / accelerate | 0.40.0 / 1.14.0 |
| `C:/ai-models/wheels/*.whl` | the 2.59 GB torch wheel, kept so a reinstall needs no download. Safe to delete. |
| `C:/ComfyUI` | a bare 60 MB clone, **no dependencies, unused** — delete it |

**Not verified: an image has never been generated.** CUDA reports available; the
pipeline has not been loaded and nothing has been sampled. Prove that first —
`StableDiffusionXLPipeline.from_single_file` against the checkpoint above — and
check Kokoro still synthesises, since the CUDA torch replaced the `+cpu` build
the voice path was using. Reverting is `pip install torch==2.13.0` from the CPU
index; no re-download.

### Why diffusers rather than ComfyUI

The maintainer asked whether this could work inside Zaram without a second app.
It can. Zaram's backend is already Python and already had torch; SDXL has a
mature diffusers pipeline and `from_single_file` loads exactly the checkpoint
that was pulled. ComfyUI would have been a second application to install, run and
keep working — and `CLAUDE.md` names that *"a permanent maintenance obligation
that breaks on every host-app update."*

### What is missing on the Zaram side

1. **The refusal path, first.** Without it, "draw me a logo" reaches a text model
   which writes a confident paragraph about an image it never made. That is
   rule 9 in a new medium, and it is the actual bug — the offer is the nice part.
2. **A binary emit-image gate.** `requires_vision` filters models that can *read*
   an image. Nothing filters for models that can *draw* one. Modality exists only
   as a 0..1 ranking score, which is this codebase's most expensive recurring
   error wearing a new hat: membership and ranking are different questions.
3. **An intent.** `core/planner.py` routes a `vision` intent; there is no
   "generate an image" intent. Routing is embeddings against exemplars, so this
   is an exemplar set.
4. **A provider.** One class behind `MediaProvider`, pointed at the local
   pipeline, and the same interface pointed at a cloud endpoint later.

**Decide first: does this register through `backend/media/`, or run beside it?**
That module is a complete, tested Media Runtime — registry, manager, sessions,
health, `MediaType.IMAGE`, `MediaLocality.LOCAL|CLOUD|HYBRID` — that **nothing
imports**, and it deliberately has no execute path. Answering this before writing
code is what stops image generation becoming a third path beside two that exist.

### The proposed user experience, as agreed

First request with nothing set up → Zaram **says so and offers**, naming the
size and the licence for local and the price and data policy for cloud, because
those are what actually decide it. Never blocks; the conversation keeps working
while it downloads. A decline is remembered — one line next time, never the
pitch again.

Once working: Zaram **expands the prompt using project memory** — "a header for
the Northwind proposal" knows what Northwind is, which is the thing no wrapper
can do — and **shows the expanded prompt, editable**, because a rewrite you
cannot inspect is one you cannot correct. The orb shows `swapping` while the
chat model unloads. The result is an artifact card with the model, the locality
and the egress stated plainly: *"SDXL · on your machine · nothing left the
device"*. Reference images to a cloud provider ask once, per destination and per
data class, then remember — `DataClass.IMAGE` already exists for exactly this.

### Model notes, verified against current sources

Draft on **Z-Image-Turbo** (Apache 2.0, 8 steps, ~1K ceiling), finish on
**Qwen-Image-2512 + Lightning** (Apache 2.0, best in-image text, native 2K) — if
those are ever added. SDXL was chosen as the first install because it is **one
self-contained 6.94 GB file**; Z-Image needs a separate 5.6 GB text encoder and
its smallest variants are FP4, which is Blackwell-only and useless on Ampere.
**FLUX.1 dev and FLUX.2 klein-9B are non-commercial** and disqualified as
defaults for client work; only klein-4B and FLUX.1 schnell are Apache. **No image
model on OpenRouter is free** — cheapest is Seedream 4.5 at $0.04/image — so the
"add a free key" story that works for text does not exist for images.

---

## Task 3 — the avatar, and it is finished

Recorded so it is not re-derived. **All nine clips bind**; the two-skeleton
problem is solved and there is no retargeting left.

- `idle` ×3, `listening` ×2, `speaking` ×3, `thinking` ×1 — watched playing
- `swapping` borrows a random idle clip and holds a smile; `statesWithoutClips`
  records `['swapping']` deliberately, so the borrow is visible not accidental
- The high-resolution GLB is shipped (37,310 tris, legs removed); rest pose
  agrees with the previous export to 0.048°
- Face atlas is **4×4**, files named `*_atlas_4x4*`. Seven mouth cells — the six
  VRM presets plus `smile` — and eight eye cells including `happy_blink`
- Idle alternates **neutral 23–41s / smile 6–10s**, drawn fresh each time, six
  second floor. Eyes lead, mouth follows one second behind, both directions
- `thinking` wears the neutral mouth; the shell is 20% glossier (`roughnessBoost`
  2.1 → 1.68)

### Still open on the avatar

1. **Lip sync has never been watched** against a real Kokoro track.
2. **GPU cost unmeasured** and the triangle count tripled. Measured this session:
   body textures **49 MB** (three 2048², 16 MB each) against the face atlases'
   **8 MB**. Shrinking the atlas saves 3.5 MB; halving the body maps saves 36 MB,
   and at ~320px on screen 2048² is almost certainly more than is used.
3. **The rim light reports nothing** — metallic body, back-placed light.
4. `CLAUDE.md` says the rest face is `sil` and the idle smile is rare; the
   alternation makes it ~20% of idle. One sentence there naming the alternation
   would close it.

---

## Traps

**Replacing the GLB reverts the mouth UV fix.** Four sessions and counting:

```bash
cp "avatar-source/Zaram_Robo Hi.glb" frontend/public/avatars/zaram-robo.glb
py avatar-source/fix_face_uvs.py --apply
node frontend/scripts/check-rig-agreement.mjs
```

**`rest-pose check: 2/65` is fine, not a warning.** An older version of this file
said anything above `0/65` meant a T-pose. The real tolerance is 0.05 rad =
**2.86°** and the clips sit at 0.25°. `check-rig-agreement.mjs` is the authority.

**Driving `orbStore` from the browser console does not reach the app.** A dynamic
`import('/src/stores/orbStore.ts')` returns a different module instance from the
one the running component holds once Vite's graph is stale. The store reports
`speaking` while the component never leaves `idle`, and every reading taken that
way is fiction. **This cost most of a session** — a mouth apparently stuck in the
speaking shape and a thinking mouth showing the wrong cell were both artefacts of
it and neither was ever a bug. Restart Vite, and read `?faceDebug=1`.

**The character GLB imports as two armatures** and Blender returns the vestigial
one-bone `DeformationSystem` first. `retarget_animations.py` now selects by bone
count; taking the first reported `carries no action`, which reads as a bad export
rather than a wrong armature.

**A hash that looks random can have a short period.** The speech fallback stepped
by `(step * 2654435761) >>> 0`, which repeated every ~7 steps — a one-second loop
at 7 steps a second. `mixStep` is a proper avalanche mix.

**Do not re-run `extend_face_atlases.py`** — historical.
`redraw_face_atlases.py` owns the layout and its eye regrid detects an
already-4×4 atlas and skips.

**The backend may already be running.** Electron spawns its own; starting a
second by hand fails on port 8420. Check before launching. **And it carries the
code from whenever it started** — this is what stopped the 3 September image
work being watched on screen. A backend that has been up since before your
changes will not have your runtime registered, and the symptom is a capability
that behaves exactly as if you had never written it.

**`HF_HUB_OFFLINE` is read once, at import.** Setting it after `import
diffusers` does nothing, because `huggingface_hub.constants.HF_HUB_OFFLINE` has
already been evaluated. Set the constant, not only the variable — and prefer
not needing either, by passing a local `config=`. Costed a run that reported
itself as passing while writing 3.2 MB into the HF cache.

**An `<a href>` and an `<img src>` do not carry the API credential.** It is
attached by a wrapper around `fetch`, and neither of those is a fetch. Anything
that needs bytes from the backend goes through `fetch` and an object URL. This
broke the download button for a week with no visible error — the click simply
did nothing.

**A test that inspects a flag the guard sets is not a test of the guard.**
Asserting `HF_HUB_OFFLINE` had been restored passed against a guard that never
applied. Remove the capability instead: block the socket, delete the cache,
and let the failure be the thing you were worried about.

**`npx vitest run` from the repository root loads the wrong vite config** and
dies on `Cannot find module '@vitejs/plugin-react'`. Run it from `frontend/`.
`check:reachability` and `check:guards` are root scripts; `check:assets` and
friends are frontend ones.

**`pytest --timeout` is not available** — `pytest-timeout` is not installed, and
passing it fails collection with exit code 0, which reads as a suite that ran
and found nothing.

---

## Prompt for the next session

> Continue Zaram. Read `docs/NEXT-SESSION-PROMPTS.md` first — the "What happened
> on 3 September" section at the top is the state; everything under it is the
> brief the work was done against. Re-deriving any of it is expensive.
>
> **Tasks 1 and 2 are built and nothing is committed.** An image has been
> generated and proved offline; the full backend path is covered by
> `test_a_drawn_image_reaches_the_conversation.py`.
>
> **Start here: watch it work.** This is the one thing not done, and it is the
> one the working agreement cares about most. Restart the app so the backend
> carries the images runtime — the running one predates it and will behave
> exactly as if the work had never happened — then ask for a picture and look
> at: the progress bar filling with a real step count, the preview panel
> opening itself, a batch of four rendering as one 2×2 card, the Download
> button actually producing a file, and Work showing a thumbnail grid. Restart
> Vite first; driving stores from the console reaches a stale module instance
> and every reading taken that way is fiction.
>
> If any of it is wrong, the code is in `backend/imaging/`,
> `backend/runtimes/images/`, `frontend/src/components/ArtifactGrid.tsx`,
> `ImageProgressCard.tsx` and `hooks/useArtifactImage.ts`.
>
> **Then, in order:** the first-run offer to install an image model (the refusal
> already names the reason, the fix and its size — the download flow is what is
> missing); prompt expansion from project memory, shown and editable; and the
> cloud image provider behind the same `ImageProvider` interface, with
> `DataClass.IMAGE` consent asked once per destination.
>
> **Task 3: the avatar is finished**; the open items are lip sync (never watched
> against real audio), the GPU measurement, and one sentence in `CLAUDE.md`
> reconciling the rest-face rule with the idle alternation.
>
> **Two stale claims in `CLAUDE.md` worth fixing while you are there**, both
> found on 3 September: it says `orchestrator/capabilities.py` maps
> `ModelCategory.IMAGE` to `Capability.VISION: 1.0`, but that package was
> deleted on 28 August — the defect it describes is gone and the sentence now
> points at nothing. And "Images, both directions" still says nothing gates
> modality; `ModelInfo.emits_image` and
> `select_model_for_task(requires_image_output=…)` are that gate.
>
> Stage paths explicitly when committing; a previous session swept a dozen
> unrelated files into an avatar commit with `git add -A frontend/src`.
