# Next session — handoff

> **Out of date at the top, current at the bottom.** The newest prompt is
> *"Prompt for the next session — written 10 September 2026"*, at the very
> end of this file, and the authoritative state is the **Current state** block
> in `docs/MILESTONES.md`.
>
> **The typing clip is done and shipped** — re-exported from `Robot_All_01`,
> standing, and the waist-exclusion workaround it needed while the source was a
> sitting Mixamo file was deleted with it.
>
> Three earlier prompts still hold something. The **8 September** one is the
> brief for that clip, and its reasoning about the waist split is now history
> rather than instruction. The **7 September, evening** one is
> the TabbyAPI migration, which is now one server restart from its first real
> answer. The **6 September (later)** one is the code pack, and its tasks 2 and
> 3 are still open. Everything else is an earlier brief: accurate about what was
> built and why, superseded on status. Read those for reasoning, not for what is
> true today.


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

## Prompt for the 4 September session — superseded

> Continue Zaram. Read the **Current state — 4 September** block at the top of
> `docs/MILESTONES.md` first; it is the handoff and re-deriving it is expensive.
> The sections below in this file are the 3 September brief and are still true
> except where that block supersedes them.
>
> **Run the backend suite with `backend/venv/Scripts/python.exe`.** Not
> `C:\Zaram\.venv`. The two environments differ in ways that decide outcomes —
> `.venv` has no diffusers — and last session ran most of its suites in the
> wrong one and had to redo them. `docs/RUNNING.md` says which; believe it.
>
> **Start here, and do not skip to the interesting work.** The running app is
> served by a *second* `main.py` on `Python311\python.exe`, spawned by the
> correct `backend/venv` process that Electron launched. That child holds port
> 8420 and has **`torch 2.12.1+cpu`, `cuda: False`** and no diffusers. So image
> generation cannot work in the app however good the provider is, everything
> local and GPU-bound is quietly on the CPU, and **any test done "in the app" is
> testing the wrong process.** The Current state block lists what has already
> been ruled out — read it before investigating, because the obvious causes are
> all eliminated. Do not install diffusers into the base interpreter to make the
> symptom go away: its torch is CPU-only and it entrenches the split that has
> already cost a 376 MB installer exclusion.
>
> **Then the egress hole.** Five suite failures share one cause: the
> `/v1/model` probe that establishes whether a chat template opens the think
> block is an extra request per message. The user is asked twice, the egress log
> gets two entries, and `test_an_image_to_a_chat_approved_host_is_refused` fails
> with *"the picture reached the transport"* — an image reaching a host approved
> only for chat. Both halves matter: the consent hole, and the double dialog
> that `CLAUDE.md` says kills daily use.
>
> **Then watch FLUX work in the app**, which could not be done last session
> because of the interpreter. It is proven at the provider level —
> `tests/test_flux_draws_locally.py` draws a blue dog and writes
> `_flux_sample.png` for a person to open — but nobody has seen it come back
> through the conversation with a progress bar, a preview panel and a Work
> thumbnail. Ask for a picture; expect ~90 s for the first (the pipeline loads
> from disk) and seconds after.
>
> **Nothing is committed.** 31 August, 3 September and 4 September are all
> sitting uncommitted on `Zaram-V0.1`. Splitting them into a few commits is
> probably worth more than one enormous one.
>
> **Left deliberately, with re-entry points:** capturing a letterhead *in chat*
> rather than only in Settings, and offering it the first time a document is
> generated without one — the store and routes exist, only the chat path is
> missing (rule 7e: no form before the first document). And letting the model
> design documents within format constraints, which is the maintainer's stated
> direction for making generated PDFs and decks less plain; the shared theme and
> a 16:9 deck are in place as the floor to design against.

## Prompt for the 3 September session — superseded, kept for the brief below

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

---

## Prompt for the 5 September session — superseded, its tasks are done

*A1, the 17 failures and A2 were all built on 5 September. Kept for the
reasoning; the prompt that follows it is the current one.*

**This was the current prompt.** Everything above it is an earlier brief, kept
for its reasoning and superseded on status. The authoritative state is
**Current state — 5 September** in `docs/MILESTONES.md`.

Paste from here down.

---

Read `docs/MILESTONES.md` — the **Current state — 5 September 2026** block —
before anything else. Then `CLAUDE.md` for the rules.

`main` is the trunk and the working tree is clean. **8 commits are unpushed.**
Do not push without being asked.

### Your task, in order

**1. A1 — make the first-run model recommendation true. Start here; it is hours.**

`core/readiness.py:121` hardcodes `SMALLEST_CHAT_BYTES = 397 MB` and offers
that same number to a 4 GB laptop and a 24 GB workstation. Meanwhile
`backend/providers/model_manifest.py` already does hardware-tier matching and
**nothing imports it**. `providers/models.manifest.json` is populated — 5
tiers, real Ollama names, dated 2026-08-30. There is no content work and no new
concept; this is wiring a finished module to a surface that is already built.

* Add a `budget_bytes` parameter to `diagnose()` at `readiness.py:156`. **Keep
  it pure** — its docstring says it *"takes what was found rather than going
  and looking"*, and a test asserts no module opens its own connection.
* Build the `PULL_MODEL` offer from the returned `Recommendation` — its `name`,
  `size_bytes`, `why`, and surface `generated` so the manifest's date is
  visible, which `CLAUDE.md` asks for.
* The caller at `main.py:1008` supplies the budget from
  `ProviderManager.resident_budget_bytes` (`providers/manager.py:220`).
* Fall back to the existing constant when `recommend_for` returns nothing.
  **Never fail closed** — the module's own docstring says so.

*Done looks like:* `GET /readiness` names a real model and a real size, and
names a **different** one when the budget is forced small. `tests/test_readiness.py`
exists and will need updating.

**2. The 17 backend failures.** They are pre-existing and nobody has read them.
`CLAUDE.md`: a failing test is fixed or deleted, never left — and classify by
the contract each asserts, never by the file it lives in. Two are about
**egress and consent**; read those first and change nothing near them casually.

**3. Only if 1 and 2 are done: A2, the pull executor.** A streaming route
through `OllamaAdapter`, never a socket of its own. Then flip
`canBeCarriedOut()` at `FirstRunPanel.tsx:69` to admit `pull_model`. **Two
decisions are the maintainer's, not yours** — Ollama's HTTP API or the CLI, and
whether a model pull is recorded in the egress log. Ask; do not choose.

### How to verify, without launching Electron

The dev credential is a file, not magic. Start both halves with the same value
and the browser authenticates:

```
cd backend && ZARAM_API_SECRET=dev venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8420
cd frontend && ZARAM_API_SECRET=dev npx vite --port 5173 --strictPort
```

A mismatch presents as every Settings row reading "unavailable", which looks
like a backend fault and is not one. The backend takes ~40s to boot.

### The gate

Nothing counts as done because it runs. It is done when something **calls** it
and these pass:

```
backend/venv/Scripts/python.exe -m pytest backend/tests/test_readiness.py -q
npm run check:reachability
cd frontend && npx tsc --noEmit && npx vitest run
```

The whole backend suite is 14m20s and is not the inner loop — run the one file,
then the suite once before committing.

### Traps this repository has already paid for

* **Check your instrument before believing it.** Three probes gave wrong
  answers in the last session alone — a regex that reported five present keys
  as missing, an `ls | head` that hid a file, a grep that missed a name on
  case. Read the file before concluding from a grep.
* **Fifteen complete, tested, unreachable subsystems** have been found here.
  That is the base rate, not pessimism. A named caller is part of done.
* **Two proxy lists** — `frontend/vite.config.js` and `electron/config.js` —
  for any new route prefix. `check:proxy` catches a miss.
* **Vite serves stale transforms.** If a runtime error contradicts the source
  on disk, compare the served module and restart Vite with `--force`.
* **Do not point Aider at `main.py`.** It is 5,143 lines, ~54,600 tokens,
  6.6× the local model's window. `docs/AIDER.md` has the full table, and Aider
  itself is installed but **not yet proven to generate anything** — its first
  dry run blocked on an interactive prompt.

### Two things recorded but deliberately not done

Neither is your task unless the maintainer says so; they are here so they are
not rediscovered.

* `ServerStore.save()` freezes derived `writes` modes into `mcp-servers.json`,
  after which the stored value wins over `KNOWN_HOSTS`. Fix belongs in
  `config.py`.
* **9,495 lines reached by nothing**, itemised in the Current state block.
  `backend/runtime/` (singular) is a dead web-search subsystem whose only
  importers are its own tests, sitting one letter from the live
  `backend/runtimes/`.

---

## Prompt for the 5 September evening session — superseded

*A1, A2 and the seventeen failures all landed. The observation it opens on —
watching a real model arrive — is still not done and is carried forward.*

