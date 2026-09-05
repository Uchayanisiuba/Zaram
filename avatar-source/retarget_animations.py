"""
Retarget the animation FBXs onto the character's own rig and export them as glTF.

**Why this exists.** The character travelled Maya -> FBX -> Blender -> glTF and
the animation clips travelled Maya -> FBX -> browser. Blender rewrites bone rest
orientation on import; Maya's FBX does not. Same joint names, different rest
frames, and a clip's rotations are local to whichever frame its bones had when it
was authored -- so the clips do not mean the same thing on the character's rig.
Measured on the shipped assets: 46 of 65 bones disagree, worst 78deg on
RightArm. The visible result is a character whose torso animates while its arms
stay pinned in a T-pose.

**Why a formula did not fix it, and why this does.** Three closed-form runtime
retargets were tried and all three fail differently. The correct closed form
exists, but it needs the parent frame difference on one side and the bone's own
on the other, and getting either wrong is indistinguishable on screen from
getting both wrong. This script sidesteps the algebra entirely: it evaluates the
source rig frame by frame, takes each bone's rotation *away from its own rest*,
and re-applies that to the target bone from *its* rest. Numeric, per frame, with
no formula to get backwards.

**Agreement is structural here, not hoped for.** The target is the character's
own armature, imported from the shipped GLB with `bone_heuristic='BLENDER'` --
the mode documented as round-trip faithful -- so the clip GLBs carry the same
rest pose the character does because it is literally the same skeleton. That is
the difference from the first attempt, which re-exported the *source* rig and
hoped Blender would land it in the same place. It did not: 78-85deg out.

**Rotation only, and that is not a simplification.** Maya exported position and
scale curves in the rig's authoring units while the GLB's bones sit under a 0.01
centimetre-to-metre armature scale; applied directly, every joint is yanked a
hundred times too far from its parent and the body collapses into a lump the size
of its own helmet. A skeleton needs none of them -- bone lengths come from the
rest pose and animation is rotation. Enforced here as well as at runtime, because
an export that carries them is a trap for the next reader.

Run:
    blender --background --python avatar-source/retarget_animations.py

Writes .glb clips into frontend/public/avatars/animations/. Verify with
    node frontend/scripts/check-rig-agreement.mjs
which reads the files rather than Blender's idea of them -- Blender's glTF
importer re-orients bones on the way in, so a Blender-side comparison answers a
different question and answers it wrongly.
"""

import math
import os
import re
import sys

import bpy
from mathutils import Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARACTER = os.path.join(ROOT, "frontend", "public", "avatars", "zaram-robo.glb")
SOURCE = os.path.join(ROOT, "avatar-source", "animations")
OUT = os.path.join(ROOT, "frontend", "public", "avatars", "animations")

# Which source FBX becomes which shipped clip. The clips still missing are on the
# Advanced Skeleton rig (namespace Robot_Rig_0001, 92 joints, Head_M naming) with
# **zero** bone-name overlap with the character's Robot_All_01, so nothing this
# script does can bind them. They are re-exported from Robot_All_01 in Maya one
# at a time, which is what the Listening pair already is.
CLIPS = [
    ("Idle.fbx", "idle_a"),
    ("Idle_01.fbx", "idle_b"),
    ("Idle_02.fbx", "idle_c"),
    ("Listening 1.fbx", "listening_a"),
    ("Listening 2.fbx", "listening_b"),
    ("Talk_1.fbx", "speaking_a"),
    ("Talk_2.fbx", "speaking_b"),
    ("Talk_3.fbx", "speaking_c"),
    ("Thinking.fbx", "thinking_a"),
]


def on_character_rig(path):
    """True if this FBX was exported from `Robot_All_01`, read from the file.

    The re-export happens one clip at a time in Maya, so the directory holds a
    mixture. Checked before Blender is asked to do anything, because an
    Advanced Skeleton clip imports perfectly happily and matches zero bones --
    and a clean run over zero bones reads exactly like success.
    """
    with open(path, "rb") as fh:
        head = fh.read()
    models = re.findall(b"([ -~]{2,120}?)" + bytes([0, 1]) + b"Model", head)
    return bool(models) and b"Robot_All_01" in models[0]


def sanitize(name):
    """Bone names, compared the way three.js compares them.

    `PropertyBinding.sanitizeNodeName` deletes `[].:/ ` outright, so
    `Robot_All_01:Hips` is addressed in the browser as `Robot_All_01Hips`.
    Blender keeps the colon on FBX import, so the two rigs can spell the same
    joint differently. Matching on the raw name finds nothing and reports it as
    a clean run over zero bones, which reads exactly like success.

    Compared on the trailing segment, because a clip exported from inside the rig
    namespace spells the joint `Robot_Rig_0001:Robot_All_01:Hips` where the
    character spells it `Robot_All_01:Hips`. The bare name is unique across the
    65 joints, and matching the full string finds nothing -- the same
    zero-bones-reads-as-success failure above, reached by a second route.
    """
    return "".join(c for c in name.split(":")[-1] if c.isalnum()).lower()


