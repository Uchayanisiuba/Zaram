"""
Retarget the six Advanced Skeleton clips onto the character's rig.

`Listening 1/2`, `Talk_1/2/3` and `Thinking` were exported from a different rig
from the character: namespace `Robot_Rig_0001`, 90 deform joints, Advanced
Skeleton's naming (`Shoulder_L`, `Elbow_L`, `Wrist_L`), against the character's
`Robot_All_01`, 65 joints, Mixamo naming. Nothing binds them by name, so they
have never shipped and four states have had no body animation at all.

**Three things had to be true for this to be fixable outside Maya, and all three
are** — checked with `probe_advanced_skeleton.py` rather than assumed:

  1. **The armature is the `DeformationSystem`.** It is the deform skeleton, not
     the control rig, so every bone corresponds to something the character has.
  2. **It carries a real bind pose.** Rest and frame 1 differ by 179 degrees.
     This is the opposite of the idles, which were exported skeleton-only and had
     no bind pose at all — Blender fell back to frame 1 and every rest-relative
     delta was measured from a pose the character never held. That trap is not
     here.
  3. **The naming is systematic**, so the map below is a lookup rather than
     guesswork.

**Which makes the maths different from `retarget_animations.py`, and the
difference matters.** That script copies the *pose* directly, because the idles
come from the same Maya skeleton as the character and a pose is a pose. These
clips come from a different skeleton with its own bind pose, so what transfers is
each bone's rotation **away from its own bind** — applied to the target from the
target's bind. That is the textbook retarget, and it is correct *here* precisely
because both sides have a real bind to measure from.

    blender --background --python avatar-source/retarget_advanced_skeleton.py

Verify with `node frontend/scripts/check-rig-agreement.mjs`, then add the clips
to `frontend/public/avatars/animations/animations.json`.
"""

import math
import os

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARACTER = os.path.join(ROOT, "frontend", "public", "avatars", "zaram-robo.glb")
SOURCE = os.path.join(ROOT, "avatar-source", "animations")
OUT = os.path.join(ROOT, "frontend", "public", "avatars", "animations")

# Which file becomes which clip. The name is what `animations.json` keys on and
# what the glTF animation is called, so it has to match there exactly.
CLIPS = [
    ("Listening 1.fbx", "listening_a"),
    ("Listening 2.fbx", "listening_b"),
    ("Talk_1.fbx", "speaking_a"),
    ("Talk_2.fbx", "speaking_b"),
    ("Talk_3.fbx", "speaking_c"),
    ("Thinking.fbx", "thinking_a"),
]

NS = "Robot_Rig_0001:"


def _limbs(source_fmt, target_fmt):
    """The same pair for both sides, since every limb bone comes in two."""
    return {
        source_fmt % "L": target_fmt % "Left",
        source_fmt % "R": target_fmt % "Right",
    }


# Advanced Skeleton to Mixamo, by hand, because there is no convention that
# converts one to the other.
#
# **What is deliberately absent is as important as what is here.** The source
# carries twist joints (`ShoulderPart1_L`, `HipPart2_R`, `RootPart1_M` and the
# rest), `Cup_L/R` in the palms, and `Eye_L/R` and `Jaw_M` in the head. The
# character has no counterpart for any of them, and inventing one — folding a
# twist into its parent, say — would put rotation somewhere the mesh is not
# weighted for. They are dropped, which costs a little forearm and thigh
# counter-rotation and nothing else.
#
# The spine is the one genuine mismatch: the source has two bones between pelvis
# and neck, the character has three. `Spine1` is left unmapped and holds its rest
# rather than being given a share of `Chest_M`, because splitting one rotation
# across two joints is a guess about where the bend belongs, and a guess that
# shows up as a wrong silhouette rather than as a stiff one.
BONE_MAP = {
    "Root_M": "Hips",
    "Spine1_M": "Spine",
    "Chest_M": "Spine2",
    "Neck_M": "Neck",
    "Head_M": "Head",
    "HeadEnd_M": "HeadTop_End",
}
BONE_MAP.update(_limbs("Scapula_%s", "%sShoulder"))
BONE_MAP.update(_limbs("Shoulder_%s", "%sArm"))
BONE_MAP.update(_limbs("Elbow_%s", "%sForeArm"))
BONE_MAP.update(_limbs("Wrist_%s", "%sHand"))
BONE_MAP.update(_limbs("Hip_%s", "%sUpLeg"))
BONE_MAP.update(_limbs("Knee_%s", "%sLeg"))
BONE_MAP.update(_limbs("Ankle_%s", "%sFoot"))
BONE_MAP.update(_limbs("Toes_%s", "%sToeBase"))
BONE_MAP.update(_limbs("ToesEnd_%s", "%sToe_End"))
for _digit in (1, 2, 3, 4):
    for _as, _mx in (
        ("ThumbFinger", "Thumb"),
        ("IndexFinger", "Index"),
        ("MiddleFinger", "Middle"),
        ("RingFinger", "Ring"),
        ("PinkyFinger", "Pinky"),
    ):
        # `%%s` is an escape only inside a `%` operation — the source format is
        # built by one and needs it, the target is plain concatenation and must
        # not have it, or the placeholder never becomes one.
        BONE_MAP.update(
            _limbs("%s%d_%%s" % (_as, _digit), "%sHand" + _mx + str(_digit))
        )