**This was the current prompt.** Everything above it is an earlier brief, kept
for its reasoning and superseded on status. The authoritative state is
**Current state — 5 September** in `docs/MILESTONES.md`.

Paste from here down.

---

Read `docs/MILESTONES.md` — the **Current state — 5 September 2026** block —
before anything else. Then `CLAUDE.md` for the rules.

`main` is the trunk and the working tree is clean. **Nothing has been pushed;**
`git rev-list --count origin/main..main` is the count.
Do not push without being asked.

The backend suite is **green**: 3,402 passed, 24 skipped, 0 failed, 0 errors,
13m33s with Ollama up — it executes different code with Ollama down, and takes
longer. It was 7 failed and 10 errors this morning. If you see a
failure, it is yours.

### Your task, in order

**1. Watch a model actually arrive. Start here; it is an hour and it is the
only thing A2 is missing.**

First run now names a model matched to the machine and downloads it when the
offer is pressed. Every part of that is asserted by tests, including the route
against the real application object — and **nobody has seen a real model
land**, because proving it means fetching gigabytes on the maintainer's
connection.

Do it on a machine with Ollama running and **no chat model** (an Ollama with
only `bge-m3` is exactly the state `/readiness` calls `engine_without_model`).
Open the conversation, and you should see the first-run screen where the
composer is. Then:

* the offer names a real size, and a line under it dated `2026-08-30`;
* pressing it opens a row and starts *nothing*;
* pressing *Start the download* streams stages and a percentage;
* when it ends the screen replaces itself with a composer, with nothing to
  dismiss;
* `GET /egress` holds **one** new entry for `registry.ollama.ai`, written
  before the bytes moved.

If any of it is wrong, the code is `backend/providers/pull.py`,
`backend/providers/api.py`'s `/providers/pull`,
`frontend/src/components/firstrun/ModelPull.tsx` and `services/pullClient.ts`.

**2. The two questions the code is holding open**, both recorded in the source
rather than decided:

* **A 24 GB machine is offered a 20 GB first download.** The manifest matches
  the machine; `CLAUDE.md` says a user asked to pull 7 GB before their first
  answer closes the app. Above ~9 GB of budget those two instructions disagree.
  `core/readiness.py`'s module docstring states the case and imposes no ceiling
  deliberately — inventing one there would be a second recommendation policy
  beside the manifest. **Ask the maintainer**; do not choose.
* **The pull cannot be cancelled.** Closing the row leaves it running, there is
  no resume, and disk-full arrives as a message with a *Try again* that starts
  over. Whether that is enough for v1 is a product call.

**3. Then packaging.** It is still the actual blocker: a stranger cannot
install this, and first-run polish does not substitute for it.

### How to verify, without launching Electron

The dev credential is a file, not magic. Start both halves with the same value
and the browser authenticates:

```
cd backend && ZARAM_API_SECRET=dev venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8420
cd frontend && ZARAM_API_SECRET=dev npx vite --port 5173 --strictPort
```

A mismatch presents as every Settings row reading "unavailable", which looks
like a backend fault and is not one. The backend takes ~40s to boot.

`GET /readiness` needs `X-Zaram-Auth: dev`. On a machine that already has a
chat model it answers `ready` with no offers, which is correct and is why task
1 needs a machine without one.

### The gate

```
backend/venv/Scripts/python.exe -m pytest backend/tests/test_readiness.py backend/tests/test_the_pull_button_fetches_the_offered_model.py -q
npm run check:reachability && npm run check:guards
cd frontend && npx tsc --noEmit && npx vitest run
```

The whole backend suite is ~20 minutes and is not the inner loop — run the two
files, then the suite once before committing.

### Traps this repository has already paid for

* **A hook body that returns something callable is a cleanup hook.**
  `beforeEach(() => mocked.mockReset())` had Vitest calling the mock itself,
  with no arguments, after every test — and the failure surfaced inside the
  stub as `onEvent is not a function`, which is the last place the cause was.
  Braces on hook bodies.
* **Classify a failure by the contract it asserts, never by its file.** Five
  files, four unrelated causes — and the ten errors in the keep-button file were
  caused by nothing in the keep path: the kernel cannot boot twice, and that
  file is the only one that starts the real application more than once.
* **Check the instrument before believing it.** A stack trace beat four rounds
  of reasoning about the Vitest failure above, and the repo has three earlier
  examples in `MILESTONES.md`.
* **Fifteen complete, tested, unreachable subsystems** have been found here. A
  named caller is part of done — `check:reachability` reports two of the five
  shapes and says so.
* **Two proxy lists** — `frontend/vite.config.js` and `electron/config.js` —
  for any new route prefix. `check:proxy` catches a miss. `/providers/pull`
  needed neither, because `/providers` was already there.
* **Do not point Aider at `main.py`.** 5,143 lines, ~54,600 tokens, 6.6× the
  local model's window. `docs/AIDER.md` has the table, and Aider is installed
  but still **not proven to generate anything**.

### Two things recorded but deliberately not done

* `ServerStore.save()` freezes derived `writes` modes into `mcp-servers.json`,
  after which the stored value wins over `KNOWN_HOSTS`. Fix belongs in
  `config.py`.
* **9,495 lines reached by nothing**, itemised in the Current state block.
  `backend/runtime/` (singular) is a dead web-search subsystem whose only
  importers are its own tests, sitting one letter from the live
  `backend/runtimes/`.

---

## Prompt for the next session — written 6 September 2026 *(superseded)*

**Superseded the same day** by the prompt at the end of this file. Its task —
a bounded tool loop, and continuation without a restart — was built; its
reasoning about *why* those two, and what must stay true in them, is still the
reasoning and is why it is kept.

Paste from here down.

---

Read `docs/MILESTONES.md` — the **Current state — 6 September 2026** block —
then `docs/CODE-PACK.md`, then `CLAUDE.md` for the rules. The code pack is the
live work and `CODE-PACK.md` holds every decision already taken about it, so
reading it first saves you re-arguing them.

`main` is the trunk, the working tree is clean, and nothing is pushed since
5 September. `git rev-list --count origin/main..main` is the count. The backend
suite is **3,489 passed, 29 skipped, 0 failed** in ~23 minutes with Ollama up.
A failure is yours.

### The task: make it an agent, and make it survive its own context

The retrieval and the tools are done. **The loop is not**, and the maintainer
asked for two things on 6 September.

**1. A bounded tool loop.**

`_run_tool_round` in `core/execution_engine.py` is called from one place, once,
and the follow-up generation gets the tool result with no tools attached. The
comment beside it says so and explains the reasoning — read it before changing
it. The consequence: the model can `search_code` **or** `read_lines`, never
*search then read what it found*, which is the minimum useful sequence for a
coding agent.

**Bound it by tokens, not rounds.** That is a recommendation, not a decision —
if you disagree, say why and put it to the maintainer. The argument for it: an
8K local model and a 64K Tabby model should degrade differently rather than
behave differently, and a round counter gives them the same allowance. Let the
model keep calling until accumulated tool output reaches a fraction of the
window, then force an answer.

Three things must stay true, and one of them is a rule:

* **The gate re-runs per call.** `McpRuntime.execute` calls `policy.decide`
  itself. More rounds must not become one permission decision reused — that is
  the "a shortlisted tool has earned nothing" line, and merging selection with
  permission has cost this codebase three times.
* **Tool results compete with recall for the window.** Three rounds of 400-line
  reads will evict the memory that makes Zaram Zaram, and that trade is the
  product's whole thesis. It must be a decision in the code with a comment, not
  a consequence.
* **Say when the loop stopped early.** A reply that quietly stops calling tools
  is the silent-degradation failure `CLAUDE.md` names — the same rule that makes
  a refused tool announce itself.

**2. Continue the task when the context fills, without a restart.**

The maintainer's words: *"I would also like the model to remember and continue
the task if the context finishes without needing a restart."*

**Do not solve this by persisting the transcript.** That is L0, and the patterns
section rejects it outright: their pipeline keeps raw dialogue for verification,
ours keeps provenance instead. Rule 7d says session state and long-term memory
are separate stores, and conflating them is what produces duplicate citations
and Zaram quoting its own replies.

The Zaram-shaped answer already has a name in `CLAUDE.md`: **Project holds the
plan** — *"the steps, decisions taken and decisions rejected"*. Continuation is
reloading that object, not replaying a conversation. **The plan object does not
exist yet**, and it is the missing piece for this *and* for diffs-as-cards, so
building it well pays twice.

Design questions worth putting to the maintainer before building:

* What is a step, and when is one finished? A finished step is what survives.
* Does a plan step become a `project:<id>` fact, or its own store? Rule 7i's
  reasoning — one field on one store, because facts move and recall needs both
  at once — argues for the former, but a plan has ordering and state that a
  fact does not.