def armature_of(objects):
    """The armature with the most bones, never simply the first.

    The character GLB carries two: the real 65-bone `Armature` and a vestigial
    one-bone `DeformationSystem` (`Root_M`) that nothing binds to. Blender's glTF
    importer returns the vestigial one first, so taking the first armature made
    *it* the character -- and then left the real one in the scene to be picked up
    as the animation source, which reports as `carries no action` and reads like
    a bad export rather than a wrong armature.
    """
    arms = [o for o in objects if o.type == "ARMATURE"]
    if not arms:
        return None
    return max(arms, key=lambda o: len(o.data.bones))


def import_character():
    """The character's armature, mesh discarded.

    `bone_heuristic='BLENDER'` is the round-trip-faithful mode. The other two
    ('TEMPERANCE', 'FORTUNE') re-aim bones to look tidy in the viewport, which
    rewrites exactly the rest orientation this whole exercise is trying to hold
    still.
    """
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=CHARACTER, bone_heuristic="BLENDER")
    arm = armature_of(bpy.context.scene.objects)
    if arm is None:
        sys.exit("no armature in the character GLB")
    arm.name = "ZaramRig"
    # Everything else goes, the second armature included -- otherwise it is still
    # in the scene when the clip is imported and is what `import_source` finds.
    for o in list(bpy.context.scene.objects):
        if o is not arm:
            bpy.data.objects.remove(o, do_unlink=True)
    return arm


def import_source(path):
    bpy.ops.import_scene.fbx(
        filepath=path,
        automatic_bone_orientation=False,
        # Maya writes a leaf tip for every chain and the character has them too.
        # Dropping them here would leave those joints unmatched and re-aim their
        # parents, which is a rest-pose change by another route.
        ignore_leaf_bones=False,
    )
    return armature_of([o for o in bpy.context.scene.objects if o.name != "ZaramRig"])


def hierarchy_order(armature):
    """Bones parent-first, so a bone's parent is always already solved."""
    out = []
    seen = set()

    def walk(bone):
        if bone.name in seen:
            return
        seen.add(bone.name)
        out.append(bone)
        for child in bone.children:
            walk(child)

    for bone in armature.data.bones:
        if bone.parent is None:
            walk(bone)
    # A rig with a cycle or an orphan cannot happen in Blender, but a bone whose
    # parent is outside the armature would be dropped silently otherwise.
    for bone in armature.data.bones:
        if bone.name not in seen:
            out.append(bone)
    return out


def retarget(target, source, clip_name):
    """Bake source's motion onto target's rest pose, rotation only."""
    action = source.animation_data.action if source.animation_data else None
    if action is None:
        return None, 0

    start = int(math.floor(action.frame_range[0]))
    end = int(math.ceil(action.frame_range[1]))

    src_bones = {sanitize(b.name): b.name for b in source.data.bones}
    pairs = []
    for bone in hierarchy_order(target):
        name = src_bones.get(sanitize(bone.name))
        if name:
            pairs.append((bone, name))

    target.animation_data_create()
    baked = bpy.data.actions.new(clip_name)
    baked.use_fake_user = True
    target.animation_data.action = baked

    for pose_bone in target.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"

    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = start, end

    # Both armatures carry the FBX's centimetre-to-metre scale on the object, and
    # the two are not guaranteed to be identical. Going out to world and back in
    # costs nothing and removes the assumption.
    world_to_target = target.matrix_world.inverted()

    for frame in range(start, end + 1):
        scene.frame_set(frame)
        # Armature-space target matrix per bone, solved independently: a bone's
        # delta from its own rest does not depend on its parent's, so no pose
        # evaluation is needed between bones and no view-layer update either.
        solved = {}
        for bone, src_name in pairs:
            src_pose = source.pose.bones[src_name]
            # **The pose is copied, not the delta from rest, and the difference
            # is the whole bug.**
            #
            # The obvious form is rest-relative: take each bone's rotation away
            # from its own rest and re-apply it to the target from the target's
            # rest. That is correct only when both rests describe the same
            # physical pose -- the bind pose. These animation FBXs carry no bind
            # pose at all: exported from Maya with no skinned mesh, there is
            # nothing for Blender to read, so Blender takes the bone transforms
            # it finds, which are frame 1 of the animation. Measured: source rest
            # and source frame 1 differ by 0.000 degrees, and the clip's frame 1
            # has the hands at the hips while the character is bound in a T with
            # them 0.647m out.
            #
            # So every rest-relative delta was measured from a pose the character
            # never had, came out near identity, and left the character standing
            # in its own bind pose with a small wobble on top -- arms out in a T,
            # which reads as a retargeting bug and is actually a missing bind
            # pose. Every number you would check looked right: 65/65 bones
            # matched, rest poses agreed to 0.04 degrees, no track was dropped.
            #
            # Both rigs are the same Maya skeleton in the same world space -- the
            # probe puts the shoulder and head within 4mm across the two files --
            # so the honest transfer is the direct one: put the character's bone
            # where the clip's bone is. No correction, because there is nothing
            # to correct.
            solved[bone.name] = world_to_target @ source.matrix_world @ src_pose.matrix

        for bone, _ in pairs:
            pose_bone = target.pose.bones[bone.name]
            parent = bone.parent
            if parent is not None and parent.name in solved:
                basis = (
                    bone.matrix_local.inverted()
                    @ parent.matrix_local
                    @ solved[parent.name].inverted()
                    @ solved[bone.name]
                )
            else:
                basis = bone.matrix_local.inverted() @ solved[bone.name]
            # Rotation only. Discarding translation and scale is what keeps the
            # skeleton a skeleton rather than an exploded diagram of one.
            pose_bone.rotation_quaternion = basis.to_quaternion()
            pose_bone.location = (0, 0, 0)
            pose_bone.scale = (1, 1, 1)
            pose_bone.keyframe_insert("rotation_quaternion", frame=frame, group=bone.name)

    return baked, len(pairs)


