"""A tool call says which checklist step it was made for.

The maintainer's direction, 28 September 2026, after reading what Antigravity
does differently: *an agent's output to a person should be verifiable
deliverables — the checklist, the plan, what it actually ran — not a stream of
tool invocations.*

Zaram had both halves and no join. `PlanCard` drew the checklist; the calls
drew as a flat run of rows beside it. A nine-step task showed nine promises
above twenty anonymous rows, and nothing on screen said which row belonged to
which promise — so "watch it work" meant reading the rows and guessing.

`plan_step` is that join. These tests pin the three answers it has to get
right, and two of them are the ones that make it a record rather than a
decoration: **`doing` before `todo`**, because the model said which it is on,
and **nothing at all** once every step is ticked, because work done after the
last claim belongs under none of them.
"""

from __future__ import annotations

from core.streaming_events import StreamEvent


class _Engine:
    """Just enough of the engine to exercise the step lookup.

    `_open_plan_step` reads only `_plan_items`, which reads only
    `_checklists` — so binding the real method to this is the whole subject
    under test and nothing else. Standing up an `ExecutionEngine` would drag in
    a bootstrapper, a planner and a provider manager to assert one index.
    """

    def __init__(self, items: list) -> None:
        self._checklists = {"s": list(items)}

    def _plan_items(self, session_id: str) -> list:
        from core.execution_engine import ExecutionEngine

        return ExecutionEngine._plan_items(self, session_id)  # type: ignore[arg-type]

    def open_step(self) -> int | None:
        from core.execution_engine import ExecutionEngine

        return ExecutionEngine._open_plan_step(self, "s")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Which step a call belongs to
# --------------------------------------------------------------------------- #


def test_the_step_the_model_says_it_is_on_wins():
    engine = _Engine(
        [
            {"text": "Read the failing test", "status": "done"},
            {"text": "Fix add()", "status": "doing"},
            {"text": "Run the tests", "status": "todo"},
        ]
    )
    assert engine.open_step() == 1


def test_the_first_unfinished_step_is_the_honest_second_guess():
    """A model that ticks one step and starts the next without marking it
    `doing` is the common case. Filing its calls under the step it is plainly
    on beats filing them under nothing."""
    engine = _Engine(
        [
            {"text": "Read the failing test", "status": "done"},
            {"text": "Fix add()", "status": "todo"},
        ]
    )
    assert engine.open_step() == 1


def test_a_finished_checklist_owns_nothing():
    """**The one that keeps the card honest.**

    Work done after the last step is ticked belongs to no step. Filing it under
    the final one would put calls beneath a claim that was already closed —
    which is the shape of a status claim that is false, and this card is the
    one place the claim and the evidence appear together.
    """
    engine = _Engine([{"text": "Fix add()", "status": "done"}])
    assert engine.open_step() is None


def test_no_plan_means_no_step():
    """Most replies never call `plan`, and must not be given a step of 0."""
    assert _Engine([]).open_step() is None


def test_a_malformed_item_does_not_take_the_whole_reply_down():
    """The list is model-written, so it can contain anything."""
    engine = _Engine(["not a dict", {"text": "Fix add()", "status": "doing"}])
    assert engine.open_step() == 1


# --------------------------------------------------------------------------- #
# How it travels
# --------------------------------------------------------------------------- #


def test_the_event_carries_the_step_when_there_is_one():
    event = StreamEvent.tool_call("code", "read_file", "allow", plan_step=2)
    assert event.data["plan_step"] == 2


def test_step_zero_survives_the_trip():
    """The first step of every plan is the one most calls belong to, and `0`
    is the value most easily lost to a truthiness test on the way out."""
    event = StreamEvent.tool_call("code", "read_file", "allow", plan_step=0)
    assert event.data["plan_step"] == 0


def test_the_field_is_absent_rather_than_null_on_the_common_case():
    """Most replies have no plan. A key that is present-but-meaningless is one
    the next reader has to test twice."""
    event = StreamEvent.tool_call("code", "read_file", "allow")
    assert "plan_step" not in event.data
