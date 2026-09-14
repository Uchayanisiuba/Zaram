"""Obligations as a calendar file — without Zaram becoming a calendar.

`CLAUDE.md`: *"Zaram surfaces obligations in context and drafts the response —
it is not a calendar and must not become one."* The calendar people already
keep is where a due date belongs, and `.ics` is the one format every one of
them reads. So this writes one: every open obligation as an all-day event on
its due date, with the clause it was read from as the description, so the
event in Outlook or Google Calendar is checkable against the document the
same way the row in Memory is.

A file, not a feed. A subscribed feed would be a URL the calendar polls, which
is a server Zaram does not run and a network path rule 3 would have to log.
The file goes to the output directory like every generated thing — never
overwriting — and the person drops it into whatever they use.

`icalendar` (BSD) does the escaping and folding; hand-rolled iCalendar is a
format that looks simple and is not.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable

from icalendar import Calendar, Event

#: The product identifier iCalendar asks every file to carry.
PRODID = "-//Zaram//Obligations//EN"

KIND_WORD = {
    "payment": "Payment",
    "deliverable": "Deliverable",
    "expiry": "Expires",
    "renewal": "Renews",
}


def _due(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def to_ics(records: Iterable[Dict[str, Any]], *, now: datetime | None = None) -> bytes:
    """One VEVENT per obligation that has a date. Undatable ones are questions,
    not events, and are not here."""
    stamp = now or datetime.now(timezone.utc)
    cal = Calendar()
    cal.add("prodid", PRODID)
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Zaram obligations")

    for record in records:
        due = _due(record.get("due"))
        if due is None:
            continue
        event = Event()
        # The obligation's own id, so re-exporting updates the event in a
        # calendar that keys on UID rather than adding a duplicate beside it.
        event.add("uid", f"{record.get('id')}@zaram")
        event.add("dtstamp", stamp)
        # All-day: a clause names a day, never a time of day.
        event.add("dtstart", due)
        event.add("dtend", due + timedelta(days=1))
        kind = KIND_WORD.get(str(record.get("kind") or ""), "")
        summary = str(record.get("summary") or "").strip()
        event.add("summary", f"{kind}: {summary}" if kind and summary else summary or kind or "Obligation")

        clause = record.get("source_clause") or {}
        text = str(clause.get("text") or "").strip() if isinstance(clause, dict) else ""
        document = str(record.get("source_document_id") or "").replace("\\", "/").rsplit("/", 1)[-1]
        lines = []
        if text:
            lines.append(f"From the clause: “{text}”")
        if document:
            lines.append(f"Document: {document}")
        amount = record.get("amount")
        if amount not in (None, ""):
            currency = str(record.get("currency") or "").strip()
            lines.append(f"Amount: {amount} {currency}".rstrip())
        lines.append("Exported from Zaram. Correct it there; this file is a copy.")
        event.add("description", "\n".join(lines))
        cal.add_component(event)

    return cal.to_ical()
