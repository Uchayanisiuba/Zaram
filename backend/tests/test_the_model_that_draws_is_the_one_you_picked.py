"""The model that draws is checked before it is driven, and it can be chosen.

Reported 29 September 2026: *"I installed Qwen Image as a replacement, seems
like it didn't replace."* It had not, and nothing anywhere said so.

`find_model` returned **the first directory in sorted order** carrying a
`model_index.json` with its weights beside it, and handed whatever that was to
`FluxPipeline`. `flux1-schnell-nf4` sorts before `qwen-image`, so the
replacement was passed over in silence — the only symptom being that nothing
changed. Named the other way round it would have been *constructed* as a FLUX
pipeline and failed somewhere inside diffusers, which reads as the new model
being broken.

The module already claimed this ground and stopped one step short. Its own
docstring says looking for `model_index.json` *"cannot make that mistake"*,
about a stray `.safetensors` being globbed up. It cannot make **that** mistake.
It made this one, because the index names the pipeline class and nothing read
it.

So these tests assert the two halves that were missing: what is found is
**verified** before it is driven, and what is found and cannot be used is
**reported by name** rather than skipped. The second is the one the maintainer
needed and did not get.
"""
from __future__ import annotations

import json

import pytest

from imaging.local_flux import (
    PIPELINE_INDEX,
    FluxProvider,
    Installed,
    find_model,
    installed_models,
    pipeline_class,
)


def make_pipeline(path, *, cls: str = "FluxPipeline", complete: bool = True):
    """A directory that looks like a diffusers pipeline of a given family.

    `_class_name` is the whole point here: it is what diffusers reads to decide
    what to construct, and it is what discovery was never looking at.
    """
    path.mkdir(parents=True, exist_ok=True)
    index = {"_class_name": cls}
    if not complete:
        # A component that must have weights beside it, with no directory —
        # which is what an interrupted download leaves behind.
        index["transformer"] = ["diffusers", "FluxTransformer2DModel"]
    (path / PIPELINE_INDEX).write_text(json.dumps(index), encoding="utf-8")
    return path


@pytest.fixture()
def folder(tmp_path, monkeypatch):
    """An empty image-model directory that discovery will look in."""
    root = tmp_path / "models"
    root.mkdir(parents=True)
    monkeypatch.delenv("ZARAM_IMAGE_MODEL", raising=False)
    monkeypatch.setenv("ZARAM_IMAGE_MODEL_DIR", str(root))
    return root


class TestReadingWhatItIs:
    def test_the_class_is_read_from_the_index_not_the_folder_name(self, tmp_path):
        """A folder's name is whatever the person typed when they downloaded
        it. The index is what diffusers will act on."""
        here = make_pipeline(tmp_path / "definitely-flux-honest", cls="QwenImagePipeline")
        assert pipeline_class(here) == "QwenImagePipeline"

    def test_an_unreadable_index_is_none_rather_than_an_error(self, tmp_path):
        broken = tmp_path / "broken"
        broken.mkdir()
        (broken / PIPELINE_INDEX).write_text("{not json", encoding="utf-8")
        assert pipeline_class(broken) is None

    def test_a_missing_index_is_none(self, tmp_path):
        assert pipeline_class(tmp_path / "nothing-here") is None


