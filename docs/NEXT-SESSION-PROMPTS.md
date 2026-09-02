# Next session — where the avatar work stands

Written 2 September 2026. `docs/AVATAR-EMBODIMENT.md` is the detail for this
subsystem; this file is the handoff. `docs/MILESTONES.md` remains the handoff for
the product as a whole.

---

## Start here

```bash
cd frontend && npx vite --port 5173
```

**If the landing shows the orb rather than the robot**, the renderer is
remembered in `localStorage` and a fresh browser profile loses it:

```js
localStorage.setItem('zaram.embodiment.renderer', 'avatar')
```

**Read the load log before touching anything.** It is the instrument, and this
session lost several rounds to not reading it. A healthy load says:

```
face panels: eyes=found mouth=found
clips loaded (9): idle_a, idle_b, idle_c, listening_a, listening_b,
                  speaking_a, speaking_b, speaking_c, thinking_a
64/64 tracks kept (rotation, fingers included)
face aspect: both square
tangents computed for 3 mesh(es) — the GLB ships none
bones with no track (1): Root_M
rest-pose check: 0/65 tracks retargeted onto the glTF rest pose
states with clips: idle, listening, speaking, thinking
```

`rest-pose check` above `0/65` means the rig and the clips have drifted, and the
character will be in a T-pose. `Root_M` having no track is correct — it is the
character's own root and no source clip drives it.

---

## What is done

- **All nine clips bind.** `idle` ×3, `listening` ×2, `speaking` ×3, `thinking` ×1.
- **Variants cycle without a pattern.** `ShuffleBag` exhausts a state's clips
  before repeating and refuses a repeat across the reshuffle seam;
  `VARIANT_FADE_SECONDS` (0.9s) crossfades, and the fade *starts before the clip
  ends* so the blend spans a part of the cycle where both clips are moving,
  rather than landing on the loop point where two poses rarely agree.
- **The idle smile has no period.** Hold 7–16s and gap 14–38s, both drawn fresh
  each occurrence.
- **The face is staggered** — eyes lead, mouth follows 1s later, except when
  speech starts.
- **Lighting** rebuilt from measured `forest.exr` values; `roughnessBoost`
  separates "too bright" from "too shiny".
- **One state table.** `STATE_PULSE` is read by both `LivingOrb` and
  `RobotAvatar` — colour, brightness and breathing rhythm.
- **Tangents** computed at load, because the GLB ships none.

## What is not

1. **Lip sync has never been watched.** The mouth renders and `visemeAt` is
   wired, but it needs the backend up and a real speech track. This is now the
   top item.
2. **`swapping` has no clip, deliberately.** It is the state where nothing is
   resident and no work is happening; holding still while the glow dims says that
   better than a clip would. Not a gap to fill without a reason.
3. **The clips are 21 MB.** `speaking_c` alone is 1314 frames (~4.1 MB). Nothing
   is wrong with them, but if the installer budget gets tight, trimming takes to
   their usable loop is the cheapest win available in this subsystem.
4. **GPU cost is unmeasured.** `CLAUDE.md` calls this "the measurement that
   decides" whether 3D may sit on the landing at all.
5. **The rim light reports nothing.** It is named in `CLAUDE.md` as the state
   channel and is invisible on this character — the body is metallic and a
   back-placed light returns almost nothing to the camera. State reaches the
   viewer through the eye cells and the glow instead. Three ways out are written
   up in `AVATAR-EMBODIMENT.md`; it is a rule-versus-code call for the maintainer.
6. **`CLAUDE.md` needs one amendment.** It says the rest face is `sil`, a flat
   line, *not* a smile. The idle smile contradicts that. Built on the
   maintainer's explicit request, idle-only, rare and brief — the same shape as
   the blink that rule already allows — but rule and code disagree.

---

## The rig story, so nobody re-derives it

The character exists in Maya as **two skeletons**, and which one an export was
selected from decides whether it is plug-and-play:

| | Namespace | Bones | Naming |
|---|---|---|---|
| Export skeleton | `Robot_All_01` | 65 | Mixamo (`LeftArm`, `LeftForeArm`) |
| Advanced Skeleton | `Robot_Rig_0001` | 90 | AS (`Shoulder_L`, `Elbow_L`) |

The three idles were exported from `Robot_All_01` and bind directly. The six
`Listening`/`Talk`/`Thinking` clips were exported from the Advanced Skeleton
`DeformationSystem` and bind to nothing by name — which is why they needed
retargeting rather than being dropped in.

**Exporting future clips from `Robot_All_01` makes them plug-and-play.** If a
clip does arrive on the AS rig, `retarget_advanced_skeleton.py` handles it.

**Do not "clean up" the character GLB to a single armature.** It carries a
vestigial `DeformationSystem` of one bone (`Root_M`) beside the real 65-bone
`Armature`. It is inert — nothing binds to it and the renderer never touches it.
Re-exporting to remove it would revert the mouth UV fix (again) and risk the rest
pose all nine clips are now baked against, for no gain.

### Two retargets, two different maths

