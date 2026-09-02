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

**Read the load log before touching anything.** A healthy load says:

```
face panels: eyes=found mouth=found
clips loaded (3): idle_a, idle_b, idle_c
65/65 tracks kept (rotation, fingers included)
face aspect: both square
tangents computed for 3 mesh(es) — the GLB ships none
bones with no track (0): none
rest-pose check: 0/65 tracks retargeted onto the glTF rest pose
states with clips: idle
```

`rest-pose check` above `0/65` means the rig and the clips have drifted and the
character will stand in a T-pose.

---

## The one thing to fix, and it is a Maya export

**The character exists in Maya as two skeletons.** Which one a clip was exported
from is the whole story:

| | Namespace | Bones | Naming |
|---|---|---|---|
| Export skeleton | `Robot_All_01` | 65 | Mixamo — `LeftArm`, `LeftForeArm` |
| Advanced Skeleton | `Robot_Rig_0001` | 90 | AS — `Shoulder_L`, `Elbow_L` |

The three idles came from `Robot_All_01` and bind directly — they work. The six
`Listening 1/2`, `Talk_1/2/3` and `Thinking` clips came from the Advanced
Skeleton `DeformationSystem`, share **no bone names** with the character, and
bind to nothing.

**The fix is to re-export those six from `Robot_All_01`**, the same skeleton the
idles came from, **with the skinned mesh in the file** (not skeleton-only — a
bind pose is stored against a skin, and its absence is what caused the T-pose
that cost an entire session). Then they drop in with no retargeting at all, which
is what the maintainer expected in the first place and is correct.

Once re-exported, add them to `frontend/public/avatars/animations/animations.json`
and update the `statesWithoutClips` assertion in `animationSet.test.ts`, which
records the gap deliberately.

### A Blender retarget was attempted, failed, and was deleted — do not rebuild it

It mapped AS naming to Mixamo naming and baked onto the character's armature.
**Every structural check came back green and the result was wrong on screen:**

```
64 of 65 bones mapped        (only Spine1 unmapped, by design)
rest poses agree to 0.04deg  (check-rig-agreement.mjs, all nine clips)
all nine clips load          (load log, four states with clips)
--> the character collapses into a heap on the floor
```

**Two lessons, and the second matters more.**

*A retarget can satisfy every number available to it and still be measured from
the wrong frame.* Nothing in the instrumentation caught this. Only looking did.

*And it should never have been built.* One `grep` for the namespace answered the
real question in seconds — the clips are on the wrong skeleton, re-export them.
That was what the maintainer needed. Everything after it was unrequested work
that cost hours and shipped nothing. **When an asset does not bind, report the
cause and stop; do not build a rescue without being asked for one.**

**Do not "clean up" the character GLB to a single armature.** It carries a
vestigial one-bone `DeformationSystem` (`Root_M`) beside the real 65-bone
`Armature`. It is inert — nothing binds to it, the renderer never touches it.
Re-exporting to remove it would revert the mouth UV fix and risk the rest pose
the idles are baked against, for no gain.

### Two retargets exist and they are not interchangeable

- **`retarget_animations.py`** (the idles, working) copies the **pose** directly.
  Correct because the idles are the same skeleton as the character. Those files
  carry **no bind pose** — exported skeleton-only, so Blender falls back to frame
  1 — which is why a rest-relative approach fails on them.
- **`retarget_advanced_skeleton.py`** (the six, failed) transfers rotation **away
  from bind**. The source does have a real bind pose (rest and frame 1 differ by
  179°, confirmed by `probe_advanced_skeleton.py`), so the approach is right in
  principle and still produced a collapsed character in practice.

---

## What is done and working

- **Three idle clips** bind, play with arms down, fingers animating from the
  mocap. Variants cycle via `ShuffleBag` (no repeat until the set is exhausted,
  and no repeat across the reshuffle seam) and crossfade over 0.9s, with the fade
  *starting before the clip ends* so the blend spans a moving part of the cycle
  rather than the loop point.
- **The idle smile has no findable period** — hold 7–16s and gap 14–38s, both
  drawn fresh each occurrence.
- **The face is staggered**: eyes lead, mouth follows 1s later — except when
  speech starts, where the mouth takes over immediately or lip sync would begin a
  second into the audio and never catch up.
- **One state table.** `STATE_PULSE` is read by both `LivingOrb` and
  `RobotAvatar` — colour, brightness and breathing rhythm. They had disagreed on
  three of five states.
- **Lighting** rebuilt from measured `forest.exr` values (CC0, Poly Haven);
  `roughnessBoost` separates "too bright" from "too shiny".
- **Tangents** computed at load, because the GLB ships none — this is what fixed
  the UV seams down the sides of the face.
- **Mouth UV island** fixed: `oh` no longer clips, texel aspect 0.991.

## What is not

1. **Six clips are unshipped** — see above. `listening`, `speaking`, `thinking`
   and `swapping` have no body animation; they hold the idle pose and change only
   through the face and glow.
2. **Lip sync has never been watched.** The mouth renders and `visemeAt` is
   wired, but it needs the backend up and a real speech track.
3. **GPU cost is unmeasured.** `CLAUDE.md` calls this "the measurement that
   decides" whether 3D may sit on the landing at all.
4. **The rim light reports nothing.** `CLAUDE.md` names it as the state channel;
   it is invisible here because the body is metallic and a back-placed light
   returns almost nothing to the camera. State reaches the viewer through the eye
   cells and the glow. Three ways out are written up in `AVATAR-EMBODIMENT.md` —
   a rule-versus-code call for the maintainer.
