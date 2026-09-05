"""Valid time against recorded time.

The scenario every test here circles: a client raises the rate in June, the
user tells Zaram in August. Recorded time says the old rate stood until August,
which is wrong about every invoice issued in between. This is the difference
between a correct answer about the past and a confident wrong one.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import pytest

from runtimes.memory.contracts import MemoryRecord
from runtimes.memory.valid_time import explain, history_of, in_force_at

JUNE = time.mktime(time.strptime("2026-06-01", "%Y-%m-%d"))
JULY = time.mktime(time.strptime("2026-07-01", "%Y-%m-%d"))
AUGUST = time.mktime(time.strptime("2026-08-01", "%Y-%m-%d"))


@dataclass
class Fact:
    """Structurally what the history helpers read, and nothing more."""

    id: str
    content: str
    valid_from: Optional[float] = None
    valid_until: Optional[float] = None
    superseded_by: Optional[str] = None
    superseded_at: Optional[float] = None


class TestTheRecordCarriesBoth:
    def test_a_record_has_valid_time_as_well_as_recorded_time(self):
        record = MemoryRecord(content="My day rate is £500")
        assert record.valid_from is None
        assert record.valid_until is None
        assert record.superseded_at is None

    def test_validity_is_not_defaulted_to_creation(self):
        """A capture timestamp presented as a validity date is a value nobody
        entered."""
        record = MemoryRecord(content="My day rate is £500")
        assert record.created_at is not None
        assert record.valid_from is None


class TestAsOfQueries:
    def _rate_history(self):
        return [
            Fact(
                id="old",
                content="My day rate is £500",
                valid_until=JUNE,
                superseded_by="new",
                superseded_at=AUGUST,
            ),
            Fact(id="new", content="My day rate is £600", valid_from=JUNE),
        ]

    def test_july_returns_the_rate_that_was_actually_in_force(self):
        """Told in August, true since June. July must answer £600."""
        in_force = in_force_at(self._rate_history(), JULY)
        assert [f.id for f in in_force] == ["new"]

    def test_a_date_before_the_change_returns_the_old_rate(self):
        may = time.mktime(time.strptime("2026-05-01", "%Y-%m-%d"))
        in_force = in_force_at(self._rate_history(), may)
        assert [f.id for f in in_force] == ["old"]

    def test_a_superseded_fact_is_included_when_the_date_is_inside_its_window(self):
        """Excluding it would make this "what is true now" with extra steps."""
        april = time.mktime(time.strptime("2026-04-01", "%Y-%m-%d"))
        assert in_force_at(self._rate_history(), april)[0].content.endswith("£500")

    def test_the_windows_meet_so_no_date_matches_two_facts(self):
        """Half-open [from, until): the instant of change belongs to the new
        fact, so an as-of query never returns a pair to choose between."""
        at_change = in_force_at(self._rate_history(), JUNE)
        assert len(at_change) == 1
        assert at_change[0].id == "new"

    def test_a_fact_with_no_dates_matches_any_moment(self):
        """Unknown is preserved, not filled in — it was captured with nobody
        stating a start date."""
        undated = [Fact(id="a", content="I prefer local models")]
        assert in_force_at(undated, JULY)
        assert in_force_at(undated, AUGUST)

    def test_recorded_time_alone_would_have_answered_wrongly(self):
        """The regression this whole feature exists to prevent."""
        history = self._rate_history()
        by_recorded_time = [
            f for f in history if f.superseded_at is None or f.superseded_at > JULY
        ]
        assert "£500" in by_recorded_time[0].content  # what the old model said

        by_valid_time = in_force_at(history, JULY)
        assert "£600" in by_valid_time[0].content  # what was actually true


class TestHistory:
    def test_follows_the_chain_oldest_first(self):
        records = [
            Fact(id="a", content="£400", superseded_by="b"),
            Fact(id="b", content="£500", superseded_by="c"),
            Fact(id="c", content="£600"),
        ]
        assert [f.id for f in history_of(records, "a")] == ["a", "b", "c"]

    def test_a_broken_chain_returns_what_it_can_reach(self):
        records = [Fact(id="a", content="£400", superseded_by="missing")]
        assert [f.id for f in history_of(records, "a")] == ["a"]

    def test_a_cycle_terminates(self):
        records = [
            Fact(id="a", content="x", superseded_by="b"),
            Fact(id="b", content="y", superseded_by="a"),
        ]
        assert len(history_of(records, "a")) == 2


class TestExplanations:
    def test_an_answer_about_the_past_says_what_it_rests_on(self):
        record = Fact(id="new", content="£600", valid_from=JUNE)
        assert "still current" in explain(record, JULY)

    def test_an_unstated_start_date_is_admitted_not_hidden(self):
        """Rule 2 applies to temporal claims too."""
        record = Fact(id="a", content="I prefer local models")
        assert "no start or end date" in explain(record, JULY)

    def test_a_closed_window_names_both_ends(self):
        record = Fact(id="old", content="£500", valid_from=JUNE, valid_until=AUGUST)
        message = explain(record, JULY)
        assert "Jun 2026" in message and "Aug 2026" in message


@pytest.mark.asyncio
async def test_correcting_a_fact_records_when_it_changed_not_only_when_told(tmp_path):
    """End to end through the real runtime and the real store."""
    from runtimes.memory.store import SQLiteMemoryStore

    store = SQLiteMemoryStore(db_path=str(tmp_path / "spine.db"))
    original = MemoryRecord(content="My day rate is £500")
    await store.put(original)

    # What `correct()` writes, exercised against the store directly so the
    # test does not depend on an embedder being available.
    replacement = MemoryRecord(content="My day rate is £600", valid_from=JUNE)
    await store.put(replacement)
    await store.put(
        MemoryRecord(
            **{
                **original.__dict__,
                "superseded_by": replacement.id,
                "superseded_at": AUGUST,
                "valid_until": replacement.valid_from,
            }
        )
    )

    reloaded_old = await store.get(original.id)
    reloaded_new = await store.get(replacement.id)

    assert reloaded_old is not None and reloaded_new is not None
    assert reloaded_old.valid_until == JUNE      # when it stopped being true
    assert reloaded_old.superseded_at == AUGUST  # when we were told
    assert reloaded_new.valid_from == JUNE

    assert [f.id for f in in_force_at([reloaded_old, reloaded_new], JULY)] == [
        replacement.id
    ]
