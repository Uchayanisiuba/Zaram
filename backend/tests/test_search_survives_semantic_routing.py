"""A time-sensitive question gets a search even when it routes as conversation.

**The failure this exists for.** Asked "Who is the current president of the
United States?", Zaram answered "Joe Biden" — from training data — with web
search switched on, `duckduckgo.com` allowed in the egress policy, and not one
source event in the stream. Nothing anywhere reported a failure, because from
the planner's point of view nothing had failed.

`IntentRouter.classify` tries the semantic router first and **returns the
moment it produces anything**. The semantic path decided search by
`decision.intent == "search"` alone, so on that path `needs_search()` was never
consulted. Measured against the live router: that question routes to
`conversation` at **0.022** confidence, while `needs_search` matches it on
three separate patterns — "who is", "current", and "president".

The conceptual error is treating `search` as a rival intent to `conversation`.
They are not exclusive. "Who is the current president" is a perfectly
conversational question whose answer changes, and the two signals belong in a
union: the intent says what kind of work this is, the classifier says whether
that work needs facts newer than the weights.

These tests use a stub router rather than the real embedder. What is under test
is the planner's *combination* of the two signals, which is where the defect
was — not the embedder's opinion, which is a separate and much slower question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from core.planner import IntentPlanner, IntentType


@dataclass
class _Decision:
    """The shape `SemanticIntentRouter.route` returns."""

    intent: str
    confidence: float
    reason: str = "stub"
    exemplar: str = "stub"
    runner_up: str | None = None
    runner_up_score: float | None = None
    scores: dict[str, float] = field(default_factory=dict)


class _RouterSaying:
    """A semantic router with a fixed opinion."""

    def __init__(self, intent: str, confidence: float = 0.5) -> None:
        self._decision = _Decision(intent=intent, confidence=confidence)

    def is_semantic(self) -> bool:
        return True

    def route(self, _prompt: str) -> Any:
        return self._decision


#: The reported question, plus two more the same reasoning covers. Each is
#: something a person would ask conversationally and whose answer is not in any
#: model's weights.
TIME_SENSITIVE = [
    "Who is the current president of the United States?",
    "What is the latest news about the election?",
    "What is the current price of bitcoin?",
]


@pytest.fixture(autouse=True)
def _search_is_permitted(monkeypatch):
    """Rule 5's gates are a separate question and are asserted separately
    below. Here they are open, so a failure means the planner and not policy."""
    monkeypatch.setattr("core.planner.web_search_enabled", lambda: True)
    # Takes the prompt too: `search_applies_to` gained it when recency was made
    # to outrank the local/cloud economy, and a stub with the old arity fails
    # with a TypeError that names neither the change nor this line.
    monkeypatch.setattr("core.planner.search_applies_to", lambda _locality, _prompt="": True)


@pytest.mark.parametrize("question", TIME_SENSITIVE)
def test_conversation_intent_still_searches_when_the_answer_changes(question):
    """The regression, stated as directly as it can be.

    The router calls it conversation — which it is — and the plan must still
    fetch the facts.
    """
    planner = IntentPlanner(semantic_router=_RouterSaying("conversation", 0.022))

    classification = planner.classify_intent(question)
    assert classification.requires_search is True, (
        f"{question!r} routed as conversation and lost its search step"
    )

    steps = [step.capability_id for step in planner.create_plan(question).steps]
    assert steps == ["knowledge.search", "reasoning.generate"], (
        f"expected a search before the answer, got {steps}"
    )


def test_the_intent_itself_is_not_overridden():
    """Search is added to the plan; it does not rewrite what kind of request
    this is. A question can be conversational and still need facts, and
    flipping the intent to SEARCH would be the same merge-two-questions error
    in the other direction."""
    planner = IntentPlanner(semantic_router=_RouterSaying("conversation", 0.022))
    classification = planner.classify_intent(TIME_SENSITIVE[0])
    assert classification.intent_type is IntentType.CONVERSATION


def test_an_ordinary_question_still_does_not_search():
    """The other half, and the one that would catch an over-correction.

    A fix that searched for everything would have passed every assertion above
    while making the product slower, chattier and less private — and it would
    have sent a question off the machine that had no need to leave.
    """
    planner = IntentPlanner(semantic_router=_RouterSaying("conversation", 0.9))
    classification = planner.classify_intent("Explain recursion to me")
    assert classification.requires_search is False
    steps = [step.capability_id for step in planner.create_plan("Explain recursion to me").steps]
    assert steps == ["reasoning.generate"]


def test_a_search_intent_is_unaffected():
    """The path that already worked keeps working."""
    planner = IntentPlanner(semantic_router=_RouterSaying("search", 0.65))
    assert planner.classify_intent("What is the latest AI news today?").requires_search is True


def test_the_capabilities_name_the_search_they_require():
    """A classification that requires a search and does not list it is a
    near-truth: `create_plan` builds steps from `requires_search` so the plan
    is right either way, and anything reading the classification to explain the
    routing decision would be told something false."""
    planner = IntentPlanner(semantic_router=_RouterSaying("conversation", 0.022))
    classification = planner.classify_intent(TIME_SENSITIVE[0])
    assert "knowledge.search" in classification.capabilities


class TestPolicyStillDecides:
    """Rule 5 is not weakened by any of the above.

    Unioning the two signals decides whether search is *wanted*. Whether it is
    *permitted* is a separate gate and stays after it — routing more accurately
    must never become a route around the user's switch.
    """

    def test_the_switch_being_off_wins(self, monkeypatch):
        monkeypatch.setattr("core.planner.web_search_enabled", lambda: False)
        planner = IntentPlanner(semantic_router=_RouterSaying("conversation", 0.022))
        assert planner.classify_intent(TIME_SENSITIVE[0]).requires_search is False

    def test_locality_being_local_only_wins(self, monkeypatch):
        monkeypatch.setattr("core.planner.search_applies_to", lambda _locality, _prompt="": False)
        planner = IntentPlanner(semantic_router=_RouterSaying("conversation", 0.022))
        assert planner.classify_intent(TIME_SENSITIVE[0]).requires_search is False
