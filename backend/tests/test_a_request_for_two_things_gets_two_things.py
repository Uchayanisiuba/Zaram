"""A request that asks for a document **and** a picture is not an image request.

Built 15 September 2026, immediately after `draw_image` — and it is the reason
that tool would otherwise have been unreachable for the exact case it was built
for. *Registering is not reaching*, one layer up: the pack was attached at boot
and the model was handed the verb, but the planner never let the tool loop run
for these prompts, so it never saw it.

Measured before the fix, and both failures were silent:

    "Write the proposal and put a cover image on it"
        -> ['vision.analyze']   — a plan to *read* a picture nobody attached,
                                  which the dispatcher then refuses
    "Draft the report, then generate an image for the cover"
        -> ['image.generate']   — a picture, and no report at all

One request gets one intent, which is the right design; the bug was calling
these requests images. They are ordinary work with a drawing in them, and the
drawing is a step.
"""

from __future__ import annotations

import pytest

from core.planner import IntentPlanner

TOOL_PLAN = ["mcp.list_tools", "reasoning.generate"]


@pytest.fixture()
def planner() -> IntentPlanner:
    return IntentPlanner()


def _plan(planner: IntentPlanner, prompt: str, **kw) -> list[str]:
    return [step.capability_id for step in planner.create_plan(prompt, **kw).steps]


class TestTwoThingsAskedForAreTwoThingsPlanned:
    @pytest.mark.parametrize(
        "prompt",
        [
            "Write the proposal and put a cover image on it",
            "Draft the report, then generate an image for the cover",
            "Make me a summary and an illustration to go with it",
        ],
    )
    def test_the_drawing_becomes_a_step_rather_than_the_whole_request(
        self, planner: IntentPlanner, prompt: str
    ) -> None:
        assert _plan(planner, prompt) == TOOL_PLAN, (
            "routed wholesale to one capability, so half of what was asked for "
            "is silently dropped"
        )


class TestAPlainDrawingIsStillAPlainDrawing:
    """The fix must not reach requests that are only about a picture. Those
    keep the direct path, which carries the modality gate and the card check
    and does not spend a tool round trip on a one-step job."""

    @pytest.mark.parametrize(
        "prompt",
        [
            "Draw me a picture of a blue dog",
            "Make me a logo for Northwind",
            "Generate an image of a city at night, photorealistic",
        ],
    )
    def test_it_goes_straight_to_the_image_capability(
        self, planner: IntentPlanner, prompt: str
    ) -> None:
        assert _plan(planner, prompt) == ["image.generate"]


class TestLookingAtNothing:
    """`vision.analyze` with no attachment is a step that cannot run.

    The dispatcher refuses it — there is no image — so the plan was a dead end
    whenever the keywords invented one. With no attachment a picture can only
    come from a tool, and the tool plan degrades to an ordinary reply when none
    applies, which is the safe direction.
    """

    def test_a_picture_question_with_nothing_attached_takes_the_tool_plan(
        self, planner: IntentPlanner
    ) -> None:
        assert _plan(planner, "What is in this screenshot") == TOOL_PLAN

    def test_an_attached_image_still_goes_to_the_model_that_can_see_it(
        self, planner: IntentPlanner
    ) -> None:
        # The fact beats the guess: an attachment is answered by generating
        # *with* it, never by a capability side door.
        assert _plan(planner, "What is in this screenshot", has_images=True) == [
            "reasoning.generate"
        ]
