# The Zaram robot — build state, and what is still wrong

Written 2 September 2026, at the end of the session that built `RobotAvatar`.
`docs/MILESTONES.md` remains the handoff for the product as a whole; this file
is the detail for one subsystem, because the detail is mostly *measurements* and
they are expensive to re-derive.

**Everything below was measured against the running product**, not reasoned
about. Where a number appears it came out of the load log or out of parsing the
GLB, and the two disagreed often enough during this session that anything
unmeasured should be treated as unknown.

---

## What this is

A glTF character — helmeted robot, dot-matrix LED face — rendered by
`frontend/src/components/embodiment/RobotAvatar.tsx`, replacing the sample VRM
on the landing state. It is Zaram's default avatar and its mascot; the rules for
both are in `CLAUDE.md` under the embodiment section, and the short version is
that the *mascot* may smile in key art while the *renderer* shows states only.

**It is a plain glTF, not a VRM, and that was deliberate.** A VRM build of the
same character has three failure modes this one does not: `vrm.update()`
overwriting animation tracks every frame via the normalized rig, expression
weights interpolating a sprite cell onto the seam between two mouths, and
additive expression binds summing into a cell that does not exist. `VrmAvatar`
stays for avatars users bring themselves. See `CLAUDE.md`.

## Files

| Path | What |
|---|---|
| `components/embodiment/RobotAvatar.tsx` | The renderer. New. |
| `lib/faceAtlas.ts` + test | Atlas cell maths, UV islands, texel-aspect measurement |
| `lib/animationSet.ts` + test | Clip manifest types, `ShuffleBag`, state grouping |
| `lib/renderTuning.ts` | `renderScaleFor` / `approachRate` / `applyTextureFiltering`, extracted from `VrmAvatar` so a second renderer could share them without pulling in `@pixiv/three-vrm` |
| `components/embodiment/Embodiment.tsx` | Now lazy-imports `RobotAvatar` instead of `VrmAvatar` |
| `public/avatars/zaram-robo.glb` | The character, 11.3 MB. Replaced from `avatar-source`; see the re-import steps below |
| `public/avatars/face/` | Atlases, alpha versions, UV templates, `manifest.json`, `uv_guide.json`, and the generator that makes them |
| `public/avatars/animations/` | Three idle `.glb` clips and `animations.json` |
| `avatar-source/` | The maintainer's exports, not served |
| `avatar-source/retarget_animations.py` | Blender: bakes the idle FBXs onto the character's own rig |
| `avatar-source/probe_rest_poses.py` | Blender: what the clip FBXs' rest pose actually is |
| `avatar-source/fix_face_uvs.py` | Measures face UV islands against the sprites, and rewrites them |
| `avatar-source/extend_face_atlases.py` | Grows the atlases to 3x3 and draws the idle smile and happy eyes |
| `avatar-source/probe_studio_reference.py` | Measures `forest.exr` into the elevation profile the environment is built from |
| `avatar-source/bake_studio_environment.py` | Bakes that EXR to an embedded 8 KB equirect. Built, verified, not shipped |
| `frontend/scripts/check-rig-agreement.mjs` | Reads the GLBs and asserts the rigs agree |

## Verified working

Read off the load log with the product running:

- Model loads, passes `inspectAvatar`, all textures embedded, no external URIs
- Both face panels found by material name; **eyes and mouth both render**
- Three idle clips load and play with the arms down; variants crossfade
- Fingers animate from the mocap; nothing is posed statically any more
- Framing derived from the geometry — see below
- Environment rebuilt from measured `forest.exr` values; procedural, no file, no network
- Idle smile with matching arced eyes, 12.8s, idle only
- State glow behind the character, on the rim's own eased colour
- Tangents computed at load — the GLB ships none
- Frontend suite green (440 tests), typecheck clean

## The measurements, so nobody re-derives them

```
head bone world Y       1.566 m     (sample VRM was 1.504)
head - hips             0.563 m     (sample VRM was 0.564)
model bounds            1.832 x 2.006 x 0.519 m
helmet above head bone  0.440 m     <- the reason bone-height framing failed
Eye_Plane   texels      841 vs 837 per world unit   ratio 1.005  correct
Mouth_Plane texels      after the UV fix: ratio 0.991   correct
Mouth_Plane patch       0.2478 x 0.1074 world (2.307:1)
Eye_Plane   patch       0.3044 x 0.1075 world (2.831:1)
rest-pose, clips vs character, before   worst 78.08deg, 46 of 65 bones out
rest-pose, clips vs character, after    worst  0.04deg,  0 of 65 bones out
source FBX rest vs its own frame 1      0.000deg  <- there is no bind pose
```

