"""
What is the animation FBX's rest pose, actually?

**The question this answers, and why it is not obvious.** Rest-relative
retargeting -- take each bone's rotation away from its own rest, re-apply it to
the target from the target's rest -- is correct only when both rests describe the
*same physical pose*, the bind pose. An FBX exported from Maya with no skinned
mesh in it carries no bind pose for Blender to read, and Blender then takes the
bone transforms it finds, which are the first frame of the animation. Rest
becomes frame 0, every delta is measured from a pose the character never had, and
the retarget silently produces the target's own rest plus a small wobble.

That failure is invisible in every number you would normally check: the rest
poses agree, all 65 tracks bind, no bone is missing, nothing is dropped. It shows
up only as a character standing in its bind pose while the animation plays on top
of it -- arms out in a T, which reads as a retargeting bug rather than as a
missing bind pose.

So measure it. Printed in world space and in metres, because the useful question
is a physical one: where are the hands relative to the hips, in the character's
rest and in the clip.

    blender --background --python avatar-source/probe_rest_poses.py
"""

import math
import os

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHARACTER = os.path.join(ROOT, "frontend", "public", "avatars", "zaram-robo.glb")
SOURCE = os.path.join(ROOT, "avatar-source", "animations", "Idle.fbx")

WATCH = ["Hips", "LeftArm", "LeftForeArm", "LeftHand", "RightHand", "Head"]


def sanitize(name):
    return "".join(c for c in name if c.isalnum()).lower()


def armature_of(objects):
    for o in objects:
        if o.type == "ARMATURE":
            return o
    return None


def find(armature, suffix):
    want = sanitize(suffix)
    for b in armature.data.bones:
        if sanitize(b.name).endswith(want):
            return b.name
    return None


def report(label, armature, use_pose):
    print("")
    print("[probe] %s (object scale %s)" % (label, tuple(round(v, 4) for v in armature.scale)))
    hips_name = find(armature, "Hips")
    hips = None
    if hips_name:
        hips = (
            armature.matrix_world @ armature.pose.bones[hips_name].matrix
            if use_pose
            else armature.matrix_world @ armature.data.bones[hips_name].matrix_local
        ).translation
    for suffix in WATCH:
        name = find(armature, suffix)
        if not name:
            print("  %-12s missing" % suffix)
            continue
        m = (
            armature.matrix_world @ armature.pose.bones[name].matrix
            if use_pose
            else armature.matrix_world @ armature.data.bones[name].matrix_local
        )
        p = m.translation
        rel = (p - hips) if hips is not None else p
        print(
            "  %-12s world [%7.3f %7.3f %7.3f]  from hips [%7.3f %7.3f %7.3f]"
            % (suffix, p.x, p.y, p.z, rel.x, rel.y, rel.z)
        )


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=CHARACTER, bone_heuristic="BLENDER")
character = armature_of(bpy.context.scene.objects)
report("character GLB — REST", character, use_pose=False)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SOURCE, automatic_bone_orientation=False, ignore_leaf_bones=False)
source = armature_of(bpy.context.scene.objects)
action = source.animation_data.action if source.animation_data else None
start = int(action.frame_range[0]) if action else 1
mid = int(sum(action.frame_range) / 2) if action else 1

report("Idle.fbx — REST (what Blender thinks the bind pose is)", source, use_pose=False)
bpy.context.scene.frame_set(start)
report("Idle.fbx — POSE at frame %d" % start, source, use_pose=True)
bpy.context.scene.frame_set(mid)
report("Idle.fbx — POSE at frame %d" % mid, source, use_pose=True)

# The decisive comparison: if rest and frame 0 are the same, Blender took the
# animation's first frame as the bind pose and every rest-relative delta is
# measured from the wrong place.
bpy.context.scene.frame_set(start)
worst = 0.0
for b in source.data.bones:
    a = (source.matrix_world @ b.matrix_local).to_quaternion()
    c = (source.matrix_world @ source.pose.bones[b.name].matrix).to_quaternion()
    d = a.rotation_difference(c).angle
    worst = max(worst, min(d, 2 * math.pi - d))
print("")
print("[probe] source rest vs source frame %d: worst %.3f deg" % (start, math.degrees(worst)))
print(
    "[probe] verdict: %s"
    % (
        "REST IS FRAME 0 — no bind pose in the FBX"
        if worst < 0.5
        else "rest is distinct from frame 0 — a real bind pose"
    )
)

# ---------------------------------------------------------------------------
# Convention, or pose?
#
# A local rest difference between the two files has two possible causes and they
# call for opposite fixes. If Blender re-aimed the character's bone axes on
# import, the two rigs describe the same pose in different frames and every clip
# needs correcting. If the axes agree and the difference is only that the clip's
# first frame has the arms down while the character is bound in a T, then the
# rigs are compatible, no correction is needed, and correcting anyway is what
# forces the arms back out.
#
# Bones in the same physical pose in both files -- the spine and head, which an
# idle holds upright -- separate the two. If those agree in world space the
# conventions match and the arm difference is pose.
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=CHARACTER, bone_heuristic="BLENDER")
char = armature_of(bpy.context.scene.objects)
char_rest = {
    sanitize(b.name): (char.matrix_world @ b.matrix_local).to_quaternion()
    for b in char.data.bones
}

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SOURCE, automatic_bone_orientation=False, ignore_leaf_bones=False)
src = armature_of(bpy.context.scene.objects)
rows = []
for b in src.data.bones:
    k = sanitize(b.name)
    if k not in char_rest:
        continue
    q = (src.matrix_world @ b.matrix_local).to_quaternion()
    d = char_rest[k].rotation_difference(q).angle
    rows.append((math.degrees(min(d, 2 * math.pi - d)), b.name))
rows.sort(reverse=True)
print("")
print("[probe] world-space rest orientation, character vs clip frame 1")
for d, name in rows[:10]:
    print("  %7.2f deg  %s" % (d, name))
print("  ... %d bones total, %d under 5 deg" % (len(rows), sum(1 for d, _ in rows if d < 5)))