* What does the user see and edit? `CODE-PACK.md` says a plan the user can read
  before it runs; that is the reviewable-not-autonomous position the whole pack
  rests on.

### Before either, one hour that decides how good this feels

**Nobody has watched the model drive any of it.** Not once, on any model. Do
this first, because if a 14B cannot sequence two tool calls then the loop's
design constraints change completely.

Open a coding project with a `root` (API only for now — see the gap below), ask
something that needs *search then read*, and watch what the model actually
emits. `docs/AIDER.md` records the local ceiling; the maintainer's Tabby model
has 64K on its next load and the Ollama `qwen3-14b-16k` is verified resident at
16K.

### The gap that blocks a user from any of it

Nothing in the interface creates a coding project with a `root`. The tools work
when one is open, and today that is reachable through the API only. Slice 4 in
`CODE-PACK.md`: when a folder added to Knowledge looks like a repository, offer
to make it a coding project — offered at the moment of doubt, never a choice in
advance.

### Still the maintainer's calls, not yours

* A 24 GB machine is offered a **20 GB first download**. `readiness.py` states
  the case and deliberately imposes no ceiling.
* The model pull has **no cancel and no resume**.
* Whether the loop's token bound is a fraction of the window or a fixed number.

### How to verify, without launching Electron

```
cd backend && ZARAM_API_SECRET=dev venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8420
cd frontend && ZARAM_API_SECRET=dev npx vite --port 5173 --strictPort
```

A mismatch presents as every Settings row reading "unavailable", which looks
like a backend fault and is not one. The backend takes ~40s to boot.

**You cannot screenshot the UI here.** The built-in browser pane refuses local
URLs and Playwright's Chrome is not installed — report API payloads as evidence
and say the visual half is unverified rather than promising a picture.

### The gate

```
backend/venv/Scripts/python.exe -m pytest backend/tests/test_the_code_tools_are_reachable.py backend/tests/test_the_code_pack_is_wired.py backend/tests/test_an_empty_answer_is_not_an_empty_card.py -q
npm run check:reachability && npm run check:guards
cd frontend && npx tsc --noEmit && npx vitest run
```

The whole backend suite is ~23 minutes and is not the inner loop.

### Traps this repository has already paid for

* **`all()` of an empty collection is true.** That is the residency bug fixed on
  6 September, and it is the shape to look for wherever an absence is read as a
  measurement.
* **Registering is not reaching.** A test asserting two lines of boot and
  calling that reachability passed for a fortnight while nothing could call
  `mcp.call`. `test_the_code_pack_is_wired.py` runs a real `kernel.boot()` for
  exactly this reason; extend it rather than writing a fixture that repeats it.
* **Classify a failure by the contract it asserts, never by its file.**
* **Check the instrument.** On 6 September `nvidia-smi`'s process list named
  Unreal and Maya as holding the card; Windows' own GPU counters showed the bulk
  was an orphaned `llama-server.exe`. Two conclusions were published before the
  right instrument was used.
* **Anything that stops Ollama must stop `llama-server` too.**
  `Get-Process ollama*` does not match the child, and the orphan holds gigabytes
  that `ollama ps` cannot see.
* **Two proxy lists** — `frontend/vite.config.js` and `electron/config.js` — for
  any new route prefix. `check:proxy` catches a miss.
* **Do not point Aider at `main.py`.** **5,221 lines** as of 6 September —
  `docs/AIDER.md` says 5,143 and ~54,600 tokens, which was true on 5 September
  and is the shape of the problem rather than the current figure. Aider is
  installed and still **not proven to generate anything**.

### Recorded, deliberately not done

* `ServerStore.save()` freezes derived `writes` modes into `mcp-servers.json`,
  after which the stored value beats `KNOWN_HOSTS`. Fix belongs in `config.py`.
* **9,495 lines reached by nothing.** `backend/runtime/` (singular) is a dead
  web-search subsystem whose only importers are its own tests, one letter from
  the live `backend/runtimes/`.
* **Packaging is still the actual blocker.** A stranger cannot install Zaram,
  and a coding agent inside an uninstallable product reaches nobody.

---

## Prompt for the next session — written 6 September 2026, later the same day

**This is the current prompt.** The one above it is the morning's brief for the
same day: still right about the code pack's shape, superseded on status, and
wrong in one specific way — the tool loop it asks for is built. The
authoritative state is **Current state — 6 September** in `docs/MILESTONES.md`.

Paste from here down.

---

Read `docs/MILESTONES.md` — the **Current state — 6 September 2026** block —
then `docs/CODE-PACK.md` (slice 3b is the newest work), then `CLAUDE.md` for the
rules.

`main` is the trunk and nothing is pushed since 5 September;
`git rev-list --count origin/main..main` is the count.

### What landed, so you do not rebuild it

`_run_tool_loop` in `core/execution_engine.py` replaced `_run_tool_round`. The
model can now search then read; a refusal stops the loop and a *failed call*
does not.

**At half the window the task hands itself over, silently.** The trigger is the
measured size of the request being sent — `ContextBudget.handoff_tokens`, half
the model's loaded context — not a round count; the steps travel into the fresh
window trimmed to `carry_tokens`, three times, and nothing is announced.
Announcing was built first and removed: *"I don't want Zaram to keep prompting
users… do the handoff behind the scenes."* A task that runs out of windows does
still say so, with an offer to pick it up.

**A stopped task is written down and survives a restart.**
`projects/plans.py`, listed in Project with Continue and Discard. It stores what
the tools returned and **no system prompt** — a resumed task re-recalls from its
question, which is rule 4 and is the thing to be careful of if you touch it.
Seven-day retention, pruned on open and on write; a finished task is deleted.

`backend/tests/test_the_tool_loop_is_bounded.py` (20) and
`backend/tests/test_an_unfinished_task_survives_a_restart.py` (22) are the
contract, all offline.

**A model has now driven it**, on `qwen3-14b-16k`, and that measurement lives in
`backend/tests/test_the_model_can_drive_the_tools.py -m measure`. It takes ~10
minutes and it is the reason two silent defects are fixed. Run it when you
change the prompt text, the tool descriptions, or the loop.

**A user can now point it at a repository, and see what it did** — 7 September,
`CODE-PACK.md` slices 3d and 3e. `root` is on the project create and update
routes with a folder field in Project, and `tool_call` events finally render
(`ToolCalls.tsx`). Both were the same defect in different clothes: working
backend machinery that nothing on the front reached, one through a missing
request field and one through a `default:` case.

**Which models actually fit is measured**, not estimated —
`test_what_actually_fits_this_card.py -m measure` reports the GPU/RAM split from
`/api/ps` and tok/s from `eval_duration`, and refuses to run at all when
something else is holding the card. The Gemma is a 128-expert MoE with 8 firing
per token: 51% resident, **17.8 tok/s**, against the fully-resident 14B's 30.5.

### The task: three things, in this order

**1. Watch a long task run, in the real app.** Nothing in this list matters if
it does not work on screen, and that has not been observed once. **Everything
needed to do it now exists**: make a coding project, point it at a folder in the
new field, ask something that needs several windows of reading, watch the tool
lines appear, watch it hand over without saying anything, let it run out, then
pick it up from Project. The loop, the store, the field and the button are each
asserted by test; the visual half is unverified — this session could not
screenshot it.

Two numbers need a person watching and cannot be settled by a test: **three
handoffs**, and **half the window** as the place to compact. Both are
judgements written down as `MAX_AUTO_CONTINUATIONS` and `HANDOFF_SHARE`, and
both are one-line changes once somebody has seen a real task run.

**2. Close the routing gap, which is slice 4 with a sharper edge.** *"Search the
code for X"* plans `filesystem.search`, not `mcp.list_tools` — the planner
checks the filesystem intent first — so the code tools are reachable only by a
user who phrases it as *"use the code tools to…"*. A person coming from Claude
Code will phrase it the first way every time. Two candidate fixes and they are
not the same: teach the classifier that a coding project changes what those
words mean, or make `filesystem.search` route to the code tools when a coding
project is open. The second is smaller and probably right; argue it before
building it.

**3. Then the rest of the plan object.** The store holds steps and makes a task
resumable. What `CLAUDE.md` also asks of it — *decisions taken and decisions
rejected*, and a plan the user reads **before** it runs — is not built, and it
is what slice 5 (diffs as cards) needs. The object exists to hang it on now;
the questions are what counts as a decision, and whether a rejected one is worth
keeping after the task finishes, given a finished task is otherwise deleted.

### Recorded, deliberately not done

* **Tool replies no longer stream.** Every generation in a tool-using reply is
  buffered, because a model told not to call a tool emitted `[TOOL_CALL]`
  anyway. The way back is a holdback filter in `tool_loop.py` that withholds any
  trailing text which could be a marker prefix — worth building when tool
  replies are common enough for the lost typewriter effect to be felt, and not
  before, because it is a new convention and needs its own tests.
