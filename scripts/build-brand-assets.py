"""Generate every Zaram brand asset from one definition of the mark.

The geometry below was **traced from the brand sheet**, not eyeballed:
`Logo_Image/Zaram_Logo_Detailes and uses.png`, hero glyph at (212,137)-(446,316),
thresholded to a mask, boundary-followed, and reduced with Ramer-Douglas-Peucker
until each plane was a handful of corners. A geometric mark should reduce to a
handful of corners, and this one reduces to six and eight — which is the check
that the trace found the real shape rather than a blurred approximation of it.

Three things that trace corrected, and they are why it was worth doing:

* **The mark is 1.31:1, not square.** An earlier reconstruction assumed a square
  glyph and was visibly too tall.
* **It is two interlocking planes, not three slabs.** The upper plane carries
  the top bar and the descending stroke; the lower carries the bottom bar and
  its own. They never touch — the diagonal gap between them is the whole
  character of the mark, and a three-slab version loses it.
* **The gradient ends in cyan, not blue.** #A853E2 → #4BADE6, sampled from the
  extreme pixels along the gradient axis rather than guessed.

Everything — SVG, PNG, ICO — is emitted from this one definition, so a favicon,
an app icon and an installer icon cannot drift into being three logos.

    .venv/Scripts/python.exe scripts/build-brand-assets.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
BRAND_DIR = ROOT / "frontend" / "public" / "brand"
#: Contact sheets go beside the source, never into `public/`. Everything under
#: `public/` is built into `dist` and shipped, and a diagnostic image riding
#: along in the installer is the same class of mistake as shipping a database.
PREVIEW_DIR = ROOT / "Logo_Image"
PUBLIC_DIR = ROOT / "frontend" / "public"
BUILD_DIR = ROOT / "build"

# --------------------------------------------------------------------------- #
# The mark, in a 0..131 x 0..100 box. Height is the unit; width follows the
# traced aspect ratio of 1.3073.
# --------------------------------------------------------------------------- #

ASPECT = 1.3073
BOX_W = 100.0 * ASPECT   # 130.73
BOX_H = 100.0

#: Top bar and the stroke descending from it.
PLANE_UPPER = [
    (31.84, 0.00), (130.17, 0.56), (83.80, 62.01),
    (64.25, 62.01), (94.41, 20.11), (17.32, 19.55),
]

#: The stroke rising into the bottom bar. Never touches the upper plane.
PLANE_LOWER = [
    (46.93, 37.43), (67.04, 37.43), (36.31, 79.89), (94.41, 79.89),
    (108.38, 62.57), (130.17, 62.57), (102.23, 99.44), (0.00, 99.44),
]

SHAPES = [PLANE_UPPER, PLANE_LOWER]

#: Sampled from the hero glyph's extreme pixels along the gradient axis.
GRADIENT_FROM = (168, 83, 226)   # #A853E2
GRADIENT_TO = (75, 173, 230)     # #4BADE6

#: The app-icon tile, sampled from the brand sheet's own tile.
TILE_BG_TOP = (36, 22, 64)       # #241640
TILE_BG_BOTTOM = (16, 10, 34)    # #100A22

#: Flat mark for light backgrounds, where the gradient loses contrast.
INK = (18, 21, 28)               # #12151C


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def gradient_image(size: int, start, end, angle_deg: float = 45.0) -> Image.Image:
    """A linear gradient along `angle_deg`.

    Per-pixel rather than banded: at favicon sizes the mark is a few dozen
    pixels across and banding shows as stripes.
    """
    img = Image.new("RGB", (size, size))
    px = img.load()
    rad = math.radians(angle_deg)
    dx, dy = math.cos(rad), math.sin(rad)
    span = abs(dx) * size + abs(dy) * size
    for y in range(size):
        for x in range(size):
            t = min(1.0, max(0.0, (x * dx + y * dy) / span))
            px[x, y] = (
                int(lerp(start[0], end[0], t)),
                int(lerp(start[1], end[1], t)),
                int(lerp(start[2], end[2], t)),
            )
    return img


def mark_mask(size: int, coverage: float = 1.0, supersample: int = 4) -> Image.Image:
    """The glyph as an alpha mask on a square canvas, centred.

    The mark is wider than tall, so a square output letterboxes it vertically.
    `coverage` is the fraction of the canvas width the glyph spans.

    Supersampled and downsampled rather than relying on polygon antialiasing:
    these are hard corners at shallow angles, and an aliased corner at 16px is
    the difference between a mark and a smudge.
    """
    big = size * supersample
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)

    scale = (big * coverage) / BOX_W
    off_x = (big - BOX_W * scale) / 2
    off_y = (big - BOX_H * scale) / 2

    for shape in SHAPES:
        draw.polygon([(off_x + x * scale, off_y + y * scale) for x, y in shape], fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def render_mark(size: int, solid=None, coverage: float = 1.0) -> Image.Image:
    mask = mark_mask(size, coverage=coverage)
    fill = (
        Image.new("RGB", (size, size), solid)
        if solid is not None
        else gradient_image(size, GRADIENT_FROM, GRADIENT_TO)
    )
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(fill, (0, 0), mask)
    return out


def rounded_tile(size: int) -> Image.Image:
    """Dark rounded square with the mark inset.

    The inset is not decoration: a glyph running to the edge is clipped by every
    platform that applies its own mask, and Windows rounds taskbar icons.
    """
    radius = int(size * 0.22)
    tile = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    bg = gradient_image(size, TILE_BG_TOP, TILE_BG_BOTTOM, angle_deg=90.0)
    corner = Image.new("L", (size, size), 0)
    ImageDraw.Draw(corner).rounded_rectangle([0, 0, size - 1, size - 1], radius, fill=255)
    tile.paste(bg, (0, 0), corner)
    tile.alpha_composite(render_mark(size, coverage=0.68))
    return tile


# --------------------------------------------------------------------------- #
# SVG, emitted from the same polygons so vector and raster cannot disagree.
# --------------------------------------------------------------------------- #

def svg(fill: str, gradient: bool) -> str:
    paths = "\n".join(
        '    <polygon points="{}" />'.format(" ".join(f"{x},{y}" for x, y in shape))
        for shape in SHAPES
    )
    defs = ""
    if gradient:
        a = "#%02X%02X%02X" % GRADIENT_FROM
        b = "#%02X%02X%02X" % GRADIENT_TO
        defs = (
            "  <defs>\n"
            '    <linearGradient id="zaram" x1="0" y1="0" x2="1" y2="1">\n'
            f'      <stop offset="0%" stop-color="{a}" />\n'
            f'      <stop offset="100%" stop-color="{b}" />\n'
            "    </linearGradient>\n"
            "  </defs>\n"
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BOX_W:.2f} {BOX_H:.2f}" '
        'role="img" aria-label="Zaram">\n'
        f"{defs}"
        f'  <g fill="{fill}">\n{paths}\n  </g>\n'
        "</svg>\n"
    )


def tile_svg(coverage: float = 0.68, radius: float = 22.0) -> str:
    """The app icon as vector: rounded square, gradient ground, mark inset.

    A PNG would do at 512px and would not at 32px, which is the size the
    interface actually draws it — so the tile is emitted as SVG for the same
    reason the mark is.

    `coverage` and `radius` are kept in step with `rounded_tile()` by being the
    same numbers; if they drift, the icon on the taskbar and the icon in the
    chrome stop being the same logo.
    """
    scale = (100.0 * coverage) / BOX_W
    off_x = (100.0 - BOX_W * scale) / 2
    off_y = (100.0 - BOX_H * scale) / 2
    paths = "\n".join(
        '      <polygon points="{}" />'.format(" ".join(f"{x},{y}" for x, y in shape))
        for shape in SHAPES
    )
    bg_a = "#%02X%02X%02X" % TILE_BG_TOP
    bg_b = "#%02X%02X%02X" % TILE_BG_BOTTOM
    fg_a = "#%02X%02X%02X" % GRADIENT_FROM
    fg_b = "#%02X%02X%02X" % GRADIENT_TO
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
        'role="img" aria-label="Zaram">\n'
        "  <defs>\n"
        '    <linearGradient id="tile" x1="0" y1="0" x2="0" y2="1">\n'
        f'      <stop offset="0%" stop-color="{bg_a}" />\n'
        f'      <stop offset="100%" stop-color="{bg_b}" />\n'
        "    </linearGradient>\n"
        '    <linearGradient id="glyph" x1="0" y1="0" x2="1" y2="1">\n'
        f'      <stop offset="0%" stop-color="{fg_a}" />\n'
        f'      <stop offset="100%" stop-color="{fg_b}" />\n'
        "    </linearGradient>\n"
        "  </defs>\n"
        f'  <rect width="100" height="100" rx="{radius}" fill="url(#tile)" />\n'
        f'  <g transform="translate({off_x:.3f} {off_y:.3f}) scale({scale:.5f})" '
        'fill="url(#glyph)">\n'
        f"{paths}\n"
        "  </g>\n"
        "</svg>\n"
    )


def main() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    written: list[tuple[str, int]] = []

    def write_bytes(path: Path, data: bytes) -> None:
        path.write_bytes(data)
        written.append((str(path.relative_to(ROOT)), len(data)))

    def save(path: Path, img: Image.Image, **kw) -> None:
        img.save(path, **kw)
        written.append((str(path.relative_to(ROOT)), path.stat().st_size))

    # The app icon, and what the interface's top-left corner draws.
    write_bytes(BRAND_DIR / "zaram-icon.svg", tile_svg().encode())
    write_bytes(BRAND_DIR / "zaram-mark.svg", svg("url(#zaram)", True).encode())
    write_bytes(BRAND_DIR / "zaram-mark-light.svg", svg("#%02X%02X%02X" % INK, False).encode())
    # The favicon is the bare glyph. Browsers draw it at 16px on their own
    # background, where a dark tile is a dark square with a smudge in it.
    write_bytes(PUBLIC_DIR / "favicon.svg", svg("url(#zaram)", True).encode())

    save(BRAND_DIR / "zaram-icon-512.png", rounded_tile(512), optimize=True)
    save(BRAND_DIR / "zaram-mark-512.png", render_mark(512), optimize=True)

    # Every size inside one .ico. Letting Windows downscale a single 256px
    # image is what makes taskbar icons look muddy.
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_path = BUILD_DIR / "icon.ico"
    rounded_tile(256).save(ico_path, format="ICO", sizes=[(s, s) for s in ico_sizes])
    written.append((str(ico_path.relative_to(ROOT)), ico_path.stat().st_size))

    # A contact sheet, because a logo deserves to be looked at rather than
    # assumed correct — the same scepticism the removed gaze feature earned.
    pad, sizes = 20, (16, 32, 48, 64, 128)
    sheet = Image.new("RGBA", (780, 360), (18, 21, 28, 255))
    x = pad
    for s in sizes:
        sheet.alpha_composite(rounded_tile(s), (x, pad + (128 - s) // 2))
        x += s + pad
    x = pad
    for s in sizes:
        sheet.alpha_composite(render_mark(s), (x, 180 + (128 - s) // 2))
        x += s + pad
    light = Image.new("RGBA", (240, 340), (245, 245, 247, 255))
    light.alpha_composite(render_mark(180, solid=INK), (30, 80))
    sheet.alpha_composite(light, (540, 10))
    save(PREVIEW_DIR / "_preview.png", sheet, optimize=True)

    print("Brand assets generated:\n")
    for name, size in written:
        print(f"  {size/1024:8.1f} KB  {name}")
    print("\nTraced from Logo_Image/. Check Logo_Image/_preview.png.")


if __name__ == "__main__":
    main()
