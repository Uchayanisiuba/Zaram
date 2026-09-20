"""A plan step is shown while it runs, in words, and settled when it is done.

Until 19 September 2026 a web search on an ordinary turn ran as a plan step
before generation and reached the screen, at best, as a notice afterwards.
`StreamEvent.step_start` and `step_complete` existed from the first day and
were only ever `_publish`ed to the event bus — built, unreached, instance
eighteen of this repository's base-rate failure. They are yielded into the
stream now, carrying the row's own words from `core/step_labels.py`, with
Claude's rows as the reference the maintainer named. `docs/PLAN.md` B1.

Three contracts:

1. The row's start reaches the stream *before* the step's output does, and
   its completion after — a person watches it happen.
2. The words are a table, not a guess: a capability the table does not name
   gets no row, and bookkeeping steps (`mcp.list_tools`, `reasoning.generate`)
   never do.
3. Recall gets a row when it recalled something, and none when it did not.
"""

from __future__ import annotations

from core.step_labels import MAX_TARGET, bound_target, describe_step
from core.streaming_events import EventType, StreamEvent
from tests.test_search_reaches_the_model import (  # the doubles, not the contract
    EMPTY,
    PAYLOAD,
    QUESTION,
    _engine_with,
)


def _events(items, kind):
    return [i for i in items if isinstance(i, StreamEvent) and i.type is kind]


class TestTheWords:
    def test_a_search_is_searching_the_web_for_its_query(self):
        row = describe_step("knowledge.search", {"query": "fable outage", "persona": "x"})
        assert row is not None
        assert (row.doing, row.done, row.target) == ("Searching the web", "Searched the web", "fable outage")

    def test_a_drawing_is_aimed_at_what_was_asked_for(self):
        row = describe_step("image.generate", {"prompt": "a lighthouse at dusk"})
        assert row is not None and row.doing == "Drawing" and row.target == "a lighthouse at dusk"

    def test_bookkeeping_steps_get_no_row(self):
        assert describe_step("mcp.list_tools", {"query": "q"}) is None
        assert describe_step("reasoning.generate", {"prompt": "q"}) is None

    def test_an_unknown_capability_gets_no_row_rather_than_a_guessed_one(self):
        assert describe_step("something.new", {"query": "q"}) is None
        assert describe_step("", None) is None

    def test_the_target_is_one_bounded_line(self):
        long = "word " * 40
        bounded = bound_target(long + "\n\nmore")
        assert "\n" not in bounded
        assert len(bounded) <= MAX_TARGET + 1
        assert bounded.endswith("…")
        assert bound_target("  a   b  ") == "a b"
        assert bound_target(None) == ""


class TestTheRowIsInTheStream:
    def test_start_comes_first_and_completion_says_how_many_results(self):
        engine, _ = _engine_with(PAYLOAD)

        out = list(engine.execute(QUESTION))

        starts = _events(out, EventType.STEP_START)
        ends = _events(out, EventType.STEP_COMPLETE)
        search_starts = [e for e in starts if e.data["capability_id"] == "knowledge.search"]
        search_ends = [e for e in ends if e.data["capability_id"] == "knowledge.search"]
        assert len(search_starts) == 1 and len(search_ends) == 1

        start, end = search_starts[0], search_ends[0]
        assert start.data["doing"] == "Searching the web"
        assert start.data["done"] == "Searched the web"
        assert start.data["target"] == QUESTION
        assert end.data["step_id"] == start.data["step_id"] != ""
        assert end.data["success"] is True
        assert end.data["detail"] == "1 result"
        assert isinstance(end.data["seconds"], float)

        # Before the answer's first token, and the completion before it too:
        # the search happened, was seen, and *then* the reply arrived.
        first_text = next(i for i, item in enumerate(out) if isinstance(item, str) and item.strip())
        assert out.index(start) < out.index(end) < first_text

    def test_an_empty_search_says_so(self):
        engine, _ = _engine_with(EMPTY)
        ends = _events(list(engine.execute(QUESTION)), EventType.STEP_COMPLETE)
        assert [e.data["detail"] for e in ends if e.data["capability_id"] == "knowledge.search"] == ["0 results"]

    def test_the_answer_step_gets_no_row(self):
        engine, _ = _engine_with(PAYLOAD)
        out = list(engine.execute(QUESTION))
        assert not [
            e for e in _events(out, EventType.STEP_START) if e.data["capability_id"] == "reasoning.generate"
        ]

    def test_recall_gets_no_row_when_nothing_was_recalled(self):
        engine, _ = _engine_with(PAYLOAD)
        out = list(engine.execute(QUESTION))
        assert not [
            e for e in _events(out, EventType.STEP_COMPLETE) if e.data["capability_id"] == "memory.recall"
        ]


