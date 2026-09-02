"""
Fit each face patch's UV island to the sprites it has to show.

**The defect.** The mouth island was sized against `sil`, which is one dot row
tall, and `oh` is fourteen. An island fitted to the first cannot show the second:
21 pixels of `oh` fall outside the window and are simply not drawn. It is only
visible while the character speaks, which nobody has watched yet, so it would
have shipped.

**Why the obvious fix is half a fix.** Growing the island downward in `v` closes
the clipping and makes the distortion worse, because the patch is not the shape
of the island. Three quantities have to agree and only two of them are usually
looked at:

  * the island must **contain** every sprite, or frames clip;
  * the island's **texel aspect** must match the patch's world aspect, or the dot
    grid renders stretched;
  * and the island must stay **inside its cell**, or it samples the neighbour.

Fitting `v` to the content and then choosing the `u` span that makes the aspect
land on 1.0 satisfies all three at once, and it is available here because the
content does not fill the cell horizontally -- there is transparent margin either
side to expand into. That costs nothing and needs no change to the mesh, which is
the alternative and means another Blender round on an 11.2 MB character.

**It edits the UV buffer in place rather than re-exporting.** Round-tripping the
character through Blender to move four texture coordinates risks the two things
this file cannot afford to lose: the face panel material names, which are how the
renderer finds the panels at all, and the bone rest pose, which the animation
clips are now baked against. Patching the accessor leaves every other byte alone.

    py avatar-source/fix_face_uvs.py            # measure, change nothing
    py avatar-source/fix_face_uvs.py --apply    # write the corrected UVs

Verify after applying with `node frontend/scripts/check-rig-agreement.mjs` (the
rest pose must be untouched) and by reloading the app -- the load log reports the
texel aspect it measures.
"""

import json
import os
import struct
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLB = os.path.join(ROOT, "frontend", "public", "avatars", "zaram-robo.glb")
FACE = os.path.join(ROOT, "frontend", "public", "avatars", "face")

CELL = 256
COLS, ROWS = 3, 3
ATLAS_W, ATLAS_H = COLS * CELL, ROWS * CELL

# Cell order within each atlas, matching `faceAtlas.ts`. Index 0 is the rest
# state on both, which is why it is first and why sizing an island against it
# is such an easy mistake to make.
PANELS = {
    "mouth": {
        "atlas": "mouth_atlas_3x3_alpha.png",
        "cells": ["sil", "aa", "ih", "ou", "ee", "oh", "smile"],
        "material": "mouth",
        "write": True,
    },
    "eyes": {
        "atlas": "eyes_atlas_3x3_alpha.png",
        "cells": ["open", "blink", "thinking", "listening", "swapping", "warming", "happy"],
        "material": "eye",
        # **Measured and deliberately left alone.** The eye island clips three
        # frames by 3px, and closing that would pull its texel aspect from 1.005
        # to 0.942 -- trading a half-percent error for a six-percent one to
        # recover a single dot row at the edge of a 96px sprite. The eyes are the
        # panel that carries state; a visibly stretched dot grid costs more than
        # 3px does. Reported every run so the decision stays visible rather than
        # becoming an omission nobody remembers making.
        "write": False,
    },
}


# --------------------------------------------------------------------- glTF


def read_glb(path):
    """Split a GLB into its JSON and BIN chunks."""
    raw = bytearray(open(path, "rb").read())
    assert struct.unpack_from("<I", raw, 0)[0] == 0x46546C67, "not a GLB"
    offset = 12
    js, bin_at, bin_len = None, None, None
    while offset < len(raw):
        length, kind = struct.unpack_from("<II", raw, offset)
        body = offset + 8
        if kind == 0x4E4F534A:
            js = json.loads(bytes(raw[body : body + length]).decode("utf-8"))
        elif kind == 0x004E4942:
            bin_at, bin_len = body, length
        offset = body + length + (-length % 4)
    return raw, js, bin_at, bin_len