**The head bone is not the head.** It sits at the base of the helmet with 0.44 m
of geometry above it out of a 2.0 m model, so framing on the bone points the
camera at the character's chest. `RobotAvatar` takes the bone as the *bottom* of
the head region and the model's bounding box as the top.

---

## Solved 2 September 2026 — the rigs disagreed, and why

**This was the blocker and it is fixed.** Kept in full because the diagnosis was
wrong twice before it was right, and both wrong versions looked correct.

The character travelled Maya -> FBX -> Blender -> glTF and the clips travelled
Maya -> FBX -> browser, so the working theory was that Blender had rewritten bone
rest orientation on one side only. Three closed-form runtime retargets were tried
against that theory and all three failed differently — the least wrong animated
the torso and left the arms pinned in a T-pose.

**The actual cause is that the animation FBXs contain no bind pose.** A previous
session asked for skeleton-only exports from Maya. Skeleton-only means no skinned
mesh, and a bind pose is stored against a skin — so there was nothing for Blender
to read, and Blender fell back to the bone transforms it found, which are frame 1
of the animation. Measured: **source rest and source frame 1 differ by 0.000
degrees**, and frame 1 has the hands at the hips while the character is bound in a
T with them 0.647 m out.

So every rest-relative correction — take a bone's rotation away from its own rest,
re-apply it from the target's rest — was measured from a pose the character never
had. It came out near identity and left the character standing in its own bind
pose with a small wobble on top. Arms out in a T, which reads as a retargeting bug
and is actually a missing bind pose.

**The fix.** `avatar-source/retarget_animations.py` imports the character's own
armature from the shipped GLB (`bone_heuristic='BLENDER'`, the round-trip-faithful
mode), evaluates the source rig frame by frame, and copies the **pose** rather
than the delta from rest — the two rigs are the same Maya skeleton in the same
world space, with the shoulder and head within 4 mm across the two files, so there
is nothing to correct. Rotation only. Exported as one `.glb` per clip.

Agreement is structural rather than hoped for: the target *is* the character's
armature, so the clips carry the rest pose the character has.

```
before   65/65 bones shared, worst 78.08deg on RightArm, 46 over tolerance
after    65/65 bones shared, worst  0.04deg on RightHandRing3, 0 over tolerance
```

### The second bug, which looked exactly like the first

Two correct exports in a row still rendered a T-pose, and the reason is worth more
than the fix. **`export_animation_mode="ACTIONS"` exports every action it can
reach**, not the one assigned. Each clip file shipped four animations —
`Armature|Take 001|BaseLayer`, a `.001` duplicate, a `DeformationSystem` take, and
the baked clip last — and `RobotAvatar` read `gltf.animations[0]`, so every file
delivered the raw un-retargeted Maya take.

The load log had been saying so the whole time: **`65/195 tracks kept`**, where 195
is 65 bones times three channels of a take that should not have been in the file,
while the baked action has 65 rotation channels and nothing else. A number nobody
read is how a broken export survives two rounds of being fixed.

