"""The contract nobody was asserting: search output reaches the model.

`main._format_search_results` was complete, correct and tested — and called by
nothing. Two tests checked that it *formatted* well. None checked that anything
*used* it, and nothing did. Meanwhile the engine captured the search step's
output into `step_results` and no line ever read it.

So Zaram searched, the request left the machine, the egress log recorded it
honestly, results came back, and the reasoning step ran with the bare question.
The model answered from its weights, which is exactly what the search existed
to prevent, and every layer reported success. That is why several attempts to
fix "web search does nothing" failed: they examined the search layer, which
was the one part working.

CLAUDE.md: *a test that asserts nothing is worse than no test, because it
reports coverage it does not have.* These assert the seam rather than the
formatting — what the model is handed, and what it is handed when the search
fails, returns nothing, or returns something unreadable.
"""

from __future__ import annotations

import json

from core.query_classifier import SEARCH_MARKER
from core.search_context import format_search_results, result_count, search_prompt

QUESTION = "what happened this week"

PAYLOAD = json.dumps(
    {
        "results": [
            {
                "title": "A thing happened",
                "url": "https://news.example.com/a",
                "snippet": "The thing happened on Tuesday.",
                "published": "2026-08-18",
            }
        ],
        "total_results": 1,
    }
)

EMPTY = json.dumps({"results": [], "total_results": 0})


class TestTheSourcesReachThePrompt:
    def test_the_model_is_handed_the_sources(self):
        built = search_prompt(QUESTION, PAYLOAD)

        assert SEARCH_MARKER in built
        assert "https://news.example.com/a" in built
        assert "The thing happened on Tuesday." in built

    def test_the_question_survives(self):
        """Folding sources in must not lose what was asked.

        The block ends with the question deliberately — a model reads its last
        instruction most reliably, and the last thing here has to be the
        question rather than the sources.
        """
        built = search_prompt(QUESTION, PAYLOAD)

        assert built.rstrip().endswith(QUESTION)

    def test_the_search_step_output_is_the_shape_the_engine_stores(self):
        """`ModelsService.search_knowledge` yields one JSON *string*, and the
        engine accumulates step output as text — so the parser has to take a
        string, not the dict the formatter was originally written for. Getting
        this wrong is silent: it degrades to the bare question."""
        assert search_prompt(QUESTION, PAYLOAD) != QUESTION


class TestItDegradesToTheQuestion:
    """Never raises, never returns empty. An answer without sources is worse
    than an answer with them, and better than no answer at all."""

    def test_no_results_leaves_the_question_alone(self):
        assert search_prompt(QUESTION, EMPTY) == QUESTION

    def test_a_failed_step_leaves_the_question_alone(self):
        assert search_prompt(QUESTION, "[FALLBACK] knowledge.search failed") == QUESTION

    def test_empty_output_leaves_the_question_alone(self):
        assert search_prompt(QUESTION, "") == QUESTION
        assert search_prompt(QUESTION, None) == QUESTION

    def test_json_that_is_not_an_object_leaves_the_question_alone(self):
        assert search_prompt(QUESTION, "[1, 2, 3]") == QUESTION


class TestCountingIsThreeValued:
    """Zero and unknown are different answers, and the notice depends on it.

    Zero means the search ran and the web had nothing, which is worth telling
    the user. ``None`` means the output could not be read — which is not a
    statement about the web and must not be reported as one.
    """

    def test_results_are_counted(self):
        assert result_count(PAYLOAD) == 1

    def test_an_empty_search_counts_zero(self):
        assert result_count(EMPTY) == 0

    def test_an_unreadable_output_counts_nothing(self):
        assert result_count("[FALLBACK] knowledge.search failed") is None
        assert result_count("") is None

    def test_zero_and_unknown_do_not_compare_equal(self):
        """The bug this guards is `if not count:`, which treats both as zero
        and announces "the web had nothing" about a search that errored."""
        assert result_count(EMPTY) is not None
        assert result_count("nonsense") != 0


class TestFormattingStillHolds:
    """Carried over from `test_alpha10c_acceptance`, which tested this well —
    it only ever tested it in isolation from anything that called it."""

    def test_sources_are_numbered_and_labelled(self):
        built = format_search_results(QUESTION, json.loads(PAYLOAD))

        # The label now names the origin. This payload carries no `type` and no
        # `provider` — the shape every caller predating that field produces —
        # and its `https://` reference is what classifies it as web.
        assert "Source 1 — from the web:" in built
        assert "Title: A thing happened" in built
        assert "Published: 2026-08-18" in built

    def test_the_model_is_told_to_prefer_live_sources(self):
        """Without this the model reconciles sources against its weights and
        hedges about a cutoff the user has just paid egress to get past.

        **The instruction is now scoped to web sources, and this test used to
        assert the bug.** It said `ALWAYS trust the live sources`, printed over
        every source in the block — including the user's own notes and their own
        earlier messages, which `knowledge.search` returns in the same list.
        Measured live, five of six were local. See
        `test_search_sources_are_labelled.py`.
        """
        built = format_search_results(QUESTION, json.loads(PAYLOAD))

        assert "trust the web source" in built
        assert "ALWAYS trust the live sources" not in built


