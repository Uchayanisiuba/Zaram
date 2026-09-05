"""Asked in as many words for a picture, Zaram plans to draw one.

Reported by the maintainer on 3 September 2026, from the running app: *"I asked
it to generate an Image of a blue dog and it didn't."* What came back was a
fluent paragraph from the chat model explaining that no image could be made —
on a machine with SDXL installed and `can_draw: true`.

**Every component worked and the plan never contained an image step.** Measured
against bge-m3 through the real `SemanticIntentRouter`:

    'Generate an Image of a blue dog'  ->  vision.analyze
    'draw a blue dog'                  ->  conversation

`vision.analyze` has no registered runtime, so `_drop_unavailable_steps` treated
it as an ordinary misroute and dropped it, and the request fell through to
`reasoning.generate`. `_NEVER_DEGRADE` and the images runtime's refusal both
exist to stop exactly that paragraph — and neither ran, because there was no
image step for them to protect.

**The keyword phrases were right and unreachable.** `classify` returns the
moment `_classify_semantically` returns non-None, so on any machine whose
embedder actually embeds, the keyword classifier is never consulted. That is the
identical defect the search block in `planner.py` already records, one intent
over: the two classifiers are not alternatives, and the deterministic signal has
to be unioned in rather than switched away from.

Similarity cannot separate the two intents and should not be asked to. *"What is
in this image"* and *"generate an image of…"* share their rarest word, and
`CLAUDE.md` settles the principle rather than tuning the threshold: *modality is
a capability gate, never a ranking* — *"can this model accept an image, or emit
one?" is binary and is a precondition*.

So the tests here assert the **override**, with a fake router that answers wrong
on purpose. A test that needed a real embedder would be a test of bge-m3's
geometry, which is not ours to fix and would go green the day the model changed.
"""

from __future__ import annotations

import pytest

from core.planner import IntentPlanner, IntentRouter, IntentType
from core.retrieval.router import RouteDecision


class FakeRouter:
    """A semantic router that returns whatever it was told to.

    Standing in for the real one at the seam that matters: `_classify_semantically`
    asks for a decision and builds everything downstream from it, so a router
    that answers `vision` reproduces the reported failure exactly, with no model
    and no Ollama in the test.
    """

    def __init__(self, intent: str, confidence: float = 0.61) -> None:
        self._intent = intent
        self._confidence = confidence

    def route(self, prompt: str) -> RouteDecision:  # noqa: ARG002
        return RouteDecision(
            intent=self._intent,
            confidence=self._confidence,
            reason=f"nearest exemplar was a {self._intent} task",
            exemplar="what is in this image",
        )


def _planner(intent: str) -> IntentPlanner:
    return IntentPlanner(semantic_router=FakeRouter(intent))


ASKED_TO_DRAW = [
    "Generate an Image of a blue dog",
    "generate an image of a city street in the rain",
    "draw me a blue dog",
    "make me a picture of a blue dog",
    "create an image of a logo for Northwind",
    "paint me something restful",
]


