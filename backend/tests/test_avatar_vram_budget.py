"""What the avatar costs the GPU, measured from the asset rather than guessed.

`CLAUDE.md` puts the 3D embodiment in v1 but records that its GPU cost is
**unmeasured**, that `docs/UI-SPEC.md` forbids 3D on the landing on GPU-budget
grounds, and that the decision is *warn, never block* — which needs a real
number to warn with. The number that appeared in conversation, "~1.5 GB", was
invented. This file replaces it with an arithmetic one.

**Why this is a test and not a script.** A number in a document goes stale
silently; the avatar asset can be swapped for a heavier one and nothing would
say so. Here the measurement runs on every suite and the ceiling fails when it
is exceeded, which is the same reason `test_egress_chokepoint.py` is a test
rather than an audit.

**What it measures, precisely.** Texture and geometry VRAM: the two costs that
scale with the asset and therefore with the choice of avatar. It does *not*
include the framebuffer, the depth buffer, three.js's own allocations or the
browser's compositor surfaces — those scale with the viewport and the renderer,
not with the model, and they are measured live instead. Both halves are recorded
in `docs/MILESTONES.md`; neither one alone is the answer.

Measured live on an RTX 3060 at 1280x720, 10 August 2026, with the orb as the
control: total GPU memory rose by roughly 190-430 MB with the avatar rendering,
across two toggle cycles, and returned below its starting point afterwards, so
nothing is leaked per cycle. That spread is wide because total-board memory is a
crude instrument on a shared desktop — which is exactly why the asset half is
computed here instead.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AVATAR = REPO_ROOT / "frontend" / "public" / "avatars" / "AvatarSample_Z.vrm"

#: A texture on the GPU is not its compressed PNG. It is decoded to RGBA8, four
#: bytes a pixel, and three.js generates mipmaps by default — which is another
#: third on top. Sizing an avatar by its file size understates it badly, and in
#: this direction: a 16 MB .vrm claims far more than 16 MB of VRAM.
BYTES_PER_PIXEL = 4
MIPMAP_MULTIPLIER = 4 / 3

#: The ceiling this asset is held to, and the number a warning is written
#: against. It is a budget decision, not a measurement: `CLAUDE.md` reserves
#: ~9.1 GB on a 12 GB card for a chat model, and an embodiment that renders
#: permanently while a local model is resident has to be small enough that it
#: never changes which model fits. The gaps between installed model sizes are
#: 1-3 GB, so a quarter-gigabyte avatar is invisible to that decision and a
#: two-gigabyte one is not.
VRAM_CEILING_BYTES = 512 * 1024 * 1024


def _read_glb(path: Path) -> tuple[dict, bytes]:
    """Split a .glb/.vrm container into its JSON chunk and its binary chunk.

    A VRM *is* a glTF binary — the format is glTF 2.0 with extensions — so no
    VRM-aware library is needed to weigh it, and none is added. The container is
    a 12-byte header followed by length-prefixed chunks.
    """
    raw = path.read_bytes()
    magic, version, _length = struct.unpack_from("<4sII", raw, 0)
    assert magic == b"glTF", f"{path.name} is not a glTF binary container"
    assert version == 2, f"unexpected glTF container version {version}"

    offset = 12
    gltf: dict | None = None
    binary = b""
    while offset < len(raw):
        chunk_length, chunk_type = struct.unpack_from("<II", raw, offset)
        body = raw[offset + 8 : offset + 8 + chunk_length]
        if chunk_type == 0x4E4F534A:  # 'JSON'
            gltf = json.loads(body.decode("utf-8"))
        elif chunk_type == 0x004E4942:  # 'BIN'
            binary = body
        offset += 8 + chunk_length + (-chunk_length % 4)

    assert gltf is not None, "glTF binary has no JSON chunk"
    return gltf, binary


def _image_dimensions(data: bytes) -> tuple[int, int] | None:
    """Width and height from a PNG or JPEG header, without decoding the pixels.

    Returns ``None`` rather than a guess for anything unrecognised, for the same
    reason `vram_bytes` returns ``None``: a plausible wrong number cannot be
    checked by the caller, and this one feeds a budget.
    """
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        # IHDR is always the first chunk, and its width and height are the first
        # two big-endian uint32s of its payload.
        width, height = struct.unpack_from(">II", data, 16)
        return width, height

    if data[:2] == b"\xff\xd8":
        offset = 2
        while offset < len(data) - 9:
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            # SOF0-SOF15, excluding the four that are not frame headers.
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack_from(">HH", data, offset + 5)
                return width, height
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                offset += 2
                continue
            (segment_length,) = struct.unpack_from(">H", data, offset + 2)
            offset += 2 + segment_length
    return None


def _texture_bytes(gltf: dict, binary: bytes) -> tuple[int, list[tuple[int, int]]]:
    """Resident bytes for every image in the asset, and their dimensions."""
    views = gltf.get("bufferViews", [])
    total = 0
    sizes: list[tuple[int, int]] = []

    for image in gltf.get("images", []):
        index = image.get("bufferView")
        if index is None:
            # An image referenced by URI. This asset has none, and one would be
            # a second network-ish fetch worth noticing rather than silently
            # weighing as zero.
            pytest.fail(f"image {image.get('name')!r} is external, not embedded")
        view = views[index]
        start = view.get("byteOffset", 0)
        data = binary[start : start + view["byteLength"]]

        dimensions = _image_dimensions(data)
        assert dimensions is not None, (
            f"image {image.get('name')!r} is neither PNG nor JPEG "
            f"({image.get('mimeType')}); its VRAM cost cannot be computed, and "
            "guessing it would put an unverifiable number in a budget."
        )
        width, height = dimensions
        sizes.append((width, height))
        total += int(width * height * BYTES_PER_PIXEL * MIPMAP_MULTIPLIER)

    return total, sizes


def _geometry_bytes(gltf: dict) -> int:
    """Bytes of vertex and index data uploaded to the GPU.

    Counted per buffer view rather than per accessor, because two accessors
    sharing an interleaved view are one upload — counting accessors would double
    it.
    """
    views = gltf.get("bufferViews", [])
    accessors = gltf.get("accessors", [])
    used: set[int] = set()

    for mesh in gltf.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            indices = list(primitive.get("attributes", {}).values())
            if "indices" in primitive:
                indices.append(primitive["indices"])
            for target in primitive.get("targets", []):
                indices.extend(target.values())
            for accessor_index in indices:
                view = accessors[accessor_index].get("bufferView")
                if view is not None:
                    used.add(view)

    return sum(views[i]["byteLength"] for i in used)


@pytest.fixture(scope="module")
def asset() -> tuple[dict, bytes]:
    if not AVATAR.exists():
        pytest.skip(f"{AVATAR.name} is not in the tree")
    return _read_glb(AVATAR)


class TestTheAvatarFitsTheGpuBudget:
    def test_the_footprint_is_measured_and_reported(self, asset, capsys):
        """Print the breakdown. The number is the point of the test."""
        gltf, binary = asset
        textures, sizes = _texture_bytes(gltf, binary)
        geometry = _geometry_bytes(gltf)
        total = textures + geometry

        with capsys.disabled():
            # Plain ASCII in the printed report: the Windows console this is
            # read on is cp1252, and an em-dash arrives as a replacement glyph.
            print(f"\n  {AVATAR.name} - {AVATAR.stat().st_size / 1e6:.1f} MB on disk")
            print(f"  textures  {textures / 1e6:8.1f} MB  ({len(sizes)} images)")
            for width, height in sorted(sizes, reverse=True)[:8]:
                each = width * height * BYTES_PER_PIXEL * MIPMAP_MULTIPLIER
                print(f"      {width:>5} x {height:<5} {each / 1e6:7.1f} MB")
            print(f"  geometry  {geometry / 1e6:8.1f} MB")
            print(f"  TOTAL     {total / 1e6:8.1f} MB of texture + geometry VRAM\n")

        assert total > 0, "measured nothing, which means the parse failed silently"

    def test_it_stays_under_the_ceiling(self, asset):
        """The budget, enforced.

        Not a claim that this is all the avatar costs — the framebuffer and
        three.js's own allocations are not in it. It is the half that changes
        when somebody swaps the asset, which is the half a ceiling can protect.
        """
        gltf, binary = asset
        textures, _ = _texture_bytes(gltf, binary)
        total = textures + _geometry_bytes(gltf)

        assert total <= VRAM_CEILING_BYTES, (
            f"the avatar claims {total / 1e6:.0f} MB of texture and geometry "
            f"VRAM, over the {VRAM_CEILING_BYTES / 1e6:.0f} MB ceiling.\n\n"
            "It renders permanently while a local model is resident, so this "
            "comes out of the chat model's budget. Either shrink the textures "
            "or raise the ceiling deliberately — but raising it means checking "
            "it still cannot change which model fits."
        )

    def test_the_file_size_is_not_the_footprint(self, asset):
        """The trap this file exists to close.

        A 16 MB .vrm is not a 16 MB claim on the GPU: textures ship compressed
        and land decoded, four bytes a pixel plus mipmaps. Anyone sizing the
        avatar by looking at the file is out by a large factor, and this asserts
        which direction — so the mistake cannot be made quietly.
        """
        gltf, binary = asset
        textures, _ = _texture_bytes(gltf, binary)
        total = textures + _geometry_bytes(gltf)

        assert total > AVATAR.stat().st_size, (
            "the resident footprint came out at or below the file size, which "
            "means the texture accounting is not running"
        )