def armature_of(objects, exclude=()):
    """The armature with the most bones, not the first one found.

    **Both files carry more than one.** The character GLB has an `Armature` of 65
    bones and a vestigial `DeformationSystem` holding a single `Root_M`; the
    source FBXs carry their own `DeformationSystem` beside whatever else Maya
    exported. Taking the first match picked the one-bone stub and mapped nothing,
    which reported as `0/64 bones mapped` and wrote empty clips — a failure that
    looks like a broken bone map rather than a wrong armature.
    """
    best = None
    for o in objects:
        if o.type != "ARMATURE" or o in exclude:
            continue
        if best is None or len(o.data.bones) > len(best.data.bones):
            best = o
    return best


def strip(name):
    """Drop the namespace both rigs carry, so the map reads as bone names."""
    return name.split(":")[-1]


def sanitize(name):
    """Lowercase alphanumerics only, for comparing names across two tools."""
    return "".join(c for c in name if c.isalnum()).lower()


def import_character():
    """The character's armature, mesh discarded.

    `bone_heuristic='BLENDER'` is the round-trip-faithful mode; the other two
    re-aim bones to look tidy in the viewport, which rewrites the rest
    orientation the shipped clips have to agree with.
    """
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=CHARACTER, bone_heuristic="BLENDER")
    arm = armature_of(bpy.context.scene.objects)
    if arm is None:
        raise SystemExit("no armature in the character GLB")
    for o in list(bpy.context.scene.objects):
        if o.type != "ARMATURE":
            bpy.data.objects.remove(o, do_unlink=True)
    arm.name = "ZaramRig"
    return arm


def hierarchy_order(armature):
    """Bones parent-first, so a parent is always solved before its children."""
    out, seen = [], set()

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
    for bone in armature.data.bones:
        if bone.name not in seen:
            out.append(bone)
    return out


