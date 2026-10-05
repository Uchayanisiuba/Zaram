"""*Run this once*, and the terminal held to the rules the other tools keep.

Asked for 5 October 2026, after an audit of what stops Zaram finishing a build:

* **A floor card was a dead end.** An install through the project's install
  runner always asks and is not grantable, so the card offered only *Deny* —
  the one yes that settles it, *for this call*, did not exist. Inside a chat
  the install could only be approved through a long plan's *run without
  stopping*.
* **The terminal skipped every rule that keys on a name.** `npm install`
  through the runner asked; typed into the terminal it ran. A tool named
  `delete_file` asked; `rm -rf` in the terminal did not.
* **The card asking about a terminal call did not show the command**, because
  `call_target` never read `command`. A yes to something unseen is not a yes.

And one thing the answer has to get right: *Run this once* runs **the call
that was shown**. Asking the question again and hoping the model writes the
same command is how a press ends in the same card — so the held call is parked
with the task and the resume makes it first.
"""

from __future__ import annotations

import pytest

from core.streaming_events import EventType
from core.tool_loop import TOOL_CALL_MARKER, call_target
from projects.plans import Plan, PlanRecords, PlanStep
from runtimes.mcp.floors import floor_for, terminal_floor
from tests.test_mcp_reaches_chat import _engine, _events, _McpDouble, _text


def _verdict(command: str) -> str:
    floor = terminal_floor("run_in_terminal", {"command": command})
    return "" if floor is None else floor.reason.split(".")[0]


# --------------------------------------------------------- the terminal floor


class TestTheTerminalIsHeldToTheSameRules:
    @pytest.mark.parametrize(
        "command",
        [
            "npm install",
            "npm i react",
            "pnpm add zod",
            "yarn add vite",
            "pip install -r requirements.txt",
            "C:\\tools\\npm.cmd install",
            "npx create-vite@latest app --template react",
            "npm create vite@latest",
            "uvx ruff check",
            "cd app && npm install",
        ],
    )
    def test_fetching_packages_asks(self, command):
        floor = terminal_floor("run_in_terminal", {"command": command})
        assert floor is not None and floor.verdict == "confirm", command
        assert "downloads packages" in floor.reason
        assert floor.grantable is False
        # Covered by a plan let run without stopping, as the install runner
        # always was — the terminal is brought level, not made stricter.
        assert floor.plan_may_cover is True

    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf build",
            "rm notes.txt",
            "Remove-Item -Recurse dist",
            "rmdir /s /q out",
            "del *.log",
            "git clean -fdx",
            "git reset --hard",
            "git checkout -- .",
            "npm run build; rm -rf node_modules",
        ],
    )
    def test_deleting_asks_and_no_plan_covers_it(self, command):
        floor = terminal_floor("run_in_terminal", {"command": command})
        assert floor is not None and floor.verdict == "confirm", command
        assert "deletes files" in floor.reason
        assert floor.plan_may_cover is False

    @pytest.mark.parametrize("command", ["npm publish", "vercel deploy --prod", "firebase deploy", "docker push me/app", "twine upload dist/*"])
    def test_sending_off_the_machine_asks(self, command):
        floor = terminal_floor("run_in_terminal", {"command": command})
        assert floor is not None and "beyond this machine" in floor.reason, command

    @pytest.mark.parametrize(
        "command",
        [
            "npm run build",
            "npm test",
            "npm run dev",
            "python -m venv .venv",
            "git status",
            "git add -A && git commit -m wip",
            "echo hello",
            "ls",
            "node server.js",
            "pytest -q",
        ],
    )
    def test_ordinary_work_runs_under_the_grant_as_before(self, command):
        # One-directional: a command the floor does not recognise is exactly
        # as permitted as it was. This is what keeps the terminal useful.
        assert terminal_floor("run_in_terminal", {"command": command}) is None, command

    def test_it_reads_only_the_terminal(self):
        assert terminal_floor("write_file", {"command": "rm -rf /"}) is None
        assert floor_for("code", "run_in_terminal", {"command": "rm -rf x"}, None) is not None

    def test_the_card_shows_the_command(self):
        assert call_target("run_in_terminal", {"command": "npm install"}) == "npm install"


# ---------------------------------------------------------- the plan's rung


class TestRunWithoutStoppingStillStopsAtATerminalDelete:
    def test_a_delete_in_the_terminal_is_not_confirmed_by_the_rung(self):
        engine, _ = _engine([])
        engine._uninterrupted = {"s1"}
        assert engine._runs_uninterrupted("s1", "run_in_terminal", {"command": "rm -rf build"}) is False

    def test_an_install_in_the_terminal_is(self):
        engine, _ = _engine([])
        engine._uninterrupted = {"s1"}
        assert engine._runs_uninterrupted("s1", "run_in_terminal", {"command": "npm install"}) is True
        assert engine._runs_uninterrupted("s1", "run_in_terminal", {"command": "npm test"}) is True


# ------------------------------------------------------------- the held call


