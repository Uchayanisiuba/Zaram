# Next session — where the avatar work stands

Rewritten 3 September 2026. `docs/AVATAR-EMBODIMENT.md` is the detail for this
subsystem; this file is the handoff. `docs/MILESTONES.md` remains the handoff for
the product as a whole.

**The two-skeleton problem is solved.** All nine clips were re-exported from
`Robot_All_01` by the maintainer and every one binds. The sections that used to
explain retargeting are gone because there is no retargeting left to explain.

---

## Start here

```bash
cd frontend && npx vite --port 5173 --strictPort
```

**If the landing shows the orb rather than the robot**, the renderer is
remembered in `localStorage` and a fresh browser profile loses it:

```js
localStorage.setItem('zaram.embodiment.renderer', 'avatar')
```

A healthy load log:

```
face panels: eyes=found mouth=found
clips loaded (9): idle_a, idle_b, idle_c, listening_a, listening_b,
                  speaking_a, speaking_b, speaking_c, thinking_a
clips failed: none
65/65 tracks kept (rotation, fingers included)
face aspect: both square
tangents computed for 3 mesh(es) — the GLB ships none
bones with no track (0): none
rest-pose check: 2/65 tracks retargeted onto the glTF rest pose
states with clips: idle, listening, speaking, thinking
model bounds: min [-0.914, 0.893, -0.262] max [0.914, 2.004, 0.229]
```

**`rest-pose check: 2/65` is correct and not a warning.** An earlier version of
this file said anything above `0/65` meant a T-pose. That was over-strict and it
would now send a session chasing nothing. The real tolerance is
`RIG_MATCH_TOLERANCE`, 0.05 rad = **2.86°**; the shipped clips sit at 0.25°.
`node frontend/scripts/check-rig-agreement.mjs` is the authority — it prints
`0 over tolerance` when the rig and the clips agree.

Debug switches: `?noAnim=1`, `?headFraction=0.85`, `?smileEvery=`, `?smileHold=`,
`?faceDebug=1`, `?envIntensity=`, `?rough=`, `?normal=`, `?glow=`, `?rim=`,
`?sky=`, `?lightScale=`, `?avatarBg=%23404858`.

---

## What is done

**All nine clips bind, and four states have a body.** `idle` ×3, `listening` ×2,
`speaking` ×3, `thinking` ×1. Watched playing, not merely asserted.

**`swapping` borrows a random idle clip and holds a smile.** A model swap is a
moment rather than a posture, so there is no clip to shoot; the body keeps doing
what it was doing and the state reports through the glow and the face.
`statesWithoutClips` still records `['swapping']`, deliberately — the borrow is
visible rather than accidental.

**The character GLB is the high-resolution export** (`Zaram_Robo Hi.glb`, 37,310
triangles against the previous 11,891, legs removed, skinning revised). Rest pose
agrees with the previous export to 0.048°, so every clip carried over untouched.

**The face atlas is 4×4** and the files are named `*_atlas_4x4*`. Seven mouth
cells — `sil aa ih ou ee oh` plus `smile` — and eight eye cells, the six states
plus `happy` and `happy_blink`.

**The idle face alternates rather than flashing a rare smile**: neutral 23–41s,
smile 6–10s, both drawn fresh each occurrence so there is no period to find, with
a six-second floor because anything quicker reads as the panel switching. Eyes
lead, mouth follows one second behind, in both directions. The smile is ~20% of
idle — widened from ~36% on request, taking "rarer" as *less often* rather than
*shorter*, so the hold is unchanged and the gap absorbed all of it.

**`thinking` wears the neutral mouth**, by decision — the state reads through the
narrowed eyes and the glow. A dedicated `think` cell was drawn and cut rather
than left dormant.

**The shell is 20% glossier** — `roughnessBoost` 2.1 → 1.68.

---

## What is not

1. **Lip sync has still never been watched** against a real Kokoro track. The
   mouth renders, `visemeAt` is wired, the fallback walks real visemes. Nobody
   has seen it move in time with audio. **This is the top item.**