def accessor_span(gltf, index):
    """Absolute byte offset, stride and count for a VEC2 float accessor."""
    acc = gltf["accessors"][index]
    assert acc["componentType"] == 5126 and acc["type"] in ("VEC2", "VEC3"), acc
    view = gltf["bufferViews"][acc["bufferView"]]
    comps = 2 if acc["type"] == "VEC2" else 3
    stride = view.get("byteStride") or comps * 4
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    return start, stride, acc["count"], comps


def read_vectors(raw, bin_at, gltf, index):
    start, stride, count, comps = accessor_span(gltf, index)
    base = bin_at + start
    out = np.empty((count, comps), dtype=np.float32)
    for i in range(count):
        out[i] = struct.unpack_from("<" + "f" * comps, raw, base + i * stride)
    return out


def write_uvs(raw, bin_at, gltf, index, uvs):
    start, stride, count, _ = accessor_span(gltf, index)
    base = bin_at + start
    for i in range(count):
        struct.pack_into("<ff", raw, base + i * stride, float(uvs[i][0]), float(uvs[i][1]))


def find_panel(gltf, material_hint):
    """The primitive whose material name mentions this panel."""
    for mesh in gltf.get("meshes", []):
        for prim in mesh.get("primitives", []):
            mat = prim.get("material")
            if mat is None:
                continue
            name = (gltf["materials"][mat].get("name") or "").lower()
            if material_hint in name:
                return prim, gltf["materials"][mat].get("name")
    return None, None


# --------------------------------------------------------------------- atlas


def cell_box(index):
    """Pixel box of one cell in the PNG.

    **glTF `v` runs downward and the atlas was authored bottom-up.** `GLTFLoader`
    sets `flipY = false`, so `v = 0` is the top pixel row, while cell 0 was drawn
    in the bottom row of the image. `cellRect` in `faceAtlas.ts` flips the row for
    exactly this reason, and the same flip has to happen here or every
    measurement lands one row out -- which reads as a driver bug rather than a
    coordinate-space one.
    """
    col, row = index % COLS, index // COLS
    x = col * CELL
    y = (ROWS - 1 - row) * CELL
    return x, y, x + CELL, y + CELL


