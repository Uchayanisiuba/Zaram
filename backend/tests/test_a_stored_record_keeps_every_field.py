"""A record handed to the store comes back whole.

`store_record` rebuilt the record field by field on the way in, and an
enumeration is the wrong shape for that job: it has to be revisited every time
the record gains a field, and nothing fails when it is not. Eight had been
missed by 24 September 2026 — `scope`, `origin`, `pinned`, `superseded_by`,
`superseded_at`, `valid_from`, `valid_until` and `recalled_in`.

Two of them are rules rather than conveniences. **`scope` is rule 7i**, and it
is the multiplayer boundary — project memory is shareable, global memory never
is — so a fact dropping to `global` because a constructor call was not updated
is a privacy decision made by an omission. **`superseded_by` is rule 4**: a
fact the user corrected came back through this path still standing, because the
tombstone saying it had been replaced was left behind.

Both failures are silent. The write succeeds, the record is there, `get_record`
returns it, and only the parts that govern who may see it are gone.

So the test that matters is not "these eight fields survive" — that is the same
enumeration, restated in a place where it will go equally stale. It is
**every field on the dataclass survives**, asserted against
`dataclasses.fields` so that a field added next year is covered by a test
written today.
"""

from __future__ import annotations

import asyncio
from dataclasses import fields

import pytest

from runtimes.memory.contracts import (
    GLOBAL_SCOPE,
    MemoryRecord,
    MemoryType,
    Origin,
    project_scope,
)
from runtimes.memory.runtime import create_memory_runtime

#: Set on the record before storing, and expected back unchanged. Every field
#: whose value the caller owns is here; the two the runtime is *allowed* to
#: decide are listed in `RUNTIME_OWNED` below with the reason.
A_FULLY_POPULATED_RECORD = MemoryRecord(
    id="fact-1",
    content="Northwind pays 30 days net, not 14.",
    memory_type=MemoryType.SEMANTIC,
    metadata={"category": "terms", "client": "Northwind"},
    embedding=[0.5] * 128,
    embedded_by="test:fixed:128",
    created_at=1_700_000_000.0,
    updated_at=1_700_000_100.0,
    access_count=7,
    last_accessed=1_700_000_200.0,
    tags=["terms", "northwind"],
    session_id="session-a",
    user_id="user-a",
    importance=0.9,
    source="user_document",
    superseded_by="fact-2",
    superseded_at=1_700_000_300.0,
    valid_from=1_690_000_000.0,
    valid_until=1_695_000_000.0,
    pinned=True,
    scope=project_scope("northwind"),
    origin=Origin.USER_DOCUMENT,
    recalled_in=["northwind", "acme"],
)

#: The runtime may fill these in, and does — an embedding is computed when the
#: caller did not bring one, and its maker is stamped beside it. Everything
#: else is the caller's.
RUNTIME_OWNED = {"embedding", "embedded_by"}


@pytest.fixture
def runtime():
    rt = create_memory_runtime(
        store_type="memory",
        index_type="hybrid",
        embedding_dim=128,
        embedding_backend="hash",
    )
    asyncio.run(rt.initialize())
    return rt


def test_every_field_the_caller_set_comes_back(runtime):
    """The contract, asserted against the dataclass rather than against a list.

    A field added to `MemoryRecord` after this was written and forgotten in
    `store_record` fails here, which is the whole point — the previous version
    of this bug was eight fields accumulating one at a time, each silent.
    """
    record_id = asyncio.run(runtime.store_record(A_FULLY_POPULATED_RECORD))
    stored = asyncio.run(runtime.get_record(record_id))
    assert stored is not None

    dropped = {
        f.name: (getattr(A_FULLY_POPULATED_RECORD, f.name), getattr(stored, f.name))
        for f in fields(MemoryRecord)
        if f.name not in RUNTIME_OWNED
        and getattr(stored, f.name) != getattr(A_FULLY_POPULATED_RECORD, f.name)
    }
    assert not dropped, f"store_record changed fields it does not own: {dropped}"


def test_the_scope_survives(runtime):
    """Rule 7i, named on its own because it is the one with a privacy cost."""
    record_id = asyncio.run(runtime.store_record(
        MemoryRecord(content="Rate agreed at 600.", scope=project_scope("northwind"))
    ))
    stored = asyncio.run(runtime.get_record(record_id))
    assert stored.scope == "project:northwind"
    assert stored.project_id == "northwind"
    assert not stored.is_global


def test_a_correction_does_not_come_back_standing(runtime):
    """Rule 4: the tombstone is part of the record, not decoration on it."""
    record_id = asyncio.run(runtime.store_record(MemoryRecord(
        content="Northwind pays 14 days net.",
        superseded_by="fact-2",
        superseded_at=1_700_000_300.0,
    )))
    stored = asyncio.run(runtime.get_record(record_id))
    assert stored.is_superseded
    assert stored.superseded_by == "fact-2"


def test_the_origin_survives(runtime):
    """Rule 7b: recall explains *where a fact came from*, and cannot if the
    store forgot. Defaulting a passage from the user's own contract to
    `CONVERSATION` is Zaram misattributing the user's document to the user's
    chatter."""
    record_id = asyncio.run(runtime.store_record(
        MemoryRecord(content="Clause 4.2 sets the notice period at 30 days.",
                     origin=Origin.USER_DOCUMENT)
    ))
    stored = asyncio.run(runtime.get_record(record_id))
    assert stored.origin is Origin.USER_DOCUMENT