* **`HANDOFF_SHARE` (0.5) and `CARRY_SHARE` (0.25) are judgements**, labelled as
  such. Nobody has measured whether they are right on a real repository, and the
  gap between them is what stops a task handing over on every call.
* **Does a generated image ever leave VRAM?** On 7 September a Zaram backend
  from the previous evening was holding **9.09 GB** of a 12 GB card while
  Ollama reported nothing resident. 9 GB is the size of a loaded image
  pipeline, so the likely reading is that `SdxlProvider` loads and never
  unloads — meaning one picture costs every local chat model until a restart.
  Unconfirmed, and the most serious open thing in this file if it is true.
* **Model switching is still ~106 s when it happens, and that is the disk.**
  The residency term stops Zaram *choosing* a swap it did not need; it cannot
  make a swap fast. Loading is disk-bound at ~196 MB/s and `C:` is already the
  fastest drive on the machine — `G:` writes at 155 MB/s and `F:` is a spinning
  disk, both measured. The remaining software lever is preloading: intent is
  classified in 10–30 ms and recall takes hundreds, so a load could start
  during recall rather than at dispatch. Worth a few hundred milliseconds
  against 106 seconds, so probably not worth building.
* **One frontend test is flaky.** A single failure in one full `vitest run` on
  7 September, passing on the two runs after it; the output scrolled before it
  could be named. Capture the run to a file when it recurs.
* **A resumed task does not restore the code project's folder by itself.** The
  root comes from the open project through a ContextVar set by the API from the
  *request's* project, so Project's Continue sends the project with it. A
  resume from somewhere that does not would find the tools refusing every call.
* Everything in the previous prompt's "Recorded, deliberately not done" still
  stands: `ServerStore.save()` freezing derived write modes, the 9,495 lines in
  `backend/runtime/` reached by nothing, and packaging as the actual blocker.

### The gate

```
backend/venv/Scripts/python.exe -m pytest backend/tests/test_the_tool_loop_is_bounded.py backend/tests/test_the_code_tools_are_reachable.py backend/tests/test_the_code_pack_is_wired.py backend/tests/test_mcp_reaches_chat.py -q
npm run check:reachability && npm run check:guards
cd frontend && npx tsc --noEmit && npx vitest run
```

### Traps, and one new one

* **A test's own prompt has to route where the test thinks it does.** Half a
  day's confusion in this session came from fixture prompts that classified as
  `filesystem.search`, so the engine never reached the tool path and every
  assertion failed with an empty call list that looked like a broken loop.
  Check the plan before blaming the code.
* **`all()` of an empty collection is true** — the 6 September residency bug.
* **Registering is not reaching.** `test_the_tool_loop_is_bounded.py` ends with
  a class asserting the Continue *flag* reaches `continue_task`, for exactly
  this reason.
* **Two proxy lists** — `frontend/vite.config.js` and `electron/config.js`.
* **Do not point Aider at `main.py`.** 5,221 lines as of 6 September.

---

## Prompt for the next session — written 7 September 2026

**This is the current prompt.** The two above it are earlier briefs for 6
September, kept for their reasoning and superseded on status. The authoritative
state is **Current state — 6–7 September** in `docs/MILESTONES.md`.

This one is narrow on purpose: it is about the **local model stack**, not the
code pack. The code pack's own brief is the prompt above.

Paste from here down.

---

Read `docs/MILESTONES.md` — the **Current state — 6–7 September 2026** block,
and in particular *"The model stack, as it stands on 7 September"*. Then
`CLAUDE.md` for the rules.

`main` is the trunk, the working tree is clean, and nothing is pushed since
5 September. The backend suite is **3,543 passed, 23 skipped, 0 failed** in
~10 minutes with Ollama up. A failure is yours.

### The task: finish setting up the local model stack

Four models are installed and **not one of the four decisions about them has
been made on evidence**. Everything needed to decide exists; nobody has run it.

**Before anything: check who has the card.** This is not boilerplate — it has
gone wrong twice in two days, differently each time.

* On 6 September a Zaram backend left running from the previous evening held
  **9.09 GB**, `/api/ps` reported nothing, and `nvidia-smi --query-compute-apps`
  listed WhatsApp and Steam with `[N/A]` while showing nothing of it.
* On 7 September the maintainer was running **Unreal**, which held 6.7 GB of the
  12 GB card, leaving 5,376 MiB free — not enough to measure anything honestly.

The instrument that works is Windows' own counters, not nvidia-smi:

```powershell
(Get-Counter '\GPU Process Memory(*)\Dedicated Usage').CounterSamples |
  Where-Object {$_.CookedValue -gt 100MB} | Sort-Object CookedValue -Descending
```

`test_what_actually_fits_this_card.py` refuses to run below 2 GB free, so it
will skip rather than print a number measured against thrashing. Do not
override that; close whatever is holding the card instead.

**1. Give Coder a context window.** `qwen3-coder:30b` has no `num_ctx`, so
Ollama will serve it at **4,096** regardless of what the weights declare —
`core/context_budget.py` exists because of exactly this, with a measured example
of a Gemma reporting 262,144 and loading with 4,096. A 4K coding model is
useless: `ChatSurface.tsx` alone is ~15,000 tokens.

```bash
printf 'FROM qwen3-coder:30b\nPARAMETER num_ctx 32768\n' | ollama create qwen3-coder-30b-32k -f -
```

32K matches Gemma so the comparison is like for like. Try 40–65K afterwards if
it fits — more context is more KV cache and less room for weights, which is the
trade the measurement will show you.

**2. Measure Coder.** Add `"qwen3-coder-30b-32k"` to the `parametrize` list in
`test_what_actually_fits_this_card.py` — one line — and run:

```bash
cd backend && venv/Scripts/python.exe -m pytest tests/test_what_actually_fits_this_card.py -m measure -s
```

The prediction on the record, so it is checkable: **~50% resident, 18–22 tok/s**
— Coder is 3B active against Gemma's 4B, so it should edge Gemma's 17.8. If it
lands far off that, the reasoning behind the whole MoE argument is wrong and
worth re-examining rather than explaining away.

**3. Measure Tabby, which has never been measured at all.** It is up on
**port 1234** with `Qwen3.8-27B-exl3-2.20bpw` and `inline_model_loading: true`,
so a chat request naming the model loads it on the spot. Its own config records
that it claims **~10.7 GiB of the 12.00 GiB card** when loaded — model 9.61 GiB
plus cache — so unlike the Ollama models it fits *entirely*, and at 2.20 bpw it
moves less memory per token than the 14B's Q4 does. **It may well be the fastest
model on the machine**, which would overturn the advice given all through
6–7 September that the 14B is the fast one.

The test speaks Ollama only. Teaching it a second endpoint is perhaps thirty
lines: `POST /v1/chat/completions` on 1234, and the OpenAI response carries
`usage.completion_tokens` — time the call yourself, since there is no
`eval_duration` equivalent. Residency comes from `/api/ps`-equivalent absence;
`providers/manager.py` already treats TabbyAPI as *"resident, size unknown"*, so
follow that shape rather than inventing a second one.

**4. Then decide the stack, from the table rather than from argument.** The
question the maintainer actually asked is whether two models can replace four.
The candidate answer was **Tabby for chat + Coder for coding**, and it turns on
step 3: if Tabby is fast, the 14B and Gemma are both redundant and ~27 GB can
go. If Tabby is slow, the 14B stays as the fast default and Gemma stays for
vision.

Whatever is decided, **write the four numbers into `MILESTONES` beside the
existing two.** A model table with two measured rows and two guesses is how the
guesses become facts.

### What is already settled, so it is not re-litigated

* **`ollama list` double-counts.** Derived `num_ctx` variants share the parent's
  blob. Deleting one frees kilobytes; it is a decision about the picker, never
  about disk. Verified by digest: the two Qwens were `a8cc1361f314`, the two
  Gemmas `7121486771cb`.
* **Do not move the model store.** Measured with `dd`, 2 GB, `conv=fsync`:
  `C:` writes at 364 MB/s and reads at 196; `G:` writes at **155**; `F:` is a
  Hitachi 7200rpm spinning disk. `C:` is the fastest drive on the machine
  despite being 93% full. Windows reports `G:` as `MediaType 4` (SSD) and it is
  half the speed — the same table reports the Hitachi's spindle speed as
  `4294967295`, uint32 saturation, the identical shape to the
  `Win32_VideoController.AdapterRAM` trap `CLAUDE.md` warns about. **Trust the
  measurement, not the label.**
