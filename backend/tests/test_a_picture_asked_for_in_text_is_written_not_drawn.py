"""A picture asked for as SVG, HTML or CSS is written, not drawn.

Found 4 October 2026 by sending the resident model the sentence a person would
type. *"Draw a minimalist fox logo as an SVG"* came back **empty in one second**:
`draw` within reach of `logo` is the whole image rule, so the request went to the
image generator, which answered "No image model is installed" and ended the
reply. The user had named the output, and the output was text -- which the model
that was right there writes well, and the image generator cannot emit at all.

*Modality is a capability gate, never a ranking.* This is the gate read from the
other side: an image model emits raster pictures, so a request that names a
format only a language model writes is not an image request whatever verb and
noun sit beside it.

Both ways of being wrong are pinned, because the first fix produced the second:
once the image rule stood aside, "make an SVG **image** of a fox" landed on the
rule for *reading* a picture and set `requires_vision`.
"""

from __future__ import annotations

import pytest

from core.planner import IntentPlanner, IntentRouter, IntentType
from tests.test_asking_for_a_picture_reaches_the_image_runtime import FakeRouter

WRITTEN_NOT_DRAWN = [
    "Draw a minimalist fox logo as an SVG.",
    "Make an SVG image of a fox",
    "Create a picture of a sunset using CSS",
    "draw me a diagram in mermaid",
    "Draw an ASCII cat",
    "design a poster in HTML",
    "generate an illustration of a mountain in SVG",
]

STILL_AN_IMAGE = [
    "Draw me a blue dog",
    "Generate an image of a city street in the rain",
    "create a logo for Northwind",
    "make me a picture of a blue dog",
    "paint me something restful",
]


class TestTheKeywordPath:
    @pytest.mark.parametrize("prompt", WRITTEN_NOT_DRAWN)
    def test_it_is_code(self, prompt):
        c = IntentPlanner().classify_intent(prompt)
        assert c.intent_type is IntentType.CODE
        assert c.capabilities == ["reasoning.generate"]

    @pytest.mark.parametrize("prompt", WRITTEN_NOT_DRAWN)
    def test_it_asks_for_no_image_model_and_no_vision_model(self, prompt):
        c = IntentPlanner().classify_intent(prompt)
        assert c.requires_image_output is False
        assert c.requires_vision is False

    @pytest.mark.parametrize("prompt", STILL_AN_IMAGE)
    def test_a_real_request_for_a_picture_is_untouched(self, prompt):
        c = IntentPlanner().classify_intent(prompt)
        assert c.intent_type is IntentType.IMAGE
        assert c.requires_image_output is True

    def test_a_format_the_person_does_not_want_is_not_a_format_they_named(self):
        c = IntentPlanner().classify_intent("Make a picture of a cat, not ASCII")
        assert c.intent_type is IntentType.IMAGE

    def test_a_question_about_an_existing_svg_is_still_for_a_model_that_can_see(self):
        """The reference guard applies: `this` marks a picture that exists."""
        c = IntentPlanner().classify_intent("what is in this svg image")
        assert c.intent_type is IntentType.VISION

    def test_drawing_up_a_contract_is_still_a_document(self):
        c = IntentPlanner().classify_intent("Draw up a contract")
        assert c.intent_type is IntentType.CONVERSATION

    def test_the_plan_carries_no_image_step(self):
        """Classification is not the deliverable; the plan is. The empty reply
        came from a plan that contained `image.generate`."""
        plan = IntentPlanner().create_plan("Draw a minimalist fox logo as an SVG.")
        assert "image.generate" not in [step.capability_id for step in plan.steps]
        assert "reasoning.generate" in [step.capability_id for step in plan.steps]


class TestTheSemanticPath:
    """On a machine whose embedder works the keyword classifier is not consulted
    at all, so the gate has to hold against a router that answers wrong."""

    @pytest.mark.parametrize("router_says", ["image", "vision", "conversation"])
    @pytest.mark.parametrize("prompt", WRITTEN_NOT_DRAWN)
    def test_it_is_still_written(self, prompt, router_says):
        c = IntentPlanner(semantic_router=FakeRouter(router_says)).classify_intent(prompt)
        assert c.intent_type is not IntentType.IMAGE
        assert c.intent_type is not IntentType.VISION
        assert c.requires_image_output is False
        assert c.requires_vision is False

    @pytest.mark.parametrize("prompt", STILL_AN_IMAGE)
    def test_a_real_picture_request_still_overrides_the_router(self, prompt):
        c = IntentPlanner(semantic_router=FakeRouter("conversation")).classify_intent(prompt)
        assert c.intent_type is IntentType.IMAGE

    def test_the_override_is_stated_rather_than_silent(self):
        c = IntentPlanner(semantic_router=FakeRouter("vision")).classify_intent(
            "Make an SVG image of a fox"
        )
        assert c.metadata.get("overrode") == "vision"

    def test_a_router_that_already_said_code_is_left_alone(self):
        c = IntentPlanner(semantic_router=FakeRouter("code")).classify_intent(
            "Draw a minimalist fox logo as an SVG."
        )
        assert c.intent_type is IntentType.CODE
        assert "overrode" not in c.metadata


class TestTheGateIsNarrow:
    def test_only_formats_a_language_model_writes_are_on_the_list(self):
        """A wide list is a way to lose real image requests. `png`, `jpg` and
        `photo` are things an image model makes; they must never appear here."""
        for raster in ("png", "jpg", "jpeg", "gif", "photo", "image", "picture", "webp"):
            assert raster not in IntentRouter._TEXT_FORMATS

    def test_a_format_alone_is_not_a_request_to_make_anything_visual(self):
        assert IntentRouter._asks_for_text_art("what does the css box model do") is False
