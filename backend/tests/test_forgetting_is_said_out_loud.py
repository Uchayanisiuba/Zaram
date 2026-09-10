"""When the conversation outgrows the window, the user is told.

**Silence is what made a bounded window read as "Zaram is forgetful."** The
maintainer reported it twice — *"it doesn't seem to follow the conversation"* —
and both times the machinery was working within a budget nobody had been shown.
`fit` drops the earliest turns, wrote a log line, and said nothing on screen, so
there was no way for a user to tell "it lost the thread" from "it is bad at
this". The task loop had been doing the honest thing for months: when it drops
the earliest tool results it says *"Continuing without the N earliest
results…"*.

`docs/UI-SPEC.md`: disabled capabilities are visible, not silent. This is that
rule applied to memory.

Two notices, deliberately different in frequency:

* **Nothing fitted** is said every time. That is not a shorter memory, it is
  none at all, and the reply is being answered as though nothing came before it.
* **Some turns dropped** is said once per session. Past the budget every
  subsequent turn drops something, so a notice per reply would be a permanent
  banner — and a warning that is always on is a warning nobody reads.

The tests here assert the notice **reaches the stream**, not merely that it is
constructed. This repository's signature failure is a complete, tested
subsystem that nothing calls, and a notice nobody yields is exactly that shape.
"""

from __future__ import annotations

import pytest

from core.context_budget import ContextBudget
from core.event_bus import EventBus
from core.execution_engine import ExecutionEngine
from core.streaming_events import EventType


@pytest.fixture
def engine() -> ExecutionEngine:
    """An engine with no runtimes; only the conversation buffer is exercised.

    A real `EventBus` rather than `None`, because `execute` publishes as it
    goes and the last test in this file drives it end to end.
    """
    return ExecutionEngine(registry=None, event_bus=EventBus())


#: A window where a few of the exchanges below fit and the rest are dropped.
#:
#: **Measured, not chosen.** One exchange costs 814 tokens, and the
#: conversation gets a quarter of three quarters of the window: at 4,096 the
#: share is 768, which one exchange already overflows, so a test sized that way
#: silently takes the *nothing fitted* branch while claiming to test the
#: partial one. Every assertion still passed. At 8,192 the share is 1,536 —
#: one exchange in, the rest out.
PARTIAL_WINDOW = 8192

#: A window too small for even one exchange, so nothing is sent at all.
EMPTY_WINDOW = 1024


def _budget(monkeypatch, total: int) -> None:
    """Pin the window, so these tests never depend on what is installed.

    The lesson of 10 September, when two helpers stubbed `requests.get` only and
    reached the developer's real Ollama through `/api/show` — one of them
    passing anyway, for a reason outside its own file.
    """
    monkeypatch.setattr(
        "core.context_budget.budget_for",
        lambda *a, **k: ContextBudget(
            total_tokens=total,
            measured=True,
            reply_reserve_tokens=int(total * 0.25),
            source="configured",
        ),
    )


def _long_exchange(i: int) -> tuple[str, str]:
    """One exchange big enough that a few of them overflow a small window."""
    return (f"question {i} " + "q" * 400, f"answer {i} " + "a" * 2000)


