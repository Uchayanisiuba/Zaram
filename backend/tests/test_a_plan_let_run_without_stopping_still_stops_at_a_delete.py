"""The plan card's second rung — *run without stopping* — is consent to a
plan's **changes**, never to its **removals**.

Built 15 September 2026 with the rung itself. The pause before a long plan was
one button, and pressing it only cleared the *plan-level* review: every
individual write still returned `needs_confirmation`, stopped the loop, and
answered without the tool, so a run could not actually finish unless every tool
had been granted in Settings first. The second rung is what lets a plan the
person has read run to the end.

The danger it introduces is obvious and is what these tests hold shut: a flag
that means "stop asking" must not also mean "you may delete". `confirmed` is
the gate's one door, and the engine — not the gate — is what decides a given
call may go through it, because the gate cannot tell a run a *person* waved
through from one the *model* waved through.

Three properties, each a separate failure if it slips:

1. an ordinary change in an uninterrupted run is confirmed;
2. a destructive tool in the same run is **not**, whatever it is called;
3. a run nobody waved through confirms nothing at all.
"""

from __future__ import annotations

import pytest

from core.execution_engine import ExecutionEngine


@pytest.fixture()
def engine() -> ExecutionEngine:
    # The predicate under test reads two fields and a name; it needs none of
    # the engine's collaborators, and constructing them would test them instead.
    return ExecutionEngine.__new__(ExecutionEngine)


def _session(engine: ExecutionEngine, *, uninterrupted: bool) -> str:
    engine._uninterrupted = {"s1"} if uninterrupted else set()
    return "s1"


def test_a_change_in_a_run_the_person_let_go_is_confirmed(engine: ExecutionEngine) -> None:
    s = _session(engine, uninterrupted=True)
    assert engine._runs_uninterrupted(s, "create_pull_request") is True
    assert engine._runs_uninterrupted(s, "imap_send_email") is True
    assert engine._runs_uninterrupted(s, "write_file") is True


@pytest.mark.parametrize(
    "tool",
    [
        "imap_delete_email",
        "imap_bulk_delete",
        "delete_file",
        "remove_branch",
        "drop_table",
        "purge_cache",
        "destroy_environment",
        "truncate_log",
    ],
)
def test_a_removal_is_never_confirmed_by_the_rung(engine: ExecutionEngine, tool: str) -> None:
    """Whatever the plan said, a delete asks. Undo does not help with most of
    them and a person who said "don't stop for each change" did not say
    "empty the mailbox"."""
    s = _session(engine, uninterrupted=True)
    assert engine._runs_uninterrupted(s, tool) is False


def test_a_run_nobody_waved_through_confirms_nothing(engine: ExecutionEngine) -> None:
    s = _session(engine, uninterrupted=False)
    assert engine._runs_uninterrupted(s, "create_pull_request") is False
    assert engine._runs_uninterrupted(s, "imap_delete_email") is False


def test_the_rung_is_scoped_to_its_own_session(engine: ExecutionEngine) -> None:
    """Two conversations are two consents. A plan waved through in one is not
    a standing permission in the other."""
    _session(engine, uninterrupted=True)
    assert engine._runs_uninterrupted("s2", "create_pull_request") is False