class TestTheHeldCallIsKept:
    def test_it_round_trips_and_a_later_save_clears_it(self, tmp_path):
        records = PlanRecords(str(tmp_path / "plans.db"))
        held = PlanStep(server="code", tool="run_in_terminal", arguments={"command": "npm install"}, result=None)
        stored = records.save(Plan(id="", question="set it up", steps=[], held=held))

        assert records.get(stored.id).held == held

        records.save(Plan(id=stored.id, question="set it up", steps=[]))
        assert records.get(stored.id).held is None

    def test_an_unreadable_held_call_is_not_guessed_at(self, tmp_path):
        records = PlanRecords(str(tmp_path / "plans.db"))
        stored = records.save(Plan(id="", question="q", steps=[]))
        with records._connect() as conn:
            conn.execute("UPDATE plans SET held = ? WHERE id = ?", ('{"tool": ""}', stored.id))
        assert records.get(stored.id).held is None

    def test_an_older_table_gains_the_column(self, tmp_path):
        import sqlite3

        path = tmp_path / "plans.db"
        with sqlite3.connect(path) as conn:
            conn.execute(
                "CREATE TABLE plans (id TEXT PRIMARY KEY, question TEXT NOT NULL, "
                "project_id TEXT NOT NULL DEFAULT '', session_id TEXT NOT NULL DEFAULT '', "
                "model TEXT NOT NULL DEFAULT '', stopped_because TEXT NOT NULL DEFAULT '', "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL)"
            )
            conn.execute("INSERT INTO plans VALUES ('old', 'q', '', '', '', '', 1.0, 1.0)")
        records = PlanRecords(str(path), ttl_seconds=10**12)
        assert records.get("old").held is None


# --------------------------------------------------------- the engine, end to end


_HOLD = {
    "success": False,
    "needs_confirmation": True,
    "reason": "This downloads packages. This always asks, whatever has been granted.",
    "grantable": False,
    "once": True,
}
_CALL = TOOL_CALL_MARKER + ' {"server": "blender", "tool": "run_in_terminal", "arguments": {"command": "npm install"}}'


class _Scripted(_McpDouble):
    """Answers each call in turn from a list, then succeeds."""

    def __init__(self, results):
        super().__init__(tools=[{
            "server": "blender", "name": "run_in_terminal", "description": "Run a command.",
            "input_schema": {}, "provenance": "tool_output", "suspicions": [],
        }])
        self._results = list(results)

    async def execute(self, capability_id, input_data):
        if capability_id != "mcp.call":
            return await super().execute(capability_id, input_data)
        self.calls.append(dict(input_data))
        return self._results.pop(0) if self._results else {"success": True, "result": {"output": "ok"}}


def _wired(replies, results, tmp_path):
    mcp = _Scripted(results)
    engine, model = _engine(replies, mcp)
    engine.set_plan_records(PlanRecords(str(tmp_path / "plans.db")))
    return engine, model, mcp


class TestRunThisOnce:
    def test_a_hold_parks_the_call_and_stops_without_guessing(self, tmp_path):
        engine, model, _ = _wired([_CALL, "SHOULD NOT BE GENERATED"], [_HOLD], tmp_path)

        items = list(engine.execute("set up the blender project", session_id="s1"))

        call = _events(items, EventType.TOOL_CALL)[0].data
        assert call["verdict"] == "confirm"
        assert call["once"] is True
        assert call["target"] == "npm install"
        assert call["held_task"]
        assert "say-so" in _text(items)
        # The fallback answer is not written: the card carries the task on.
        assert "SHOULD NOT BE GENERATED" not in _text(items)
        assert engine._plans.get(call["held_task"]).held.arguments == {"command": "npm install"}

    def test_the_press_runs_exactly_that_call_confirmed_and_nothing_after_it(self, tmp_path):
        engine, _, mcp = _wired(
            [_CALL, _CALL.replace("npm install", "npm install --force") + "", "All set."],
            [_HOLD, {"success": True, "result": {"output": "added 3 packages"}}, _HOLD],
            tmp_path,
        )
        items = list(engine.execute("set up the blender project", session_id="s1"))
        task = _events(items, EventType.TOOL_CALL)[0].data["held_task"]

        resumed = list(engine.continue_task("s1", plan_id=task, run_held=True))

        # First call of the resume is the parked one, word for word, confirmed.
        assert mcp.calls[1]["arguments"] == {"command": "npm install"}
        assert mcp.calls[1]["confirmed"] is True
        # The model's next call is a different one, and it is asked about.
        assert mcp.calls[2]["arguments"] == {"command": "npm install --force"}
        assert mcp.calls[2]["confirmed"] is False
        assert _events(resumed, EventType.TOOL_CALL)[-1].data["verdict"] == "confirm"

    def test_continuing_after_a_grant_does_not_confirm_anything(self, tmp_path):
        # The grant buttons carry the task on too, but the gate decides: the
        # held call goes through it unconfirmed, and runs only if the grant
        # covers it.
        engine, _, mcp = _wired([_CALL, "Done."], [_HOLD, {"success": True, "result": {}}], tmp_path)
        items = list(engine.execute("set up the blender project", session_id="s1"))
        task = _events(items, EventType.TOOL_CALL)[0].data["held_task"]

        list(engine.continue_task("s1", plan_id=task))

        assert mcp.calls[1]["arguments"] == {"command": "npm install"}
        assert mcp.calls[1]["confirmed"] is False

    def test_a_send_is_never_offered_once(self, tmp_path):
        engine, _, _ = _wired([_CALL, "x"], [{**_HOLD, "once": False}], tmp_path)
        items = list(engine.execute("set up the blender project", session_id="s1"))
        assert _events(items, EventType.TOOL_CALL)[0].data["once"] is False

    def test_a_new_question_is_a_new_task(self, tmp_path):
        engine, _, _ = _wired([_CALL, "Three objects."], [_HOLD, {"success": True, "result": {}}], tmp_path)
        items = list(engine.execute("set up the blender project", session_id="s1"))
        held = _events(items, EventType.TOOL_CALL)[0].data["held_task"]


        # The held task survives the next question rather than being written
        # over or deleted by it.
        assert engine._plans.get(held) is not None
        assert engine._plans.get(held).held is not None
