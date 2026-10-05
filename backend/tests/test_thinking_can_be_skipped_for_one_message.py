"""Thinking, for one message, without touching the setting.

Measured 4 October 2026 against the resident 27B: **870 seconds** for a looping
CSS animation, 3,956 frames of reasoning to 542 of answer. The setting's own
comment predicted 10-40 s. The switch is the right control and the wrong moment
(rule 7h): nobody knows before asking whether a question will make the model
think for fourteen minutes; they know eighty seconds in.

What is pinned:

* An override changes **that request** and not the setting, and not the next.
* **No override changes nothing.** Every request that did not ask behaves as it
  did.
* Both local engines honour it, by the field they each use.
* Two requests in flight do not decide each other's thinking.
* A retry does not write the question into the transcript a second time.
"""

from __future__ import annotations

import asyncio

import pytest

from core.thinking_override import set_thinking_override, thinking_override, thinking_wanted
from core.user_settings import get_user_settings


@pytest.fixture(autouse=True)
def clean():
    settings = get_user_settings()
    before = settings.thinking
    set_thinking_override(None)
    yield
    set_thinking_override(None)
    settings.set_thinking(before)


class TestTheOverride:
    def test_no_override_means_the_setting_decides(self):
        get_user_settings().set_thinking(True)
        assert thinking_wanted() is True
        get_user_settings().set_thinking(False)
        assert thinking_wanted() is False

    def test_an_override_beats_the_setting_in_both_directions(self):
        get_user_settings().set_thinking(True)
        set_thinking_override(False)
        assert thinking_wanted() is False
        get_user_settings().set_thinking(False)
        set_thinking_override(True)
        assert thinking_wanted() is True

    def test_it_never_writes_the_setting(self):
        get_user_settings().set_thinking(True)
        set_thinking_override(False)
        assert get_user_settings().thinking is True

    def test_a_non_boolean_is_no_opinion(self):
        """An override that is not a real yes or no must not turn thinking off
        because it was truthy or falsy by accident."""
        get_user_settings().set_thinking(True)
        for junk in ("false", 0, 1, [], "no"):
            set_thinking_override(junk)
            assert thinking_override() is None
            assert thinking_wanted() is True

    def test_clearing_it_returns_to_the_setting(self):
        get_user_settings().set_thinking(True)
        set_thinking_override(False)
        set_thinking_override(None)
        assert thinking_wanted() is True


class TestTwoRequestsDoNotDecideEachOther:
    @pytest.mark.asyncio
    async def test_each_task_sees_its_own(self):
        get_user_settings().set_thinking(True)
        seen: dict = {}

        async def request(name, value):
            set_thinking_override(value)
            await asyncio.sleep(0.01)  # the other request runs in the gap
            seen[name] = thinking_wanted()

        await asyncio.gather(request("quick", False), request("deep", None))
        assert seen == {"quick": False, "deep": True}


class TestTheEnginesHonourIt:
    def test_ollama_asks_for_think_false(self):
        from runtimes.models.engines import ollama_engine

        get_user_settings().set_thinking(True)
        set_thinking_override(False)
        assert ollama_engine._thinking_wanted() is False
        set_thinking_override(None)
        assert ollama_engine._thinking_wanted() is True

    def test_the_openai_compatible_engine_sends_enable_thinking_false(self):
        from runtimes.models.engines import openai_compatible_engine as oai

        get_user_settings().set_thinking(True)
        set_thinking_override(False)
        assert oai._thinking_wanted() is False
        set_thinking_override(None)
        assert oai._thinking_wanted() is True

    def test_they_share_the_one_answer(self):
        """One source of truth. Two copies of the rule is how Ollama would thin
        and TabbyAPI would not."""
        import inspect

        from runtimes.models.engines import ollama_engine, openai_compatible_engine as oai

        assert "core.thinking_override" in inspect.getsource(ollama_engine._thinking_wanted)
        assert "core.thinking_override" in inspect.getsource(oai._thinking_wanted)


class TestTheRequest:
    def test_it_accepts_the_two_fields_and_defaults_to_neither(self):
        import main

        plain = main.ChatRequest(text="hi")
        assert plain.thinking is None
        assert plain.retry is False
        quick = main.ChatRequest(text="hi", thinking=False, retry=True)
        assert quick.thinking is False
        assert quick.retry is True

    def test_the_chat_route_sets_the_override_on_every_request(self):
        import inspect

        import main

        assert "set_thinking_override(request.thinking)" in inspect.getsource(main.chat)


class TestARetryIsNotRecordedTwice:
    @pytest.fixture
    def store(self, tmp_path, monkeypatch):
        import main
        from conversations.records import ConversationRecords

        records = ConversationRecords(str(tmp_path / "c.db"))
        monkeypatch.setattr(main, "_conversation_store", lambda: records)
        return records

    def test_a_first_attempt_records_the_question(self, store):
        import main

        conv, started = main._open_conversation(main.ChatRequest(text="a bouncing ball"))
        assert started is True
        assert [m.text for m in store.messages(conv)] == ["a bouncing ball"]

    def test_a_retry_into_the_same_conversation_does_not_record_it_again(self, store):
        import main

        conv, _ = main._open_conversation(main.ChatRequest(text="a bouncing ball"))
        again, started = main._open_conversation(
            main.ChatRequest(text="a bouncing ball", conversation_id=conv, thinking=False, retry=True)
        )
        assert again == conv and started is False
        assert [m.text for m in store.messages(conv)] == ["a bouncing ball"]

    def test_a_retry_that_has_no_conversation_still_records_it_once(self, store):
        """If the first attempt never got a conversation (the store was down),
        the retry has nothing to repeat: record it, or it is lost."""
        import main

        conv, started = main._open_conversation(main.ChatRequest(text="x", retry=True))
        assert started is True
        assert [m.text for m in store.messages(conv)] == ["x"]

    def test_an_ordinary_follow_up_is_still_recorded(self, store):
        import main

        conv, _ = main._open_conversation(main.ChatRequest(text="one"))
        main._open_conversation(main.ChatRequest(text="two", conversation_id=conv))
        assert [m.text for m in store.messages(conv)] == ["one", "two"]
