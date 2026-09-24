"""Editing a picture, and the gate that decides who may be asked to.

Qwen-Image 2.1 arrived on 20 September 2026 as the first open-weight model
whose *editing* surface is ahead of the closed ones — ten reference pictures,
region edits, a real alpha channel. Zaram ships none of it and never will
(no image weights, ever); it routes, with the user's key, through the gate,
into the log.

The claim under test is not "Qwen works" — that needs a key and a network.
It is the thing that goes wrong **before** any of that: a request carrying
reference pictures handed to a generator that cannot read them. Nothing
raises. FLUX draws something from the prompt alone and returns it, and the
person gets a confident picture of the wrong thing with nothing on screen
saying their photograph was ignored.

CLAUDE.md names this exactly — *"Modality is a capability gate, never a
ranking"* — and records the same mistake costing this codebase three times in
retrieval. So capability decides **membership**: a generator that cannot do
what was asked is not ranked lower, it is not in the running.
"""

from __future__ import annotations

import pytest

from imaging import MAX_REFERENCES, TEXT_TO_IMAGE_ONLY, ImageCapabilities, ImageRequest
from imaging.cloud import (
    CLOUD_PROVIDERS,
    FalImages,
    QwenImages,
    RoutedImageProvider,
    _can_serve,
)

PNG = b"\x89PNG\r\n\x1a\n"


def edit_request(**kwargs) -> ImageRequest:
    return ImageRequest(prompt="put it on a mug", references=(PNG,), **kwargs)


class TestTheRequest:
    def test_a_picture_may_be_worked_from(self):
        assert edit_request().references == (PNG,)

    def test_ten_is_the_ceiling_and_it_is_the_models(self):
        ten = ImageRequest(prompt="x", references=tuple(PNG for _ in range(MAX_REFERENCES)))
        assert len(ten.references) == 10

        with pytest.raises(ValueError, match="at most 10"):
            ImageRequest(prompt="x", references=tuple(PNG for _ in range(11)))

    def test_an_empty_reference_is_refused(self):
        # An empty byte string is not a picture, and a provider handed one
        # answers about a picture that was never sent.
        with pytest.raises(ValueError, match="no bytes"):
            ImageRequest(prompt="x", references=(b"",))

    def test_an_ordinary_request_is_unchanged(self):
        plain = ImageRequest(prompt="a fox")
        assert plain.references == () and plain.transparent is False


class TestTheGate:
    def test_a_generator_that_edits_may_be_asked_to(self):
        assert _can_serve(QwenImages(), edit_request()) is True

    def test_one_that_does_not_is_out_of_the_running(self):
        # Not last in it. Ranked lower, it wins whenever it is the only key
        # connected, and then draws from the words with the photograph
        # silently dropped.
        assert _can_serve(FalImages(), edit_request()) is False

    def test_transparency_is_the_same_kind_of_question(self):
        assert _can_serve(FalImages(), ImageRequest(prompt="a logo", transparent=True)) is False
        assert _can_serve(QwenImages(), ImageRequest(prompt="a logo", transparent=True)) is True

    def test_an_ordinary_request_still_reaches_everyone(self):
        plain = ImageRequest(prompt="a fox in a forest")
        assert all(_can_serve(p, plain) for p in CLOUD_PROVIDERS)

    def test_no_request_means_no_opinion(self):
        # `availability()` asks "can anything draw", which is a question about
        # the provider and not about a request.
        assert _can_serve(FalImages(), None) is True


class _Generator:
    """A generator with a key, a grant and a declared set of abilities."""

    def __init__(self, name: str, capabilities: ImageCapabilities):
        self.name = name
        self._capabilities = capabilities
        self.asked = []

    def availability(self):
        from imaging import AVAILABLE

        return AVAILABLE

    def capabilities(self) -> ImageCapabilities:
        return self._capabilities

    def describe(self) -> str:
        return self.name

    def generate(self, request, on_progress=None):
        self.asked.append(request)
        return []