class TestAnUnambiguousRequestOverridesTheRouter:
    @pytest.mark.parametrize("prompt", ASKED_TO_DRAW)
    def test_the_router_saying_vision_does_not_lose_the_picture(self, prompt):
        """The reported failure, in one line."""
        classification = _planner("vision").classify_intent(prompt)
        assert classification.intent_type is IntentType.IMAGE
        assert classification.capabilities == ["image.generate"]

    @pytest.mark.parametrize("prompt", ASKED_TO_DRAW)
    def test_the_router_saying_conversation_does_not_either(self, prompt):
        classification = _planner("conversation").classify_intent(prompt)
        assert classification.intent_type is IntentType.IMAGE

    def test_the_plan_carries_the_step_the_runtime_answers(self):
        """Classification is not the deliverable; the plan is.

        The whole failure was a plan with no image step in it, so asserting on
        the classification alone would pass for a build that still could not
        draw.
        """
        plan = _planner("vision").create_plan("Generate an Image of a blue dog")
        assert "image.generate" in [step.capability_id for step in plan.steps]

    def test_the_flags_follow_the_resolved_intent_not_the_router(self):
        """`requires_vision` picks the model, and it must not stay true here.

        Left at the router's answer, the request would plan an image step and
        then choose a model selected for its ability to *read* a picture —
        two halves of one request disagreeing about which direction the image
        goes.
        """
        classification = _planner("vision").classify_intent("draw me a blue dog")
        assert classification.requires_image_output is True
        assert classification.requires_vision is False

    def test_the_override_is_stated_rather_than_silent(self):
        """CLAUDE.md: show routing decisions in plain language.

        "We ignored the classifier here" is precisely the thing a reader of this
        metadata must be told rather than left to infer from a mismatch between
        the exemplar and the intent.
        """
        classification = _planner("vision").classify_intent("draw me a blue dog")
        assert classification.metadata.get("overrode") == "vision"


class TestItStaysNarrow:
    def test_a_genuine_vision_question_is_left_alone(self):
        classification = _planner("vision").classify_intent("what is in this image")
        assert classification.intent_type is IntentType.VISION
        assert classification.requires_vision is True
        assert "overrode" not in classification.metadata

    def test_drawing_up_a_contract_is_still_a_document(self):
        """Bare "draw" is absent from the phrases for this exact sentence.

        The override is only as safe as that omission, so it is asserted here
        rather than trusted to a comment in the keyword set.
        """
        classification = _planner("document").classify_intent(
            "draw up a contract for the Northwind job"
        )
        assert classification.intent_type is not IntentType.IMAGE

    def test_a_router_that_already_said_image_is_not_relabelled(self):
        classification = _planner("image").classify_intent(
            "generate an image of a city street"
        )
        assert classification.intent_type is IntentType.IMAGE
        assert "overrode" not in classification.metadata

    def test_no_phrase_means_the_router_decides(self):
        """The router keeps every case the phrases do not name.

        This is an override, not a replacement: a machine with a working
        embedder must still get semantic routing for everything else, or the
        fix would be a downgrade wearing a bug fix's clothes.
        """
        classification = _planner("conversation").classify_intent(
            "what did we decide about the deposit"
        )
        assert classification.intent_type is IntentType.CONVERSATION


class TestOneTypoDoesNotCostTheFeature:
    """The second report, the day after the first.

    The override above shipped, and the maintainer's next attempt was
    *"Generate and image of a blue"* — `and` for `an`, and the sentence cut
    short. `"generate an image"` was in the phrase list; `"generate and image"`
    was not, and no list ever will be. So the *shape* is matched instead: a
    making verb within a few words of a picture noun, unless the noun refers to
    a picture that already exists.
    """

    @pytest.mark.parametrize(
        "prompt",
        [
            "Generate and image of a blue",          # the reported typo, verbatim
            "Generate and image of a blue dog",
            "generate a image of a lighthouse",      # the other half of the same slip
            "generate for the proposal an image of a harbour",
            "design a header image for the proposal",
            "create an icon for the app",
            "render a poster for the launch",
            "sketch a portrait of the founder",
        ],
    )
    def test_a_request_no_list_anticipated_still_reaches_the_runtime(self, prompt):
        assert _planner("conversation").classify_intent(prompt).intent_type is IntentType.IMAGE


