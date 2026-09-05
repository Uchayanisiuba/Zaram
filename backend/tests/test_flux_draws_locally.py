"""FLUX.1 [schnell] on this machine: found, refused honestly, and drawn.

Replaces SDXL as the local image provider — the maintainer's decision on
4 September 2026. The comparison and the reason the weights arrive already
quantised are in `imaging/local_flux.py`.

**Two halves, and the split is the point.** Everything about discovery and
availability runs anywhere, in milliseconds, with no weights: those are the
paths a user on a fresh machine actually hits, and they are where a wrong
message costs someone an afternoon. The generation test is gated on the model
being present, because a suite that silently skips the only test that proves
the feature works is how this repository has been fooled before — so it skips
*loudly*, naming what is missing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from imaging import ImageRequest
from imaging.local_flux import (
    GUIDANCE,
    MAX_SEQUENCE_LENGTH,
    PIPELINE_INDEX,
    SOURCE_REPO,
    FluxProvider,
    default_model_dir,
    find_model,
)


def make_pipeline_dir(path, *, index: bool = True):
    """A directory that looks like a diffusers pipeline.

    `model_index.json` is the whole test: it is what diffusers reads first and
    what `find_model` uses to tell a pipeline from any other folder.
    """
    path.mkdir(parents=True, exist_ok=True)
    if index:
        (path / PIPELINE_INDEX).write_text(
            json.dumps({"_class_name": "FluxPipeline"}), encoding="utf-8"
        )
    return path


class TestFindingTheModel:
    def test_nothing_installed_is_none_rather_than_an_error(self, tmp_path, monkeypatch):
        """The state most machines are in. The caller's job is to offer, not to
        raise."""
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(tmp_path / "empty"))
        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        assert find_model() is None

    def test_the_model_directory_may_be_the_pipeline_itself(self, tmp_path, monkeypatch):
        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(make_pipeline_dir(tmp_path / "m")))
        assert find_model() == tmp_path / "m"

    def test_a_pipeline_inside_the_model_directory_is_found(self, tmp_path, monkeypatch):
        root = tmp_path / "models"
        make_pipeline_dir(root / "flux1-schnell-nf4")
        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(root))
        assert find_model() == root / "flux1-schnell-nf4"

    def test_a_leftover_sdxl_checkpoint_is_not_mistaken_for_a_pipeline(
        self, tmp_path, monkeypatch
    ):
        """The hazard the old discovery had, and the reason this looks for a
        directory rather than globbing `*.safetensors`.

        SDXL arrived as one file and its finder took the first `.safetensors`
        it saw. After the switch that file is still sitting in the same folder,
        and handing it to a FLUX pipeline fails in a way that reads as the new
        model being broken.
        """
        root = tmp_path / "models"
        root.mkdir(parents=True)
        (root / "sd_xl_base_1.0.safetensors").write_bytes(b"not a pipeline")
        make_pipeline_dir(root / "flux1-schnell-nf4")

        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(root))
        assert find_model() == root / "flux1-schnell-nf4"

    def test_the_choice_is_stable_across_runs(self, tmp_path, monkeypatch):
        """Two pipelines in one folder must not draw with a different one each
        launch."""
        root = tmp_path / "models"
        for name in ("b-model", "a-model", "c-model"):
            make_pipeline_dir(root / name)
        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(root))
        assert find_model() == root / "a-model"
        assert find_model() == root / "a-model"

    def test_a_named_model_that_is_not_a_pipeline_is_not_pretended_into_being(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("ZARAM_IMAGE_MODEL", str(make_pipeline_dir(tmp_path / "x", index=False)))
        assert find_model() is None

    def test_a_half_downloaded_model_is_not_installed(self, tmp_path, monkeypatch):
        """Found by running these tests against a 78%-complete download.

        `model_index.json` is one of the small files and lands in the first
        seconds, so an interrupted 13.4 GB fetch leaves a directory that *looks*
        like a pipeline. Reporting that as installed tells the user `can_draw`
        and then fails at the moment they ask for a picture — which reads as the
        model being broken rather than as a download being unfinished.
        """
        root = tmp_path / "models"
        half = make_pipeline_dir(root / "flux1-schnell-nf4")
        (half / PIPELINE_INDEX).write_text(
            json.dumps(
                {
                    "_class_name": "FluxPipeline",
                    "transformer": ["diffusers", "FluxTransformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKL"],
                }
            ),
            encoding="utf-8",
        )
        # The VAE arrived; the transformer did not.
        (half / "vae").mkdir()
        (half / "vae" / "diffusion_pytorch_model.safetensors").write_bytes(b"weights")

        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(root))
        assert find_model() is None

    def test_a_complete_model_is_installed(self, tmp_path, monkeypatch):
        """The other half of the check, so it cannot pass by refusing
        everything."""
        root = tmp_path / "models"
        whole = make_pipeline_dir(root / "flux1-schnell-nf4")
        (whole / PIPELINE_INDEX).write_text(
            json.dumps(
                {
                    "_class_name": "FluxPipeline",
                    "transformer": ["diffusers", "FluxTransformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKL"],
                    # Declared and not shipped — a null component must not be
                    # read as a missing one.
                    "safety_checker": None,
                }
            ),
            encoding="utf-8",
        )
        for part in ("transformer", "vae"):
            (whole / part).mkdir()
            (whole / part / "diffusion_pytorch_model.safetensors").write_bytes(b"w")

        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(root))
        assert find_model() == whole

    def test_an_unreadable_index_is_not_installed_rather_than_an_error(
        self, tmp_path, monkeypatch
    ):
        """The caller's job here is to decide whether to offer, and a directory
        nobody can parse is not something to offer."""
        root = tmp_path / "models"
        broken = make_pipeline_dir(root / "broken")
        (broken / PIPELINE_INDEX).write_text("{not json", encoding="utf-8")
        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(root))
        assert find_model() is None

    def test_the_default_directory_is_under_the_data_directory(self, monkeypatch):
        """The user's data lives in the user's data directory — never in the
        backend source tree, which is unwritable in an install."""
        monkeypatch.delenv("ZARAM_IMAGE_MODEL_DIR", raising=False)
        assert default_model_dir().parts[-2:] == ("models", "image")


class TestSayingWhyItCannotDraw:
    def test_a_missing_model_names_the_repository_and_the_size(self, tmp_path, monkeypatch):
        """"Images are unavailable" is not something a user can act on.

        The size matters as much as the name: 13.4 GB is a decision on a
        metered connection, and naming the fix without naming its cost is not a
        choice the user can make.
        """
        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(tmp_path / "empty"))

        availability = FluxProvider().availability()
        if not availability.ok:
            assert SOURCE_REPO in availability.remedy
            assert "13.4 GB" in availability.remedy

    def test_a_half_download_says_it_is_half_rather_than_missing(
        self, tmp_path, monkeypatch
    ):
        """"No image model is installed" would send someone to start a 13.4 GB
        fetch they have mostly already done. Resuming costs the remainder."""
        root = tmp_path / "models"
        half = make_pipeline_dir(root / "flux1-schnell-nf4")
        (half / PIPELINE_INDEX).write_text(
            json.dumps({"transformer": ["diffusers", "FluxTransformer2DModel"]}),
            encoding="utf-8",
        )
        monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
        monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(root))

        availability = FluxProvider().availability()
        if not availability.ok and "partly downloaded" in availability.reason:
            assert "resumes" in availability.remedy

    def test_bitsandbytes_gets_its_own_reason(self, tmp_path, monkeypatch):
        """Folding it into "install diffusers" would send a user to install
        that, and still leave them unable to draw — the weights are stored
        4-bit and bitsandbytes is what reads them."""
        import imaging.local_flux as flux

        monkeypatch.setattr(
            flux, "_module_present", lambda name: name != "bitsandbytes"
        )
        availability = FluxProvider().availability()
        assert availability.ok is False
        assert "bitsandbytes" in availability.remedy


class TestTheParametersSchnellNeeds:
    def test_guidance_is_zero(self):
        """Schnell is guidance-distilled. A scale above zero does not make it
        more faithful, it makes it worse."""
        assert GUIDANCE == 0.0

    def test_the_sequence_length_is_the_trained_one(self):
        assert MAX_SEQUENCE_LENGTH == 256

    def test_a_negative_prompt_is_reported_rather_than_swallowed(self, caplog):
        """`FluxPipeline` does not take the argument at all.

        Ignoring it silently would leave a user believing they had excluded
        something — which is rule 9's failure in miniature: confident, plausible
        and not what happened.
        """
        import logging

        provider = FluxProvider()

        # **Loading is stubbed out, and the first version of this test did not
        # do that.** It relied on `generate` raising because no weights were
        # installed — which was true when it was written and stopped being true
        # the moment the download finished, at which point the test quietly
        # spent two minutes loading a 13 GB pipeline and drawing a picture
        # before failing on the missing exception. A test whose meaning depends
        # on what happens to be on disk is not testing what its name says.
        def refuse(*_args, **_kwargs):
            raise RuntimeError("not loading a pipeline for this test")

        provider._load = refuse  # type: ignore[method-assign]

        request = ImageRequest(prompt="a blue dog", negative_prompt="collar", steps=4)
        with caplog.at_level(logging.INFO, logger="imaging.local_flux"):
            with pytest.raises(RuntimeError):
                provider.generate(request)

        # Emitted before loading is attempted, so the notice survives on a
        # machine with no weights as well as on one with them.
        assert any("Negative prompt ignored" in r.message for r in caplog.records)


@pytest.mark.skipif(
    find_model() is None,
    reason=(
        f"No FLUX pipeline in {default_model_dir()} — download {SOURCE_REPO} "
        "to run the test that actually draws"
    ),
)
class TestAnImageIsActuallyProduced:
    """The only test here that proves the feature works.

    Gated rather than mocked, and it skips with the reason and the remedy in the
    message. A suite that quietly skips its one real test reports coverage it
    does not have — which is the failure `CLAUDE.md` records as this
    repository's most expensive.
    """

    #: Where the drawn image is left for a person to look at.
    #:
    #: **Asserting on bytes is not the same as seeing the picture.** Every
    #: assertion below would pass for a blue rectangle, and this repository has
    #: already shipped one thing — pointer-tracking gaze — whose maths was unit
    #: tested and which visibly did not work. Writing the file costs nothing and
    #: means the claim "FLUX draws" can be checked by opening it.
    OUTPUT = Path(__file__).resolve().parent / "_flux_sample.png"

    @pytest.fixture(scope="class")
    def drawn(self):
        provider = FluxProvider()
        steps: list = []
        images = provider.generate(
            ImageRequest(prompt="a blue dog", width=512, height=512, steps=4, seed=7),
            on_progress=steps.append,
        )
        provider.unload()
        TestAnImageIsActuallyProduced.OUTPUT.write_bytes(images[0].png)
        return images, steps

    def test_it_returns_a_real_png(self, drawn):
        images, _ = drawn
        assert len(images) == 1
        assert images[0].png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_the_pixels_are_not_all_one_colour(self, drawn):
        """A black or grey square is what a dtype mistake produces, and it is a
        valid PNG. fp16 overflows in FLUX's attention; bf16 does not."""
        import io

        from PIL import Image

        images, _ = drawn
        image = Image.open(io.BytesIO(images[0].png)).convert("RGB")
        assert len(set(image.getdata())) > 100

    def test_the_seed_is_reported_so_the_image_can_be_asked_for_again(self, drawn):
        images, _ = drawn
        assert images[0].seed == 7

    def test_progress_was_reported_for_every_step(self, drawn):
        _, steps = drawn
        assert [s.step for s in steps] == [1, 2, 3, 4]