class TestWhatItWillDrive:
    def test_a_flux_pipeline_is_drawn_with(self, folder):
        make_pipeline(folder / "flux1-schnell-nf4")
        assert find_model() == folder / "flux1-schnell-nf4"

    def test_a_flux_variant_is_still_recognised(self, folder):
        """Matched on the prefix, so img2img and inpainting forks still work.
        A whitelist of exact class names would refuse a model that runs."""
        make_pipeline(folder / "a-model", cls="FluxImg2ImgPipeline")
        assert find_model() == folder / "a-model"

    def test_another_family_is_not_handed_to_a_flux_pipeline(self, folder):
        """The loud half of the bug. Named so it sorts first, it would have
        been constructed as FLUX and failed inside diffusers — which reads as
        the new model being broken rather than as the wrong model."""
        make_pipeline(folder / "a-qwen-image", cls="QwenImagePipeline")
        assert find_model() is None

    def test_the_second_model_is_not_silently_passed_over(self, folder):
        """The quiet half, and the one that was actually reported.

        Sorted order put the old model first, so the new one was never reached
        and nothing was wrong enough to say anything. Discovery still picks
        FLUX — that part is correct — but the Qwen must be *visible*, which is
        what `installed_models` is for.
        """
        make_pipeline(folder / "flux1-schnell-nf4")
        make_pipeline(folder / "qwen-image", cls="QwenImagePipeline")

        assert find_model() == folder / "flux1-schnell-nf4"

        found = {m.name: m for m in installed_models()}
        assert set(found) == {"flux1-schnell-nf4", "qwen-image"}
        assert found["qwen-image"].usable is False
        assert "FLUX" in found["qwen-image"].why_not()


class TestSayingWhichOne:
    def test_the_chosen_model_draws(self, folder):
        make_pipeline(folder / "a-flux")
        make_pipeline(folder / "b-flux")
        assert find_model() == folder / "a-flux"
        assert find_model("b-flux") == folder / "b-flux"

    def test_a_chosen_model_that_has_gone_falls_back(self, folder):
        """Deleting the model you picked must not leave you unable to draw —
        the same posture `default_model` takes when its model is uninstalled."""
        make_pipeline(folder / "a-flux")
        assert find_model("one-i-deleted") == folder / "a-flux"

    def test_a_chosen_model_that_cannot_be_driven_is_not_used(self, folder):
        """The pick is honoured *while it is usable*, never instead of the
        check. Otherwise the setting becomes a route around the fix above."""
        make_pipeline(folder / "a-flux")
        make_pipeline(folder / "qwen-image", cls="QwenImagePipeline")
        assert find_model("qwen-image") == folder / "a-flux"


class TestSayingWhyNot:
    def test_the_family_is_answered_before_the_download(self):
        """Finishing a 13.4 GB download for a pipeline this cannot construct is
        an evening spent on a model that will still not draw. The maintainer's
        own leftover `sdxl-config` is incomplete *and* the wrong family, and
        only the second fact is worth telling anybody."""
        both_wrong = Installed(
            path=None,
            name="sdxl-config",
            pipeline="StableDiffusionXLPipeline",
            complete=False,
            drivable=False,
        )
        assert "FLUX" in both_wrong.why_not()
        assert "downloaded" not in both_wrong.why_not()

    def test_an_interrupted_flux_download_still_says_so(self):
        half = Installed(
            path=None, name="flux1-schnell-nf4", pipeline="FluxPipeline",
            complete=False, drivable=True,
        )
        assert "partly downloaded" in half.why_not()

    def test_a_usable_model_has_nothing_to_explain(self):
        fine = Installed(
            path=None, name="flux1-schnell-nf4", pipeline="FluxPipeline",
            complete=True, drivable=True,
        )
        assert fine.why_not() == ""


class TestWhatTheUserIsTold:
    def test_availability_names_the_model_it_cannot_use(self, folder, monkeypatch):
        """The sentence that was missing entirely.

        Before this, a folder holding only a Qwen pipeline reported *"the image
        model is only partly downloaded"* — because the half-download check ran
        first and a complete Qwen has its index too. That sends somebody to
        resume a fetch that finished, for a model that was never going to run
        here. Two absences, two fixes, and the wrong one costs an evening.
        """
        monkeypatch.setattr("imaging.local_flux._module_present", lambda _n: True)
        make_pipeline(folder / "qwen-image", cls="QwenImagePipeline")

        answer = FluxProvider().availability()
        assert answer.ok is False
        assert "qwen-image" in answer.reason
        assert "QwenImagePipeline" in answer.reason
        assert "partly downloaded" not in answer.reason

    def test_an_empty_folder_still_says_nothing_is_installed(self, folder, monkeypatch):
        monkeypatch.setattr("imaging.local_flux._module_present", lambda _n: True)
        answer = FluxProvider().availability()
        assert answer.ok is False
        assert "No image model is installed" in answer.reason