def content_rows(atlas_path, count):
    """Where the lit pixels actually are, per cell, in cell-local pixels."""
    img = np.array(Image.open(atlas_path).convert("RGBA"))
    out = []
    for i in range(count):
        x0, y0, x1, y1 = cell_box(i)
        cell = img[y0:y1, x0:x1, 3]
        ys, xs = np.nonzero(cell > 8)
        if len(ys) == 0:
            out.append(None)
            continue
        out.append((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    return out


# --------------------------------------------------------------------- main


def main():
    apply = "--apply" in sys.argv
    raw, gltf, bin_at, _ = read_glb(GLB)
    changed = False

    for panel, spec in PANELS.items():
        prim, mat_name = find_panel(gltf, spec["material"])
        if prim is None:
            print("[uv] %s: no primitive found" % panel)
            continue

        uv_index = prim["attributes"]["TEXCOORD_0"]
        pos_index = prim["attributes"]["POSITION"]
        uvs = read_vectors(raw, bin_at, gltf, uv_index)
        pos = read_vectors(raw, bin_at, gltf, pos_index)

        u0, v0 = float(uvs[:, 0].min()), float(uvs[:, 1].min())
        u1, v1 = float(uvs[:, 0].max()), float(uvs[:, 1].max())

        # The patch's world proportions, measured the way the renderer measures
        # them: the two largest axes of the local bounding box, because a face
        # panel is a flat quad and its third axis is noise.
        extent = sorted((pos.max(axis=0) - pos.min(axis=0)).tolist(), reverse=True)
        world_w, world_h = extent[0], extent[1]

        boxes = content_rows(os.path.join(FACE, spec["atlas"]), len(spec["cells"]))
        need_x0 = min(b[0] for b in boxes if b)
        need_y0 = min(b[1] for b in boxes if b)
        need_x1 = max(b[2] for b in boxes if b)
        need_y1 = max(b[3] for b in boxes if b)

        island_x0, island_y0 = u0 * CELL, v0 * CELL
        island_x1, island_y1 = u1 * CELL, v1 * CELL

        def aspect(px0, py0, px1, py1):
            return ((px1 - px0) / world_w) / ((py1 - py0) / world_h)

        print("")
        print("[uv] %s (material %s, %d verts)" % (panel, mat_name, len(uvs)))
        print("  patch world %.4f x %.4f (aspect %.3f)" % (world_w, world_h, world_w / world_h))
        print(
            "  island   px x %.1f..%.1f  y %.1f..%.1f  (%.1f x %.1f) texel aspect %.3f"
            % (
                island_x0, island_x1, island_y0, island_y1,
                island_x1 - island_x0, island_y1 - island_y0,
                aspect(island_x0, island_y0, island_x1, island_y1),
            )
        )
        print(
            "  content  px x %d..%d  y %d..%d  (%d x %d)"
            % (need_x0, need_x1, need_y0, need_y1, need_x1 - need_x0, need_y1 - need_y0)
        )
        for name, b in zip(spec["cells"], boxes):
            if not b:
                continue
            clip_top = max(0, island_y0 - b[1])
            clip_bottom = max(0, b[3] - island_y1)
            clip_left = max(0, island_x0 - b[0])
            clip_right = max(0, b[2] - island_x1)
            worst = max(clip_top, clip_bottom, clip_left, clip_right)
            if worst > 0.5:
                print(
                    "    %-10s rows %d-%d cols %d-%d  CLIPS %.0fpx"
                    % (name, b[1], b[3], b[0], b[2], worst)
                )

        # Target island. `v` is fitted to the content, because that is what
        # closes the clipping and there is nothing to gain from margin. `u` is
        # then chosen so the texel aspect lands on 1.0 -- centred on the content,
        # expanding into the transparent margin either side -- and clamped to the
        # cell so it can never sample the neighbouring frame.
        ty0, ty1 = float(need_y0), float(need_y1)
        want_w = (ty1 - ty0) * (world_w / world_h)
        centre = (need_x0 + need_x1) / 2
        tx0, tx1 = centre - want_w / 2, centre + want_w / 2
        if tx0 < 0:
            tx0, tx1 = 0.0, min(float(CELL), want_w)
        if tx1 > CELL:
            tx1, tx0 = float(CELL), max(0.0, CELL - want_w)

        fits = tx0 <= need_x0 and tx1 >= need_x1
        print(
            "  target   px x %.1f..%.1f  y %.1f..%.1f  (%.1f x %.1f) texel aspect %.3f%s"
            % (
                tx0, tx1, ty0, ty1, tx1 - tx0, ty1 - ty0,
                aspect(tx0, ty0, tx1, ty1),
                "" if fits else "  -- WARNING: narrower than the content",
            )
        )

        moved = max(
            abs(tx0 - island_x0), abs(tx1 - island_x1),
            abs(ty0 - island_y0), abs(ty1 - island_y1),
        )
        if moved < 0.5:
            print("  already correct — nothing to do")
            continue
        if not spec.get("write"):
            print("  measured only — this panel is deliberately not rewritten")
            continue
        if not apply:
            print("  (run with --apply to write it)")
            continue

        # Remap each vertex's UV from the old island box onto the new one. A
        # linear remap keeps the sprite's internal proportions and moves only the
        # window, which is the whole intent -- the patch's own geometry is not
        # touched.
        span_u = (u1 - u0) or 1.0
        span_v = (v1 - v0) or 1.0
        new = np.empty_like(uvs)
        new[:, 0] = (tx0 + ((uvs[:, 0] - u0) / span_u) * (tx1 - tx0)) / CELL
        new[:, 1] = (ty0 + ((uvs[:, 1] - v0) / span_v) * (ty1 - ty0)) / CELL
        write_uvs(raw, bin_at, gltf, uv_index, new)
        changed = True
        print("  applied")

    if changed:
        open(GLB, "wb").write(bytes(raw))
        print("")
        print("[uv] wrote %s" % GLB)
        print("[uv] verify: node frontend/scripts/check-rig-agreement.mjs, then reload the app")


main()
