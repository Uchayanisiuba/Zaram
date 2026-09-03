"""
Derive the transparent runtime atlases and the UV-mapping templates.

Two outputs, for two different jobs.

**The `_alpha` atlases are the runtime texture.** RGB is copied through
untouched and alpha is taken from the pixel's own brightness, so the black
background becomes transparent while every lit dot keeps exactly the colour it
was authored with. That last part matters: the `swapping` frame is dimmed in
RGB (#2D3157) rather than in alpha, deliberately, because the runtime composites
these additively and ignores the alpha channel entirely. Dimming with alpha
would render at full brightness — a bug this asset set already had once.

**The `_uv_template` files are for Maya and Blender.** One cell, at cell
resolution, with every frame of that atlas overlaid so the UV island can be
sized to hold all of them at once. Sizing against a single frame is what caused
the mouth island to clip its own vowels: `sil` is one dot row tall and `oh` is
fourteen, and an island fitted to the first cannot show the second.

Run from this directory:  python make_alpha_and_templates.py
"""

from PIL import Image, ImageDraw
import numpy as np
import json
import os

CELL = 256
COLS, ROWS = 4, 4
LIT = (129, 140, 248)


def alpha_from_luminance(path: str, out: str) -> None:
    """Black background to transparency, colours untouched."""
    rgb = np.array(Image.open(path).convert("RGB")).astype(np.uint16)
    # The brightest channel tracks the anti-aliased falloff of a dot better
    # than a weighted luminance does, because these dots are a single hue and
    # a perceptual weighting would thin the blue channel that carries them.
    a = rgb.max(axis=2)
    # Normalise so a fully lit dot is opaque. The dim `swapping` frame peaks
    # well below the lit colour, so scaling by its own max would erase the
    # distinction between dim and bright; scale by the palette instead.
    a = np.clip(a.astype(float) / max(LIT) * 255.0, 0, 255).astype(np.uint8)
    out_img = np.dstack([rgb.astype(np.uint8), a])
    Image.fromarray(out_img, mode="RGBA").save(out)
    print(f"  {out}  ({(a > 0).sum()} non-transparent px)")


def union_bbox(atlas: str) -> tuple[int, int, int, int]:
    """The smallest box inside one cell that contains every frame's content."""
    a = np.array(Image.open(atlas).convert("RGB")).astype(int)
    x0, y0, x1, y1 = CELL, CELL, 0, 0
    for r in range(ROWS):
        for c in range(COLS):
            sub = a[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            ys, xs = np.nonzero(sub.sum(2) > 18)
            if len(xs) == 0:
                continue
            x0, y0 = min(x0, xs.min()), min(y0, ys.min())
            x1, y1 = max(x1, xs.max()), max(y1, ys.max())
    return int(x0), int(y0), int(x1), int(y1)


def template(atlas: str, out: str, label: str) -> tuple[int, int, int, int]:
    """One cell, transparent, with every frame overlaid and the cell edge drawn."""
    a = np.array(Image.open(atlas).convert("RGB")).astype(int)
    stack = np.zeros((CELL, CELL, 3), dtype=int)
    for r in range(ROWS):
        for c in range(COLS):
            stack = np.maximum(stack, a[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL])

    alpha = np.clip(stack.max(axis=2).astype(float) / max(LIT) * 255.0, 0, 255)
    # Overlaid frames are guides, not content — held well below full so the
    # cell border and the union box stay the most legible things in the image.
    img = Image.fromarray(
        np.dstack([stack.astype(np.uint8), (alpha * 0.55).astype(np.uint8)]), mode="RGBA"
    )

    d = ImageDraw.Draw(img)
    # The cell edge: this is what the UV island must span, corner to corner.
    d.rectangle([0, 0, CELL - 1, CELL - 1], outline=(255, 96, 96, 255), width=2)
    # Centre cross, for aligning the island against the face's midline.
    d.line([CELL // 2, 0, CELL // 2, CELL - 1], fill=(255, 96, 96, 90))
    d.line([0, CELL // 2, CELL - 1, CELL // 2], fill=(255, 96, 96, 90))

    box = union_bbox(atlas)
    d.rectangle(list(box), outline=(120, 255, 160, 200), width=1)
    img.save(out)
    w, h = box[2] - box[0] + 1, box[3] - box[1] + 1
    print(f"  {out}  {label} union {w}x{h}px, aspect {w / h:.3f}:1")
    return box


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("runtime atlases with alpha:")
    alpha_from_luminance("eyes_atlas_4x4.png", "eyes_atlas_4x4_alpha.png")
    alpha_from_luminance("mouth_atlas_4x4.png", "mouth_atlas_4x4_alpha.png")

    print("UV templates:")
    eyes_box = template("eyes_atlas_4x4.png", "eyes_uv_template.png", "eyes")
    mouth_box = template("mouth_atlas_4x4.png", "mouth_uv_template.png", "mouth")

    def rec(box):
        w, h = box[2] - box[0] + 1, box[3] - box[1] + 1
        return {"union_px": [box[0], box[1], box[2], box[3]],
                "union_size_px": [w, h],
                "union_aspect": round(w / h, 4)}

    with open("uv_guide.json", "w") as f:
        json.dump({
            "cell_px": CELL,
            "instruction": (
                "Map each face patch's UV island to the FULL cell, corner to corner "
                "(the red border in the template). Keep the patch's world aspect "
                "square, because the cell is square — a non-square patch stretches "
                "the dot grid. The union box shows where content actually falls; "
                "everything outside it is transparent margin and is meant to be."
            ),
            "eyes": rec(eyes_box),
            "mouth": rec(mouth_box),
        }, f, indent=2)
    print("  uv_guide.json")
