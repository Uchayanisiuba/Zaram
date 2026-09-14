"""Obligations as an `.ics` file — a copy for the calendar the person keeps.

Zaram is not a calendar and must not become one (`CLAUDE.md`). What it can
do is hand the dates over: one all-day event per dated obligation, keyed on
the obligation's own id so a re-export updates rather than duplicates, with
the clause it came from in the description so the event is checkable.
Undatable clauses are questions, not events, and are left out.
"""

from __future__ import annotations

from datetime import datetime, timezone

from obligations.calendar import to_ics


def _record(**over):
    base = {
        "id": "ob-1",
        "kind": "payment",
        "summary": "Abuja fit-out invoice 12 due",
        "due": "2026-10-14",
        "source_clause": {"text": "Payment terms: net 30 from date of invoice.", "start": 0, "end": 10},
        "source_document_id": "C:/Clients/Abuja/Abuja_fitout_SOW_rev2.pdf",
        "direction": "owed_to_me",
        "status": "open",
        "amount": "450000",
        "currency": "NGN",
    }
    base.update(over)
    return base


def test_one_all_day_event_per_dated_obligation_with_its_clause():
    ics = to_ics([_record()], now=datetime(2026, 9, 14, 12, tzinfo=timezone.utc)).decode()
    assert "BEGIN:VEVENT" in ics
    assert "UID:ob-1@zaram" in ics
    assert "DTSTART;VALUE=DATE:20261014" in ics
    assert "DTEND;VALUE=DATE:20261015" in ics
    assert "SUMMARY:Payment: Abuja fit-out invoice 12 due" in ics
    # The clause and the document, so the event is checkable — folded lines
    # are unfolded before looking, since iCalendar wraps at 75 octets.
    flat = ics.replace("\r\n ", "")
    assert "net 30 from date of invoice" in flat
    assert "Abuja_fitout_SOW_rev2.pdf" in flat
    assert "450000 NGN" in flat


def test_an_undated_clause_is_a_question_not_an_event():
    ics = to_ics([_record(due=""), _record(id="ob-2", due=None)]).decode()
    assert "BEGIN:VEVENT" not in ics
    assert "BEGIN:VCALENDAR" in ics
