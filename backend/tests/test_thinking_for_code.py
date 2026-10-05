"""The Thinking switch has a middle state: think when the request is code.

The maintainer ran the resident 27B with Thinking off and it wrote a game with
twenty-three missing `++`. Whether thinking would have caught that is a
hypothesis -- `scripts/compare_thinking.py` is how it is measured -- but the
control for someone who wants it only when they ask for a program is cheap and
has to behave exactly: never override a message's own choice, never touch an
everyday question, never read as "on" when it was not set.
"""

from __future__ import annotations

import pytest

from core.thinking_override import decide_thinking, is_code_request


@pytest.mark.parametrize(
    "text",
    [
        "make a minecraft style game in html",
        "write a python function that parses dates",
        "debug this: ```js\nfor(;;){}\n```",
        "refactor the backend and add tests",
        "build me a website",
    ],
)
def test_code_requests_are_recognised(text):
    assert is_code_request(text)


@pytest.mark.parametrize(
    "text",
    [
        "what is the capital of france",
        "write a polite email declining the invoice",
        "summarise this contract",
        "apply for the grant",  # 'app' must not match inside 'apply'
        "what class of risk is this",
    ],
)
def test_everyday_requests_are_not(text):
    assert not is_code_request(text)


def test_a_follow_up_to_a_code_reply_is_a_code_request():
    # "the floor collision doesn't work" names no code at all.
    assert is_code_request("the floor collision doesn't work", last_answer="here:\n```html\n<p>x</p>\n```")


def test_for_code_thinks_on_a_code_request_when_everyday_thinking_is_off():
    assert decide_thinking(None, code=True, for_code=True) is True


def test_it_leaves_everyday_questions_to_the_setting():
    assert decide_thinking(None, code=False, for_code=True) is None


def test_it_does_nothing_unless_chosen():
    assert decide_thinking(None, code=True, for_code=False) is None


def test_a_messages_own_choice_always_wins():
    # "Answer without thinking" after a long think must still turn it off.
    assert decide_thinking(False, code=True, for_code=True) is False
    assert decide_thinking(True, code=False, for_code=False) is True


def test_the_setting_is_stored_off_by_default_and_round_trips(tmp_path):
    from core.user_settings import UserSettings

    path = str(tmp_path / "settings.json")
    first = UserSettings(path)
    assert first.thinking_for_code is False
    first.set_thinking_for_code(True)
    again = UserSettings(path)
    assert again.thinking_for_code is True
    assert again.thinking is True  # the everyday setting is untouched


def test_the_chat_route_applies_it(monkeypatch):
    # The route is where the decision is made; a helper nothing calls is the
    # base rate here. Read the source of the one place that sets the override.
    import inspect

    import main

    source = inspect.getsource(main)
    assert "decide_thinking(" in source and "is_code_request(request.text" in source