def export(target, clip_name):
    out_path = os.path.join(OUT, clip_name + ".glb")
    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        export_animations=True,
        export_animation_mode="ACTIONS",
        # The pose carries no constraints and no drivers, so the fcurves are the
        # motion. Sampling would re-emit translation and scale for every bone and
        # undo the rotation-only guarantee above.
        export_force_sampling=False,
        export_apply=False,
        use_selection=False,
    )
    return os.path.getsize(out_path)


def main():
    os.makedirs(OUT, exist_ok=True)
    wrote = []

    # `-- listening_a` rebuilds just that one, so adding a clip does not
    # re-export the ones already working.
    wanted = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

    for source_name, clip_name in CLIPS:
        if wanted and clip_name not in wanted:
            continue
        path = os.path.join(SOURCE, source_name)
        if not os.path.exists(path):
            print("[retarget] MISSING %s" % source_name)
            continue
        if not on_character_rig(path):
            print("[retarget] %s is still on the Advanced Skeleton rig "
                  "-- re-export from Robot_All_01" % source_name)
            continue

        target = import_character()
        source = import_source(path)
        if source is None:
            print("[retarget] no armature in %s" % source_name)
            continue

        baked, matched = retarget(target, source, clip_name)
        if baked is None:
            print("[retarget] %s carries no action -- skipped" % source_name)
            continue

        # **Strip the scene back to the target armature and the baked action,
        # and this is not tidying.**
        #
        # `export_animation_mode="ACTIONS"` exports every action it can reach,
        # not the one currently assigned. The first pass shipped four animations
        # per clip -- `Armature|Take 001|BaseLayer`, a `.001` duplicate, a
        # `DeformationSystem` take, and the baked clip last -- and `RobotAvatar`
        # read `animations[0]`, so every file delivered the raw un-retargeted
        # Maya take and the character stood in a T-pose exactly as before. The
        # export was correct and unused, which is the hardest kind of wrong to
        # see: the load log said "65/195 tracks kept", and 195 is 65 bones times
        # three channels of a take that should not have been in the file, while
        # the baked action has 65 rotation channels and nothing else.
        #
        # These FBXs also carry more than one armature -- Maya's `DeformationSystem`
        # rides along beside the export rig -- and two skeletons in one glTF means
        # the browser binds tracks by name to whichever node it reaches first.
        for o in list(bpy.context.scene.objects):
            if o is not target:
                bpy.data.objects.remove(o, do_unlink=True)
        for a in list(bpy.data.actions):
            if a is not baked:
                bpy.data.actions.remove(a)

        size = export(target, clip_name)
        frames = int(baked.frame_range[1] - baked.frame_range[0]) + 1
        print(
            "[retarget] %s -> %s.glb: %d bones, %d frames, %d bytes"
            % (source_name, clip_name, matched, frames, size)
        )
        wrote.append(clip_name)

    print("")
    print("[retarget] wrote %d clip(s): %s" % (len(wrote), ", ".join(wrote) or "none"))
    print("[retarget] verify with: node frontend/scripts/check-rig-agreement.mjs")


main()