* **Switching cannot be made fast, only rarer.** Loading is disk-bound at ~196
  MB/s, so a cold 26B costs 106 seconds and no configuration changes that. The
  software half shipped on 7 September: routing now prefers the model that is
  **already loaded** over one that merely fits.
* **`qwen3-14b-16k` is capped at 16K by its Modelfile and the weights declare
  40,960.** If it survives step 4, that is 2.5× the context for one
  `ollama create` and no download.

### Two things that are open and are not this task

* **Does a generated image ever leave VRAM?** The 9.09 GB held by a Zaram
  backend on 6 September is the size of a loaded image pipeline. If
  `SdxlProvider` loads and never unloads, one picture costs every local chat
  model until a restart. Unconfirmed and the most serious open item anywhere in
  this file.
* **Nobody has watched the code pack run in the real app.** See the previous
  prompt; everything needed now exists, including a folder field and visible
  tool calls.

### The gate

```
backend/venv/Scripts/python.exe -m pytest backend/providers/tests/ backend/tests/test_routing_preference_is_not_inert.py -q
npm run check:reachability && npm run check:guards
cd frontend && npx tsc --noEmit && npx vitest run
```

The whole backend suite is ~10–35 minutes depending on what else the machine is
doing, and is not the inner loop.


---

## Prompt for the next session — written 7 September 2026, evening

**This is the current prompt.** Everything above it is an earlier brief: accurate
about what was built and why, superseded on status.

Paste from here down.

---

Read `docs/MILESTONES.md` — the **Current state** block — then `CLAUDE.md` for
the rules. `main` is the trunk, the working tree is clean, and nothing has been
pushed since 5 September.

### The task: move the model stack onto TabbyAPI

The maintainer's decision, taken on the evidence below: **pull the exl3
equivalents of the Ollama models and replace them.** Not because Ollama is bad,
but because on a 12 GB card exl3 is the only format that fits a 27B *entirely*
with a 64K window, and every GGUF model in the set spends half its weights in
system RAM.

### What was measured, so none of it is re-derived

Every row: clear card, exactly 300 generated tokens, thinking off, one prompt no
model finishes early. Those conditions are not decoration — each was added
because leaving it out produced a number that was wrong in a way that looked
right. `backend/tests/test_what_actually_fits_this_card.py -m measure -s` is the
instrument and it now speaks to both servers.

| | on card | context | cold load | tok/s |
|---|---|---|---|---|
| TabbyAPI `Qwen3.8-27B-exl3-2.20bpw` | **8.48 GiB, fits entirely** | **65,536** | 90 s | **26.3** |
| `qwen3-14b-16k` | 10.41 GB, 100% | 16,384 | 122 s | 32.0 |
| `gemma4-26b-32k` | 9.17 of 18.14 GB, 51% | 32,768 | 164 s | 20.0 |
| `qwen3-coder-30b-32k` | 10.61 of 20.56 GB, 52% | 32,768 | 178 s | 19.4 |

Tabby's first token arrives in **0.7 s**. It reproduces: 25.9 and 26.3 tok/s
across two clean runs, claiming 8.41 and 8.48 GiB.

**The budget for the whole card.** 12,288 MiB total; a Windows desktop holds
~1.3 GB for the compositor and a browser, so **~10,750 MiB is the most this
machine ever offers**. A threshold above that is a test that never runs — which
is what happened when the Tabby guard was first set at 11,000.

**Disk: 73 GB free on C:** (93% full), against 44 GB of Ollama blobs. Do not
move the store — measured with `dd`, C: writes at 364 MB/s and reads at 196,
G: writes at 155, F: is a spinning disk. C: is the fastest drive on the machine
despite being nearly full.

### The machine's Tabby setup, as it stands

* `C:\Users\user\tabbyAPI\config.yml`, port **1234**, `disable_auth: true`
* `model_dir: C:\Users\user\models` — holds **exactly one** model today
* `inline_model_loading: true`, so a request naming a model loads it on the spot
* `cache_mode: 4,4`, `cache_size: 65536`, `max_seq_len: 65536`
* `gpu_split_auto: true`, `autosplit_reserve: [96]`
* `/v1/models` lists what is in `model_dir`; `/v1/model` describes what is loaded

**Tabby's Qwen already has vision, disabled in config.** Its own load log says
so: *"The provided model has vision capabilities, vision is disabled in config."*
That is the replacement path for Gemma — a config flag to test, not a download —
and if it works, 17.99 GB of Ollama blobs go.

### How to size a replacement

At **2.20 bpw** the 27B costs 8.48 GiB *including* its 64K 4-bit cache, against
~10,750 MiB available. So there is roughly **2 GiB of headroom**, which buys
either a higher bpw on the same model or a larger one at low bpw. Spend it
deliberately and measure after: this file's whole history is numbers that looked
right and were not.

Do **not** take exl3 repository names from this document — none are given on
purpose, because inventing one that does not exist wastes a session. Find
current quants and check the bpw against the budget above.

### The order, and the part that matters most

1. **Pull one replacement and measure it before deleting anything.** Add its
   name to the `parametrize` list in `test_what_actually_fits_this_card.py` and
   run the measure marker. A model that is slower or does not fit is a model
   the Ollama original should outlive.
2. **Test Gemma's replacement by enabling vision on the Qwen**, not by
   downloading. It is a config change.
3. **Only then delete**, and know that `ollama list` double-counts: derived
   `num_ctx` variants share the parent's blob, so removing a manifest frees
   kilobytes. Deleting is a decision about the picker, never about disk.
4. **Re-run the measure suite and rewrite the MILESTONES table.** A table with
   measured rows beside guesses is how guesses become facts.

### Traps, every one of which has bitten in the last two days

* **Something else is holding the card, and `nvidia-smi` will not say what.**
  Windows' own counters will:
  `(Get-Counter '\GPU Process Memory(*)\Dedicated Usage').CounterSamples | Where-Object {$_.CookedValue -gt 100MB}`.
  Unreal held 6.24 GB; the Zaram app itself holds it while running.
* **Ollama acknowledges an unload long before the memory comes back.**
  `/api/ps` answered `{"models":[]}` while `llama-server` still held 10.15 GB,
  and the row measured next read a quarter of its real speed. `SETTLE_TIMEOUT`
  now waits for two consecutive clear readings; do not shorten it.
* **The `measure` marker is registered and never deselected**, so a plain
  `pytest` on those files runs the live GPU work — but only when the card
  happens to be free, and skips in a second when it is not. A task chip exists
  for this.
* **Run the Electron suite with no Zaram running.** The single-instance lock
  makes a running app look exactly like a regression.
* **Only one model is resident at a time**, on either server. A Tabby switch is
  ~90 s cold, which is why the 6 September routing change — prefer the model
  already loaded over one that merely fits — matters more after this migration,
  not less.
* **Use the Grep tool, never a recursive shell grep.** The repository is
  duplicated under `.kilo/`, `.trae/` and `.continue/`; a shell grep times out.
* Python is `backend/venv/Scripts/python.exe`. The bare `python` on this machine
  is broken (a missing 3.14 install path).

### What this session left unfinished, in priority order

1. **Per-task model assignment does not exist**, and the maintainer asked for
   it: local and cloud models allocated to chat, coding, vision, image reading.
   `RoutingSettings` carries one `defaultModel`; `INTENT_SPECIALISATION` maps an
   intent to a *kind* of model (`code`), not to a user's choice. This is a
   backend store, an API and a Settings surface — and the maintainer's stated
   intent is that **it becomes what Auto uses as its strategy**.
2. **The chat project picker cannot create a project**, and it reads
   `/artifacts/projects` — ids derived from artifacts — while a real project
   store with `create(name, type, note, root)` sits in `projectStore.ts` unused
   by it. Creation must ask for a **type**, which `CLAUDE.md` says is the one
   thing that cannot be asked later; `coding` also needs a root, which is the
   code tools' sandbox boundary.
3. **Nothing built on 7 September has been seen working on screen** — the
   spell-check underline, the token counter, the activity panel, the coding
   embodiment state. Every layer beneath them is measured and tested. The avatar
   lesson applies exactly: gaze tracking shipped with green tests and a
   confirmed rig while nothing moved, because the fringe covered the eyes.
4. **The coding animation clip does not exist.** The state, the manifest slot
   and the fallback are wired; the asset is a licence decision. Mixamo's terms
   restrict redistributing animation files, which is what bundling one in a repo
   and an installer does.
5. **Does a generated image ever leave VRAM?** Still unconfirmed, still the most
   serious open item anywhere in this file.

### The gate

```
backend/venv/Scripts/python.exe -m pytest backend/ -q -m "not measure"
npm run check:reachability && npm run check:guards
npm run test:electron            # with no Zaram running
cd frontend && npx tsc --noEmit && npx vitest run
```

---

## Prompt for the next session — written 7 September 2026, late evening

