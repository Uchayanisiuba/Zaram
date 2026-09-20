"""Work that runs on its own never approves itself — coworker step 4.

`core/triggers.py`. The runner is driven here with a fake `ask` — what is
under test is the schedule, the expansion of the obligations kind, the
dedupe, the circuit breaker, the retention, and the API — not the model.
That a run *is* an ordinary `POST /chat` is asserted by the route test at
the end, which watches the real route receive the question under a session
nobody has granted anything to.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime

import pytest

from core.triggers import (
    BREAKER_AFTER,
    RUN_TTL_DAYS,
    Trigger,
    TriggerRunner,
    TriggerStore,
    obligation_question,
    outcome_of,
)


#: When every trigger in this file was made: a Sunday at noon, so the
#: simulated week that follows is not owed anything from before.
BORN = datetime(2026, 9, 20, 12, 0).timestamp()


class _Store(TriggerStore):
    def create(self, *args, **kwargs):
        kwargs.setdefault("created_at", BORN)
        return super().create(*args, **kwargs)


@pytest.fixture
def store(tmp_path):
    return _Store(str(tmp_path / "triggers.db"))


class TestTheSchedule:
    def test_a_weekly_trigger_is_due_once_its_moment_has_passed_and_not_before(self, store):
        t = store.create("The month's picture.", "weekly", "09:00", weekday="mon")
        monday_0859 = datetime(2026, 9, 21, 8, 59)  # a Monday
        monday_0901 = datetime(2026, 9, 21, 9, 1)
        assert t.is_due(monday_0859) is False
        assert t.is_due(monday_0901) is True

    def test_a_machine_asleep_at_nine_still_runs_it_at_ten(self, store):
        # The person asked for the picture, not for punctuality.
        t = store.create("The month's picture.", "weekly", "09:00", weekday="mon")
        assert t.is_due(datetime(2026, 9, 21, 10, 30)) is True
        # And Tuesday still counts as this week's, until it has run.
        assert t.is_due(datetime(2026, 9, 22, 10, 30)) is True

    def test_once_run_it_waits_for_next_week(self, store):
        t = store.create("The month's picture.", "weekly", "09:00", weekday="mon")
        store.record_run(t, started_at=datetime(2026, 9, 21, 9, 5).timestamp(), outcome="done", conversation_id="c1", question=t.question)
        t = store.get(t.id)
        assert t.is_due(datetime(2026, 9, 22, 9, 5)) is False
        assert t.is_due(datetime(2026, 9, 28, 9, 5)) is True

    def test_daily_and_next_run(self, store):
        t = store.create("Anything due today?", "daily", "08:30")
        now = datetime(2026, 9, 21, 8, 0)
        assert t.is_due(now) is False
        assert datetime.fromtimestamp(t.next_run_at(now)) == datetime(2026, 9, 21, 8, 30)
        assert t.is_due(datetime(2026, 9, 21, 8, 31)) is True

    def test_disabled_and_paused_never_run(self, store):
        t = store.create("x", "daily", "08:30")
        store.set_enabled(t.id, False)
        assert store.get(t.id).is_due(datetime(2026, 9, 21, 9, 0)) is False
        assert store.get(t.id).next_run_at() is None

    def test_bad_input_is_refused_with_a_reason(self, store):
        with pytest.raises(ValueError):
            store.create("x", "hourly", "08:30")
        with pytest.raises(ValueError):
            store.create("x", "daily", "25:00")
        with pytest.raises(ValueError):
            store.create("", "daily", "08:30")


def _asking(answers):
    """A fake `ask` that returns the next scripted outcome and records the
    session it was asked under."""
    asked = []

    async def ask(question, session_id, project_id):
        asked.append((question, session_id, project_id))
        return answers.pop(0) if answers else ("done", "conv", "")

    ask.asked = asked
    return ask


class TestTheRunner:
    def test_a_due_trigger_runs_under_a_session_nobody_granted_anything_to(self, store):
        t = store.create("The month's picture.", "weekly", "09:00", weekday="mon")
        ask = _asking([("done", "conv-1", "")])
        runner = TriggerRunner(store, ask)

        runs = asyncio.run(runner.tick(datetime(2026, 9, 21, 9, 5)))

        assert len(runs) == 1 and runs[0].outcome == "done" and runs[0].conversation_id == "conv-1"
        question, session, _ = ask.asked[0]
        assert question == "The month's picture."
        assert session.startswith(f"trigger:{t.id}:")
        assert store.get(t.id).last_run_at > 0

    def test_the_breaker_pauses_after_three_holds_in_a_row(self, store):
        t = store.create("Chase every overdue invoice.", "daily", "09:00")
        ask = _asking([("held", "c1", "held at email/send"), ("held", "c2", "held at email/send"), ("held", "c3", "held at email/send")])
        runner = TriggerRunner(store, ask)
        for day in (21, 22, 23):
            asyncio.run(runner.tick(datetime(2026, 9, day, 9, 5)))

        paused = store.get(t.id)
        assert paused.held_in_a_row == BREAKER_AFTER
        assert "Paused" in paused.paused_reason
        assert paused.is_due(datetime(2026, 9, 24, 9, 5)) is False
        # Turning it back on is the person having looked.
        store.set_enabled(t.id, True)
        assert store.get(t.id).paused_reason == "" and store.get(t.id).held_in_a_row == 0

    def test_a_done_run_resets_the_count(self, store):
        t = store.create("x", "daily", "09:00")
        ask = _asking([("held", "c1", ""), ("done", "c2", ""), ("held", "c3", "")])
        runner = TriggerRunner(store, ask)
        for day in (21, 22, 23):
            asyncio.run(runner.tick(datetime(2026, 9, day, 9, 5)))
        assert store.get(t.id).held_in_a_row == 1
        assert store.get(t.id).paused_reason == ""

    def test_run_now_runs_a_paused_trigger_once(self, store):
        t = store.create("x", "daily", "09:00")
        store.set_enabled(t.id, False)
        ask = _asking([("done", "c", "")])
        runner = TriggerRunner(store, ask)
        assert asyncio.run(runner.run_trigger(store.get(t.id))) == []
        assert len(asyncio.run(runner.run_trigger(store.get(t.id), force=True))) == 1

    def test_a_failing_trigger_does_not_stop_the_others(self, store):
        a = store.create("a", "daily", "09:00")
        b = store.create("b", "daily", "09:00")

        async def ask(question, session_id, project_id):
            if question == "a":
                raise RuntimeError("boom")
            return "done", "c", ""

        runs = asyncio.run(TriggerRunner(store, ask).tick(datetime(2026, 9, 21, 9, 5)))
        assert [r.outcome for r in runs] == ["done"]
        assert store.runs(trigger_id=a.id)[0].outcome == "failed"
        assert store.runs(trigger_id=b.id)[0].outcome == "done"


class TestTheObligationsKind:
    def test_each_obligation_due_within_the_window_is_drafted_once(self, store):
        t = store.create("", "obligations", "08:00", days_ahead=7)
        due = [("ob-1", "Northwind invoice 0042", "2026-09-25"), ("ob-2", "the Acme deliverable", "2026-09-27")]
        ask = _asking([("done", "c1", ""), ("held", "c2", "held at email/send")])
        runner = TriggerRunner(store, ask, obligations=lambda days: due)

        first = asyncio.run(runner.tick(datetime(2026, 9, 21, 8, 5)))
        assert [r.obligation_id for r in first] == ["ob-1", "ob-2"]
        assert ask.asked[0][0] == obligation_question("Northwind invoice 0042", "2026-09-25")
        assert "Do not send anything" in ask.asked[0][0]
        assert ask.asked[0][1] == f"trigger:{t.id}:ob-1"

        # The next morning: nothing new, nothing re-drafted — one run saying so.
        again = asyncio.run(runner.tick(datetime(2026, 9, 22, 8, 5)))
        assert len(again) == 1 and again[0].obligation_id == "" and "nothing due" in again[0].note
        assert len(ask.asked) == 2

    def test_a_new_obligation_tomorrow_is_drafted_then(self, store):
        store.create("", "obligations", "08:00")
        due = [("ob-1", "x", "2026-09-25")]
        ask = _asking([])
        runner = TriggerRunner(store, ask, obligations=lambda days: list(due))
        asyncio.run(runner.tick(datetime(2026, 9, 21, 8, 5)))
        due.append(("ob-2", "y", "2026-09-26"))
        runs = asyncio.run(runner.tick(datetime(2026, 9, 22, 8, 5)))
        assert [r.obligation_id for r in runs] == ["ob-2"]


class TestRetention:
    def test_old_runs_are_pruned_and_triggers_are_not(self, store, monkeypatch):
        t = store.create("x", "daily", "09:00")
        store.record_run(t, started_at=time.time(), outcome="done", conversation_id="c", question="x")
        long_ago = time.time() - (RUN_TTL_DAYS + 1) * 24 * 3600
        with store._connect() as conn:
            conn.execute("UPDATE runs SET finished_at = ?", (long_ago,))
        assert store.prune() == 1
        assert store.runs() == []
        assert store.get(t.id) is not None

    def test_deleting_a_trigger_takes_its_runs(self, store):
        t = store.create("x", "daily", "09:00")
        store.record_run(t, started_at=time.time(), outcome="done", conversation_id="c", question="x")
        assert store.delete(t.id) is True
        assert store.runs() == []


class TestHowARunEnded:
    def test_a_held_tool_is_held_and_names_the_tool(self):
        events = [
            {"type": "token", "data": {"content": "hi"}},
            {"type": "tool_call", "data": {"server": "email", "tool": "send", "verdict": "confirm", "reason": "needs you"}},
        ]
        outcome, note = outcome_of(events)
        assert outcome == "held" and note.startswith("held at email/send")

    def test_an_error_is_failed_and_a_clean_reply_is_done(self):
        assert outcome_of([{"type": "error", "data": {"message": "no model"}}]) == ("failed", "no model")
        assert outcome_of([{"type": "token", "data": {"content": "done"}}]) == ("done", "")


class TestTheRoutes:
    """The API, and that a run really is the chat route."""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        import main
        from starlette.testclient import TestClient

        monkeypatch.setattr(main, "trigger_store", TriggerStore(str(tmp_path / "triggers.db")))
        asked = []

        async def ask(question, session_id, project_id):
            asked.append((question, session_id))
            return "done", "conv-9", ""

        monkeypatch.setattr(main, "trigger_runner", TriggerRunner(main.trigger_store, ask))
        c = TestClient(main.app)  # conftest carries the credential
        c.asked = asked
        return c

    def test_create_list_run_now_disable_delete(self, client):
        made = client.post("/triggers", json={"question": "The month's picture.", "kind": "weekly", "at": "09:00", "weekday": "mon"})
        assert made.status_code == 200, made.text
        trigger_id = made.json()["id"]
        assert made.json()["next_run_at"] is not None

        listed = client.get("/triggers").json()
        assert [t["id"] for t in listed["triggers"]] == [trigger_id]
        assert listed["kinds"] == ["daily", "weekly", "obligations"]

        ran = client.post(f"/triggers/{trigger_id}/run").json()
        assert ran["runs"][0]["outcome"] == "done" and ran["runs"][0]["conversation_id"] == "conv-9"
        assert client.asked[0][0] == "The month's picture."

        off = client.patch(f"/triggers/{trigger_id}", json={"enabled": False}).json()
        assert off["enabled"] is False and off["next_run_at"] is None

        assert client.delete(f"/triggers/{trigger_id}").status_code == 200
        assert client.get("/triggers").json()["triggers"] == []

    def test_bad_input_is_a_400_with_the_reason(self, client):
        bad = client.post("/triggers", json={"question": "x", "kind": "hourly", "at": "09:00"})
        assert bad.status_code == 400 and "kind" in bad.json()["detail"]
