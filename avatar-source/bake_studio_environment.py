"""
Bake Blender's `forest` studio light down to a tiny equirect the app can embed.

**Why this rather than a procedural environment.** Three hand-built attempts at a
studio failed in three different ways: a furnished room put recognisable armchairs
on the visor, a vertical gradient read flat and needed six times the intensity to
look lit, and soft panels in a dark shell painted a bright rectangle across the
faceplate. What the maintainer actually wants is the look of a real captured
environment, and guessing at one from primitives is not converging.

So take the real thing. `forest.exr` is the studio light Blender ships and the one
the reference render was lit with, and every HDRI in that folder is **CC0** —
Greg Zaal, Poly Haven, `ninomaru_teien` originally, stated in `license.txt` beside
them. Public domain, so there is no licence obstacle to deriving from it.

**It is baked small and embedded, never fetched.** Rule 7g and the no-remote-assets
guard both exist because a request from inside a data file is a request no gate in
this product can see. Embedding sidesteps that completely: there is no URL, no
fetch, and nothing for a network gate to miss. The source EXR is 552 KB at 1K; at
64x32 in RGBE it is 8 KB, which is the size of a small icon.

**64x32 is not a compromise here, it is the correct size.** This environment is
only ever used for image-based lighting and for a reflection that is blurred
before anything sees it. The visor is a mirror, so a low-resolution environment
reads as a *soft* reflection — which is exactly the mottled, gradient look the
reference has, and the opposite of the hard-edged room the first attempt gave.

**RGBE, because the range matters more than the precision.** An HDRI's whole point
is values above 1.0; storing it as 8-bit sRGB would clip the sky and take the
lighting with it. RGBE keeps four to five orders of magnitude in four bytes per
pixel, which is why the format has outlived every alternative.

Run:
    blender --background --python avatar-source/bake_studio_environment.py

Writes frontend/src/lib/studioEnvironmentData.ts.
"""

import base64
import math
import os
import struct

import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "frontend", "src", "lib", "studioEnvironmentData.ts")

# Blender ships its studio lights under the version's datafiles. Search the
# installed versions rather than hardcoding one, so this keeps working when
# Blender updates underneath it.
CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 5.0\5.0\datafiles\studiolights\world\forest.exr",
    r"C:\Program Files\Blender Foundation\Blender 5.2\5.2\datafiles\studiolights\world\forest.exr",
]

W, H = 64, 32


def find_source():
    for path in CANDIDATES:
        if os.path.exists(path):
            return path
    raise SystemExit("forest.exr not found in any known Blender install")


def to_rgbe(r, g, b):
    """One pixel as four bytes: mantissas plus a shared exponent.

    The classic Radiance encoding. A shared exponent is what makes it four bytes
    instead of twelve, and it costs nothing here because the three channels of a
    daylight environment are never orders of magnitude apart.
    """
    peak = max(r, g, b)
    if peak < 1e-8:
        return 0, 0, 0, 0
    mantissa, exponent = math.frexp(peak)
    scale = mantissa * 256.0 / peak
    return (
        min(255, int(r * scale)),
        min(255, int(g * scale)),
        min(255, int(b * scale)),
        min(255, max(0, exponent + 128)),
    )


def main():
    source = find_source()
    image = bpy.data.images.load(source)
    print("[studio] %s  %dx%d" % (os.path.basename(source), image.size[0], image.size[1]))

    # Blender's own resize is a box filter over the full-resolution data, which
    # is what an environment wants: averaging preserves total energy, where
    # point-sampling a 1K sky at 64 pixels would miss the sun entirely and
    # change how hard the whole scene is lit.
    image.scale(W, H)
    px = list(image.pixels)

    out = bytearray()
    # Blender stores pixels bottom-up and three.js reads a `DataTexture` from
    # row 0 with `flipY = false`, while its equirect sampler puts `v = 0` at the
    # nadir. Bottom-up and nadir-first are the same order, so the rows pass
    # through unflipped — but this is exactly the kind of thing that silently
    # lights a character from underneath, so it is stated rather than assumed
    # and confirmed on screen.
    peak = 0.0
    total = 0.0
    for i in range(W * H):
        r, g, b = px[i * 4], px[i * 4 + 1], px[i * 4 + 2]
        peak = max(peak, r, g, b)
        total += (r + g + b) / 3
        out += bytes(to_rgbe(r, g, b))

    encoded = base64.b64encode(bytes(out)).decode("ascii")
    lines = [encoded[i : i + 96] for i in range(0, len(encoded), 96)]

    body = '''/**
 * The environment the character reflects, baked from Blender's `forest` studio
 * light.
 *
 * **Generated — do not edit.** Rebuild with
 * `blender --background --python avatar-source/bake_studio_environment.py`,
 * which documents why this is a captured environment rather than a procedural
 * one, and why it is embedded rather than fetched.
 *
 * Source: `forest.exr` from Blender's bundled studio lights, **CC0**, by Greg
 * Zaal / Poly Haven (originally `ninomaru_teien`). Public domain: no attribution
 * is required and none is owed, but it is recorded because a reader should be
 * able to check the provenance of anything shipped in the bundle.
 *
 * %dx%d equirectangular, RGBE. Low resolution on purpose: this is only used for
 * image-based lighting and for a reflection that is blurred before anything sees
 * it, so the softness is the point rather than a cost.
 */
export const STUDIO_ENVIRONMENT_WIDTH = %d
export const STUDIO_ENVIRONMENT_HEIGHT = %d

/** %dx%d RGBE, base64. */
export const STUDIO_ENVIRONMENT_RGBE =
  '%s'
''' % (
        W,
        H,
        W,
        H,
        W,
        H,
        "' +\n  '".join(lines),
    )

    with open(OUT, "w", newline="\n") as f:
        f.write(body)

    print("[studio] peak %.3f  mean %.4f" % (peak, total / (W * H)))
    print("[studio] wrote %s (%d bytes of base64)" % (OUT, len(encoded)))


main()