class TestRouting:
    @staticmethod
    def routed(local=None, cloud=()):
        return RoutedImageProvider(local=local, cloud=list(cloud), prefer=lambda: "local")

    def test_the_editor_is_chosen_for_an_edit_even_when_local_would_draw(self):
        """Local-first is the rule for *drawing*, not for a job it cannot do.

        CLAUDE.md's routing order puts capability above speed and says so:
        *"capability first, speed second"*. A card sitting there able to draw
        is not a reason to answer the wrong question locally.
        """
        local = _Generator("flux (local)", TEXT_TO_IMAGE_ONLY)
        editor = _Generator("qwen", ImageCapabilities(references=10, transparent=True))
        routed = self.routed(local=local, cloud=[editor])

        routed.generate(edit_request())

        assert editor.asked and not local.asked

    def test_local_still_draws_an_ordinary_picture(self):
        local = _Generator("flux (local)", TEXT_TO_IMAGE_ONLY)
        editor = _Generator("qwen", ImageCapabilities(references=10))
        routed = self.routed(local=local, cloud=[editor])

        routed.generate(ImageRequest(prompt="a fox"))

        assert local.asked and not editor.asked

    def test_a_request_nothing_can_serve_says_what_is_missing(self):
        routed = self.routed(local=_Generator("flux (local)", TEXT_TO_IMAGE_ONLY))

        verdict = routed.availability_for(edit_request())

        assert verdict.ok is False
        assert "reference picture" in verdict.reason
        assert verdict.remedy, "a refusal with no remedy is a dead end"

    def test_it_does_not_claim_the_general_case_is_broken(self):
        # "Nothing can draw" and "nothing can draw *this*" are different
        # sentences, and telling someone with a working generator that they
        # have none sends them to fix the wrong thing.
        routed = self.routed(local=_Generator("flux (local)", TEXT_TO_IMAGE_ONLY))

        assert routed.availability().ok is True

    def test_what_the_interface_may_offer_is_what_the_chosen_one_can_do(self):
        routed = self.routed(local=_Generator("flux (local)", TEXT_TO_IMAGE_ONLY))

        assert routed.capabilities().edits is False


class TestQwenAsItWouldBeSent:
    """The body, without sending it. A key and a network are not the subject."""

    @staticmethod
    def body(request: ImageRequest):
        return QwenImages()._body(request, seed=7)

    def test_a_reference_travels_as_data_not_as_a_link(self):
        # A URL would make drawing a fetch nobody declared, and a path would
        # let a request body choose which file on this machine is sent.
        body = self.body(edit_request())

        assert body["image_urls"][0].startswith("data:image/png;base64,")
        assert body["image_url"] == body["image_urls"][0]

    def test_transparency_asks_for_a_format_that_can_hold_it(self):
        body = self.body(ImageRequest(prompt="a logo", transparent=True))

        assert body["transparent_background"] is True
        assert body["output_format"] == "png"

    def test_an_ordinary_request_carries_neither(self):
        body = self.body(ImageRequest(prompt="a fox"))

        assert "image_urls" not in body and "transparent_background" not in body

    def test_the_edit_endpoint_is_used_only_when_there_is_something_to_edit(self):
        qwen = QwenImages()

        assert qwen._url(ImageRequest(prompt="a fox")) == qwen.endpoint
        assert qwen._url(edit_request()) == qwen.edit_endpoint


class TestReachingItFromAMessage:
    """What the composer already sends, read as what it plainly means."""

    def test_an_attached_picture_becomes_a_reference(self):
        import base64

        from runtimes.images.runtime import _references

        attached = [base64.b64encode(PNG).decode("ascii")]
        assert _references(attached) == (PNG,)

    def test_a_data_uri_is_accepted_as_it_arrives(self):
        import base64

        from runtimes.images.runtime import _references

        uri = "data:image/png;base64," + base64.b64encode(PNG).decode("ascii")
        assert _references([uri]) == (PNG,)

    def test_something_that_is_not_base64_is_refused(self):
        from runtimes.images.runtime import _references

        with pytest.raises(ValueError, match="base64"):
            _references(["not base64 at all"])

    @pytest.mark.parametrize(
        "prompt",
        [
            "a fox on a transparent background",
            "a logo with no background",
            "a sticker of a cat",
            "cut out the subject",
        ],
    )
    def test_asking_for_it_in_words_is_how_anyone_asks(self, prompt):
        from runtimes.images.runtime import _asks_for_transparency

        assert _asks_for_transparency(prompt) is True

    def test_an_ordinary_request_is_not_read_as_asking(self):
        from runtimes.images.runtime import _asks_for_transparency

        assert _asks_for_transparency("a fox in a forest at dusk") is False
