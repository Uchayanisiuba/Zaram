"""Does discovery keep what OpenRouter says a model can see and draw?

Queue item 7. It arrives in the same response the pricing is read from, in the
same object `_is_free_tier` already opens, and it was discarded.

`OpenAICompatibleAdapter._to_model` hardcodes `ModelCategory.LLM` and never
sets `supports_vision`. Its comment justifies that correctly for plain OpenAI —
*"/v1/models exposes only an id + ownership; deeper metadata is not part of the
spec"* — and that reasoning does not carry to OpenRouter, whose
`/api/v1/models` returns `architecture` with `input_modalities` and
`output_modalities`.

The consequence was a refusal built on missing data, which is the hardest kind
to notice because it looks like the safety working. A user with a connected
OpenRouter account and a dozen vision-capable models attaches a screenshot and
is told **"No model on this machine can read images. Zaram will not answer
about a picture it cannot see."** That is `main.py:682`, it is the correct
sentence, and it was reading a flag nothing ever set.
`select_model_for_task(requires_vision=True)` — the gate — was already built
and already had live callers. This is the one thing it was missing.

**Input and output stay two questions.** `CLAUDE.md`: *"'reads images', 'makes
images' and 'makes video' are one number — ask for a model that can draw and
you can get one that can only look."* The deleted `orchestrator/capabilities.py`
was exactly that. So accepting images sets a flag and leaves the model a chat
model; emitting them *instead of* text changes what kind of thing it is.
"""

from __future__ import annotations

import pytest

from providers.contracts import DataPolicy, ModelCategory
from providers.discoverers.openrouter import OpenRouterAdapter


@pytest.fixture
def adapter():
    return OpenRouterAdapter(api_key="sk-or-not-real")


def entry(*, accepts=None, emits=None, pricing=None):
    """One row of `/api/v1/models`, trimmed to the fields that matter."""
    row: dict = {"pricing": pricing if pricing is not None else {"prompt": "0.000003", "completion": "0.000015"}}
    if accepts is not None or emits is not None:
        architecture: dict = {}
        if accepts is not None:
            architecture["input_modalities"] = accepts
        if emits is not None:
            architecture["output_modalities"] = emits
        row["architecture"] = architecture
    return row


class TestAModelThatCanSeeSaysSo:
    def test_image_input_sets_the_flag_the_gate_reads(self, adapter):
        model = adapter._to_model(
            "anthropic/claude-sonnet-4.5", entry(accepts=["text", "image"], emits=["text"])
        )

        assert model.supports_vision is True, (
            "the gate is `select_model_for_task(requires_vision=True)` and it "
            "filters on this flag; without it a connected account full of "
            "vision-capable models is told nothing can see"
        )

    def test_it_is_still_a_chat_model(self, adapter):
        """A chat model that can also see is still a chat model.

        Same shape Ollama discovery already produces from `/api/show`, which is
        what keeps one flag meaning one thing across providers. Making it a
        `VISION` category would remove it from ordinary chat selection, which
        is the opposite of what "it can also read pictures" means.
        """
        model = adapter._to_model(
            "anthropic/claude-sonnet-4.5", entry(accepts=["text", "image"], emits=["text"])
        )

        assert model.category is ModelCategory.LLM
        assert "vision" in model.capabilities

    def test_a_text_only_model_is_untouched(self, adapter):
        model = adapter._to_model("some/text-model", entry(accepts=["text"], emits=["text"]))

        assert model.supports_vision is False
        assert model.category is ModelCategory.LLM


class TestSeeingAndDrawingAreNotOneNumber:
    def test_a_model_that_only_draws_is_not_offered_as_a_chat_model(self, adapter):
        """`select_model_for_task` filters by category.

        Without this a model that can only emit pictures is a candidate for
        answering a question, and it answers by not answering.
        """
        model = adapter._to_model("some/image-maker", entry(accepts=["text"], emits=["image"]))

        assert model.category is ModelCategory.IMAGE

    def test_drawing_does_not_imply_seeing(self, adapter):
        """The failure `CLAUDE.md` names, in the direction it names it.

        `orchestrator/capabilities.py` scored `IMAGE` and `VISION`
        identically, so a model that could draw would satisfy a request to
        look. These are two fields here precisely so they cannot be one
        number.
        """
        model = adapter._to_model("some/image-maker", entry(accepts=["text"], emits=["image"]))

        assert model.supports_vision is False

    def test_seeing_does_not_imply_drawing(self, adapter):
        model = adapter._to_model("some/looker", entry(accepts=["text", "image"], emits=["text"]))

        assert model.category is not ModelCategory.IMAGE

    def test_a_model_that_emits_both_stays_a_chat_model(self, adapter):
        """It can still hold the conversation, so removing it from chat would
        cost the user a model for no reason."""
        model = adapter._to_model(
            "some/multimodal", entry(accepts=["text", "image"], emits=["text", "image"])
        )

        assert model.category is ModelCategory.LLM
        assert model.metadata["output_modalities"] == ["text", "image"]


class TestItRefusesToInferFromAMissingField:
    def test_no_architecture_leaves_the_base_behaviour_alone(self, adapter):
        """A partial or older response must not become an answer.

        Absent is "we do not know", never "text only" — the same rule as
        `data_policy` being `None` in this very adapter, and as `vram_bytes`
        being `None` rather than 0.
        """
        model = adapter._to_model("old/model", entry())

        assert model.supports_vision is False
        assert model.category is ModelCategory.LLM
        assert "input_modalities" not in model.metadata

    def test_a_malformed_architecture_is_ignored_rather_than_parsed(self, adapter):
        model = adapter._to_model(
            "odd/model", {"architecture": "text+image->text", "pricing": {"prompt": "1"}}
        )

        assert model.supports_vision is False
        assert model.category is ModelCategory.LLM


class TestThePolicyRulesAreUnchanged:
    """The thing this change must not have loosened.

    `test_openrouter_policy.py` asserts that no OpenRouter model is ever
    `selectable_by_default`, and its framing is the rule: *we can sometimes
    prove a model logs; we can never prove one does not.* A modality field is
    not evidence about terms, and a vision-capable free model is still a free
    model.
    """

    def test_a_free_vision_model_is_still_the_logged_tier(self, adapter):
        model = adapter._to_model(
            "some/vision-model:free",
            entry(accepts=["text", "image"], emits=["text"], pricing={"prompt": "0", "completion": "0"}),
        )

        assert model.supports_vision is True
        assert model.data_policy is DataPolicy.LOGGED_AND_TRAINED_ON
        assert model.selectable_by_default is False

    def test_a_paid_vision_model_still_vouches_for_nothing(self, adapter):
        model = adapter._to_model(
            "anthropic/claude-sonnet-4.5", entry(accepts=["text", "image"], emits=["text"])
        )

        assert model.data_policy is None
        assert model.selectable_by_default is False
