"""Removing one file from Knowledge, not the whole source that holds it.

The gap this closes: every dropped or pasted document shares a single uploads
source, so the only removal available was `withdraw(source_id)` -- discarding
everything ever pasted in order to be rid of one file. Rule 4 says the user can
delete any stored thing, and "all of them or none" is not that.

The assertions that earn this file are the ones about *what is not deleted*: a
scanned folder holds the user's originals, and following a stored path to an
unlink without checking where it lands is how "Zaram deleted my file" happens.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from ingest.records import IngestRecords


@pytest.fixture()
def records(tmp_path):
    return IngestRecords(str(tmp_path / "ingest.db"))


def _seed(records, source_root, name, fact_ids):
    """Insert a source and one outcome directly, as a scan would have."""
    source_id = records.upsert_source(str(source_root))
    outcome_id = f"out-{name}"
    with sqlite3.connect(records._path) as con:  # noqa: SLF001 - fixture setup
        con.execute(
            "INSERT INTO outcomes (id, source_id, path, name, status, parser,"
            " chars, pages, fact_ids, reason, remedy, seconds, recorded_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                outcome_id, source_id, str(source_root / name), name, "indexed",
                "plaintext", 10, 1, json.dumps(fact_ids), "", "", 0.1, 0.0,
            ),
        )
    return source_id, outcome_id


def test_removing_a_file_returns_its_facts_for_the_caller_to_forget(records, tmp_path):
    _, outcome_id = _seed(records, tmp_path, "a.txt", ["fact-1", "fact-2"])
    assert records.remove_outcome(outcome_id) == ["fact-1", "fact-2"]


def test_the_row_is_gone_afterwards(records, tmp_path):
    source_id, outcome_id = _seed(records, tmp_path, "a.txt", ["f"])
    records.remove_outcome(outcome_id)
    assert records.get_outcome(outcome_id) is None
    assert records.outcomes(source_id=source_id) == []


def test_siblings_survive(records, tmp_path):
    """The whole point: one file leaves, the rest of the source stays."""
    source_id = records.upsert_source(str(tmp_path))
    with sqlite3.connect(records._path) as con:  # noqa: SLF001
        for name in ("keep-1.txt", "drop.png", "keep-2.txt"):
            con.execute(
                "INSERT INTO outcomes (id, source_id, path, name, status,"
                " parser, chars, pages, fact_ids, reason, remedy, seconds,"
                " recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"out-{name}", source_id, str(tmp_path / name), name,
                 "indexed", "p", 1, 1, "[]", "", "", 0.0, 0.0),
            )

    records.remove_outcome("out-drop.png")
    left = sorted(o["name"] for o in records.outcomes(source_id=source_id))
    assert left == ["keep-1.txt", "keep-2.txt"]


def test_the_source_row_survives_its_last_file(records, tmp_path):
    """An empty uploads directory is still where the next drop goes.

    Deleting the source here would make the next paste re-create it under a
    fresh id, detaching it from any domain that pointed at the old one.
    """
    source_id, outcome_id = _seed(records, tmp_path, "only.txt", [])
    records.remove_outcome(outcome_id)
    assert records.source_root(source_id) is not None


def test_an_unknown_outcome_is_none_not_an_empty_list(records):
    """None is 'no such file' -> 404. `[]` would mean 'removed, no facts'."""
    assert records.remove_outcome("out-does-not-exist") is None


def test_a_file_that_produced_no_facts_is_still_removable(records, tmp_path):
    """The reported case: an unsupported PNG, indexed nothing, still has a row,
    a stored reason and a staged copy. Asking for it to be gone means all of
    those, not a shrug."""
    _, outcome_id = _seed(records, tmp_path, "Broad Street_3.1.1.png", [])
    assert records.remove_outcome(outcome_id) == []
    assert records.get_outcome(outcome_id) is None