**This is the current prompt.** Everything above it is an earlier brief:
accurate about what was built and why, superseded on status.

Read `docs/MILESTONES.md` — the **Current state** block — then `CLAUDE.md`.
`main` is the trunk, the working tree is clean, and nothing has been pushed
since 5 September.

### Start here: three things are built and unwatched

This session was driven request by request and shipped seven commits. Every
one is tested and typechecked; three of them have never been *used*, and this
file's whole history is green suites over things that did not happen.

1. **The latched microphone has never been spoken into.** Hold the microphone
   button (or Alt-click it, or press Shift+Space anywhere) and it should stay
   open across turns, show a ring that moves with what it hears, and stop
   Zaram talking the moment you start. The ring and the level are wired to real
   audio; barge-in is wired to `speechStore`. **`ONSET_RMS_WHILE_SPEAKING` in
   `frontend/src/lib/voiceActivity.ts` is not a measured number** and says so
   in the file. It is the one constant to turn after listening in a real room
   with real speakers: too low and Zaram interrupts itself, too high and
   barge-in never fires. Nothing else in that file needs touching to tune it.
2. **Work has never been seen with files in it.** The layout was rebuilt —
   toolbar, grouped headings, aligned columns, checkboxes, a selection strip —
   and the browser pane cannot authenticate to the backend, so every listing
   there is empty by construction. Open the real app and look at it with a
   dozen artifacts in it. The three things to check are whether the group
   headings earn their vertical space, whether the columns still read at the
   narrow width Work gets beside the conversation, and whether the glass
   checkbox is findable without being loud.
3. **Removal has been exercised only in tests.** Select a few files, remove
   them, and confirm three things by looking: they leave the listing, they are
   sitting in `<output>/.trash/` with a timestamp prefix, and **Undo puts them
   back**. Then delete one from the trash by hand and check the undo says so
   rather than failing silently.

### Then: the Tabby migration, which is one restart from its first real answer

`C:\Users\user\tabbyAPI\config.yml` has `vision: true` and
`vision_offload: true` set, with `use_as_default` extended to carry them —
without that they would have applied only to a startup load, which this config
never does, and every real request would have had vision off. Backup at
`config.yml.bak-20260907`.

**Nothing has been restarted, so nothing is proven.** In order:

1. Restart TabbyAPI. Confirm `GET /v1/model` reports `use_vision: true` once a
   model is loaded — that is the check, not the log line.
2. Measure the card with vision on. It was **9,075 MB** for the process and
   **11,758 of 12,288 MiB** for the card with vision off; if offload is doing
   its job the first number should barely move. If it does move, `cache_size`
   is the lever and 65536 → 32768 frees far more than the tower costs.
3. Send it a real image and check the answer is about the image.
4. **Only then** delete `gemma4-26b-32k` (17.99 GB), which was being kept for
   exactly this job. The maintainer's standing instruction: a model pulled to
   Tabby **replaces** its Ollama equivalent rather than joining it. On a disk
   at 93% that is what stops the migration stalling.
5. Then the exl3 replacements for the remaining Ollama models, one at a time,
   measured before anything is deleted — the 7 September morning prompt above
   has the budget arithmetic and the traps, and they still hold.

### Still unfinished, from the earlier list

* **The chat project picker cannot create a project.** It reads
  `/artifacts/projects` — ids derived from artifacts — while a real store with
  `create(name, type, note, root)` sits in `projectStore.ts` unused by it.
  Creation must ask for a **type**, which `CLAUDE.md` calls the one thing that
  cannot be asked later.
* **The coding animation clip does not exist.** State, manifest slot and
  fallback are wired; the asset is a licence decision.
* **Does a generated image ever leave VRAM?** Still unconfirmed, still the most
  serious open item anywhere in this file.

### One diagnosis worth keeping

The history lip was reported as "stopped working" and had not stopped working —
it had stopped being **visible**, while remaining mounted and hit-testable. A
`CSSTransition` on its opacity stalls at `currentTime: 0` after the first
open-and-close and never advances, leaving a 22px transparent strip at the
screen edge. Why it stalls is **still not established**. The fix does not
depend on knowing: whether a control can be seen is never the output of an
animation. If a control is ever reported as dead, measure
`getComputedStyle` against the inline style before reading any code —
they disagreed here, and that took ten minutes where reading took an hour.

### The gate

```
backend/venv/Scripts/python.exe -m pytest backend/ -q -m "not measure"
npm run check:reachability && npm run check:guards
npm run test:electron            # with no Zaram running
cd frontend && npx tsc --noEmit && npx vitest run
```

---

## Prompt for the next session — written 8 September 2026

**Superseded on status by the 8 September, later prompt at the end of this
file.** Tasks 1 and 2 below are built; the reasoning in them still holds and
the licence question in task 1 is still open.

Read `docs/MILESTONES.md` — the **Current state** block — then `CLAUDE.md`.
`main` is the trunk. The working tree is clean except for one untracked file,
`avatar-source/animations/Typing.fbx`, which is the subject of task 1 and which
**must not be committed until the licence question below is answered**.

**Unreal is running on this machine.** Do not start the Zaram desktop app — it
takes VRAM the maintainer is using. The Vite dev server plus the browser pane is
how the interface was verified all session and is enough for everything here;
note that the pane cannot authenticate to the backend, so every listing renders
empty and only the chrome can be watched.

---

### Task 1 — the typing animation, standing rather than sitting

`avatar-source/animations/Typing.fbx` is a **sitting** typing animation. The
maintainer wants the character standing and typing, and proposed the right
solution: **retarget the upper body only and leave the waist down alone.**

Four things were established by reading the files, so none of it needs
re-deriving:

| | |
|---|---|
| **It is a Mixamo clip.** | First model node is `mixamorig9:Hips`. Every other clip in that folder is `Robot_Rig_0001:Robot_All_01:Hips` — exported from the character's own rig in Maya. |
| **`retarget_animations.py` will skip it today.** | `on_character_rig()` looks for the literal `Robot_All_01` in the first model name and answers `False`. It is also absent from the `CLIPS` list. |
| **But the bones would bind.** | `sanitize()` already compares only the trailing segment, and the character rig uses Mixamo naming: `Hips, Spine, Spine1, Spine2, Neck, Head, LeftShoulder…`. **All 65 character joints are present in `Typing.fbx`.** The 7 extras (`ch31body`, `ch31hair`, `ch31sweater`, …) are mesh nodes, not joints, and match nothing. |
| **The waist split is clean.** | 11 lower-body joints — `Hips`, and `Left/Right` `UpLeg`, `Leg`, `Foot`, `ToeBase`, `Toe_End` — leaving **54 upper-body joints** to retarget. |

So the work is small and the shape is decided:

1. Add a per-clip **bone allow-list** to `retarget_animations.py`, so a clip can
   name the joints it may drive. `Typing.fbx` drives the 54 upper-body joints
   and leaves the 11 lower ones at the character's rest pose.
   **`Hips` is the one that matters most** and it belongs in the excluded set:
   it is the root, and a sitting clip carries the sit in it — lowered and
   rotated back. Excluding it is what makes the character stand.
2. `on_character_rig()` is a **proxy** for "will the bones match", and for this
   file the proxy says no while the real answer is 65 of 65. Widen it to check
   bone agreement rather than a namespace string, or allow the clip explicitly
   — but keep a check. Its own comment records why: *"an Advanced Skeleton clip
   imports perfectly happily and matches zero bones, and a clean run over zero
   bones reads exactly like success."*
3. Verify with `node frontend/scripts/check-rig-agreement.mjs`, which reads the
   written files rather than Blender's idea of them.
4. Add the clip to `frontend/public/avatars/animations/animations.json`, which
   has **no `coding` entry today** — the slot is genuinely empty.

**Watch it before believing it.** The gaze-tracking lesson is the exact
precedent: unit tests plus a confirmed rig is not evidence that anything moved
on screen, and the one check nobody made was the one that mattered. A standing
character whose legs are at rest while its arms type is either right or
obviously wrong, and a screenshot settles it in a second.

#### The licence question, which is a stop rather than a caveat

`CLAUDE.md`'s embodiment section and the 7 September handoff both already record
this, and the file's provenance now confirms it: **Mixamo's terms restrict
redistributing animation files, which is exactly what bundling one into this
repository and the installer does.** Every other clip in that folder was
authored on the character's own rig and carries no such restriction.

This is the maintainer's call, not the next session's. Three routes, and the
first is the one the script's own comments point at:

* **Re-export the motion from `Robot_All_01` in Maya**, as the Listening pair
  already was. Then it is the maintainer's own asset and the question goes away.
* **Keep it out of the repository** — generated locally, gitignored, absent
  from the installer, with the coding state falling back to `thinking` as it
  does now.
