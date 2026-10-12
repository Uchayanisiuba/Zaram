"""Ordinary prompts are not desktop control and not a change to Zaram's settings.

10 October 2026, found auditing a batch of changes. The computer-use and settings
intents matched single common words -- `type`, `window`, `app`, `copy`, `name`,
`local`, `use`, `tone`, `tool`, `allow`, `morning` -- and were checked ahead of vision,
search and the rest, so "what type of invoice" or "write this in a professional tone"
was classified as desktop control or a settings change, and given an `mcp.list_tools`
step it did not ask for. Eleven older tests caught it by accident.

A prompt may only be routed there by a phrase that asks for it.
"""

from __future__ import annotations

import pytest

from core.planner import IntentRouter, IntentType

ORDINARY = [
    "what is the name of my largest client",
    "what type of invoice should I send for a retainer",
    "write this email in a professional tone",
    "copy edit this paragraph for me",
    "summarise the app store reviews for the product",
    "close the loop with the client on the quote",
    "use bullet points in the summary",
    "what is the local tax rate on software",
    "explain how the cloud billing works",
    "which window should the deposit be paid in",
    "move the deadline to Friday in the plan",
    "select the best of these three proposals",
    "every client I have had in March",
    "what did I decide about the server migration",
    "how do I grant a licence to a client",
    "I want to allow two weeks for review",
    "give me a morning routine for freelancers",
    "what is the best style guide for contracts",
    "what permission does a contractor need to enter the site",
    "can you tell me what a tool call is",
]

WANTS_THE_DESKTOP = ["click the save button", "launch notepad", "press enter", "bring vscode to front"]
WANTS_A_SETTING = ["switch to avatar", "set voice to bella", "prefer cloud", "every monday morning", "grant click tool"]


@pytest.fixture(scope="module")
def router():
    return IntentRouter()


@pytest.mark.parametrize("prompt", ORDINARY)
def test_an_everyday_prompt_gets_no_tool_step_it_did_not_ask_for(router, prompt):
    got = router.classify(prompt)
    assert got.intent_type not in (IntentType.COMPUTER_USE, IntentType.SETTINGS), (prompt, got.intent_type)
    assert "mcp.list_tools" not in got.capabilities, (prompt, got.capabilities)
    assert got.requires_computer_use is False and got.requires_settings is False


@pytest.mark.parametrize("prompt", WANTS_THE_DESKTOP)
def test_a_phrase_that_asks_for_the_desktop_still_gets_it(router, prompt):
    assert router.classify(prompt).intent_type is IntentType.COMPUTER_USE


@pytest.mark.parametrize("prompt", WANTS_A_SETTING)
def test_a_phrase_that_asks_for_a_setting_still_gets_it(router, prompt):
    assert router.classify(prompt).intent_type is IntentType.SETTINGS


def test_the_keyword_sets_hold_no_single_common_word():
    for common in ("type", "window", "app", "screen", "copy", "close", "select", "name",
                   "local", "use ", "tone", "tool", "allow", "morning", "auto", "settings"):
        assert common not in IntentRouter._COMPUTER_USE_KEYWORDS, common
        assert common not in IntentRouter._SETTINGS_KEYWORDS, common


@pytest.mark.parametrize("prompt", WANTS_THE_DESKTOP + ["take a screenshot", "list windows", "click on the start button"])
def test_a_desktop_request_is_given_the_tools_to_act(prompt):
    """10 October 2026: these classified as COMPUTER_USE and the plan never listed the
    tools, so with cua-driver installed and healthy the model could only describe a
    click. The intent now takes the tool plan, the same as TOOL."""
    from core.planner import IntentPlanner

    ids = [step.capability_id for step in IntentPlanner().create_plan(prompt).steps]
    assert ids[0] == "mcp.list_tools", (prompt, ids)
    assert "reasoning.generate" in ids


@pytest.mark.parametrize("prompt", ORDINARY)
def test_an_ordinary_prompt_still_gets_no_tool_list(prompt):
    from core.planner import IntentPlanner

    ids = [step.capability_id for step in IntentPlanner().create_plan(prompt).steps]
    assert "mcp.list_tools" not in ids, (prompt, ids)
