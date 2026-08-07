"""`ExecutionEngine`'s ephemeral session buffer must stay bounded.

Rule 7d keeps conversation out of the Spine, so the recent-turns buffer that
resolves "write *that* up as a proposal" lives in process memory instead. It
was bounded per session and unbounded across them: the frontend mints a new
session id on every page load, so the map only ever grew.

Two caps, and the tests are separate because they fail for different reasons —
a per-session cap says nothing about the number of sessions, which is exactly
the mistake the original code made.
"""

from __future__ import annotations

from core.execution_engine import ExecutionEngine


def _engine() -> ExecutionEngine:
    """An engine with no runtimes. `_record_exchange` touches nothing else."""
    return ExecutionEngine.__new__(ExecutionEngine)


def _fresh() -> ExecutionEngine:
    engine = _engine()
    from collections import OrderedDict

    engine._session_turns = OrderedDict()
    return engine


def test_turns_are_capped_per_session():
    engine = _fresh()

    for i in range(ExecutionEngine.MAX_SESSION_TURNS * 3):
        engine._record_exchange("session-a", f"prompt {i}", f"answer {i}")

    assert len(engine._session_turns["session-a"]) == ExecutionEngine.MAX_SESSION_TURNS


def test_the_most_recent_turns_are_the_ones_kept():
    """Oldest-first eviction. Keeping the *first* 8 turns of a long
    conversation would resolve "that" against something said an hour ago."""
    engine = _fresh()

    for i in range(ExecutionEngine.MAX_SESSION_TURNS + 5):
        engine._record_exchange("session-a", f"prompt {i}", f"answer {i}")

    kept = engine._session_turns["session-a"]
    assert kept[-1] == (
        f"prompt {ExecutionEngine.MAX_SESSION_TURNS + 4}",
        f"answer {ExecutionEngine.MAX_SESSION_TURNS + 4}",
    )
    assert kept[0] == ("prompt 5", "answer 5")


def test_sessions_are_capped_too():
    """The leak. A page reload is a new session id, and nothing evicted."""
    engine = _fresh()

    for i in range(ExecutionEngine.MAX_SESSIONS * 2):
        engine._record_exchange(f"session-{i}", "hi", "hello")

    assert len(engine._session_turns) == ExecutionEngine.MAX_SESSIONS


def test_eviction_drops_the_least_recently_used_session():
    engine = _fresh()

    for i in range(ExecutionEngine.MAX_SESSIONS):
        engine._record_exchange(f"session-{i}", "hi", "hello")

    # Touch the oldest, then overflow by one.
    engine._record_exchange("session-0", "still here", "yes")
    engine._record_exchange("session-new", "hi", "hello")

    assert "session-0" in engine._session_turns, (
        "a conversation left open in one tab must survive a burst of reloads "
        "in another — eviction is by last use, not by creation order"
    )
    assert "session-1" not in engine._session_turns
    assert len(engine._session_turns) == ExecutionEngine.MAX_SESSIONS


def test_a_blank_exchange_is_not_recorded():
    """An empty answer creates a session entry that can never help resolve
    anything, and on the reload path that is a pure leak."""
    engine = _fresh()

    engine._record_exchange("session-a", "", "an answer")
    engine._record_exchange("session-b", "a prompt", "")
    engine._record_exchange("session-c", "   ", "   ")

    assert engine._session_turns == {}
