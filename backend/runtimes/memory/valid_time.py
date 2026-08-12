"""Answering "what was true then", not "what is true now".

Supersession already answers *what replaced what*. This answers the question
that only valid time can: on a given date, which version of a fact was in
force. "What was my day rate in July" is not a question about the store's
history — it is a question about the world's — and the two differ whenever the
user tells Zaram about a change after it happened, which is nearly always.

The distinction it rests on:

* `superseded_at` — **recorded time.** When Zaram was told.
* `valid_from` / `valid_until` — **valid time.** When it was actually so.

A client raises the rate in June and the user says so in August. Recorded time
says the old rate stood until August, which is wrong about every invoice issued
in between. Valid time says it stopped in June, which is what an accounting
question needs.

**Unknown is preserved rather than filled in.** A fact whose `valid_from` is
None was captured with nobody stating a start date, and treating `created_at`
as one would present a capture timestamp as a claim about the world. So an
unbounded start is treated as "as far back as Zaram knows" — it matches any
date — and that is stated in `explain()` rather than hidden, because an answer
resting on an assumption should say so.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

__all__ = ["in_force_at", "history_of", "explain"]


def _starts_before(record: Any, when: float) -> bool:
    valid_from = getattr(record, "valid_from", None)
    # None means no stated start. Matching anything is the honest reading:
    # Zaram knows of no date before which this was untrue.
    return valid_from is None or valid_from <= when


def _ends_after(record: Any, when: float) -> bool:
    valid_until = getattr(record, "valid_until", None)
    # Half-open on purpose: [valid_from, valid_until). The instant a
    # replacement takes over belongs to the replacement, so an as-of query at
    # exactly that moment returns one fact rather than two.
    return valid_until is None or when < valid_until


def in_force_at(records: Iterable[Any], when: float) -> List[Any]:
    """Every fact that was true at `when`.

    Superseded facts are *included* when the date falls inside their window —
    that is the entire point. Filtering them out would reduce this to "what is
    true now" with extra steps.
    """
    return [
        record
        for record in records
        if _starts_before(record, when) and _ends_after(record, when)
    ]


def history_of(records: Iterable[Any], record_id: str) -> List[Any]:
    """One fact's chain, oldest first.

    Follows `superseded_by` forward from `record_id`. Returns what it can
    reach rather than raising on a broken link: a chain with a missing middle
    is a store that lost a row, and refusing to show the rest of it helps
    nobody.
    """
    by_id = {getattr(record, "id", None): record for record in records}
    chain: List[Any] = []
    seen: set[str] = set()
    current: Optional[str] = record_id

    while current and current in by_id and current not in seen:
        seen.add(current)
        record = by_id[current]
        chain.append(record)
        current = getattr(record, "superseded_by", None)

    return chain


def explain(record: Any, when: float) -> str:
    """One line saying why this fact answers a question about `when`.

    Provenance for a temporal answer. "Your rate was £500 in July" is a claim
    about the past, and rule 2 applies to it exactly as it does to any other
    recalled fact — including saying plainly when the answer rests on an
    unstated start date rather than a recorded one.
    """
    import time as _time

    stamp = _time.strftime("%d %b %Y", _time.localtime(when))
    valid_from = getattr(record, "valid_from", None)
    valid_until = getattr(record, "valid_until", None)

    if valid_from is None and valid_until is None:
        return (
            f"In force on {stamp}, as far as Zaram knows — no start or end date "
            "was ever recorded for this."
        )
    if valid_from is None:
        until = _time.strftime("%d %b %Y", _time.localtime(valid_until))
        return f"In force on {stamp}; no start date was recorded, and it ended {until}."
    since = _time.strftime("%d %b %Y", _time.localtime(valid_from))
    if valid_until is None:
        return f"In force on {stamp}; true since {since}, and still current."
    until = _time.strftime("%d %b %Y", _time.localtime(valid_until))
    return f"In force on {stamp}; true from {since} until {until}."
