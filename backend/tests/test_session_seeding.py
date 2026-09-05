"""`seed_session_turns`, against the real engine rather than a stand-in.

`test_chat_endpoint_writes_a_transcript.py` uses a stub for the wiring, which is
right — it is testing that the endpoint calls this at all. A stub cannot prove
the rules the method actually keeps, and those rules are where the damage is:
overwrite a live session and the exchange that just happened is replaced by an
older copy of itself; forget the cap and a long transcript pins the whole buffer.

**Why the method exists.** `_session_turns` is in-process and dies with it. That
is rule 7d's ephemeral half and it is correct — false starts must not reach the
Spine — but until transcripts were stored it also meant a resumed conversation
arrived with nothing in front of it, so "write that up as a proposal" resolved
against an empty buffer. Rule 9's referential failure, after a restart.

Nothing here weakens 7d: this fills one session store from another, and the
Spine remains the memory runtime's decision.
"""

from __future__ import annotations

import pytest

from core.execution_engine import ExecutionEngine


@pytest.fixture()
def engine() -> ExecutionEngine:
    """A bare engine. Seeding touches only the turn buffer, so nothing else
    needs to exist — and constructing a full kernel would make this file slow
    enough that nobody runs it."""
    return ExecutionEngine.__new__(ExecutionEngine)


@pytest.fixture(autouse=True)
def _buffer(engine):
    from collections import OrderedDict

    engine._session_turns = OrderedDict()
    return engine._session_turns


class TestSeedingFillsAnEmptySession:
    def test_pairs_are_kept_in_order(self, engine):
        engine.seed_session_turns("s", [("q1", "a1"), ("q2", "a2")])

        assert engine._session_turns["s"] == [("q1", "a1"), ("q2", "a2")]

    def test_nothing_to_seed_is_not_an_empty_session(self, engine):
        """An empty list must not create a key. A session that exists with no
        turns is indistinguishable from one that was seeded and found nothing,
        and the second is what stops a later real seed from running."""
        engine.seed_session_turns("s", [])

        assert "s" not in engine._session_turns

    def test_a_session_without_an_id_is_refused(self, engine):
        engine.seed_session_turns("", [("q", "a")])

        assert not engine._session_turns


class TestALiveSessionWins:
    def test_existing_turns_are_not_replaced(self, engine):
        """A buffer with anything in it is a live session. Overwriting it with
        a transcript read from disk discards the exchange that just happened in
        favour of an older copy of itself."""
        engine._session_turns["s"] = [("live q", "live a")]

        engine.seed_session_turns("s", [("stored q", "stored a")])

        assert engine._session_turns["s"] == [("live q", "live a")]

    def test_seeding_twice_does_not_double(self, engine):
        engine.seed_session_turns("s", [("q", "a")])
        engine.seed_session_turns("s", [("q", "a")])

        assert engine._session_turns["s"] == [("q", "a")]


class TestTheBoundsAreTheOnesTheBufferAlreadyKeeps:
    def test_only_the_most_recent_turns_are_kept(self, engine):
        pairs = [(f"q{i}", f"a{i}") for i in range(30)]

        engine.seed_session_turns("s", pairs)

        kept = engine._session_turns["s"]
        assert len(kept) == ExecutionEngine.MAX_SESSION_TURNS
        # The recent end, not the start: a resumed conversation needs what was
        # just said, not what opened it.
        assert kept[-1] == ("q29", "a29")

    def test_the_session_map_stays_bounded(self, engine):
        """The frontend mints a session id per page load, so without eviction
        the map grows for the life of the process — the reason
        `MAX_SESSIONS` exists. Seeding must not be the path that bypasses it."""
        for i in range(ExecutionEngine.MAX_SESSIONS + 10):
            engine.seed_session_turns(f"s{i}", [("q", "a")])

        assert len(engine._session_turns) <= ExecutionEngine.MAX_SESSIONS

    def test_the_oldest_session_is_the_one_evicted(self, engine):
        for i in range(ExecutionEngine.MAX_SESSIONS + 1):
            engine.seed_session_turns(f"s{i}", [("q", "a")])

        assert "s0" not in engine._session_turns
        assert f"s{ExecutionEngine.MAX_SESSIONS}" in engine._session_turns
