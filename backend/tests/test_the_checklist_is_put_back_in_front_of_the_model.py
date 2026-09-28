"""The plan ticks, because the model is shown it again.

**The checklist was write-once.** `plan`'s own description says *"Mark a step
done when its tool call has returned"*, and that instruction was given at the
top of the first round and never repeated. A model working through a nine-step
task writes the list, starts working, and never mentions it again — so
`PlanCard` rendered `todo` beside every step while the work visibly happened,
and "0/9 done" sat under a finished answer.

Reported 28 September 2026 as *"Zaram doesn't seem to check off completed
tasks"*, with a screenshot of `Plan 0/1 done` beneath a reply that had plainly
done the thing.

That is not a model ignoring an instruction. It is an instruction given once
and never repeated, which is the same mistake as putting the tool rules at the
tail of a prompt instead of the head — and this module already knows that,
because its ordering guarantee exists for exactly that reason.

So the fix is re-injection, and these tests pin the four properties that make
it safe rather than merely present.
"""

from __future__ import annotations

from core.tool_loop import ToolCall, ToolTurn, current_plan, result_prompt


def _plan_turn(items: list[dict]) -> ToolTurn:
    """A `plan` call as the loop records it."""
    return ToolTurn(
        call=ToolCall(server="code", tool="plan", arguments={"items": items}),
        result={"ok": True},
    )


def _work_turn(tool: str = "read_file") -> ToolTurn:
    return ToolTurn(
        call=ToolCall(server="code", tool=tool, arguments={"path": "app.py"}),
        result="...",
    )


# --------------------------------------------------------------------------- #
# It comes back
# --------------------------------------------------------------------------- #


def test_an_open_checklist_is_shown_again_with_its_statuses():
    """The bug, directly: the list must reappear, and carry where each step got to."""
    turns = [
        _plan_turn(
            [
                {"text": "Write the HTML and CSS", "status": "done"},
                {"text": "Add the game loop", "status": "doing"},
                {"text": "Wire the keyboard", "status": "todo"},
            ]
        ),
        _work_turn(),
    ]
    prompt = result_prompt("build me a tetris game", turns, may_call_again=True)

    assert "checklist" in prompt.lower()
    assert "[done] Write the HTML and CSS" in prompt
    assert "[doing] Add the game loop" in prompt
    assert "[todo] Wire the keyboard" in prompt


def test_it_asks_for_the_whole_list_back():
    """`plan` replaces rather than patches, so a partial list would erase steps.

    The reminder has to say so, because the model is being asked to call the
    tool again several rounds after it read the tool's description.
    """
    turns = [_plan_turn([{"text": "Read the file", "status": "todo"}]), _work_turn()]
    prompt = result_prompt("anything", turns, may_call_again=True)
    assert "whole list" in prompt


# --------------------------------------------------------------------------- #
# It goes away
# --------------------------------------------------------------------------- #


def test_a_finished_checklist_is_not_repeated():
    """A list that is already right must not be re-sent.

    Two costs, and the second is the real one: tokens every round, and an
    invitation to keep editing something that is correct. A model handed a
    finished list and told to correct it will find something to change.
    """
    turns = [
        _plan_turn(
            [
                {"text": "Write the HTML", "status": "done"},
                {"text": "Add the loop", "status": "done"},
            ]
        ),
        _work_turn(),
    ]
    prompt = result_prompt("anything", turns, may_call_again=True)
    assert "checklist" not in prompt.lower()


def test_no_checklist_means_no_reminder():
    """Most replies never call `plan`, and they must not be told about one."""
    prompt = result_prompt("what is 2 + 2", [_work_turn()], may_call_again=True)
    assert "checklist" not in prompt.lower()


def test_nothing_is_asked_of_a_model_that_has_no_round_left():
    """**The last word stays the closing instruction.**

    This module's ordering guarantee is that the true instruction is read last.
    A model being told to answer now has no round in which to tick anything, so
    asking would spend the final line of the prompt on an impossible request —
    and risk it answering with a plan update instead of an answer.
    """
    turns = [_plan_turn([{"text": "Add the loop", "status": "doing"}]), _work_turn()]
    prompt = result_prompt("anything", turns, may_call_again=False)
    assert "checklist" not in prompt.lower()


def test_the_reminder_comes_before_the_closing_instruction():
    """Order, asserted — not left to whoever edits `result_prompt` next."""
    turns = [_plan_turn([{"text": "Add the loop", "status": "doing"}]), _work_turn()]
    prompt = result_prompt("anything", turns, may_call_again=True)

    reminder_at = prompt.lower().index("checklist")
    closing_at = prompt.index("Now either answer the original question")
    assert reminder_at < closing_at


# --------------------------------------------------------------------------- #
# Where the list comes from
# --------------------------------------------------------------------------- #


def test_the_latest_plan_call_wins():
    """The list is derived from the turns, so the most recent call *is* the record.

    No second copy is kept, deliberately: `plan` already sends the whole list
    every time, and a stored one could disagree with what the model last said.
    """
    turns = [
        _plan_turn([{"text": "Add the loop", "status": "todo"}]),
        _work_turn(),
        _plan_turn([{"text": "Add the loop", "status": "done"},
                    {"text": "Wire the keyboard", "status": "todo"}]),
    ]
    plan = current_plan(turns)
    assert plan is not None
    assert [item["status"] for item in plan] == ["done", "todo"]


def test_a_plan_call_with_no_items_is_not_a_plan():
    """An empty list would otherwise render as a checklist with nothing on it."""
    turns = [_plan_turn([]), _work_turn()]
    assert current_plan(turns) is None