5. **`CLAUDE.md` needs one amendment.** It says the rest face is `sil`, a flat
   line, *not* a smile. The idle smile contradicts that. Built on the
   maintainer's explicit request, idle-only, rare and brief — the same shape as
   the blink that rule already allows — but rule and code disagree.

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

## Answers the maintainer had to ask for more than once

- **A friendly male voice** — already `am_michael`, set 19 August at the
  maintainer's request. `test_the_default_voice_is_male` asserts the default stays
  male by checking the id's gender character, not the literal, so swapping to
  another male voice keeps it green. Locally cached male alternatives:
  `am_adam`, `bm_george`. Override with `ZARAM_VOICE_DEFAULT_VOICE`.
- **Shipping one Kokoro voice instead of all** — **not worth doing.** Voices are
  512 KB each and fetched on demand; only 7 of 54 are cached. Dropping six saves
  ~3 MB of a 316 MB model cache. **The real lever is
  `backend/requirements-voice-onnx.txt`**, whose header measures torch at 494 MB
  and transformers at 96 MB. `voice/providers/kokoro_onnx.py` is reachable via
  `ZARAM_VOICE_BACKEND=onnx` — same weights, same 54 voices, same output.
  `DEFAULT_BACKEND` is still `"torch"` and the comment says why: it is waiting on
  someone listening to it.

---

## Things that cost this session time

- **`Number(null)` is `0`, not `NaN`.** Every URL knob guarded as
  `Number.isFinite(raw) && raw >= 0` silently returned zero when absent.
  `envIntensity`, `glow` and `normal` were all switched off by default, and each
  was diagnosed as a different bug — the dark character was blamed on the
  environment and **four environments were rebuilt** chasing it. **When a debug
  override makes a problem disappear, that is evidence about the override.**
- **Green numbers on a broken retarget.** 64/65 bones, 0.04° rest agreement, all
  clips loading — and a collapsed character. Only looking caught it.
- **Taking the first armature in a file that has two.** Reported `0/64 bones
  mapped`, which reads as a broken bone map rather than a wrong armature.
- **A number in the log nobody read.** `65/195 tracks kept` named a bug for two
  whole rounds of "fixing" it.
- **Guessing at an environment.** Four failed. The fifth was measured off the
  reference in ten minutes and worked.
- **Confusing brightness with gloss.** On a near-mirror most of the brightness
  you see *is* the reflection, so dimming removes the surface with the glare.
- **Comparing two rigs by importing both into Blender.** Its glTF importer
  re-orients bones on the way in — 157–172° of pure noise.
- **`git add -A frontend/src`**, which swept a dozen unrelated files into an
  avatar commit. Stage paths explicitly.

---

## Prompt for the next session

> Continue the Zaram robot avatar work. Read `docs/AVATAR-EMBODIMENT.md` and
> `docs/NEXT-SESSION-PROMPTS.md` first — they hold the measurements, the four
> lighting approaches that failed, and the two-skeleton rig story. Re-deriving any
> of it is expensive.
>
> State: the character renders on the landing with three idle clips (shuffled and
> crossfaded), a dot-matrix LED face with a staggered idle smile, a state glow
> sharing one table with the orb, and lighting rebuilt from measured `forest.exr`
> values. 440 tests pass, typecheck clean, everything committed.
>
> Run the app with `preview_start` (`zaram-frontend`) and **verify by looking, not
> by asserting** — read the load log first, and if the landing shows the orb
> rather than the robot, set `localStorage['zaram.embodiment.renderer'] = 'avatar'`.
>
> **Answer the maintainer's questions before doing any building.** The previous
> session repeatedly kept working while questions went unanswered, which wasted
> their time and their tokens.
>
> In order:
> 1. **If the six `Listening`/`Talk`/`Thinking` clips have been re-exported from
>    `Robot_All_01`** (not the Advanced Skeleton rig, and with the skinned mesh in
>    the file): add them to `animations.json`, run
>    `node frontend/scripts/check-rig-agreement.mjs`, update the
>    `statesWithoutClips` assertion in `animationSet.test.ts`, and **watch each
>    state play before calling it done**. A Blender retarget of the old exports
>    passed every structural check and produced a collapsed character; do not
>    trust the numbers alone.
> 2. **Watch it speak.** Lip sync has never been observed against a real speech
>    track. Start the backend, get Kokoro synthesising, confirm `visemeAt` drives
>    the mouth in time with the audio. The mouth deliberately bypasses the 1s
>    expression lag when `speaking` starts — check the first viseme lands on the
>    audio rather than a second into it.
> 3. **Consider the ONNX voice backend** — `ZARAM_VOICE_BACKEND=onnx` saves ~590 MB
>    and is waiting on someone listening to it. Pairs naturally with (2).
> 4. **Measure the GPU cost**, which `CLAUDE.md` calls the measurement that
>    decides whether 3D may sit on the landing at all.
>
> If the GLB has been re-exported: copy it from `avatar-source`, **re-run
> `py avatar-source/fix_face_uvs.py --apply`** (the mouth fix does not survive a
> replacement and has been missed three times), then run the rig check before
> anything else. Do not re-export the GLB to remove its vestigial one-bone
> `DeformationSystem` — it is inert and the re-export costs more than it saves.
>
> Debug switches: `?noAnim=1`, `?headFraction=0.9`, `?smileEvery=4`,
> `?envIntensity=1.8`, `?rough=2.1`, `?normal=1`, `?glow=0.85`, `?rim=1`,
> `?sky=0.5`, `?lightScale=0.25`, `?avatarBg=%23404858`.