class TestItStillKnowsMakingFromLookingAt:
    """Where the rule earns the reference check.

    Every prompt here pairs a making verb with a picture noun and asks about a
    picture rather than for one. Without the check each would route to a
    diffusion model, and the user would get a drawing where they asked for a
    sentence — the mirror of the bug being fixed, and just as silent.
    """

    @pytest.mark.parametrize(
        "prompt",
        [
            "generate a summary of the image I sent",
            "make a transcript of the text in this picture",
            "what is in this image",
            "read the text in the attached picture",
            "tell me about my photo",
            "create a caption from the photo above",
        ],
    )
    def test_asking_about_a_picture_is_not_asking_for_one(self, prompt):
        assert IntentRouter._asks_for_a_drawing(prompt) is False

    @pytest.mark.parametrize(
        "prompt",
        [
            "draw up a contract for the Northwind job",
            "make a chart of my expenses",
            "write a document that includes a picture of the site",
            "generate an invoice for March",
        ],
    )
    def test_ordinary_work_is_left_alone(self, prompt):
        """`chart` and `diagram` are absent from the nouns on purpose: a chart
        is made from the user's own numbers by the exporter, and a diffusion
        model handed that request would draw a plausible picture of figures
        nobody has."""
        assert IntentRouter._asks_for_a_drawing(prompt) is False

    def test_a_verb_that_governs_something_else_does_not_reach(self):
        """The reach is what stops a picture mentioned in passing taking the
        whole request.

        Five words is deliberately short. It covers the ordinary insertions —
        *"generate for the proposal an image of a harbour"*, asserted above —
        and stops well before the sentence below, where the verb governs a
        document and the picture is a detail inside it. A window wide enough
        for every contrived phrasing would be wide enough for that one too, and
        an unwanted drawing is the same silent wrongness as an unwanted
        paragraph.
        """
        assert (
            IntentRouter._asks_for_a_drawing(
                "generate a document that explains the process and includes a picture"
            )
            is False
        )


class TestAMisspeltWordIsStillTheSameRequest:
    """Asked for on 4 September 2026, after the shape rule shipped.

    The shape rule handles a wrong word between the verb and the noun. It does
    not, on its own, handle a wrong letter *inside* them — `imgae`, `genrate`,
    `pictrue` — and a typo in the noun is the same request typed by someone in
    a hurry.

    `_looks_like` accepts two forms and refuses everything else: a
    transposition at any length, and one edit in a word of six letters or more.
    The classes below are the reason for that second bound rather than a
    general edit distance.
    """

    @pytest.mark.parametrize(
        "prompt",
        [
            "generate an imgae of a blue dog",
            "generate an iamge of a blue dog",
            "genrate an image of a blue dog",
            "creat an image of a logo",
            "create a pictrue of a lighthouse",
            "make an illustation of a harbour",
            "generate a photograpgh of a street",
        ],
    )
    def test_a_typo_still_asks_for_a_picture(self, prompt):
        assert IntentRouter._asks_for_a_drawing(prompt) is True

    @pytest.mark.parametrize(
        "prompt",
        [
            "generate an email for the client",
            "generate a usage report",
            "create an invoice for March",
            "point to the image I sent",
        ],
    )
    def test_a_near_miss_is_not_a_typo(self, prompt):
        """The four the bounds exist for.

        `email` and `usage` are the pair the first version of this rule
        declined fuzzy matching over, and they are still refused — `email` and
        `usage` share no first letter with `image`. `point` is one edit from
        `paint` and is refused on length, which is the whole reason the
        six-letter floor is there.
        """
        assert IntentRouter._asks_for_a_drawing(prompt) is False

    def test_a_transposition_is_allowed_where_one_edit_is_not(self):
        """The two bounds are different rules, and this is the seam.

        `pictrue` is a rearrangement of `picture` and is accepted at any
        length. `point` is one edit from `paint` and is refused because `paint`
        is only five letters. Asserting the seam directly stops the two being
        collapsed into one looser rule later.
        """
        assert IntentRouter._looks_like("pictrue", "picture") is True
        assert IntentRouter._looks_like("point", "paint") is False
        assert IntentRouter._looks_like("proto", "photo") is False

    def test_the_first_letter_anchors_it(self):
        """People fumble the middle of a word, not its start."""
        assert IntentRouter._looks_like("usage", "image") is False
        assert IntentRouter._looks_like("mage", "image") is False
