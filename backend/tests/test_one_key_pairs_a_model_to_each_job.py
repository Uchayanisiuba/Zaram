"""One key, the right model for each job — offered from what the key can see.

`providers.pairing`. Three contracts: only a model discovery actually
returned is ever recommended, in the manifest's order of preference; a slot
with no surviving candidate is left alone rather than filled with a name
that would fail on every message; and applying writes exactly the fields the
Advanced picker writes — chat is `default_model`, the rest are task slots —
and nothing else.

And the shape scales: every paired provider carries the same three slots,
so OpenRouter and Groq are entries, not code.
"""

from __future__ import annotations

import pytest

from core.user_settings import TaskSlot, UserSettings
from providers import pairing


class TestOnlyWhatTheKeyCanSee:
    def test_the_first_candidate_the_key_can_see_wins(self):
        seen = [
            "meta/llama-3.3-70b-instruct",           # third choice for chat
            "qwen/qwen2.5-coder-32b-instruct",       # fourth choice for code
            "moonshotai/kimi-k2-instruct",           # second choice for code
        ]
        picks = pairing.recommend("nvidia_nim", seen)
        assert picks["chat"]["model"] == "meta/llama-3.3-70b-instruct"
        assert picks["code"]["model"] == "moonshotai/kimi-k2-instruct"
        # No vision model was seen: the slot is left alone, not invented.
        assert "vision" not in picks

    def test_a_prefixed_id_is_the_same_model(self):
        picks = pairing.recommend("nvidia_nim", ["nvidia_nim/qwen/qwen3-coder-480b-a35b-instruct"])
        assert picks["code"]["model"] == "nvidia_nim/qwen/qwen3-coder-480b-a35b-instruct"

    def test_a_longer_name_is_not_a_match(self):
        # llama-3.3-70b must not be found inside llama-3.3-70b-vision-something.
        picks = pairing.recommend("groq", ["llama-3.3-70b-versatile-vision"])
        assert picks == {}

    def test_nothing_seen_nothing_offered(self):
        assert pairing.recommend("nvidia_nim", []) == {}
        assert pairing.recommend("a-provider-nobody-paired", ["anything"]) == {}


class TestApplyingWritesThePickerFields:
    def test_chat_is_the_default_model_and_the_rest_are_slots(self, tmp_path):
        settings = UserSettings(str(tmp_path / "settings.json"))
        settings.set_task_model(TaskSlot.VISION, "keep-me")
        out = pairing.apply(
            settings,
            {"chat": {"model": "fast-one", "why": ""}, "code": {"model": "coder", "why": ""}},
        )
        assert settings.default_model == "fast-one"
        assert settings.task_models[TaskSlot.CODE.value] == "coder"
        # A slot the offer did not name is untouched.
        assert settings.task_models[TaskSlot.VISION.value] == "keep-me"
        assert out == {"chat": "fast-one", "code": "coder", "vision": "keep-me", "document": None}


class TestTheShapeScales:
    @pytest.mark.parametrize("provider_id", pairing.paired_providers())
    def test_every_paired_provider_carries_every_slot_with_a_reason(self, provider_id):
        p = pairing.PAIRINGS[provider_id]
        for slot in pairing.SLOTS:
            candidates = getattr(p, slot)
            assert candidates, (provider_id, slot)
            for pick in candidates:
                assert pick.model and pick.why, (provider_id, slot)
                # Model names, not files.
                assert not pick.model.lower().endswith((".gguf", ".safetensors", ".bin"))

    def test_the_manifest_is_dated(self):
        assert pairing.GENERATED >= "2026-09-14"