def retarget(target, source, clip_name):
    action = source.animation_data.action if source.animation_data else None
    if action is None:
        return None, 0, 0

    start = int(math.floor(action.frame_range[0]))
    end = int(math.ceil(action.frame_range[1]))

    # Matched on the sanitized *suffix* rather than on the whole name, because
    # both rigs carry a Maya namespace (`Robot_All_01:Hips`,
    # `Robot_Rig_0001:Shoulder_L`) and neither importer is guaranteed to keep or
    # drop the colon consistently. The suffix is the part that means something.
    def suffix_match(bones, want):
        target_key = sanitize(want)
        for b in bones:
            if sanitize(b.name).endswith(target_key):
                return b.name
        return None

    pairs, unmapped = [], []
    for bone in hierarchy_order(target):
        as_name = next(
            (k for k, v in BONE_MAP.items() if sanitize(bone.name).endswith(sanitize(v))),
            None,
        )
        src_name = suffix_match(source.data.bones, as_name) if as_name else None
        if src_name:
            pairs.append((bone, src_name))
        else:
            unmapped.append(strip(bone.name))
    if unmapped:
        print("[as]   unmapped target bones (%d): %s" % (len(unmapped), ", ".join(unmapped)))

    target.animation_data_create()
    baked = bpy.data.actions.new(clip_name)
    baked.use_fake_user = True
    target.animation_data.action = baked
    for pose_bone in target.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"

    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = start, end

    # Everything is composed in world space, because the two armatures arrive
    # from different importers with their own axis conversions and object
    # scales. Comparing them in either one's local space would fold that
    # difference into the animation.
    src_world = source.matrix_world.to_quaternion()
    tgt_world = target.matrix_world.to_quaternion()
    tgt_world_inv = tgt_world.inverted()

    src_rest = {
        name: (src_world @ source.data.bones[name].matrix_local.to_quaternion())
        for _, name in pairs
    }
    tgt_rest = {
        bone.name: (tgt_world @ bone.matrix_local.to_quaternion()) for bone, _ in pairs
    }

    for frame in range(start, end + 1):
        scene.frame_set(frame)
        solved = {}
        for bone, src_name in pairs:
            pose = src_world @ source.pose.bones[src_name].matrix.to_quaternion()
            # How far this bone has turned from its own bind pose, in world
            # terms — then the same turn applied to the target from *its* bind.
            # This is the step the idles could not use, because their files
            # carried no bind pose to measure from.
            delta = pose @ src_rest[src_name].inverted()
            solved[bone.name] = tgt_world_inv @ (delta @ tgt_rest[bone.name])

        for bone, _ in pairs:
            local = bone.matrix_local.to_quaternion()
            parent = bone.parent
            if parent is not None and parent.name in solved:
                basis = (
                    local.inverted()
                    @ parent.matrix_local.to_quaternion()
                    @ solved[parent.name].inverted()
                    @ solved[bone.name]
                )
            else:
                basis = local.inverted() @ solved[bone.name]
            pose_bone = target.pose.bones[bone.name]
            # Rotation only. Bone lengths come from the character's own rest, and
            # a translation curve authored against another rig's proportions is
            # what turns a skeleton into an exploded diagram of one.
            pose_bone.rotation_quaternion = basis
            pose_bone.location = (0, 0, 0)
            pose_bone.scale = (1, 1, 1)
            pose_bone.keyframe_insert("rotation_quaternion", frame=frame, group=bone.name)

    return baked, len(pairs), end - start + 1


def main():
    os.makedirs(OUT, exist_ok=True)
    wrote = []

    for source_name, clip_name in CLIPS:
        path = os.path.join(SOURCE, source_name)
        if not os.path.exists(path):
            print("[as] MISSING %s" % source_name)
            continue

        target = import_character()
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.fbx(
            filepath=path, automatic_bone_orientation=False, ignore_leaf_bones=False
        )
        source = armature_of(
            [o for o in bpy.context.scene.objects if o not in before], exclude=(target,)
        )
        if source is None:
            print("[as] no armature in %s" % source_name)
            continue

        baked, matched, frames = retarget(target, source, clip_name)
        if baked is None:
            print("[as] %s carries no action" % source_name)
            continue

        # Strip to the target armature and the one action. `ACTIONS` mode
        # exports everything it can reach, and the first pass on the idles
        # shipped four animations per file with the raw Maya take first — which
        # the loader then played, because it read `animations[0]`.
        for o in list(bpy.context.scene.objects):
            if o is not target:
                bpy.data.objects.remove(o, do_unlink=True)
        for a in list(bpy.data.actions):
            if a is not baked:
                bpy.data.actions.remove(a)

        out_path = os.path.join(OUT, clip_name + ".glb")
        bpy.ops.export_scene.gltf(
            filepath=out_path,
            export_format="GLB",
            export_animations=True,
            export_animation_mode="ACTIONS",
            export_force_sampling=False,
            export_apply=False,
            use_selection=False,
        )
        size = os.path.getsize(out_path)
        print(
            "[as] %s -> %s.glb: %d/%d bones mapped, %d frames, %.1f MB"
            % (source_name, clip_name, matched, len(BONE_MAP), frames, size / 1e6)
        )
        wrote.append(clip_name)

    print("")
    print("[as] wrote %d clip(s): %s" % (len(wrote), ", ".join(wrote) or "none"))
    print("[as] verify: node frontend/scripts/check-rig-agreement.mjs")


main()
