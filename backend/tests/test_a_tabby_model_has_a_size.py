"""A model served over the OpenAI-compatible port is sized from its own name.

`discoverers/ollama.py` reports `size_bytes`; `discoverers/openai_compat.py`
did not, because the `/v1/models` contract carries an id and an owner and
nothing else. So the residency gate graded nothing about a model served by
TabbyAPI -- which, on the maintainer's machine, is the one that answers.

The id of an exl2/exl3 quantisation states both numbers needed
(`Qwen3.8-27B-exl3-2.20bpw`: 27 billion parameters, 2.20 bits each), so the
size is arithmetic rather than a guess. The rule that keeps it honest is
*both or nothing*: a count without a precision, or the reverse, would be filled
from a default chosen by looking at one model.
"""

from __future__ import annotations

import pytest

from providers.contracts import ProviderKind
from providers.discoverers.openai_compat import OpenAICompatibleAdapter, size_from_id

GB = 1_000_000_000


class TestTheArithmetic:
    def test_the_maintainers_model(self):
        # 27e9 * 2.20 / 8 = 7.425 GB -- the figure the milestone predicted.
        assert size_from_id("Qwen3.8-27B-exl3-2.20bpw") == int(27e9 * 2.20 / 8)

    def test_a_different_precision_is_a_different_size(self):
        small = size_from_id("Some-Model-8B-exl2-4.0bpw")
        large = size_from_id("Some-Model-8B-exl2-6.0bpw")
        assert small == 4 * GB
        assert large == 6 * GB

    def test_a_fractional_count(self):
        assert size_from_id("tiny-0.6B-exl3-4.0bpw") == int(0.6e9 * 4 / 8)

    def test_a_mixtures_total_is_used_not_its_active_count(self):
        """`30B-A3B` is 30 billion in memory and 3 billion per token. The
        weights that have to fit are the 30."""
        assert size_from_id("moe-30B-A3B-exl3-3.0bpw") == int(30e9 * 3.0 / 8)


class TestBothOrNothing:
    @pytest.mark.parametrize(
        "model_id",
        [
            "llama-3.1-8b-instant",          # a count, no precision
            "model-exl3-4.0bpw",             # a precision, no count
            "gemma-3-12b-it-q4_k_m",         # a GGUF tag, not bits per weight
            "gpt-4o",                        # neither
            "Model-8bit",                    # `8bit` is not `8B`
            "",
        ],
    )
    def test_it_is_none_rather_than_a_guess(self, model_id):
        assert size_from_id(model_id) is None

    def test_an_absurd_precision_is_refused(self):
        assert size_from_id("model-8B-exl3-99bpw") is None


class TestItReachesTheModel:
    def _adapter(self, kind):
        return OpenAICompatibleAdapter("tabby", base_url="http://127.0.0.1:1234", kind=kind)

    def test_a_local_model_carries_the_derived_size_and_says_where_it_came_from(self):
        model = self._adapter(ProviderKind.LOCAL_AI_SERVER)._to_model(
            "Qwen3.8-27B-exl3-2.20bpw", {"id": "x"}
        )
        assert model.size_bytes == int(27e9 * 2.20 / 8)
        assert model.metadata["size_source"] == "derived from the model id"

    def test_a_model_with_no_quantisation_in_its_id_is_still_unsized(self):
        model = self._adapter(ProviderKind.LOCAL_AI_SERVER)._to_model("some-local-model", {"id": "x"})
        assert model.size_bytes is None
        assert "size_source" not in model.metadata

    def test_a_cloud_model_is_never_sized_from_its_name(self):
        """A figure for a model on someone else's hardware would be graded
        against this machine's card."""
        model = self._adapter(ProviderKind.CLOUD_API)._to_model(
            "vendor/model-8B-exl3-4.0bpw", {"id": "x"}
        )
        assert model.size_bytes is None