2. **GPU cost is unmeasured**, and the triangle count just tripled. `CLAUDE.md`
   calls this the measurement that decides whether 3D may sit on the landing at
   all. Measured this session and worth knowing before optimising the wrong
   thing: body textures are **49 MB** (three 2048², 16 MB each), the two face
   atlases **8 MB**. Shrinking the atlas to 3×3 saves 3.5 MB; halving the body
   textures saves 36 MB, and at ~320px on screen 2048² is almost certainly more
   texel density than is used.
3. **The rim light still reports nothing** — metallic body, back-placed light.
   State reaches the viewer through the eye cells and the glow.
4. **`CLAUDE.md` and the code still differ about the rest face, but less.** The
   rule says the rest face is `sil` and the idle smile is a rare sanctioned
   exception. It is now ~20% of idle, down from ~36%, which is close enough to
   "rare" to be arguable rather than contradictory. Worth one sentence in
   `CLAUDE.md` naming the alternation, rather than leaving rule and code to
   drift.

---

## Traps, in the order they will bite

**Replacing the GLB reverts the mouth UV fix.** Still true, has now caught four
sessions. It is a buffer edit, not a code path:

```bash
cp "avatar-source/Zaram_Robo Hi.glb" frontend/public/avatars/zaram-robo.glb
py avatar-source/fix_face_uvs.py --apply
node frontend/scripts/check-rig-agreement.mjs
```

**Driving `orbStore` from the browser console does not reach the app.** A
dynamic `import('/src/stores/orbStore.ts')` returns a *different module instance*
from the one the running component holds once Vite's module graph has gone stale.
The store reports `speaking` while the component never leaves `idle`, and every
reading taken that way is fiction. **This cost most of an afternoon**: a mouth
that appeared stuck in the speaking shape and a thinking mouth showing the wrong
cell were both artefacts of it, and neither was ever a real bug. Restart Vite for
a clean module graph, and read `?faceDebug=1` — which reports the state, the
lagged mouth state, and the cell each panel is showing — rather than inferring
from a screenshot.

**The character GLB imports as two armatures**, and Blender's glTF importer
returns the vestigial one-bone `DeformationSystem` *first*.
`retarget_animations.py` used to take the first armature, which made that the
character and left the real 65-bone one to be found as the animation source —
reported as `carries no action`, which reads as a bad export rather than a wrong
armature. It now selects by bone count.

**A hash that looks random can have a short period.** The speech fallback stepped
by `(step * 2654435761) >>> 0`, which repeated every ~7 steps — at 7 steps a
second, a one-second loop. It was caught by two screenshots a second apart
landing on the same shape, and misread as a stuck mouth first.
`mixStep` is a proper avalanche mix; the period was measured after replacing it.

**Do not re-run `avatar-source/extend_face_atlases.py`.** It migrated 3×2 → 3×3
and is now historical. `redraw_face_atlases.py` owns the layout; its eye regrid
detects an already-4×4 atlas and skips rather than scattering every cell.

---

## The other strand: image generation

Researched this session, **designed, not built.** Re-deriving it is expensive.

**The architecture is unchanged from `CLAUDE.md`**: Zaram ships no image weights,
ever. The user installs a runner or brings a key, and Zaram routes, logs the
egress and shows what left.

**Model recommendations for a 12 GB card, all verified against current sources:**

| Model | Licence | Note |
|---|---|---|
| **Z-Image-Turbo** (6B) | Apache 2.0 | 8 steps, fastest local; **~1K resolution ceiling** |
| **Qwen-Image-2512** + Lightning LoRA | Apache 2.0 | best in-image text by a wide margin, native 2K; ~4 steps with Lightning |
| SDXL + finetunes | OpenRAIL++ | LoRA/ControlNet ecosystem; finetune licences vary per checkpoint |
| FLUX.1 dev, FLUX.2 klein-9B | **non-commercial** | disqualified as a default for client work |
| FLUX.2 klein-4B, FLUX.1 schnell | Apache 2.0 | the commercially clean FLUX variants |

