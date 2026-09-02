"""
Grow the face atlases from 3x2 to 3x3 and draw the idle smile into the new row.

**Why the layout had to change.** Both atlases were 3x2 with all six cells
spoken for — the mouth's six are visemes, every one of which `visemeAt` can emit
mid-sentence, so none could be given up. A seventh expression needs a seventh
cell, and a third row is the cheapest way to get one: `COLS` stays at 3, the cell
stays 256px square, and the UV islands do not move at all, because a mesh's
island is normalised inside its cell and `repeat` scales it there. Only `ROWS`,
the atlas height, and the manifest change.

The eyes get the third row too, empty. Keeping one layout for both atlases keeps
`cellRect` a single pair of constants instead of a per-atlas lookup threaded
through every caller, and three spare eye cells is a cheaper thing to carry than
that indirection.

**The smile is generated, not drawn by hand**, because the manifest records
exactly how these sprites were made — 32x32 grid, 8px pitch, 3px dot radius,
`#818cf8`, supersampled 4x — so a generated arc is indistinguishable from an
authored one. Doing it by eye in an image editor would put the dots off-lattice,
and an LED face with one row of dots off the grid reads as a rendering fault.

Run once. It rewrites the atlas sources and the manifest; then run
`make_alpha_and_templates.py` beside them to derive the runtime alpha atlases,
the UV templates and `uv_guide.json`.

    py avatar-source/extend_face_atlases.py
    py frontend/public/avatars/face/make_alpha_and_templates.py
"""

import json
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACE = os.path.join(ROOT, "frontend", "public", "avatars", "face")

CELL = 256
COLS = 3
OLD_ROWS = 2
NEW_ROWS = 3

# Read from the manifest rather than restated, so the smile cannot drift from
# the sprites it sits beside.
MANIFEST = os.path.join(FACE, "manifest.json")

MOUTH_CELLS = ["sil", "aa", "ih", "ou", "ee", "oh", "smile"]
EYE_CELLS = ["open", "blink", "thinking", "listening", "swapping", "warming"]


def cell_origin(index, rows):
    """Top-left pixel of a cell, in the same convention `cellRect` uses.

    The atlas is authored bottom-up and glTF's `v` runs downward, so cell 0 lives
    in the *bottom* row of the image. `faceAtlas.cellRect` flips the row for this
    reason and so must anything that writes the file, or the two disagree and
    every rest state lands on the wrong row.
    """
    col, row = index % COLS, index // COLS
    return col * CELL, (rows - 1 - row) * CELL


def regrid(src, rows_before, rows_after):
    """Same cells, same indices, taller image."""
    out = Image.new("RGBA", (COLS * CELL, rows_after * CELL), (0, 0, 0, 255))
    for index in range(COLS * rows_before):
        sx, sy = cell_origin(index, rows_before)
        dx, dy = cell_origin(index, rows_after)
        out.paste(src.crop((sx, sy, sx + CELL, sy + CELL)), (dx, dy))
    return out


def draw_smile(img, index, pitch, radius, colour, supersample):
    """An arc of lit dots, on the same lattice as every other frame.

    Ten dots, symmetric about the cell's midline, curving down in the middle —
    a `U`, because in image space `y` grows downward and a smile's corners are
    its highest points. The offsets come from a parabola rounded to whole lattice
    rows: a smooth curve sampled off-grid would put dots between the holes of a
    dot-matrix panel, which is the one thing that would give it away.
    """
    ox, oy = cell_origin(index, NEW_ROWS)

    # Columns 9..22 centre the arc on the cell: their dot centres run 76..180,
    # symmetric about 128. **Fourteen dots, not ten** — the first pass was
    # narrower than `sil`'s twelve, which read as a small pinched mouth rather
    # than a smile. A smile should be at least as wide as the neutral line it
    # replaces, or the face looks like it shrank.
    cols = list(range(9, 23))
    # **Flat-bottomed with sharply upturned tips**, matching the key art rather
    # than a plain parabola. A parabola spends most of its width near the middle
    # and turns up only at the very ends, which at this size reads as a shallow
    # bowl. The reference smile holds a level base for two thirds of its width
    # and lifts hard in the last three dots — that lift is what the eye reads as
    # a smile rather than as a curved line.
    top_row = 14
    offsets = [0, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 3, 2, 0]

    s = supersample
    layer = Image.new("RGBA", (CELL * s, CELL * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for col, off in zip(cols, offsets):
        cx = (col * pitch + pitch // 2) * s
        cy = ((top_row + off) * pitch + pitch // 2) * s
        r = radius * s
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour + (255,))
    layer = layer.resize((CELL, CELL), Image.LANCZOS)

    cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 255))
    cell.alpha_composite(layer)
    img.paste(cell, (ox, oy))


def main():
    manifest = json.load(open(MANIFEST))
    pitch = manifest["pitch"]
    radius = manifest["dot_radius"]
    supersample = manifest["supersample"]
    lit = manifest["lit_colour"].lstrip("#")
    colour = tuple(int(lit[i : i + 2], 16) for i in (0, 2, 4))
    print("[face] lattice pitch %d radius %d colour %s" % (pitch, radius, manifest["lit_colour"]))

    for name, cells in (("mouth", MOUTH_CELLS), ("eyes", EYE_CELLS)):
        old = os.path.join(FACE, "%s_atlas_3x2.png" % name)
        new = os.path.join(FACE, "%s_atlas_3x3.png" % name)
        # **Re-runnable.** The 3x2 -> 3x3 migration happens once, but the smile
        # is a drawing and drawings get revised; a script that only worked on a
        # pristine tree would mean hand-editing a PNG the second time.
        if os.path.exists(new):
            out = Image.open(new).convert("RGBA")
            note = "redrew"
        else:
            src = Image.open(old).convert("RGBA")
            if src.size != (COLS * CELL, OLD_ROWS * CELL):
                raise SystemExit("%s is %s, expected %s" % (old, src.size, (COLS * CELL, OLD_ROWS * CELL)))
            out = regrid(src, OLD_ROWS, NEW_ROWS)
            os.remove(old)
            note = "migrated"
        if name == "mouth":
            draw_smile(out, cells.index("smile"), pitch, radius, colour, supersample)
        out.save(new)
        print("[face] %s %s (%d cells)" % (note, os.path.basename(new), len(cells)))

        entry = manifest["atlases"][name]
        entry["filename"] = "%s_atlas_3x3.png" % name
        entry["size"] = [COLS * CELL, NEW_ROWS * CELL]
        entry["expressions"] = {}
        for i, cell in enumerate(cells):
            col, row = i % COLS, i // COLS
            entry["expressions"][cell] = {
                "index": i,
                "offset": [col / COLS, (NEW_ROWS - 1 - row) / NEW_ROWS],
            }

    manifest["repeat"] = [1 / COLS, 1 / NEW_ROWS]
    manifest["version"] = "zaram-led-face-v4"
    json.dump(manifest, open(MANIFEST, "w"), indent=2, sort_keys=True)
    print("[face] manifest rewritten: repeat %s" % manifest["repeat"])
    print("[face] now run frontend/public/avatars/face/make_alpha_and_templates.py")


main()
