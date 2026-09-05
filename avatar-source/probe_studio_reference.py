"""
Measure Blender's `forest` studio light so it can be rebuilt procedurally.

**The point is to copy the numbers, not the pixels.** Embedding the baked HDRI
works and is only 8 KB, but the maintainer's call is that the environment stays
generated in code — so the reference has to be reduced to something a few lines
of arithmetic can reproduce. That means measuring what actually makes it look the
way it does, rather than guessing at it from primitives, which is what the three
previous hand-built environments did and why each of them failed differently.

What matters for image-based lighting on a glossy character, in order:

  * **The elevation profile.** How brightness falls from zenith to nadir is what
    puts the highlight on the crown of the helmet and darkness under the jaw. It
    is the single most important curve here.
  * **The colour shift down that profile.** A real environment is not one hue:
    `forest` is cool and bright above, warmer and much darker below where the
    ground bounces. A gradient with one colour reads as artificial immediately.
  * **How concentrated the bright part is.** Peak against mean says whether the
    sky is an even wash or has a sun in it, which decides whether reflections are
    soft gradients or hard spots.

Azimuth is measured too but is expected to matter least: a forest sky is roughly
uniform around the horizon, and any strong azimuthal feature would be a landmark
that reflects as a recognisable shape — the exact failure `RoomEnvironment` had.

    blender --background --python avatar-source/probe_studio_reference.py
"""

import os

import bpy

CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 5.0\5.0\datafiles\studiolights\world\forest.exr",
    r"C:\Program Files\Blender Foundation\Blender 5.2\5.2\datafiles\studiolights\world\forest.exr",
]

W, H = 64, 32
BANDS = 16


def find_source():
    for path in CANDIDATES:
        if os.path.exists(path):
            return path
    raise SystemExit("forest.exr not found")


def main():
    source = find_source()
    image = bpy.data.images.load(source)
    print("[ref] %s  %dx%d" % (os.path.basename(source), image.size[0], image.size[1]))
    image.scale(W, H)
    px = list(image.pixels)

    def pixel(x, y):
        i = (y * W + x) * 4
        return px[i], px[i + 1], px[i + 2]

    print("")
    print("[ref] elevation profile, nadir (row 0) to zenith")
    print("      band   elev      R       G       B      lum    peak")
    rows_per = H // BANDS
    for b in range(BANDS):
        acc = [0.0, 0.0, 0.0]
        peak = 0.0
        n = 0
        for y in range(b * rows_per, (b + 1) * rows_per):
            for x in range(W):
                r, g, bl = pixel(x, y)
                acc[0] += r
                acc[1] += g
                acc[2] += bl
                peak = max(peak, r, g, bl)
                n += 1
        r, g, bl = (v / n for v in acc)
        lum = 0.2126 * r + 0.7152 * g + 0.0722 * bl
        # v runs 0 at the nadir to 1 at the zenith in three.js' equirect
        # sampler, and Blender's rows are bottom-up, so band 0 is the ground.
        elev = (b + 0.5) / BANDS
        print(
            "      %4d  %5.3f  %6.3f  %6.3f  %6.3f  %6.3f  %6.2f"
            % (b, elev, r, g, bl, lum, peak)
        )

    print("")
    print("[ref] azimuth around the horizon band (is there a landmark?)")
    sectors = 8
    cols_per = W // sectors
    horizon = range(H // 2 - 2, H // 2 + 3)
    lums = []
    for sct in range(sectors):
        acc = 0.0
        n = 0
        for y in horizon:
            for x in range(sct * cols_per, (sct + 1) * cols_per):
                r, g, bl = pixel(x, y)
                acc += 0.2126 * r + 0.7152 * g + 0.0722 * bl
                n += 1
        lums.append(acc / n)
    for sct, lum in enumerate(lums):
        print("      sector %d  %6.3f" % (sct, lum))
    print(
        "      spread: min %.3f max %.3f ratio %.2f"
        % (min(lums), max(lums), (max(lums) / min(lums)) if min(lums) > 0 else 0)
    )

    total = 0.0
    peak = 0.0
    for y in range(H):
        for x in range(W):
            r, g, bl = pixel(x, y)
            total += 0.2126 * r + 0.7152 * g + 0.0722 * bl
            peak = max(peak, r, g, bl)
    mean = total / (W * H)
    print("")
    print("[ref] overall mean lum %.4f  peak %.2f  peak/mean %.1f" % (mean, peak, peak / mean))


main()
