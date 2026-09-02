# Next session — where the avatar work stands

Written 2 September 2026, end of the session that fixed the T-pose, the face
atlas, the lighting and the seams. `docs/AVATAR-EMBODIMENT.md` is the detail;
this file is the handoff. `docs/MILESTONES.md` remains the handoff for the
product as a whole.

---

## Start here

```bash
cd frontend && npx vite --port 5173
```

Then open the landing with the avatar renderer selected. **If you get the orb
instead of the robot**, the renderer is remembered in `localStorage` and a fresh
browser profile loses it:

```js
localStorage.setItem('zaram.embodiment.renderer', 'avatar')
```

**Read the load log before touching anything.** It is the instrument, and this
session lost two rounds to not reading it. A healthy load says:

```
face panels: eyes=found mouth=found
clips loaded (3): idle_a, idle_b, idle_c
65/65 tracks kept (rotation, fingers included)
face aspect: both square
tangents computed for 3 mesh(es) — the GLB ships none
bones with no track (0): none
rest-pose check: 0/65 tracks retargeted onto the glTF rest pose
```

Anything other than `65/65` means the clip files carry more than the baked
action. `rest-pose check` above `0/65` means the rig and the clips have drifted.

---

## What is done

- **The T-pose.** The animation FBXs carried no bind pose (skeleton-only export),
  so every rest-relative retarget was measured from a pose the character never
  had. Clips are now baked onto the character's own armature by
  `avatar-source/retarget_animations.py`. Rest agreement: 78.08deg worst → 0.04deg.
- **The face atlas** grew 3x2 → 3x3 for `smile` and `happy`. Idle smile with
  matching arced eyes, 12.8s, idle only, every 14–32s.
- **The mouth UV island** — `oh` was clipping 21px. Fixed to texel aspect 0.991.
- **The lighting.** Five environments; the fifth is measured off Blender's
  `forest` studio light rather than invented. Plus `roughnessBoost`, which is
  what separates "too bright" from "too shiny".
- **UV seams** — the GLB ships no `TANGENT`, so they are computed at load.
- **The state glow** behind the character, on the rim's own eased colour.

## What is not

1. **Six clips still bind to nothing.** `Listening 1/2`, `Talk_1/2/3`, `Thinking`
   in `avatar-source/animations/` are on an Advanced Skeleton rig — namespace
   `Robot_Rig_0001:`, 92 joints, `Head_M` naming — against the character's
   `Robot_All_01:`, 65 joints, Mixamo naming. **Zero overlap**, confirmed by
   reading the files. They need retargeting onto `Robot_All_01` in Maya, baked to
   joints, and **exported with the skinned mesh in the file, not skeleton-only** —
   that is the whole lesson of the T-pose. `animationSet.test.ts` asserts the gap,
   so filling it is a deliberate edit.
2. **Lip sync has never been watched.** The mouth renders and cell selection
   works, but `visemeAt` needs a real speech track, which needs the backend up.
3. **GPU cost is unmeasured.** `CLAUDE.md` calls this "the measurement that
   decides" whether 3D may sit on the landing at all. Body textures are 2048²
   across four maps — roughly 90 MB of VRAM and 10.3 MB of the GLB's 11.3.
4. **`CLAUDE.md` needs one amendment.** It says the rest face is `sil`, a flat
   line, *not* a smile. The idle smile now contradicts that. It was built on the
   maintainer's explicit request and is idle-only, rare and brief — the same shape
   as the blink that rule already allows — but the rule and the code disagree and
   that is the maintainer's call to settle, not a future session's.

---

## The trap that has now caught two sessions

**Replacing the GLB silently reverts two fixes.** The mouth UV correction is a
buffer edit, not a code path, so a fresh export arrives without it:

```bash
cp "avatar-source/Zaram_Robo _.glb" frontend/public/avatars/zaram-robo.glb
py avatar-source/fix_face_uvs.py --apply
node frontend/scripts/check-rig-agreement.mjs
```

The rig check is not optional. The idle clips are baked against a specific rest
pose; a re-export that moved it puts the character straight back in a T-pose, and
the load log is the only place that would tell you.

---

## Things that cost this session time

- **`Number(null)` is `0`, not `NaN`.** Every URL knob guarded as
  `Number.isFinite(raw) && raw >= 0` silently returned zero when the parameter was
  absent. `envIntensity`, `glow` and `normal` were all switched off by default,
  and each was diagnosed as a different bug — the dark character was blamed on the
  environment and **four environments were rebuilt** chasing it. Passing the value
  in the URL "fixed" it every time, which is what kept the parameter looking
  innocent. **When a debug override makes a problem disappear, that is evidence
  about the override.** All readers now go through `numberParam`.
- **A number in the log nobody read.** `65/195 tracks kept` named the bug for two
  whole rounds of "fixing" it. 195 is 65 bones × 3 channels of a Maya take that
  should not have been in the file.
- **Guessing at an environment.** Four hand-built environments failed, each
  differently. The fifth was measured off the reference in ten minutes and worked.
  When there is a reference file, measure it.
- **Confusing brightness with gloss.** Turning the environment down to stop the
  shell blowing out took the character to a silhouette, because on a near-mirror
  most of the brightness you see *is* the reflection. Roughness is the other knob.
- **Comparing two rigs by importing both into Blender.** Its glTF importer
  re-orients bones on the way in, so the answer was 157–172deg of pure noise. Read
  the GLB JSON chunk instead — `check-rig-agreement.mjs` does.
- **Staging with `git add -A frontend/src`**, which swept a dozen unrelated
  chat/settings files into an avatar commit. Stage paths explicitly.

---

## Prompt for the next session

> Continue the Zaram robot avatar work. Read `docs/AVATAR-EMBODIMENT.md` first —
> it has the measurements and the four lighting approaches that failed, and
> re-deriving any of it is expensive.
>
> State: the character renders on the landing with three idle clips, a dot-matrix
> LED face, an idle smile with matching arced eyes, a state glow, and lighting
> rebuilt from measured `forest.exr` values. 440 tests pass, typecheck clean,
> everything committed.
>
> Run the app with `preview_start` (`zaram-frontend`) and **verify by looking, not
> by asserting** — read the load log first, and if the landing shows the orb
> rather than the robot, set `localStorage['zaram.embodiment.renderer'] = 'avatar'`.
>
> In order:
> 1. The six `Listening`/`Talk`/`Thinking` clips are on an Advanced Skeleton rig
>    with zero bone-name overlap with the character. If the maintainer has
>    retargeted and re-exported them from Maya — **with the skinned mesh in the
>    file, not skeleton-only** — bake them with
>    `avatar-source/retarget_animations.py`, verify with
>    `frontend/scripts/check-rig-agreement.mjs`, and add them to `animations.json`.
>    `animationSet.test.ts` asserts the current gap.
> 2. Watch it speak. Lip sync has never been observed against a real speech track.
> 3. Measure the GPU cost, which `CLAUDE.md` calls the measurement that decides
>    whether 3D may sit on the landing at all.
>
> If the GLB has been re-exported: copy it from `avatar-source`, **re-run
> `py avatar-source/fix_face_uvs.py --apply`** (the mouth fix does not survive a
> replacement and has been missed twice), and re-run the rig check before anything
> else.
>
> Debug switches: `?noAnim=1`, `?headFraction=0.9`, `?smileEvery=4`,
> `?envIntensity=1.8`, `?rough=2.1`, `?normal=1`, `?glow=0.35`, `?avatarBg=%23404858`.
