"""Saying that an answer was given without the search it wanted.

`CLAUDE.md`: *disabled capabilities are visible, not silent. If a question
would have used search and search is off, say so rather than answering quietly
without it.* Before this, the only trace was a `logger.debug` line — so the
user asked about last week, the switch refused, and a model answered
confidently from weights that end before then with nothing on screen.

That is the most dangerous shape of wrong this product can produce, because a
stale answer and a correct one are indistinguishable to the person reading
them. Everything else it gets wrong looks wrong.

Also here: two fixes that fell out of removing six models on 19 August 2026,
both of which had left a name behind that no longer resolves.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import pytest

from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.planner import IntentRouter, IntentType
from core.registry import RuntimeRegistry
from core.streaming_events import EventType
from core.user_settings import UserSettings, set_user_settings_path


@contextmanager
def env(value: str | None):
    """Set, or genuinely unset, ``ZARAM_WEB_SEARCH``."""
    previous = os.environ.get("ZARAM_WEB_SEARCH")
    if value is None:
        os.environ.pop("ZARAM_WEB_SEARCH", None)
    else:
        os.environ["ZARAM_WEB_SEARCH"] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ZARAM_WEB_SEARCH", None)
        else:
            os.environ["ZARAM_WEB_SEARCH"] = previous


@pytest.fixture
def settings(tmp_path):
    """A settings file of this test's own, with the singleton restored after.

    The teardown is the load-bearing half: `web_search_enabled` consults the
    singleton, so a test leaving it pointed at a file where search is *on*
    opens the gate for everything that runs afterwards.
    """
    import core.user_settings as module

    previous_path = module._settings_path
    previous_instance = module._settings

    set_user_settings_path(str(tmp_path / "settings.json"))
    try:
        yield UserSettings(str(tmp_path / "settings.json"))
    finally:
        module._settings_path = previous_path
        module._settings = previous_instance


#: Matches the time-sensitive classifier without naming a real event.
TIME_SENSITIVE = "what happened this week"
ORDINARY = "help me think through a decision"


def _engine() -> ExecutionEngine:
    """An engine with no runtimes. The notice is decided before any step runs,
    so nothing needs to be registered to ask for it."""
    bus = EventBus()
    return ExecutionEngine(RuntimeRegistry(bus), bus)


class TestTheClassificationCarriesIt:
    def test_a_time_sensitive_question_with_search_off_is_marked(self, settings):
        with env(None):
            classification = IntentRouter().classify(TIME_SENSITIVE)

        assert classification.search_suppressed is True
        assert classification.requires_search is False

    def test_an_ordinary_question_is_not_marked(self, settings):
        """The distinction the field exists for.

        `requires_search` is False here too, and if the notice keyed on that it
        would fire on every conversational message — an indicator that appears
        constantly is one nobody reads by the second day.
        """
        with env(None):
            classification = IntentRouter().classify(ORDINARY)

        assert classification.search_suppressed is False

    def test_nothing_is_suppressed_when_search_is_on(self, settings):
        with env(None):
            settings.set_web_search(True)
            classification = IntentRouter().classify(TIME_SENSITIVE)

        assert classification.search_suppressed is False
        assert classification.requires_search is True


class TestTheNoticeReachesTheReply:
    def test_a_suppressed_search_produces_a_notice(self, settings):
        with env(None):
            notice = _engine()._search_suppressed_notice(TIME_SENSITIVE)

        assert notice is not None
        assert notice.type is EventType.NOTICE

    def test_an_ordinary_question_produces_none(self, settings):
        with env(None):
            assert _engine()._search_suppressed_notice(ORDINARY) is None

    def test_the_notice_says_why_and_offers_the_setting(self, settings):
        """A disclosure that does not name the remedy is half a disclosure."""
        with env(None):
            notice = _engine()._search_suppressed_notice(TIME_SENSITIVE)

        assert "search is off" in notice.data["content"].lower()
        assert notice.data["action"] == "settings"

    def test_a_broken_classifier_costs_the_notice_and_not_the_answer(self, settings):
        """The engine must degrade to silence, never to an exception.

        `execute` yields this before the plan exists, so raising here would
        take down the reply for a message about a *disabled feature*.
        """
        engine = _engine()

        class Exploding:
            def classify_intent(self, prompt):
                raise RuntimeError("classifier down")

        engine._planner = Exploding()

        assert engine._search_suppressed_notice(TIME_SENSITIVE) is None


class TestTheNoticeDoesNotMisstateTheSetting:
    """Reported by the maintainer, 31 August 2026: *"when web search is turned
    on by the user it doesn't keep to keep popping up again"*.

    `search_required` is a conjunction of three conditions — the question wants
    search, the switch is on, and search is worth running for the answering
    model — and `search_suppressed` was its plain negation. So the *economy*
    refusing looked exactly like the *switch* refusing, and the notice named
    the switch either way. A user who had turned search on was told on every
    search-shaped question that it was off.

    This codebase's recurring defect in a new place: one number standing for
    two questions. The remedy is the same one it always is — say which quantity
    is being asserted, and assert on that.

    A notice that misstates a setting is worse than no notice. It sends the
    user to a switch that is already where they want it, and the second time it
    happens they stop believing the indicator — on the one surface whose whole
    job is to be trusted.
    """

    #: Search-shaped without being time-sensitive, so the economy can refuse it.
    #: Recency overrides the economy, so a "what happened this week" prompt
    #: cannot reach the branch under test.
    FACTUAL = "who is the chief executive of that company"

    @contextmanager
    def _answering_from(self, locality: str):
        from core import planner

        token = planner._search_locality.set(locality)
        try:
            yield
        finally:
            planner._search_locality.reset(token)

    def test_the_economy_refusing_is_not_reported_as_the_switch(self, settings):
        """The bug itself."""
        with env(None):
            settings.set_web_search(True)
            with self._answering_from("cloud"):
                classification = IntentRouter().classify(self.FACTUAL)

        assert classification.requires_search is False, (
            "this prompt must be one the economy declines, or the test is "
            "asserting nothing"
        )
        assert classification.search_suppressed_reason == "not_applicable"
        assert _engine()._search_suppressed_notice(self.FACTUAL) is None, (
            "search is on; a notice saying it is off sends the user to a "
            "switch already set the way they want it"
        )

    def test_the_switch_refusing_still_says_so(self, settings):
        """The guard against fixing the false notice by removing the true one.

        With the switch off, the disclosure `CLAUDE.md` requires is unchanged:
        the reply came from the weights alone and the user is told.
        """
        with env(None):
            with self._answering_from("cloud"):
                classification = IntentRouter().classify(TIME_SENSITIVE)

            assert classification.search_suppressed_reason == "off"
            notice = _engine()._search_suppressed_notice(TIME_SENSITIVE)

        assert notice is not None
        assert "search is off" in notice.data["content"].lower()

    def test_a_classifier_without_the_field_still_discloses(self, settings):
        """Silence is the dangerous direction, so absence means "off".

        A classification predating `search_suppressed_reason` must keep warning
        rather than go quiet: the failure it prevents is a stale answer with
        nothing on screen, and the failure it risks is a redundant line.
        """
        engine = _engine()

        class Old:
            def classify_intent(self, prompt):
                class _C:
                    search_suppressed = True

                return _C()

        engine._planner = Old()

        assert engine._search_suppressed_notice(TIME_SENSITIVE) is not None


class TestTheKeywordFallbackReachesTheCodeIntent:
    """The path that runs when the embedder is unavailable.

    Which is precisely the machine where routing matters most, because it is
    the one where nothing else is going to catch a misrouted question.
    """

    def test_a_coding_question_no_longer_routes_to_the_terminal(self):
        classification = IntentRouter().classify(
            "is there a cleaner way to write this code"
        )

        assert classification.intent_type is IntentType.CODE

    def test_a_stack_trace_is_a_coding_question(self):
        assert (
            IntentRouter().classify("what does this stack trace mean").intent_type
            is IntentType.CODE
        )

    def test_running_the_tests_is_still_a_tool_request(self):
        """The keyword removed was `code`, not the tool intent.

        Tool is *acting on* a repository, and that reading has to survive —
        deleting the collision must not take the neighbour with it.
        """
        assert (
            IntentRouter().classify("run the tests").intent_type is IntentType.TOOL
        )

    def test_an_ordinary_question_is_still_conversation(self):
        assert (
            IntentRouter().classify(ORDINARY).intent_type is IntentType.CONVERSATION
        )


class TestTheAdapterNamesNoModel:
    """`OllamaLLM.default_model` was `gemma3:latest`, which is now uninstalled.

    Nothing sets it from outside — unlike `OllamaEngine.default_model`, which
    the models runtime assigns from the provider layer's vetted pick — so it
    was a hardcoded model name on a live path.
    """

    def test_no_model_yields_an_error_rather_than_a_guess(self):
        from implementations.ollama_llm import OllamaLLM
        from runtimes.models.engines.base_engine import ERROR_PREFIX

        chunks = list(OllamaLLM().stream_response("hello"))

        assert len(chunks) == 1
        assert chunks[0].startswith(ERROR_PREFIX)
        assert "Settings" in chunks[0]

    def test_the_default_is_not_a_model_name(self):
        """Naming a different model would repeat the mistake with a fresher
        name — the point is that this adapter cannot know."""
        from implementations.ollama_llm import OllamaLLM

        assert OllamaLLM.default_model is None

    def test_the_vision_advice_names_no_model_either(self):
        """It read `(qwen2.5vl:7b)`, uninstalled the same day. Advice pointing
        at a model the user does not have is worse than advice naming none."""
        import inspect

        from implementations.ollama_llm import OllamaLLM

        source = inspect.getsource(OllamaLLM.stream_response)
        # The yielded line only. Reading the surrounding block would match the
        # comment that records *why* the model name was removed, which is a
        # test that fails for explaining itself.
        advice = [
            line
            for line in source.splitlines()
            if "yield" in line and "does not support image input" in line
        ]

        assert len(advice) == 1
        assert "qwen" not in advice[0].lower()
