"""
Grow both face atlases to 4x4 and redraw the mouth from the reference sheet.

**Why the mouth was redrawn rather than extended.** The shapes themselves were
the problem, not the vocabulary: the set is still six visemes plus a smile, and
nothing here is invented. A `talk_m`/`talk_w`/`pause` ladder was drawn for the
no-audio fallback and then cut — a mouth that speaks in shapes no phoneme maps to
is a second vocabulary to keep in step with the first, and the visemes already
cover the range. The fallback now walks the real ones.

**The shapes are rounded rectangles, not ellipses, and that is the whole reason
they read cleanly.** A rounded rect lands on the dot lattice exactly. An ellipse
of this size snaps into flat runs with ragged corners and comes out looking like
a smudged box — measured by drawing it that way first. The reference sheet the
maintainer supplied uses rounded rects throughout, which is what gave it away.

**Indices 0-5 are the VRM 1.0 presets and do not move.** `visemeAt` maps ~40 IPA
phonemes onto `aa ih ou ee oh sil`, and those six are what *every* VRM carries.
Adding AW or WIDE OH as new visemes would render on this robot and on nothing a
user brought themselves, so the reference sheet's extra open shapes improved the
art for `aa` and `oh` instead of becoming cells. Everything from index 7 up is
robot-only and driven by state rather than by phonemes.

**Thinking wears the neutral mouth, by the maintainer's decision.** A dedicated
`think` cell was drawn — a short compressed line, since a wave serrates at this
pitch and a centre dip is indistinguishable from a shallow smile — and then cut:
the state already reads through the narrowed eyes and the glow, and a second
near-flat line beside `sil` bought nothing a viewer could name. A cell with no
trigger is a cell that rots, so it is gone rather than dormant.

**What was left out, and it is most of the sheet.** SURPRISED, EXCITED,
SKEPTICAL, CONFUSED, WORRIED, DISAPPOINTED, the frowns, GRIN and BIG SMILE are
emotions the system does not have, and `CLAUDE.md` is explicit that the
embodiment renders state and never mood. Separately and just as decisive: five of
them are the same upward arch differing by a dot or two, and at 8px pitch that
difference does not survive — the thinking wave was drawn three ways and every
version either serrated or collapsed into a shallow smile. They remain good
mascot art, which is a job this asset also has.

**The eyes are regridded, never redrawn.** Their cells carry work this script
must not undo — the narrowed `thinking` eyes among it — so cell N is copied from
its 3x3 position to its 4x4 one and only the new `happy_blink` is drawn. Growing
the mouth forces the eyes to move because `COLS`/`ROWS` are one pair of constants
read by both atlases; keeping one layout is cheaper than threading a per-atlas
lookup through every caller.

Run, then derive the runtime atlases beside it:

    py avatar-source/redraw_face_atlases.py
    py frontend/public/avatars/face/make_alpha_and_templates.py
"""

import json
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACE = os.path.join(ROOT, "frontend", "public", "avatars", "face")
EYES = os.path.join(FACE, "eyes_atlas_4x4.png")
MOUTH = os.path.join(FACE, "mouth_atlas_4x4.png")
MANIFEST = os.path.join(FACE, "manifest.json")

CELL, PITCH, RADIUS, SUPERSAMPLE = 256, 8, 3, 4
LIT = (0x81, 0x8C, 0xF8)
OLD_COLS, OLD_ROWS = 3, 3
COLS, ROWS = 4, 4

#: The mouth patch's UV island covers cell y 80..192 — lattice rows 10..23 and
#: nothing else. Anything drawn outside is silently not rendered, which is what
#: clipped `oh` by 21px before `fix_face_uvs.py` existed.
TOP, BOT, MID, CX = 10, 23, 16, 16

MOUTH_CELLS = [
    "sil", "aa", "ih", "ou", "ee", "oh",   # VRM 1.0 presets — order is fixed
    "smile",                                # the sanctioned idle expression
]
EYE_CELLS = [
    "open", "blink", "thinking", "listening", "swapping", "warming",
    "happy", "happy_blink",
]


def cell_origin(index, cols, rows):
    """Top-left pixel of a cell. Authored bottom-up: cell 0 is the bottom row,
    because glTF's `v` runs downward and `faceAtlas.cellRect` flips for it."""
    col, row = index % cols, index // cols
    return col * CELL, (rows - 1 - row) * CELL


def band(dots):
    return {(r, c) for r, c in dots if TOP <= r <= BOT}


def row(r, c0, c1):
    return {(r, c) for c in range(c0, c1 + 1)}


def curve(c0, rows_):
    return {(r, c0 + i) for i, r in enumerate(rows_)}


def rrect(half_w, half_h, corner=1, cy=MID, flat_top=False):
    """Rounded-rectangle outline — the reference sheet's shape language."""
    left, right = CX - half_w, CX + half_w
    top, bottom = cy - half_h, cy + half_h
    top_cut = 0 if flat_top else corner
    dots = row(top, left + top_cut, right - top_cut)
    dots |= row(bottom, left + corner, right - corner)
    for y in range(top + top_cut, bottom - corner + 1):
        dots.add((y, left))
        dots.add((y, right))
    if corner:
        if not flat_top:
            dots.add((top + 1, left + 1))
            dots.add((top + 1, right - 1))
        dots.add((bottom - 1, left + 1))
        dots.add((bottom - 1, right - 1))
    return band(dots)