class TestTheChoiceTakesEffect:
    def test_rediscovering_forgets_the_cached_directory(self, folder):
        """Without this the pick would not apply until the app restarted, which
        reads as the picker doing nothing — the same silence one screen along.
        """
        make_pipeline(folder / "a-flux")
        make_pipeline(folder / "b-flux")

        provider = FluxProvider()
        assert provider.model == folder / "a-flux"

        # The person picks the other one. The provider is holding the first.
        provider.rediscover()
        assert provider._model is None


class TestFourBitNeedsACard:
    """Reported 29 September 2026 with a screenshot, after a 214-second wait:
    *"could not draw that: flux-schnell: No GPU found. A GPU is needed for
    quantization."*

    `availability` had answered **ok**. Its no-CUDA branch warned that a
    picture would be slow, which is true of FLUX in bf16 and false of the model
    Zaram ships: `magespace/FLUX.1-schnell-bnb-nf4` stores its transformer and
    T5 with ``load_in_4bit``, and bitsandbytes reads those on an NVIDIA GPU and
    nowhere else. There was no slow path. There was no path.

    Rule 9 in a new place — the invention was a capability.
    """

    def quantised(self, folder, *, bits: str = "load_in_4bit"):
        model = make_pipeline(folder / "flux1-schnell-nf4")
        part = model / "transformer"
        part.mkdir()
        (part / "config.json").write_text(
            json.dumps({"quantization_config": {"quant_method": "bitsandbytes", bits: True}}),
            encoding="utf-8",
        )
        return model

    def test_quantised_weights_are_recognised_from_the_config(self, folder):
        from imaging.local_flux import needs_a_card

        assert needs_a_card(self.quantised(folder)) is True

    def test_eight_bit_counts_too(self, folder):
        from imaging.local_flux import needs_a_card

        assert needs_a_card(self.quantised(folder, bits="load_in_8bit")) is True

    def test_an_unquantised_pipeline_does_not(self, folder):
        from imaging.local_flux import needs_a_card

        assert needs_a_card(make_pipeline(folder / "plain-flux")) is False

    def test_an_unreadable_config_is_not_evidence_of_quantisation(self, folder, tmp_path):
        """The failure that matters is refusing a pipeline that would have
        worked, so anything unreadable answers no."""
        from imaging.local_flux import needs_a_card

        model = make_pipeline(folder / "odd")
        part = model / "transformer"
        part.mkdir()
        (part / "config.json").write_text("{not json", encoding="utf-8")
        assert needs_a_card(model) is False

    def test_no_card_and_four_bit_refuses_rather_than_promising_a_slow_picture(
        self, folder, monkeypatch
    ):
        import torch

        monkeypatch.setattr("imaging.local_flux._module_present", lambda _n: True)
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        self.quantised(folder)

        answer = FluxProvider().availability()
        assert answer.ok is False
        assert "4-bit" in answer.reason
        # The remedy names what is actually wrong. "No GPU found" sent somebody
        # to Device Manager to diagnose a card they already own.
        assert "CPU-only build" in answer.reason
        assert "pytorch.org" in answer.remedy

    def test_no_card_and_plain_weights_still_offers_the_slow_picture(
        self, folder, monkeypatch
    ):
        """Refusing this would be the same mistake pointed the other way: an
        unquantised pipeline genuinely draws on a CPU, slowly."""
        import torch

        monkeypatch.setattr("imaging.local_flux._module_present", lambda _n: True)
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        make_pipeline(folder / "plain-flux")

        answer = FluxProvider().availability()
        assert answer.ok is True
        assert "tens of minutes" in answer.reason