# --------------------------------------------------------------------------- #
# The seam itself.
#
# Everything above tests the helper. The bug was never in the helper — it was
# that nothing called it, and a test suite full of helper tests reported
# coverage it did not have. These drive the real engine and assert on what the
# model was actually handed.
# --------------------------------------------------------------------------- #

from core.bootstrapper import KernelBootstrapper  # noqa: E402
from core.contracts import Capability, RuntimeMetadata, RuntimeState  # noqa: E402
from core.execution_engine import ExecutionEngine  # noqa: E402
from core.planner import IntentPlanner  # noqa: E402


class _RecordingService:
    """Answers both steps, and keeps the prompt the model was given."""

    def __init__(self, search_output: str):
        self.search_output = search_output
        self.prompt_seen: str | None = None

    def search_knowledge(self, query, persona="zaram_prime"):
        yield self.search_output

    def generate_response(self, user_text, personality_context="", model=None):
        self.prompt_seen = user_text
        yield "an answer"


class _SearchingRuntime:
    """Serves both capabilities a search plan needs."""

    def __init__(self, service):
        self._service = service
        self._state = RuntimeState.READY

    def get_runtime_id(self):
        return "fake"

    def get_version(self):
        return "0.0.1"

    def get_metadata(self):
        return RuntimeMetadata(
            runtime_id="fake",
            version="0.0.1",
            priority="normal",
            capabilities=[
                Capability(id="reasoning.generate", runtime_id="fake"),
                Capability(id="knowledge.search", runtime_id="fake"),
            ],
        )

    async def initialize(self):
        self._state = RuntimeState.READY

    async def shutdown(self):
        self._state = RuntimeState.STOPPED

    def get_state(self):
        return self._state

    def health_check(self):
        return {"state": self._state.value}

    def get_service(self):
        return self._service


class _SearchPlanner(IntentPlanner):
    """Forces the search plan, so the test asserts the injection rather than
    the classifier's opinion of the question."""

    # `**_` because this double forces one fixed plan and cares about none of
    # the planner's inputs. Mirroring the real signature would make every
    # future keyword a failure in a search test that has no opinion about it.
    def create_plan(self, prompt, priority="normal", **_):
        from core.contracts import ExecutionPlan, ExecutionStep, PlanState
        import time as _time
        import uuid as _uuid

        return ExecutionPlan(
            correlation_id=str(_uuid.uuid4()),
            original_prompt=prompt,
            steps=[
                ExecutionStep(
                    capability_id="knowledge.search",
                    input_data={"query": prompt, "persona": "zaram_prime"},
                    depends_on=[],
                ),
                ExecutionStep(
                    capability_id="reasoning.generate",
                    input_data={"prompt": prompt},
                    depends_on=[0],
                ),
            ],
            state=PlanState.PENDING,
            priority=priority,
            created_at=_time.time(),
        )


def _engine_with(search_output: str):
    service = _RecordingService(search_output)
    kernel = KernelBootstrapper()
    kernel.registry.register(_SearchingRuntime(service))
    engine = ExecutionEngine(kernel.registry, kernel.event_bus)
    engine._planner = _SearchPlanner()
    return engine, service


class TestTheEngineHandsTheSourcesToTheModel:
    def test_the_model_receives_the_sources(self):
        """The assertion that would have caught this. Before the fix the model
        was handed the bare question and this fails."""
        engine, service = _engine_with(PAYLOAD)

        list(engine.execute(QUESTION))

        assert service.prompt_seen is not None
        assert "https://news.example.com/a" in service.prompt_seen
        assert SEARCH_MARKER in service.prompt_seen

    def test_the_search_output_never_reaches_the_user_as_text(self):
        """`knowledge.search` is an internal capability: its raw JSON is
        context for the next step, not something to stream into the reply."""
        engine, _ = _engine_with(PAYLOAD)

        streamed = "".join(t for t in engine.execute(QUESTION) if isinstance(t, str))

        assert "news.example.com" not in streamed
        assert streamed.strip() == "an answer"

    def test_an_empty_search_still_answers(self):
        engine, service = _engine_with(EMPTY)

        streamed = "".join(t for t in engine.execute(QUESTION) if isinstance(t, str))

        assert streamed.strip() == "an answer"
        assert service.prompt_seen == QUESTION

    def test_an_empty_search_says_so(self):
        """Otherwise a search that found nothing is indistinguishable from one
        that never ran, and the answer is from the weights in both cases."""
        from core.streaming_events import EventType

        engine, _ = _engine_with(EMPTY)

        notices = [
            e for e in engine.execute(QUESTION)
            if not isinstance(e, str) and getattr(e, "type", None) is EventType.NOTICE
        ]

        assert any("no results" in n.data["content"].lower() for n in notices)

    def test_a_readable_search_says_nothing(self):
        """The notice has to stay rare to stay worth reading."""
        from core.streaming_events import EventType

        engine, _ = _engine_with(PAYLOAD)

        notices = [
            e for e in engine.execute(QUESTION)
            if not isinstance(e, str) and getattr(e, "type", None) is EventType.NOTICE
        ]

        assert not any("no results" in n.data["content"].lower() for n in notices)