MOUTH_SHAPES = {
    # **Two rows, not one.** A single row of dots is a dash: it reads as a
    # dividing line rather than as a closed mouth, which the maintainer called
    # the moment they saw it on the face. The second row gives it lip thickness
    # and the one-dot taper each end gives it corners. Filled rather than
    # outlined, so it cannot be confused with `ih`, which *is* a small opening.
    "sil": row(16, 9, 23) | row(17, 10, 22),
    # Flat top over a rounded jaw, the way the reference draws AH.
    "aa": rrect(6, 3, corner=2, flat_top=True),
    "ih": rrect(5, 1),
    "ou": rrect(3, 3),
    "ee": rrect(7, 1),
    "oh": rrect(3, 5),
    # Flat-bottomed with sharply upturned tips. A plain parabola spends most of
    # its width near the middle and reads as a shallow bowl at this size.
    "smile": curve(9, [14, 16, 17, 18, 18, 18, 18, 18, 18, 18, 18, 17, 16, 14]),
}

#: `happy` narrowed further, for a blink that lands *during* a smile. Without it
#: `smiling` suppresses the blink outright, and a face that stops blinking for
#: the length of a smile reads as frozen rather than warm.
HAPPY_BLINK_ROWS = [17, 16, 16, 15, 15, 16, 16, 17]
HAPPY_BLINK_COLS = [range(4, 12), range(20, 28)]
HAPPY_BLINK_THICKNESS = 2


def happy_blink_dots():
    dots = set()
    for cols in HAPPY_BLINK_COLS:
        for col, top in zip(cols, HAPPY_BLINK_ROWS):
            for r in range(top, top + HAPPY_BLINK_THICKNESS):
                dots.add((r, col))
    return dots


def render(dots):
    s = SUPERSAMPLE
    layer = Image.new("RGBA", (CELL * s, CELL * s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for r, c in dots:
        cx, cy = (c * PITCH + PITCH // 2) * s, (r * PITCH + PITCH // 2) * s
        rr = RADIUS * s
        draw.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=LIT + (255,))
    return layer.resize((CELL, CELL), Image.LANCZOS)


def blank_atlas():
    return Image.new("RGBA", (COLS * CELL, ROWS * CELL), (0, 0, 0, 255))


def paste(atlas, index, dots):
    cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 255))
    cell.alpha_composite(render(dots))
    atlas.paste(cell, cell_origin(index, COLS, ROWS))


def main():
    mouth = blank_atlas()
    for i, name in enumerate(MOUTH_CELLS):
        paste(mouth, i, MOUTH_SHAPES[name])
    mouth.save(MOUTH)

    # **The eye regrid is a one-time migration; the mouth is regenerable.**
    # Running the regrid twice would treat a 4x4 as a 3x3 and scatter every eye
    # into the wrong cell — silently, since the result is still a valid PNG of
    # the right size. So it is detected and skipped rather than refused, which
    # keeps the mouth redrawable without hand-editing this file.
    old = Image.open(EYES).convert("RGBA")
    if old.size == (OLD_COLS * CELL, OLD_ROWS * CELL):
        eyes = blank_atlas()
        for i in range(OLD_COLS * OLD_ROWS):
            sx, sy = cell_origin(i, OLD_COLS, OLD_ROWS)
            eyes.paste(old.crop((sx, sy, sx + CELL, sy + CELL)),
                       cell_origin(i, COLS, ROWS))
        paste(eyes, EYE_CELLS.index("happy_blink"), happy_blink_dots())
        eyes.save(EYES)
        eye_note = "regridded, happy_blink drawn"
    else:
        eye_note = "already %dx%d — left alone" % (COLS, ROWS)

    with open(MANIFEST, encoding="utf8") as fh:
        manifest = json.load(fh)
    for atlas_name, names in (("eyes", EYE_CELLS), ("mouth", MOUTH_CELLS)):
        expressions = {}
        for i, name in enumerate(names):
            col, r = i % COLS, i // COLS
            expressions[name] = {
                "index": i,
                "offset": [col / COLS, (ROWS - 1 - r) / ROWS],
            }
        manifest["atlases"][atlas_name]["expressions"] = expressions
    manifest["repeat"] = [1 / COLS, 1 / ROWS]
    with open(MANIFEST, "w", encoding="utf8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")

    outside = [n for n, d in MOUTH_SHAPES.items()
               if any(r < TOP or r > BOT for r, _ in d)]
    print("mouth: %d cells -> %s" % (len(MOUTH_CELLS), os.path.basename(MOUTH)))
    print("eyes:  %d cells (%s) -> %s"
          % (len(EYE_CELLS), eye_note, os.path.basename(EYES)))
    print("layout: %dx%d, atlas %dpx" % (COLS, ROWS, COLS * CELL))
    print("outside the drawable band:", outside or "none")
    print("now run frontend/public/avatars/face/make_alpha_and_templates.py")


if __name__ == "__main__":
    main()