* **Confirm the licence permits it** before it is committed.

Do not commit `Typing.fbx` or a `.glb` derived from it until one of those is
settled.

---

### Task 2 — the typing state on the orb

The maintainer asked for a typing state that fires *"as Zaram reads through
portions of the LLM's reply that are code"* and *"when code data is being
generated"*.

**That already exists and already fires on both.** `codingActivity` in
`frontend/src/lib/orbActivity.ts` derives `coding` from an opened code fence in
the accumulated reply, or from the code tools having run — its own comment says
so: *"the reply is writing code. An opened fence in the text so far is the
literal thing the maintainer asked to see embodied."* Say so rather than
building it a second time; this repository has shipped fifteen complete,
tested, unreachable subsystems, and building over a working one is how the
sixteenth arrives.

**What is genuinely open is the look**, and it is a one-line decision the
maintainer has now made differently twice:

* 7 September: *"No new colour: thinking's violet, a different rhythm."*
  `LivingOrb`'s `coding` entry is that — violet rings, violet glow.
* 8 September: *"the orb stays pulsating with the default glow and behaviour."*

Those disagree. The second is the more recent instruction, so unless the
maintainer says otherwise, `coding` should render exactly as `idle` does —
default glow, default pulse — while the *avatar* carries the typing clip. That
is coherent with the embodiment rule: the character is where an activity is
embodied, and the orb's job is to stay calm.

If that is taken, `STATE_CONFIG.coding` in `LivingOrb.tsx` becomes a copy of
`idle`'s glow and filter, keeping its own entry rather than being deleted, so
the state still exists and can be given a look later. `OrbitalParticles`'
`FIELD.coding` should follow the same decision — it currently borrows
thinking's gesture at a shorter period.

---

### What landed on 8 September, and what was not watched

Two commits, both on `main`.

**`fix(memory)` — the one that matters.** The maintainer reported that Zaram
does not keep context across a chat. The machinery was complete and three
ceilings on top of it were all sized for a 4,096-token model: the history cap
was computed from `FALLBACK_CONTEXT_TOKENS` (768 tokens for every model on
every machine), the buffer was then sliced to three exchanges, and retention
was eight. A model loaded with 65,536 tokens was shown three turns inside a
budget belonging to a different model. It now uses `budget_for`'s **measured**
window, the turn slice is gone — `fit` drops oldest-first and whole turns — and
retention is 40.

**`feat(landing)` and the aura.** The caption slot clears the orbit ring by
arithmetic rather than by a percentage; the voice hint follows the orb sideways
via `orbGeometry`; and `OrbAura` gives the avatar the same two state-coloured
rings and ten motes the orb draws, inside the element that carries the shift
and zoom so it travels into the conversation.

**Not watched on screen, and it is the first thing to check:**

* **The aura behind the avatar in the conversation.** The landing was verified
  — 10 motes, 2 rings, no doubling on the orb path — but the *conversation*
  view with the character selected was not, and that is precisely what the
  maintainer reported missing. Confirm the rings appear and that no mote paints
  across the visor.
* **The memory fix has not been used in a real conversation.** It is measured
  by tests against a pinned window. Open a long chat on the Tabby model and
  check the engine's own log line, which now names the figure and whether it
  was measured: `gave the reply N prior turn(s), M dropped for a K-token share
  of a measured 65536-token window`.
* **The particle states.** `thinking`, `listening`, `speaking`, `coding` and
  `swapping` each move differently now. Only `idle` was seen.

### Still unfinished, from the earlier list

* **TabbyAPI still has not been restarted**, so `vision: true` and
  `vision_offload: true` in `C:\Users\user\tabbyAPI\config.yml` are set and
  unproven. Confirm `use_vision` on `/v1/model`, measure the card, send it a
  real image, and only then delete `gemma4-26b-32k`. Backup at
  `config.yml.bak-20260907`.
* **The chat project picker cannot create a project.**
* **Does a generated image ever leave VRAM?** Still unconfirmed, still the most
  serious open item anywhere in this file.

### The gate

```
backend/venv/Scripts/python.exe -m pytest backend/ -q -m "not measure"
npm run check:reachability && npm run check:guards
npm run test:electron            # with no Zaram running
cd frontend && npx tsc --noEmit && npx vitest run
```


---

## Prompt for the next session — written 8 September 2026, later *(superseded)*

**Superseded by the 10 September prompt at the end of this file.** Kept for
its reasoning; not current on status.

Read `docs/MILESTONES.md` — the **Current state** block — then `CLAUDE.md`.
`main` is the trunk and the working tree is clean apart from two untracked
files, `avatar-source/animations/Typing.fbx` and
`frontend/public/avatars/animations/coding_a.glb`, which are the subject of the
decision below and **must not be committed until it is made**.

**Unreal is running on this machine.** Do not start the Zaram desktop app. The
Vite dev server plus the browser pane is how the avatar was watched, and
`?orb=<state>` now pins the orb's starting state in development so any of the
six can be looked at without a backend.

---

### The typing clip is done — 10 September 2026

**Closed, not carried.** The maintainer re-exported the motion from
`Robot_All_01` in Maya (`Typing_01.fbx`, standing, joints only), so Mixamo's
redistribution terms no longer apply and `coding_a.glb` ships. `coding` has a
body clip; only `swapping` is still without one, deliberately.

The per-clip waist-exclusion table that made the sitting Mixamo source stand was
deleted with it. It was a retarget-time workaround for a problem fixed at the
source, and the rebuilt clip is byte-identical without it. If a third-party clip
ever needs that facility, take it out of the history rather than rebuilding it
from the description.

**Nothing here is open.** The rest of this list is.

---

### What is still open, in the order it was left

* **Keep one Ollama chat model installed**, whatever happens to the rest. The
  10 September bug was an *Ollama* bug — eviction — and TabbyAPI structurally
  cannot have it. First run recommends five Ollama tags and names no other
  engine, so moving off Ollama entirely means nobody is exercising the path
  every new user lands on.
* **TabbyAPI has still not been restarted, and it now blocks three things
  rather than one.** `vision: true` and `vision_offload: true` are set in
  `C:\Users\user\tabbyAPI\config.yml` (backup `config.yml.bak-20260907`) and
  unproven. On the restart, in one pass:
  1. confirm `use_vision` is true on `/v1/model`, send it a real image, and
     only then delete `gemma4-26b-32k` (17.99 GB);
  2. confirm the **window probe** reads `parameters.max_seq_len` off the same
     route — it is tested against the contract and has never run against a live
     server;
  3. confirm `auto` actually routes to Tabby now that ranking prefers the
     larger window. Every reply names the model that answered, so this is a
     one-question check.

* **Nothing has compared the models on quality, and the quantization gap makes
  that a real gap rather than a tidy one.** Measured 10 September: every Ollama
  chat model is **Q4_K_M** (~4.5 bits per weight) — `qwen3-14b-16k` is 14.8B at
  9.28 GB — while the TabbyAPI model is `exl3-**2.20bpw**`, which is how a 27B
  fits in 8.48 GiB. The table that made Tabby the default measures speed,
  context and residency, and none of those is quality. A 27B squeezed to
  2.2bpw against a 14.8B at Q4_K_M is not an obvious win in either direction,
  and it is the one comparison the maintainer can make and a benchmark cannot.
* ~~The memory fix has never run in a real conversation.~~ **Done, and it was
  incomplete.** See the 10 September entry in `docs/MILESTONES.md`: the budget
  was measured only from `/api/ps`, which goes silent when Ollama evicts an idle
  model, so the conversation's share collapsed back to the same 768 tokens the
  8 September commit was written to delete. Fixed by reading the model's
  configured `num_ctx` from `/api/show`, and verified in a real chat with the
  model force-evicted between turns.

  **What is left is a judgement, not a bug.** `CONVERSATION_SHARE = 0.25` gives
  the 14B ~9,200 characters of history — three or four code exchanges — and
  nobody has tested that against real use. Turn it only with a transcript to
  point at.
* **The chat project picker cannot create a project.**
* **Does a generated image ever leave VRAM?** Still unconfirmed, still the most
  serious open item anywhere in this file.
* **First run dead-ends a stranger with no engine, and the place is known.**
  `readiness.py` builds an `INSTALL_ENGINE` offer — *"Set up a local model"*,
  with `ENGINE_BYTES + model size` quoted as one number — but
  `canBeCarriedOut` in `FirstRunPanel.tsx` permits only `explore`,
  `use_cloud_key` and `pull_model`, so the card renders disabled under *"Zaram
  can't set this up for you yet."* The word **Ollama appears nowhere in the
  first-run UI** and there is no link. It is scrupulously honest and it names no
  next step, which is `CLAUDE.md`'s "a stranger cannot install this" with a
  file and a line number. The cheap fix is wording on the disabled card; the
  real one is letting the button run the installer, which is mutative and
  egressive and wants consent plus an egress entry. Read, not changed.