Draft on Z-Image, finish on Qwen. **The output licence is headline metadata** for
the same reason `CLAUDE.md` makes a cloud model's data policy headline: five FLUX
variants carry five different answers depending on the size digit, and a
freelancer who picks wrong cannot deliver the work.

**There are no free image models on OpenRouter** — every one is paid, cheapest
Seedream 4.5 at $0.04/image. So the "add a free key" acquisition story that works
for text does **not** exist for images. Worth checking whether Google AI Studio's
own free tier covers Gemini Flash Image; that would be the one free cloud path.

**Three facts that shape the build:**

- **Ollama cannot generate images.** Local image generation is a *second local
  runtime* beside it, with its own install and VRAM claim — not a model download.
- **`backend/media/` is a complete, tested Media Runtime that nothing imports.**
  Registry, manager, sessions, health, `MediaType.IMAGE`, `MediaLocality`. It has
  no execute path by design. Decide wire-up versus delete before building a third
  image path beside it.
- **Modality is a ranking score, not a gate.** `requires_vision` filters models
  that can *read* an image; nothing filters for models that can *draw* one. That
  gate is the first real work, and the refusal path must exist before the offer —
  without it, "draw me a logo" reaches a text model that writes a confident
  paragraph about an image it never made.

---

## Prompt for the next session

> Continue the Zaram robot avatar work. Read `docs/NEXT-SESSION-PROMPTS.md` and
> `docs/AVATAR-EMBODIMENT.md` first — they hold the measurements, the rig story
> and the traps. Re-deriving any of it is expensive.
>
> State: the high-resolution character renders on the landing with all nine clips
> bound and four states carrying a body; `swapping` borrows an idle clip and
> holds a smile. The face is a 4×4 atlas — six visemes, an idle smile, and eight
> eye cells including a smiling blink. The idle face alternates neutral 10–18s
> with a smile 6–10s, eyes leading the mouth by a second. 440 tests pass,
> typecheck is clean. **Nothing is committed** — see the file list below.
>
> **Restart Vite before verifying anything in the browser.** Driving `orbStore`
> from the console reaches a different module instance once the module graph goes
> stale, and every reading taken that way is fiction. Use `?faceDebug=1` to read
> what the face is actually showing rather than inferring from a screenshot.
>
> In order:
> 1. **Watch it speak.** Start the backend (Electron spawns its own — do not
>    start one by hand as well, port 8420 will already be taken), get Kokoro
>    synthesising, and confirm `visemeAt` drives the mouth in time with the
>    audio. The mouth deliberately bypasses the one-second expression lag when
>    `speaking` starts; check the first viseme lands on the audio rather than a
>    second into it. This has never been observed and it is the top item.
> 2. **Measure the GPU cost**, which `CLAUDE.md` calls the measurement that
>    decides whether 3D belongs on the landing. The triangle count just tripled.
>    Body textures are 49 MB against the face atlases' 8 MB — measure before
>    optimising, and note 2048² body maps on a ~320px render are the obvious
>    lever.
> 3. **Consider the ONNX voice backend** — `ZARAM_VOICE_BACKEND=onnx` saves
>    ~590 MB and is waiting on someone listening to it. Pairs with (1).
> 4. **Reconcile the rest-face rule.** `CLAUDE.md` says the rest face is `sil`
>    and the idle smile is rare; the alternation makes it ~20% of idle. One
>    sentence in `CLAUDE.md` naming the alternation would close it.
>
> Uncommitted work is the avatar animation set (`retarget_animations.py`, the six
> new clip `.glb`s, `animations.json`, `animationSet.test.ts`), the face atlas
> rework (`redraw_face_atlases.py`, `redraw_thinking_eyes.py`, the renamed
> `*_atlas_4x4*` files, `manifest.json`, `faceAtlas.ts` and its test), the
> character GLB swap, and `RobotAvatar.tsx`. Stage paths explicitly — a previous
> session swept a dozen unrelated files into an avatar commit with
> `git add -A frontend/src`.