They are not interchangeable and picking the wrong one fails silently:

- **`retarget_animations.py`** (the idles) copies the **pose** directly. Correct
  because the idles are the same skeleton as the character. Those files carry
  **no bind pose** — exported skeleton-only, so Blender falls back to frame 1 —
  which is exactly why a rest-relative approach fails on them and produced a
  T-pose for a whole session.
- **`retarget_advanced_skeleton.py`** (the six) transfers each bone's rotation
  **away from its own bind pose**. Correct because those files *do* have a real
  bind (rest and frame 1 differ by 179°), confirmed with
  `probe_advanced_skeleton.py` before writing a line of it.

---

## The trap that has now caught three sessions

**Replacing the GLB silently reverts the mouth UV fix.** It is a buffer edit, not
a code path, so a fresh export arrives without it and `oh` clips by 21px again:

```bash
cp "avatar-source/Zaram_Robo _.glb" frontend/public/avatars/zaram-robo.glb
py avatar-source/fix_face_uvs.py --apply
node frontend/scripts/check-rig-agreement.mjs
```

The rig check is not optional: the clips are baked against a specific rest pose,
and a re-export that moved it puts the character back in a T-pose.

---

## Things that cost this session time

- **`Number(null)` is `0`, not `NaN`.** Every URL knob guarded as
  `Number.isFinite(raw) && raw >= 0` silently returned zero when absent.
  `envIntensity`, `glow` and `normal` were all switched off by default, and each
  was diagnosed as a different bug — the dark character was blamed on the
  environment and **four environments were rebuilt** chasing it. **When a debug
  override makes a problem disappear, that is evidence about the override.**
- **Taking the first armature in a file that has two.** Reported `0/64 bones
  mapped`, which reads as a broken bone map rather than a wrong armature. Take
  the one with the most bones, and print what stayed unmapped.
- **A number in the log nobody read.** `65/195 tracks kept` named a bug for two
  whole rounds of "fixing" it.
- **Guessing at an environment.** Four failed. The fifth was measured off the
  reference in ten minutes and worked. When there is a reference file, measure it.
- **Confusing brightness with gloss.** On a near-mirror most of the brightness
  you see *is* the reflection, so dimming removes the surface with the glare.
- **Comparing two rigs by importing both into Blender.** Its glTF importer
  re-orients bones on the way in — 157–172° of pure noise. Read the GLB JSON
  chunk instead, as `check-rig-agreement.mjs` does.
- **`git add -A frontend/src`**, which swept a dozen unrelated files into an
  avatar commit. Stage paths explicitly.

---

## Prompt for the next session

> Continue the Zaram robot avatar work. Read `docs/AVATAR-EMBODIMENT.md` first —
> it holds the measurements, the four lighting approaches that failed, and the
> two-skeleton rig story. Re-deriving any of it is expensive.
>
> State: the character renders on the landing with **all nine clips bound**
> (idle ×3, listening ×2, speaking ×3, thinking ×1), variants shuffled and
> crossfaded, a dot-matrix LED face with a staggered idle smile, a state glow
> sharing one table with the orb, and lighting rebuilt from measured `forest.exr`
> values. 440 tests pass, typecheck clean, everything committed.
>
> Run the app with `preview_start` (`zaram-frontend`) and **verify by looking, not
> by asserting** — read the load log first, and if the landing shows the orb
> rather than the robot, set `localStorage['zaram.embodiment.renderer'] = 'avatar'`.
>
> In order:
> 1. **Watch it speak.** Lip sync has never been observed against a real speech
>    track — start the backend, get Kokoro synthesising, and confirm `visemeAt`
>    drives the mouth in time with the audio. The mouth deliberately bypasses the
>    1s expression lag when `speaking` starts; check that the first viseme lands
>    on the audio rather than a second into it.
> 2. **Consider the ONNX voice backend.** `backend/requirements-voice-onnx.txt`
>    swaps torch for onnxruntime — its header measures torch at 494 MB and
>    transformers at 96 MB. `voice/providers/kokoro_onnx.py` is reachable via
>    `ZARAM_VOICE_BACKEND=onnx`, same weights, same voices. `DEFAULT_BACKEND` is
>    still `"torch"` and the comment says why: it is waiting on someone listening
>    to it. Pairs naturally with (1).
> 3. **Measure the GPU cost**, which `CLAUDE.md` calls the measurement that
>    decides whether 3D may sit on the landing at all.
>
> If the GLB has been re-exported: copy it from `avatar-source`, **re-run
> `py avatar-source/fix_face_uvs.py --apply`** (the mouth fix does not survive a
> replacement and has been missed three times), then
> `node frontend/scripts/check-rig-agreement.mjs` before anything else.
>
> Debug switches: `?noAnim=1`, `?headFraction=0.9`, `?smileEvery=4`,
> `?envIntensity=1.8`, `?rough=2.1`, `?normal=1`, `?glow=0.85`, `?rim=1`,
> `?sky=0.5`, `?lightScale=0.25`, `?avatarBg=%23404858`.
