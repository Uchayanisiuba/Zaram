"""
Redraw the `thinking` eye cell so it stops looking like a shrunken `open`.

**The complaint and the measurement agree, which is what made this cheap.** The
maintainer's report was that the thinking eyes are too small and throw the face
out of proportion. Measured off the shipped atlas on the 8px lattice, every
other eye cell centres its pair on row 14.5:

    open       rows 10-19   (h 10)   centre 14.5
    blink      rows 14-15   (h  2)   centre 14.5
    listening  rows  9-20   (h 12)   centre 14.5
    thinking   rows 10-15   (h  6)   centre 12.5   <- the odd one out

So `thinking` was doing two things at once: shrinking to 60% of the open eye's
height *and* floating two rows above the line every other frame sits on. The
second is what reads as "not proportional" — a face whose eyes change size is
expressive, a face whose eyes change size *and drift upward* looks misaligned.

**There is no vertical room, and that is the constraint that chose the design.**
The obvious fix is an upward glance, which is the universal thinking gesture and
would have kept the eye's mass intact. It is not available. Read off the GLB,
the eye patch's UV island covers cell rows **9.4 to 20.7** — about eleven usable
rows, and `open` already spends ten of them. A block shifted up would have had
its top row cut off by the island edge, which on screen looks like a broken
sprite rather than a glance. That was measured before it was drawn, because the
same class of mistake has already cost this asset set a session: `happy`'s own
comment records rows being kept above 20 for exactly this reason.

**So the change is horizontal, because that is where the room is.** Full height,
rows 10-19, identical to `open` — the proportion complaint is answered by not
changing the thing that was complained about. Narrowed from 8 dots to 6, which
is a squint: the eye holds its size and closes in from the sides, which reads as
concentration rather than as shrinking. Symmetric, so it cannot be mistaken for
a rendering fault the way an off-centre pair can.

**Not a gaze.** Shifting the pair sideways was drawn and rejected. It reads well
in isolation and it is the wrong thing on this face: nothing else on the visor
moves, so an off-centre pair reads as a misaligned panel first and a glance
second — and `CLAUDE.md` has already removed one gaze feature from this avatar
for a related reason.

Run, then regenerate the runtime atlas beside it:

    py avatar-source/redraw_thinking_eyes.py
    py frontend/public/avatars/face/make_alpha_and_templates.py
"""

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACE = os.path.join(ROOT, "frontend", "public", "avatars", "face")
ATLAS = os.path.join(FACE, "eyes_atlas_4x4.png")

CELL = 256
COLS, ROWS = 4, 4
PITCH = 8
RADIUS = 3
COLOUR = (0x81, 0x8C, 0xF8)
SUPERSAMPLE = 4

#: `thinking` is index 2 in `EYE_CELLS`.
INDEX = 2

#: Rows 10-19, exactly `open`'s band. The whole point of the change.
TOP, HEIGHT = 10, 10
#: Six dots rather than `open`'s eight, closing in by one column each side.
#: `open` runs cols 4-11 and 20-27, so these run 5-10 and 21-26 and the pair
#: stays centred on the cell.
LEFT_COL, RIGHT_COL, WIDTH = 5, 21, 6
#: One dot off each corner, the treatment every other block cell uses. Without
#: it the eye is a hard rectangle and reads as a different family of shape.
TRIM = 1


def cell_origin(index):
    """Top-left pixel of a cell. The atlas is authored bottom-up — see
    `extend_face_atlases.cell_origin`, which this matches deliberately."""
    col, row = index % COLS, index // COLS
    return col * CELL, (ROWS - 1 - row) * CELL


def eye_dots(col0):
    lo, hi = col0, col0 + WIDTH - 1
    for row in range(TOP, TOP + HEIGHT):
        rounded = row < TOP + TRIM or row >= TOP + HEIGHT - TRIM
        for col in range(col0, col0 + WIDTH):
            if rounded and col in (lo, hi):
                continue
            yield row, col


def main():
    img = Image.open(ATLAS).convert("RGBA")
    ox, oy = cell_origin(INDEX)

    s = SUPERSAMPLE
    layer = Image.new("RGBA", (CELL * s, CELL * s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    dots = 0
    for col0 in (LEFT_COL, RIGHT_COL):
        for row, col in eye_dots(col0):
            cx = (col * PITCH + PITCH // 2) * s
            cy = (row * PITCH + PITCH // 2) * s
            r = RADIUS * s
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=COLOUR + (255,))
            dots += 1
    layer = layer.resize((CELL, CELL), Image.LANCZOS)

    cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 255))
    cell.alpha_composite(layer)
    img.paste(cell, (ox, oy))
    img.save(ATLAS)
    print(
        "thinking: %d dots, rows %d-%d, cols %d-%d and %d-%d -> %s"
        % (dots, TOP, TOP + HEIGHT - 1, LEFT_COL, LEFT_COL + WIDTH - 1,
           RIGHT_COL, RIGHT_COL + WIDTH - 1, os.path.basename(ATLAS))
    )
    print("now run frontend/public/avatars/face/make_alpha_and_templates.py")


if __name__ == "__main__":
    main()
