"""An image has actually been sampled on this machine.

Written 3 September 2026 because the handoff said, plainly, that CUDA reported
available and the checkpoint verified and **no image had ever been generated**.
A pipeline that loads on paper is not a pipeline that draws, and the gap between
those two is where this repository's characteristic failure lives: a complete,
tested, unreachable subsystem that nothing has ever run end to end.

Two halves, and the split matters
---------------------------------
Most of this file is arithmetic and refusals and runs everywhere in
milliseconds — the progress maths, the request validation, the availability
messages a machine with nothing installed must produce. Those are the contract.

One class actually loads seven gigabytes and samples. It is marked ``measure``
— the marker this repository already uses for *"measures against a live local
model; skips when unavailable"* — and skips when the checkpoint or the
libraries are absent, because a stranger checking out this repository must not
have their suite hang on a model they do not have. But it is a **test**, not a script in a scratch directory: the one
question the handoff cared about is whether this works, and a question worth
asking once is worth asking on every release.

Run it with::

    pytest backend/tests/test_local_image_generation.py -m measure

Measured here, 3 September 2026: RTX 3060 12 GB, torch 2.13.0+cu126,
diffusers 0.40.0, ``sd_xl_base_1.0.safetensors`` (6.94 GB).
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

from imaging.contracts import (
    MAX_IMAGES,
    GeneratedImage,
    ImageProgress,
    ImageRequest,
)
from imaging.local_sdxl import (
    CHECKPOINT_ENV,
    CONFIG_DIR_ENV,
    MODEL_DIR_ENV,
    SdxlProvider,
    default_model_dir,
    find_checkpoint,
    find_pipeline_config,
)


def _module_present(name: str) -> bool:
    from importlib.util import find_spec

    try:
        return find_spec(name) is not None
    except (ImportError, ValueError):
        return False


# ===================================================== progress is measured ===


class TestProgressIsMeasuredNotPredicted:
    """Percentage and step count, and nothing resembling a time remaining.

    The decision is recorded in the handoff and it is the same one
    ``vram_bytes`` makes by returning ``None`` rather than ``0``: a diffusion
    pipeline emits a callback per step, so percentage is a real measurement,
    while seconds-left is a guess until several steps have run — and a
    confident wrong number is worse than no number.
    """

    def test_percent_runs_from_nothing_to_everything(self):
        assert ImageProgress(step=0, total_steps=30).percent == 0
        assert ImageProgress(step=15, total_steps=30).percent == 50
        assert ImageProgress(step=30, total_steps=30).percent == 100

    def test_a_batch_fills_one_bar_rather_than_four(self):
        """The bar must not reset three times.

        A bar that fills and empties four times reads as three failures and a
        success. The wait the user is sitting through is the whole batch, so
        that is what is reported.
        """
        first_done = ImageProgress(step=30, total_steps=30, index=1, count=4)
        assert first_done.percent == 25

        third_halfway = ImageProgress(step=15, total_steps=30, index=3, count=4)
        assert third_halfway.percent == 62  # (2 * 30 + 15) / 120

        last_done = ImageProgress(step=30, total_steps=30, index=4, count=4)
        assert last_done.percent == 100

    def test_progress_never_leaves_the_range(self):
        """Defensive, because this number is rendered as a bar width.

        A provider reporting more steps than it promised would otherwise draw a
        bar past the end of its track.
        """
        assert ImageProgress(step=99, total_steps=30).percent == 100
        assert ImageProgress(step=1, total_steps=0).percent == 0

    def test_there_is_no_time_remaining_field(self):
        """Asserted rather than described.

        A comment saying "we do not estimate time" is a comment somebody adds a
        field next to. This fails on the commit that adds one.
        """
        fields = set(ImageProgress.__dataclass_fields__)
        assert fields == {"step", "total_steps", "index", "count"}
        assert not any("eta" in f or "remaining" in f or "seconds" in f for f in fields)


# ======================================================== the request refuses ===


class TestARequestRefusesWhatItCannotDraw:
    def test_an_empty_prompt_is_refused(self):
        with pytest.raises(ValueError, match="nothing to draw"):
            ImageRequest(prompt="   ")

    def test_the_batch_is_bounded(self):
        """Four, which is what the card's 2x2 grid holds.

        Not an arbitrary cap: each image costs seconds of GPU time the user
        waits through, so a request for twenty is a request to sit still for
        minutes — which is not a thing to discover after saying yes.
        """
        assert MAX_IMAGES == 4
        ImageRequest(prompt="a lighthouse", count=MAX_IMAGES)
        with pytest.raises(ValueError, match="count must be"):
            ImageRequest(prompt="a lighthouse", count=MAX_IMAGES + 1)

    def test_a_size_the_unet_cannot_honour_is_refused(self):
        """Rounding silently would make the record disagree with the file.

        SDXL works in units of 8 pixels and the pipeline rounds a size that is
        not a multiple. The artifact record would then say 1023 and the PNG
        would be 1024, which is a small lie in the one place the product claims
        to be checkable.
        """
        with pytest.raises(ValueError, match="multiples of 8"):
            ImageRequest(prompt="a lighthouse", width=1023)


# ================================================ absence is a real answer ===


class TestAMachineWithNothingInstalledSaysSo:
    """No image model is the state most machines are in.

    CLAUDE.md: disabled capabilities are visible, not silent — and naming the
    fix without naming its cost is not a choice a user on metered data can
    make. So every unavailable branch carries both a reason and a remedy, and
    the remedy carries a size.
    """

    def test_no_checkpoint_anywhere_is_none_rather_than_an_error(self, tmp_path, monkeypatch):
        monkeypatch.delenv(CHECKPOINT_ENV, raising=False)
        monkeypatch.setenv(MODEL_DIR_ENV, str(tmp_path / "not-a-directory"))
        assert find_checkpoint() is None

    def test_an_installed_checkpoint_is_found_by_directory(self, tmp_path, monkeypatch):
        monkeypatch.delenv(CHECKPOINT_ENV, raising=False)
        monkeypatch.setenv(MODEL_DIR_ENV, str(tmp_path))
        (tmp_path / "some-model.safetensors").write_bytes(b"not really a model")
        assert find_checkpoint() == tmp_path / "some-model.safetensors"

    def test_the_choice_is_stable_across_runs(self, tmp_path, monkeypatch):
        """Two checkpoints in a directory must not draw with a different one
        each launch — the picture would change for no reason the user can see."""
        monkeypatch.delenv(CHECKPOINT_ENV, raising=False)
        monkeypatch.setenv(MODEL_DIR_ENV, str(tmp_path))
        for name in ("zebra.safetensors", "alpha.safetensors", "middle.safetensors"):
            (tmp_path / name).write_bytes(b"x")
        assert find_checkpoint().name == "alpha.safetensors"

    def test_a_named_checkpoint_that_does_not_exist_is_not_pretended_into_being(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(CHECKPOINT_ENV, str(tmp_path / "missing.safetensors"))
        assert find_checkpoint() is None

    def test_the_unavailable_message_names_the_fix_and_its_size(self, tmp_path, monkeypatch):
        monkeypatch.delenv(CHECKPOINT_ENV, raising=False)
        monkeypatch.setenv(MODEL_DIR_ENV, str(tmp_path))

        availability = SdxlProvider().availability()
        if _module_present("torch") and _module_present("diffusers"):
            assert not availability.ok
            assert "No image model is installed" in availability.reason
            assert "GB" in availability.remedy
        else:
            # A machine without the libraries fails earlier, and that message
            # has to carry a size too — 2.6 GB of CUDA torch is the largest
            # download this product ever asks for.
            assert not availability.ok
            assert "GB" in availability.remedy or "pip install" in availability.remedy

    def test_the_default_directory_is_under_the_data_directory(self, monkeypatch):
        """Not beside the source. `core/paths` owns the one answer, and a store
        that resolved to the checkout is unwritable in an install."""
        monkeypatch.delenv(MODEL_DIR_ENV, raising=False)
        from core.paths import data_dir

        assert data_dir() in default_model_dir().parents


# =========================================================== it actually draws ===

_CHECKPOINT = find_checkpoint()
_CAN_SAMPLE = (
    _CHECKPOINT is not None
    and find_pipeline_config() is not None
    and _module_present("torch")
    and _module_present("diffusers")
)


@pytest.mark.measure
@pytest.mark.skipif(
    not _CAN_SAMPLE,
    reason=(
        "No image checkpoint, no local pipeline config, or torch/diffusers absent. "
        f"Set {CHECKPOINT_ENV} to a Stable Diffusion XL .safetensors file and "
        f"{CONFIG_DIR_ENV} to its pipeline config to run this."
    ),
)
class TestAnImageIsActuallyProduced:
    """The measurement the handoff asked for, and it loads the real weights.

    Small and few-stepped on purpose: 512x512 at 6 steps is off SDXL's trained
    distribution and produces an unlovely picture, which is fine — the question
    is whether the pipeline loads, samples, and hands back decodable PNG bytes,
    not whether it draws well. Load time dominates either way.
    """

    @pytest.fixture(scope="class")
    def drawn(self):
        """Loads and samples **with the network taken away**.

        The socket guard is the assertion, not decoration around it. The first
        version of this file asserted that the loader had *restored the
        environment variable it borrowed*, which is true of a guard that never
        applied — and it did not apply: measured 3 September 2026, 3.2 MB of
        tokenizer and config files were written into ``~/.cache/huggingface``
        during a run this file reported as passing. `huggingface_hub` reads
        ``HF_HUB_OFFLINE`` once at import, and ``import diffusers`` had already
        done that.

        A test that cannot fail for the reason it names is worse than no test,
        because it reports a guarantee nobody has. So this one removes the
        capability rather than inspecting a flag: if anything in the load or
        the sampling opens a socket, it raises here and the test fails with the
        thing it tried to reach.
        """
        import socket

        opened: list[object] = []
        real_connect = socket.socket.connect

        def refuse(self, address, *args, **kwargs):
            opened.append(address)
            raise AssertionError(
                f"image generation tried to open a socket to {address!r} — "
                "the whole claim on the card is that nothing left the device"
            )

        socket.socket.connect = refuse
        provider = SdxlProvider()
        try:
            availability = provider.availability()
            assert availability.ok, f"{availability.reason} {availability.remedy}"

            seen: list[ImageProgress] = []
            images = provider.generate(
                ImageRequest(
                    prompt="a lighthouse on a rocky coast at dawn",
                    width=512,
                    height=512,
                    steps=6,
                    seed=1234,
                ),
                on_progress=seen.append,
            )
            yield images, seen
        finally:
            socket.socket.connect = real_connect
            provider.unload()

    def test_it_returns_a_real_png(self, drawn):
        images, _ = drawn
        assert len(images) == 1
        image = images[0]
        assert isinstance(image, GeneratedImage)
        # The signature, not the length. A file of the right size full of zeroes
        # would pass a size check and is not a picture.
        assert image.png[:8] == bytes.fromhex("89504e470d0a1a0a")
        assert image.width == 512 and image.height == 512

    def test_the_pixels_are_not_all_one_colour(self, drawn):
        """A pipeline that runs and produces a flat grey square has failed in
        the way that looks most like success — black output is the classic
        fp16 VAE symptom, and it passes every check but this one."""
        from PIL import Image

        images, _ = drawn
        decoded = Image.open(io.BytesIO(images[0].png)).convert("RGB")
        colours = decoded.getcolors(maxcolors=1_000_000)
        assert colours is not None and len(colours) > 100, (
            f"only {len(colours or [])} distinct colours — the sampler ran but "
            "produced a flat image, which is what a broken VAE looks like"
        )

    def test_the_seed_is_reported_so_the_image_can_be_asked_for_again(self, drawn):
        images, _ = drawn
        assert images[0].seed == 1234

    def test_progress_was_reported_for_every_step(self, drawn):
        """The bar is driven by this. If the callback never fires the card
        shows nothing for the whole wait, which is the state images are in
        today and the reason 1.3 exists."""
        _, seen = drawn
        assert [p.step for p in seen] == [1, 2, 3, 4, 5, 6]
        assert seen[-1].percent == 100

    def test_nothing_left_the_device(self, drawn):
        """The claim the card makes in words, and the fixture is the proof.

        Reaching this test at all means the load and the sampling both
        completed with `socket.connect` raising — see the fixture. What is left
        to assert here is the belt to that braces: the configuration was
        resolved from a directory on this machine rather than from a repository
        id that only happened to be cached, so the guarantee survives somebody
        clearing their cache.
        """
        images, _ = drawn
        assert images  # it drew, with the network taken away

        config = find_pipeline_config()
        assert config is not None and config.is_dir()
        assert (config / "model_index.json").is_file()

    def test_a_missing_config_refuses_rather_than_fetching_it(self, tmp_path, monkeypatch):
        """The state a stranger's machine is in, and it must not self-repair.

        This is the branch the measurement above turned into a real concern: a
        feature that quietly downloads what it is missing looks identical to
        one that works, right up until somebody asks what left the machine.
        """
        monkeypatch.setenv(CONFIG_DIR_ENV, str(tmp_path / "nothing"))
        availability = SdxlProvider().availability()
        assert not availability.ok
        assert "will not fetch" in availability.reason
        assert "MB" in availability.remedy