def test_a_pinned_fact_stays_pinned(runtime):
    record_id = asyncio.run(runtime.store_record(
        MemoryRecord(content="Always invoice on the 1st.", pinned=True)
    ))
    assert asyncio.run(runtime.get_record(record_id)).pinned is True


def test_the_id_the_caller_brought_is_the_id_it_gets_back(runtime):
    """`ConversationHistory` and `EpisodicMemory` unpacked the record into
    `store()`, which builds a *new* one — so the id the caller was holding was
    not the id of the fact that had been written."""
    record_id = asyncio.run(runtime.store_record(
        MemoryRecord(id="a-known-id", content="A fact with a name.")
    ))
    assert record_id == "a-known-id"


def test_an_origin_given_as_a_string_is_accepted(runtime):
    """The dataclass validates nothing, so the runtime normalises rather than
    storing a `str` where every reader expects an `Origin`."""
    record_id = asyncio.run(runtime.store_record(
        MemoryRecord(content="From a generated draft.", origin="generated")
    ))
    assert asyncio.run(runtime.get_record(record_id)).origin is Origin.GENERATED


def test_an_empty_scope_becomes_global(runtime):
    """`""` is not a scope. It would compare equal to nothing and be excluded
    from both a project's recall and the user's own."""
    record_id = asyncio.run(runtime.store_record(
        MemoryRecord(content="A fact with no scope set.", scope="")
    ))
    assert asyncio.run(runtime.get_record(record_id)).scope == GLOBAL_SCOPE


def test_a_correction_keeps_the_scope_and_the_origin(runtime):
    """Rule 4 changes what a fact *says*. It does not change who may see it.

    `correct()` built the replacement field by field too, and left `scope` and
    `origin` behind — so fixing a rate on a client's contract moved the fact
    out of that project and into the store rule 7i says is never shared, and
    re-attributed a passage from the user's own document to something they had
    merely said in passing.
    """
    original_id = asyncio.run(runtime.store_record(MemoryRecord(
        content="Northwind pays 14 days net.",
        scope=project_scope("northwind"),
        origin=Origin.USER_DOCUMENT,
        recalled_in=["northwind", "acme"],
    )))

    result = asyncio.run(runtime.correct(original_id, "Northwind pays 30 days net."))
    replacement = asyncio.run(runtime.get_record(result["replacement_id"]))

    assert replacement.scope == "project:northwind"
    assert replacement.origin is Origin.USER_DOCUMENT
    # Promotion evidence is about the fact, not its wording — a fact that gets
    # refined must not be one that can never reach the three-project threshold.
    assert replacement.recalled_in == ["northwind", "acme"]


def test_changing_the_importance_changes_only_the_importance(runtime):
    """`reinforce` and `apply_decay` run unattended, on a timer and on recall.

    This rebuilt the record around one float and dropped nine other fields with
    it — so a background task nudging a number resurrected a corrected fact,
    moved a project's fact into `global`, and blanked the embedder stamp, which
    is the field that decides whether the vector is comparable at all.
    """
    record_id = asyncio.run(runtime.store_record(MemoryRecord(
        content="Northwind pays 30 days net.",
        embedding=[0.5] * 128,
        embedded_by="ollama:bge-m3:1024",
        scope=project_scope("northwind"),
        origin=Origin.USER_DOCUMENT,
        pinned=True,
        superseded_by="fact-later",
        superseded_at=1_700_000_300.0,
        valid_from=1_690_000_000.0,
        recalled_in=["northwind"],
        importance=0.4,
    )))

    assert asyncio.run(runtime.update_importance(record_id, 0.9)) is True
    stored = asyncio.run(runtime.get_record(record_id))

    assert stored.importance == 0.9
    assert stored.embedded_by == "ollama:bge-m3:1024"
    assert stored.scope == "project:northwind"
    assert stored.origin is Origin.USER_DOCUMENT
    assert stored.pinned is True
    assert stored.superseded_by == "fact-later"
    assert stored.valid_from == 1_690_000_000.0
    assert stored.recalled_in == ["northwind"]


def test_conversation_history_keeps_the_whole_record(runtime):
    """The wrapper delegates to the runtime rather than re-deriving a record."""
    record = MemoryRecord(
        id="turn-1",
        content="I said something.",
        memory_type=MemoryType.CONVERSATION,
        source="user",
        scope=project_scope("northwind"),
        origin=Origin.CONVERSATION,
        pinned=True,
    )
    record_id = asyncio.run(runtime.history.store_record(record))
    stored = asyncio.run(runtime.get_record(record_id))
    assert record_id == "turn-1"
    assert stored.source == "user"
    assert stored.scope == "project:northwind"
    assert stored.pinned is True


def test_episodic_keeps_the_whole_record(runtime):
    record = MemoryRecord(
        id="event-1",
        content="Event: invoice_sent - Northwind, 600.",
        memory_type=MemoryType.EPISODIC,
        source="episodic_event",
        scope=project_scope("northwind"),
        pinned=True,
    )
    record_id = asyncio.run(runtime.episodic.store_record(record))
    stored = asyncio.run(runtime.get_record(record_id))
    assert record_id == "event-1"
    assert stored.source == "episodic_event"
    assert stored.scope == "project:northwind"
    assert stored.pinned is True