class TestWhereTheTimeWent:
    """A1 of `docs/PLAN.md`: one `timing` event per reply, every phase a
    measured number or ``None``, never a zero standing in for "unmeasured"."""

    def test_one_timing_event_after_the_reply(self):
        engine, _ = _engine_with(PAYLOAD)
        out = list(engine.execute(QUESTION))

        timings = _events(out, EventType.TIMING)
        assert len(timings) == 1
        t = timings[0].data
        for key in ("recall_ms", "plan_ms", "steps_ms", "first_token_ms", "generation_ms", "total_ms"):
            assert key in t
        assert isinstance(t["total_ms"], int) and t["total_ms"] >= 0
        assert isinstance(t["plan_ms"], int)
        assert isinstance(t["steps_ms"], int), "the search step ran and was timed"
        assert isinstance(t["first_token_ms"], int), "the answer generated a first token"
        assert isinstance(t["generation_ms"], int)
        # After the last text token, so it reports on the whole reply.
        last_text = max(i for i, item in enumerate(out) if isinstance(item, str) and item.strip())
        assert out.index(timings[0]) > last_text


class TestThePlannersStepsAreAChecklist:
    """C1 of `docs/PLAN.md`: a multi-step plan ticks as a checklist, in the
    same shape as the model's own `plan`; a one-step plan shows no list."""

    def test_search_then_answer_ticks(self):
        engine, _ = _engine_with(PAYLOAD)
        out = list(engine.execute(QUESTION))

        plans = [e.data["items"] for e in _events(out, EventType.PLAN)]
        assert plans, "a two-step plan sends a checklist"
        texts = [i["text"] for i in plans[0]]
        assert texts == [f"Searching the web — {QUESTION}", "Answering"]
        assert [i["status"] for i in plans[0]] == ["todo", "todo"]
        # It moved: the search was doing, then done, then the answer.
        statuses = [tuple(i["status"] for i in p) for p in plans]
        assert ("doing", "todo") in statuses
        assert ("done", "todo") in statuses
        assert statuses[-1] == ("done", "done")
        # Whole each time, never a diff; no `awaiting_go` — nothing to consent to.
        assert all(len(p) == 2 for p in plans)
        assert not any(e.data["awaiting_go"] for e in _events(out, EventType.PLAN))

    def test_a_failed_step_is_skipped_with_its_reason(self):
        engine, _ = _engine_with("[FALLBACK] knowledge.search failed: search is off\n")
        out = list(engine.execute(QUESTION))
        last = _events(out, EventType.PLAN)[-1].data["items"]
        assert last[0]["status"] == "skipped"
        assert "search is off" in last[0].get("reason", "")

    def test_a_single_step_plan_shows_no_list(self):
        from core.contracts import ExecutionPlan, ExecutionStep, PlanState
        from core.execution_engine import ExecutionEngine

        engine, _ = _engine_with(PAYLOAD)
        one = ExecutionPlan(
            correlation_id="c", original_prompt="q",
            steps=[ExecutionStep(capability_id="knowledge.search", input_data={"query": "q"}, depends_on=[])],
            state=PlanState.PENDING, priority="normal", created_at=0.0,
        )
        assert ExecutionEngine._planner_checklist(engine, one) is None