Both halves are now closed: the script strips the scene to the target armature and
purges every other action before exporting, and the loader matches the clip **by
name** with a warning naming what it found instead. These FBXs also carry a second
armature (Maya's `DeformationSystem`), which is its own reason not to export the
whole scene — two skeletons in one glTF and the browser binds by name to whichever
node it reaches first.

### How you know it is right

```
node frontend/scripts/check-rig-agreement.mjs
```

reads the GLB JSON chunks directly and compares local rest rotation per bone.
**Directly is the point**: the first attempt compared them after importing both
into Blender, and Blender's glTF importer re-orients bones on the way in, so it
answered a different question and answered it wrongly (157–172 degrees, all noise).

In the app, the load log now reads:

```
65/65 tracks kept (rotation, fingers included)
bones with no track (0): none
rest-pose check: 0/65 tracks retargeted onto the glTF rest pose
face aspect: both square
```

`RIG_MATCH_TOLERANCE` decides, the runtime retarget is now a no-op, and the finger
tracks came back on their own. The retarget code stays for avatars users bring
themselves, where the rests genuinely may differ.

## Open problem — six clips bind to nothing

`Listening 1/2`, `Talk_1/2/3` and `Thinking` in `avatar-source/animations/` were
exported against an **Advanced Skeleton** rig — namespace `Robot_Rig_0001:`,
92 joints, bones named `Head_M` / `HeadEnd_M`. The character's rig is
`Robot_All_01:`, 65 joints, Mixamo naming. **Zero overlap**: re-confirmed by
reading the files, each contains one namespace and it is not the character's.
Those clips would load, report as valid, and move nothing, so they are not
shipped. Nothing the retarget script does can bind them — it matches by name.

They need retargeting onto `Robot_All_01` in Maya and re-exporting. Their file
sizes (3.7–7.2 MB against the idles' 680 KB) suggest they also carry the control
rig rather than baked joints, so bake on the way out.

**Export them with the skinned mesh in the file, not skeleton-only.** That is the
whole of the lesson above: a bind pose is stored against a skin, and without one
every tool downstream has to guess. The idles work now only because the character
GLB could stand in as the bind reference.

`animationSet.test.ts` asserts the current gap, so filling it is a deliberate edit
rather than something nobody notices either way.

## Solved 2 September 2026 — the mouth island

`Mouth_Plane`'s UV island was sized against `sil`, which is one dot row tall,
while `oh` is fourteen. Measured: the island covered cell rows 100.5–195.5 and
`oh` needs 80–192, so 21 px of it were simply not drawn, and `aa` lost 5.

**The obvious fix is half a fix, which is why it is recorded.** Growing the island
downward in `v` closes the clipping and makes the distortion *worse* — the patch
is 2.307:1 in world and the content box is 1.571:1, so fitting `v` alone takes the
texel aspect from 0.905 to about 0.75. Three quantities have to agree: the island
must contain every sprite, its texel aspect must match the patch's world aspect,
and it must stay inside its cell.

Fitting `v` to the content and then choosing the `u` span that lands the aspect on
1.0 satisfies all three at once, and it was available because the content does not
fill the cell horizontally — there is transparent margin either side to expand
into. `avatar-source/fix_face_uvs.py` measures it and patches the UV accessor in
the GLB in place, which leaves the material names and the bone rest pose alone;
re-exporting an 11.2 MB character through Blender to move four texture coordinates
risks both.

```
before   island 27.6..225.9 x 100.5..195.5   texel aspect 0.905, oh clips 21px
after    island  0.0..256.0 x  80.0..192.0   texel aspect 0.991, nothing clips
```

The load log now says `face aspect: both square`.

**The eyes were measured and deliberately left alone.** They clip three frames by
3 px, and closing that would pull their texel aspect from 1.005 to 0.942 — trading
a half-percent error for a six-percent one to recover one dot row at the edge of a
96 px sprite. The eyes are the panel that carries state. The script reports the
decision every run rather than letting it become an omission nobody remembers
making.

## Unverified

- **Lip sync.** The mouth renders and cell selection works, but `visemeAt` needs
  a real speech track, which needs the backend running. Nobody has watched it
  speak.
- **GPU cost.** `CLAUDE.md` still says this is *"the measurement that decides"*
  for the warn-never-block call on the landing, and it is still unmeasured.
  Body textures are 2048 squared across four maps — roughly 90 MB of VRAM and
  10.3 MB of the GLB's 11.2. A downscale to 1024 head / 512 body is worth doing.

## Things that cost time this session, so they do not cost it again

- **`GLTFLoader` deletes colons from node names.** `PropertyBinding.sanitizeNodeName`
  strips `[].:/ ` entirely, so `Robot_All_01:Head` arrives as `Robot_All_01Head`.
  A bone lookup matching on `':head'` silently fell through to fallback camera
  constants; it was caught only because the log prints measured values beside
  the defaults it would otherwise have used.
- **glTF v runs downward.** The atlas was authored bottom-up, `GLTFLoader` sets
  `flipY = false`, so cell row 0 is the *lower* half of the PNG and the top in v.
  `cellRect` flips it in one place.
- **Normalising a UV island to its cell warps the sprite.** It fixes clipping and
  breaks aspect: the cell is square in texels and the patches are not. Compare in
  texels, never in UV units — UV is not isotropic on a 768x512 atlas.
- **Face panels must be unlit.** As exported they are `MeshStandardMaterial` and
  catch the environment, so the panel reads as a faint rectangle on the visor
  well outside its dots. `MeshBasicMaterial` + additive blending is what makes
  black mathematically absent rather than merely dark.
- **A skeleton-only FBX has no bind pose, and every tool downstream guesses.**
  The bind pose is stored against a skin. Export animations with the skinned mesh
  in the file. This one cost a whole session and produced three wrong retargeting
  formulas before anybody measured the rest pose itself.
- **Blender exports every action it can reach, not the one assigned.** With
  `export_animation_mode="ACTIONS"`, strip the scene and purge the action list
  first. And never read `gltf.animations[0]` — match the clip by name.
- **Do not compare two rigs by importing both into Blender.** Its glTF importer
  re-orients bones on the way in (`bone_heuristic`), so the comparison answers a
  different question. Read the GLB JSON chunk instead. The Blender-side answer was
  157–172 degrees of pure noise.
- **A test fixture with a literal date is a test that fails from one morning on.**
  `Commitments.test.tsx` pinned a due date to `2026-09-01` and went permanently red
  on the 2nd — not a regression, just one red test every future reader has to
  re-diagnose before trusting the other 438.
- **A misdiagnosis worth remembering.** When only a shiny blob rendered it looked
  like a black body lost on a black backdrop, and the environment was pushed to
  2.6 — which turned the helmet silver. The body was missing because the skeleton
  had collapsed. `?noAnim=1` separated the two in one reload.

## Debug switches

All on `RobotAvatar`, all read from the URL:

| Query | Does |
|---|---|
| `?headFraction=0.12` | Pulls the camera back to see the whole character |
| `?avatarBg=%23404858` | Flat backdrop, for reading the silhouette |
| `?noAnim=1` | Loads the character and plays nothing — separates model faults from animation faults |
| `?fingerCurl=0.4` | Tunes the static finger pose |
| `?lightScale=5.5` | Multiplies key, fill and ambient. Not the rim — that is the state channel |
| `?envIntensity=0.5` | How reflective the character is. Raise and it goes mirror-like, not brighter |
| `?envBlur=0.35` | How much the room smears before the visor reflects it |
| `?lightSpread=3.4` | How broad the room's area lights are. `1` restores the untouched room |
| `?glow=1` | The state glow's opacity behind the character |
| `?rough=2.1` | Roughness multiplier. `1` is the material as exported; higher is matter |
| `?envIntensity=1.8` | How bright. Raise with `rough` or the shell goes chrome |
| `?smileEvery=3` | Seconds between idle smiles. Shipped at 14–32, which is too long to sit through |

## The bug underneath the whole lighting saga

**`Number(null)` is `0`, not `NaN`.** Every URL knob was written as

```ts
const raw = Number(new URLSearchParams(location.search).get('envIntensity'))
return Number.isFinite(raw) && raw >= 0 ? raw : 1.8
```

`URLSearchParams.get` returns `null` for an absent key, `Number(null)` is `0`,
and `0` is finite and `>= 0` — so the guard passed and the function returned
**zero** whenever the parameter was not in the URL. Which is to say always,
outside a debug link.

Three knobs were affected and each failure was diagnosed as something else:

| Knob | Silently | Looked like |
|---|---|---|
| `envIntensity` | 0 | The environment is wrong. **Four were rebuilt.** |
| `glow` | 0 | The glow mesh is not rendering |
| `normal` | 0 | The normal map is weak or missing |

Passing the value explicitly in the URL "fixed" it every time, which is precisely
what kept the parameter looking innocent — the comparison that would have exposed
it, defaults against the same values written out, was never run until late.

Guards written `raw > 0` escaped by accident, because `0 > 0` is false. That is a
coin toss rather than a defence, so every reader now goes through `numberParam`.

**The lesson is more general than the bug:** when a debug override makes a
problem disappear, that is evidence about the override, not only about the value.

## Lighting — settled 2 September 2026, after five attempts

**Four environments were built and thrown away before this one, and the reason
each failed is the useful part.**

| Attempt | Failed because |
|---|---|
| `RoomEnvironment`, sharp | It is *furnished*. A near-mirror visor showed recognisable armchairs sliding across the face |
| `RoomEnvironment`, blurred | Blur removes the crisp reflections that give glossy black its form. The character read **darker** with more light in the scene |
| Vertical gradient | One hue over the whole sphere reads as artificial. Needed 6x intensity to look lit, at which point the visor went milky |
| Softbox panels in a dark shell | A softbox is a rectangle, and a mirror shows you the rectangle. Moving the panels behind the character took the visor back to black |

All four were guesses at what a captured environment looks like. The fifth is
measured.

### What shipped

`FOREST_PROFILE` in `RobotAvatar.tsx` is the elevation profile of Blender's
`forest` studio light — sixteen bands of mean linear RGB, printed by
`avatar-source/probe_studio_reference.py`. `studioEnvironment()` interpolates it
into a 64x32 equirect at runtime. No image ships; the environment is arithmetic
over 48 measured numbers.

Source: `forest.exr` from `datafiles/studiolights/world`, **CC0**, Greg Zaal /
Poly Haven (originally `ninomaru_teien`), per the `license.txt` beside it.

**Two measured features do the work, and neither survived being invented:**

```
ground (v 0.03-0.47)   lum 0.08-0.16   WARM   R > G > B
horizon step           0.42 -> 2.53 between bands 8 and 9
sky    (v 0.65-0.97)   lum 1.3-1.56    COOL   B > G > R
overall                peak 81.75, mean 0.78, peak/mean 105
```

A single-hue gradient has neither, which is why three of them read as plastic.
The horizon *step* is what puts a defined bright edge along the top of the helmet
instead of a soft wash.

**The sun is placed behind the character, and that is the one departure from the
source.** A mirror facing the viewer reflects the hemisphere *behind the viewer*,
so a bright feature in front is painted straight across the faceplate. Behind, the
same light rims the helmet while the visor reflects dark ground and even sky —
which is why the Blender reference has a dark faceplate under a bright
environment.

### Brightness and gloss are different knobs

**This is the thing that cost the most time.** The shell rendered as chrome where
the reference is matte, and turning the environment down far enough to stop it
blowing out took the whole character to a silhouette — because on a near-mirror
almost all the brightness you see *is* the reflection.

`roughnessBoost` separates them. A **multiplier** on `material.roughness`, not a
floor: the visor's near-zero roughness stays the glossiest thing on the character
while the helmet's mid roughness moves far enough to stop mirroring. A floor would
have flattened both and taken the faceplate with it. three.js multiplies by the
map's green channel and clamps to 1, so values above 1 are meaningful and cannot
overshoot.

With roughness handled, intensity could come back up without chrome returning.
Shipped defaults, chosen by the maintainer off screenshots:

```
envIntensity  1.8     how bright
rough         2.1     how matte  (1 = the material exactly as exported)
lightScale    1       key/fill/ambient multiplier; the rim is never scaled
```

**Baking the EXR itself was tried, worked, and was reverted.** 64x32 RGBE is 8 KB
embedded — no fetch, no installer weight, and it looked right. Reverted on the
maintainer's call that the environment stays generated in code. If it is ever
wanted back, `avatar-source/bake_studio_environment.py` still produces it.

## The GLB is replaced from `avatar-source`, and two things do not survive it

```bash
cp "avatar-source/Zaram_Robo _.glb" frontend/public/avatars/zaram-robo.glb
py avatar-source/fix_face_uvs.py --apply          # the mouth island fix
node frontend/scripts/check-rig-agreement.mjs     # the clips must still bind
```

**The mouth UV fix is a buffer edit, not a code path**, so a new GLB arrives
without it and `oh` clips by 21px again. This has now been missed twice. And the
rig check is not optional: the baked idle clips are bound to a specific rest pose,
and a re-export that moved it would put the character back in a T-pose.

**Tangents are computed at load** because the GLB ships none. Without them three.js
derives a tangent frame from screen-space derivatives, which is discontinuous
across UV islands — a hairline of wrong shading down both sides of the face. The
load log reports how many meshes needed it, so a GLB that starts shipping tangents
will say so instead of silently keeping the workaround.

## Where to start

1. **Retarget the six Advanced Skeleton clips in Maya** onto `Robot_All_01`, bake
   the joints, and export them **with the skinned mesh in the file** — not
   skeleton-only. Then add them to `animations.json`; `animationSet.test.ts`
   asserts the gap, so filling it is a deliberate edit.
2. Watch it speak. Lip sync has never been observed with a real speech track.
3. Measure the GPU cost, which `CLAUDE.md` calls the measurement that decides
   whether 3D may sit on the landing at all.

## Rebuilding the assets

```bash
blender --background --python avatar-source/retarget_animations.py
node frontend/scripts/check-rig-agreement.mjs
py avatar-source/fix_face_uvs.py            # measure
py avatar-source/fix_face_uvs.py --apply    # rewrite the mouth island
```

`fix_face_uvs.py` edits the shipped GLB in place, so re-run
`check-rig-agreement.mjs` afterwards — it is what proves the bone rest pose was
not disturbed.
