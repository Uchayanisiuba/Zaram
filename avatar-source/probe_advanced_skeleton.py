"""
What is actually in the six Advanced Skeleton clips, and can they be retargeted?

The `Listening`, `Talk` and `Thinking` exports are on a different rig from the
character: namespace `Robot_Rig_0001`, 92 joints, against the character's
`Robot_All_01` and 65. Nothing binds them by name, so they have never shipped.

Three questions decide whether that is fixable here or has to go back to Maya,
and they are asked in this order because each one can rule the next out:

  1. **What are the bones called?** If the rig carries Advanced Skeleton's
     control naming (`Head_M`, `Wrist_L`) then a name map is possible. If the
     92 joints are controls rather than deform joints, there may be nothing that
     corresponds to a skeleton at all.
  2. **Is there a bind pose?** The idles had none — exported skeleton-only, so
     Blender fell back to frame 1 — and every rest-relative retarget measured
     from the wrong place. If these are the same, the same trap is waiting.
  3. **Are the proportions the same?** Retargeting between rigs of different
     limb lengths needs more than a rotation copy. If the joints sit in the same
     places as the character's, a rotation-only transfer is enough.

    blender --background --python avatar-source/probe_advanced_skeleton.py
"""

import math
import os

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "avatar-source", "animations", "Thinking.fbx")
CHARACTER = os.path.join(ROOT, "frontend", "public", "avatars", "zaram-robo.glb")


def armature_of(objects):
    for o in objects:
        if o.type == "ARMATURE":
            return o
    return None


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(
        filepath=SOURCE, automatic_bone_orientation=False, ignore_leaf_bones=False
    )
    arms = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    print("[as] armatures: %s" % [a.name for a in arms])
    src = armature_of(bpy.context.scene.objects)
    if src is None:
        raise SystemExit("no armature")

    names = [b.name for b in src.data.bones]
    print("[as] %d bones" % len(names))
    print("[as] all bone names:")
    for n in sorted(names):
        print("      %s" % n)

    # Is rest the same as frame 1? If so there is no bind pose, exactly as with
    # the idles, and any rest-relative retarget would measure from a pose the
    # character never held.
    action = src.animation_data.action if src.animation_data else None
    start = int(action.frame_range[0]) if action else 1
    bpy.context.scene.frame_set(start)
    worst = 0.0
    for b in src.data.bones:
        a = (src.matrix_world @ b.matrix_local).to_quaternion()
        c = (src.matrix_world @ src.pose.bones[b.name].matrix).to_quaternion()
        d = a.rotation_difference(c).angle
        worst = max(worst, min(d, 2 * math.pi - d))
    print("")
    print("[as] rest vs frame %d: worst %.3f deg" % (start, math.degrees(worst)))
    print(
        "[as] %s"
        % (
            "NO BIND POSE — rest is frame 1, same trap as the idles"
            if worst < 0.5
            else "has a real bind pose distinct from frame 1"
        )
    )
    if action:
        print("[as] action %r frames %s" % (action.name, tuple(action.frame_range)))


main()