class TestSomeTurnsDropped:
    def test_the_user_is_told_which_model_could_not_hold_it(self, engine, monkeypatch):
        _budget(monkeypatch, PARTIAL_WINDOW)
        engine._session_turns["s"] = [_long_exchange(i) for i in range(8)]

        prompt, notice = engine._augment_with_conversation("", "s", "qwen3-14b-16k")

        assert notice is not None
        assert notice.type is EventType.NOTICE
        assert notice.data["kind"] == "memory"
        # Named, because the limit is this model's. "The model" invites the
        # reading that Zaram is forgetful rather than that this model is small.
        assert "qwen3-14b-16k" in notice.data["content"]
        # And the reply still gets what did fit.
        assert "THE CONVERSATION SO FAR" in prompt

    def test_it_is_said_once_and_not_on_every_later_turn(self, engine, monkeypatch):
        """A banner on every reply is a warning nobody reads."""
        _budget(monkeypatch, PARTIAL_WINDOW)
        engine._session_turns["s"] = [_long_exchange(i) for i in range(8)]

        _, first = engine._augment_with_conversation("", "s", "m")
        _, second = engine._augment_with_conversation("", "s", "m")
        _, third = engine._augment_with_conversation("", "s", "m")

        assert first is not None
        assert second is None
        assert third is None

    def test_another_session_is_told_in_its_own_right(self, engine, monkeypatch):
        _budget(monkeypatch, PARTIAL_WINDOW)
        for sid in ("s", "t"):
            engine._session_turns[sid] = [_long_exchange(i) for i in range(8)]

        _, told_s = engine._augment_with_conversation("", "s", "m")
        _, told_t = engine._augment_with_conversation("", "t", "m")

        assert told_s is not None
        assert told_t is not None

    def test_the_set_of_told_sessions_stays_bounded(self, engine, monkeypatch):
        """The frontend mints a session id per page load, so an unbounded set
        of dead sessions is a slow leak — the same reason the buffer beside it
        is capped."""
        _budget(monkeypatch, PARTIAL_WINDOW)
        for i in range(ExecutionEngine.MAX_SESSIONS + 25):
            sid = f"s{i}"
            engine._session_turns[sid] = [_long_exchange(j) for j in range(8)]
            engine._augment_with_conversation("", sid, "m")

        assert len(engine._told_about_dropped_turns) <= ExecutionEngine.MAX_SESSIONS


class TestNothingFitted:
    def test_the_user_is_told_the_reply_stands_alone(self, engine, monkeypatch):
        # A 192-token conversation share, which one exchange cannot fit.
        _budget(monkeypatch, EMPTY_WINDOW)
        engine._session_turns["s"] = [_long_exchange(0)]

        prompt, notice = engine._augment_with_conversation("", "s", "m")

        assert notice is not None
        assert notice.data["kind"] == "memory"
        # No heading over an empty exchange: a section claiming continuity that
        # is not being supplied is worse than none.
        assert "THE CONVERSATION SO FAR" not in prompt

    def test_it_is_said_every_time_rather_than_once(self, engine, monkeypatch):
        """Unlike the partial case. Being answered as though nothing came
        before is the reported failure, and a user who missed the first notice
        has no other signal that it is happening."""
        _budget(monkeypatch, EMPTY_WINDOW)
        engine._session_turns["s"] = [_long_exchange(0)]

        _, first = engine._augment_with_conversation("", "s", "m")
        _, second = engine._augment_with_conversation("", "s", "m")

        assert first is not None
        assert second is not None


class TestQuietWhenThereIsNothingToSay:
    def test_a_conversation_that_fits_says_nothing(self, engine, monkeypatch):
        _budget(monkeypatch, 65536)
        engine._session_turns["s"] = [_long_exchange(i) for i in range(3)]

        prompt, notice = engine._augment_with_conversation("", "s", "m")

        assert notice is None
        assert "THE CONVERSATION SO FAR" in prompt

    def test_a_first_turn_says_nothing(self, engine, monkeypatch):
        """Nothing to follow, so no heading and no notice — a warning about an
        empty buffer would teach the user that notices are furniture."""
        _budget(monkeypatch, PARTIAL_WINDOW)

        prompt, notice = engine._augment_with_conversation("carry on", "fresh", "m")

        assert notice is None
        assert prompt == "carry on"


class TestTheNoticeReachesTheStream:
    def test_execute_yields_it_rather_than_dropping_it(self, engine, monkeypatch):
        """**The assertion this file exists for.**

        A notice that is built and never yielded is this repository's most
        expensive recurring shape, and it would be invisible here: every test
        above would still pass while the user saw nothing.
        """
        _budget(monkeypatch, PARTIAL_WINDOW)
        engine._session_turns["s"] = [_long_exchange(i) for i in range(8)]

        events = list(engine.execute("and what about the last one?", session_id="s"))

        memory_notices = [
            e
            for e in events
            if getattr(e, "type", None) is EventType.NOTICE
            and getattr(e, "data", {}).get("kind") == "memory"
        ]
        assert memory_notices, (
            "the conversation-memory notice was constructed but never reached "
            "the stream"
        )
