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
| `public/avatars/zaram-robo.glb` | The character, 11.2 MB |
| `public/avatars/face/` | Atlases, alpha versions, UV templates, `manifest.json`, `uv_guide.json`, and the generator that makes them |
| `public/avatars/animations/` | Three idle `.glb` clips and `animations.json` |
| `avatar-source/` | The maintainer's exports, not served |
| `avatar-source/retarget_animations.py` | Blender: bakes the idle FBXs onto the character's own rig |
| `avatar-source/probe_rest_poses.py` | Blender: what the clip FBXs' rest pose actually is |
| `avatar-source/fix_face_uvs.py` | Measures face UV islands against the sprites, and rewrites them |
| `frontend/scripts/check-rig-agreement.mjs` | Reads the GLBs and asserts the rigs agree |

## Verified working

Read off the load log with the product running:

- Model loads, passes `inspectAvatar`, all textures embedded, no external URIs
- Both face panels found by material name; **eyes and mouth both render**
- Three idle clips load and play with the arms down; variants crossfade
- Fingers animate from the mocap; nothing is posed statically any more
- Framing derived from the geometry — see below
- `RoomEnvironment` reflections, procedural, no file and no network
- Frontend suite green (439 tests), typecheck clean

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
| `?glow=0.5` | The state glow's opacity behind the character |

## Lighting, and the two knobs that are not interchangeable

Settled 2 September 2026 against the character key art, after several passes that
each fixed one thing and broke another.

**Brightness and reflectivity are separate controls, and confusing them is what
cost the time.** `environmentIntensity` makes the character *reflective*; the
lights make it *bright*. On a glossy black character it is tempting to reach for
the environment for both, and it does not work — the visor is a near-mirror, so
it goes milky long before the armour looks lit. Measured: body readable at 2.0,
frosted glass at 3.2. The shipped balance is the opposite of the first instinct:
environment **down** to 0.5, lights **up** to 5.5.

**Three settings, not two, and the third is the visor.** Softening the lamps is
not the same as softening the room: the room still has walls and furniture, and
on a near-mirror faceplate those resolve into recognisable blobs the moment the
reflection is bright enough to see at all. So the visor could be flat black or
reflective-and-cluttered and neither is right. `envBlur` separates them — it
keeps the sheen and smears the structure below the point where it reads as
objects. Landed by looking: flat at 0.15, furniture visible at 0.6 unblurred,
silver at 1.1. Shipped at 0.5 with 0.35 of blur.

**The pale streak on the visor was one lamp, not the room.** `RoomEnvironment`'s
`light4` — a flat 4.4x5.4 panel on the +Z wall, above and slightly left — sits
exactly where a mirror-like visor facing the viewer takes its reflection from.
`softenAreaLights` grows every emissive panel and dims it by the area gained, so
total emitted power is unchanged and no source is compact enough to resolve into
a shape. A bare bulb becomes a softbox.

**Blurring the whole environment was tried and reverted.** It removes the streak
and removes the crisp reflections everywhere else, which is what gives glossy
black its form — the character came out flat and read *darker* than before
despite more light in the scene. Adding directional light back could not recover
it, because on a gloss surface most of the brightness you see is a sharp
reflection. A gradient environment was tried for the same reason and failed the
same way.

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