* **`CONVERSATION_SHARE = 0.25` is a judgement nobody has tested.** It gives
  the 14B ~9,200 characters of history — three or four code exchanges — and
  Tabby ~36,900. Zaram now *says* when it drops turns, so the next report will
  arrive with a number attached rather than as "it feels forgetful". Turn the
  constant only with a transcript to point at.
* **Should code Zaram writes reach the Spine?** Open, and the maintainer's call.
  `_remember` stores the user's statements as facts and never the exchange,
  which is right and is why Zaram stopped quoting its own replies. But
  `transcript.py` justifies dropping turns rather than summarising them on the
  grounds that *"Zaram has a second store"* — and that store holds what the user
  said, not what Zaram produced. So an evicted code exchange is gone: not
  summarised, not recalled, not recoverable. Rule 7b already indexes generated
  *artifacts* with origin tagging; a code block in a reply is the same object
  without a file.
* **Four particle states have still not been *watched* moving**, only reasoned
  about. `?orb=thinking`, `?orb=listening`, `?orb=speaking` and `?orb=swapping`
  on the dev server put each one on screen. Note the instrument warning in
  `docs/MILESTONES.md`: sampling `currentTime` from JS in the browser pane
  measures nothing, because the document timeline only advances on paint.
  Screenshots separated by a wait are the honest instrument.

### Publishing

**Everything that reaches GitHub goes out in the maintainer's name, from the
maintainer's account** — `Anisiuba Uche`, `Uchayanisiuba/Zaram`. Commits,
branches, pushes, PRs, releases, issues. Commits carry no `Co-Authored-By:`
trailer — revised 10 September 2026 — and a session is never a second author.

A session that cannot authenticate as the maintainer **stops and hands over**.
It does not hunt for another route, read a stored credential, or ask for a token
to be pasted to it. Push the branch if git's own helper allows it, say what is
left, and leave the publishing step to the person whose name is on it.
`CLAUDE.md` carries the full rule under *"Publishing: one name, one account"*.

### The gate

```
backend/venv/Scripts/python.exe -m pytest backend/ -q -m "not measure"
npm run check:reachability && npm run check:guards
npm run test:electron            # with no Zaram running
cd frontend && npx tsc --noEmit && npx vitest run
```

---

## Prompt for the next session — written 10 September 2026

**This is the current prompt.** Everything above it is an earlier brief:
accurate about what was built and why, superseded on status.

Read `docs/MILESTONES.md` — the **Current state** block, whose top three
entries are all 10 September — then `CLAUDE.md`. `main` is the trunk and the
working tree is clean.

**Unreal was closed for the memory verification and may be running again.** Do
not start the Zaram desktop app without checking. The Vite dev server plus the
browser pane is how the avatar is watched, and `?orb=<state>` pins the orb's
starting state in development so any of the six can be looked at without a
backend.

---

### What closed on 10 September

Four memory items, and two of them were on this list as open questions.

* **The context ceiling, twice.** An evicted Ollama model reports no window on
  `/api/ps`, so the budget silently fell back to 4,096 and the conversation got
  768 tokens of it. Fixed by reading the configured `num_ctx` from `/api/show`,
  and verified in a real chat with the model force-evicted between turns.
* **~~`CONVERSATION_SHARE = 0.25` is a judgement nobody has tested.~~** It is no
  longer the number that decides. The conversation takes the request's
  *remainder* — the system prompt and question measured, a 96-token margin held
  back — with the quarter kept only as a floor so a long document cannot starve
  it. 11,788 tokens on the 14B rather than 3,072. There is nothing left to
  "turn" here; if the symptom returns it is a different bug.
* **~~Should code Zaram writes reach the Spine?~~ Yes, and it is built.**
  Fenced blocks only, 200–6,000 characters, two per turn, request prepended,
  `Origin.GENERATED` on every one so `MemoryRanker`'s penalty applies and a user
  source still wins. It runs before the fact gate, because *"write me a
  function"* is an instruction and the gate refuses instructions.
* **The conflict detector has a caller** — the sixteenth complete, tested,
  unreachable subsystem found here. It notices and never resolves: both facts
  are stored, one question is raised in the reply, and the user settles it in
  Memory.

Zaram also now **says when it drops turns**, once per conversation, with "Open
Memory" as the next step.

---

### What is still open, in the order it was left

* **TabbyAPI has still not been restarted, and it blocks three things.**
  `vision: true` and `vision_offload: true` are set in
  `C:\Users\user\tabbyAPI\config.yml` (backup `config.yml.bak-20260907`) and
  unproven. On the restart, in one pass:
  1. confirm `use_vision` is true on `/v1/model`, send it a real image, and
     only then delete `gemma4-26b-32k` (17.99 GB);
  2. confirm the **window probe** reads `parameters.max_seq_len` off the same
     route — tested against the contract, never against a live server;
  3. confirm `auto` actually routes to Tabby now that ranking prefers the
     larger window. Every reply names the model that answered, so this is a
     one-question check.
* **Keep one Ollama chat model installed**, whatever happens to the rest. The
  eviction bug was an *Ollama* bug and TabbyAPI structurally cannot have it.
  First run recommends five Ollama tags and names no other engine, so moving off
  Ollama entirely means nobody is exercising the path every new user lands on.
* **Nothing has compared the models on quality, and the quantization gap makes
  that a real gap.** Every Ollama chat model is **Q4_K_M** (~4.5 bits per
  weight); the TabbyAPI model is `exl3-**2.20bpw**`, which is how a 27B fits in
  8.48 GiB. The table that made Tabby win measures speed, context and residency
  — none of those is quality — and this is the one comparison the maintainer can
  make and a benchmark cannot.
* **`find_conflicts` is called on the remember path only.** Recall does not ask
  it, so a contradiction already sitting in the Spine is raised the next time
  the subject comes up rather than on sight. Deliberate — it is the cheaper half
  and the half the reported symptom needed — but it is the obvious next reach if
  contradictions turn out to be common.
* **Lexical retrieval is still naive term overlap.** `CLAUDE.md` names BM25
  beside the vectors as the one retrieval change with a documented failure
  waiting for it: rare tokens — a client name, a reference number — are exactly
  what a dense embedding is worst at. Fuse by rank (RRF), never by score, and
  for **ordering** only.
* **The chat project picker cannot create a project.**
* **Does a generated image ever leave VRAM?** Still unconfirmed, still the most
  serious open item anywhere in this file.
* **First run dead-ends a stranger with no engine, and the place is known.**
  `readiness.py` builds an `INSTALL_ENGINE` offer — *"Set up a local model"*,
  with `ENGINE_BYTES + model size` quoted as one number — but `canBeCarriedOut`
  in `FirstRunPanel.tsx` permits only `explore`, `use_cloud_key` and
  `pull_model`, so the card renders disabled under *"Zaram can't set this up for
  you yet."* The word **Ollama appears nowhere in the first-run UI** and there
  is no link. It is scrupulously honest and it names no next step, which is
  `CLAUDE.md`'s "a stranger cannot install this" with a file and a line number.
  The cheap fix is wording on the disabled card; the real one is letting the
  button run the installer, which is mutative and egressive and wants consent
  plus an egress entry. Read, not changed.
* **Four particle states have still not been *watched* moving**, only reasoned
  about. `?orb=thinking`, `?orb=listening`, `?orb=speaking` and `?orb=swapping`
  on the dev server put each one on screen. Note the instrument warning in
  `docs/MILESTONES.md`: sampling `currentTime` from JS in the browser pane
  measures nothing, because the document timeline only advances on paint.
  Screenshots separated by a wait are the honest instrument.
* **The draft PR was never opened.** `gh` is installed and unauthenticated, and
  the publishing rule below is why this session stopped rather than finding
  another route.

### Publishing

**Everything that reaches GitHub goes out in the maintainer's name, from the
maintainer's account** — `Anisiuba Uche`, `Uchayanisiuba/Zaram`. Commits,
branches, pushes, PRs, releases, issues. Commits carry no `Co-Authored-By:`
trailer — revised 10 September 2026 — and a session is never a second author.

A session that cannot authenticate as the maintainer **stops and hands over**.
It does not hunt for another route, read a stored credential, or ask for a token
to be pasted to it. Push the branch if git's own helper allows it, say what is
left, and leave the publishing step to the person whose name is on it.
`CLAUDE.md` carries the full rule under *"Publishing: one name, one account"*.

### The gate

```
backend/venv/Scripts/python.exe -m pytest backend/ -q -m "not measure"
npm run check:reachability && npm run check:guards
npm run test:electron            # with no Zaram running
cd frontend && npx tsc --noEmit && npx vitest run
```
