"""Noticing when a new fact contradicts one already stored.

The machinery for *recording* a supersession already exists: `correct()` writes
a replacement, marks the original superseded, drops it from the index and keeps
it visible struck through. What has never existed is anything that **notices**.
Until now a contradiction was only handled when the user went looking for it,
which means the ordinary path was to store both and let recall pick — and
recall picking between "the target is developers" and "the target is ordinary
consumers" is a coin toss dressed as an answer.

**Nothing here resolves anything.** Detection surfaces a question; the user
answers it; `correct()` applies it. That division is deliberate and it is the
part most likely to be argued away later, so the reasoning is recorded here.

Auto-resolving on recency would be wrong roughly as often as it was right. "I
prefer local models" and "I want this one to go to Claude" are not a
contradiction, they are a general preference and a specific exception.
Auto-resolving on confidence would let a well-phrased sentence in an uploaded
PDF overwrite something the user said out loud. Both failures are silent, and
both destroy exactly the record rule 4 exists to protect.

**Scope is what makes this tractable, and it is why the two-store designs this
was compared against cannot express it.** Rule 7i: a fact is `global` or
`project:<id>`. Two projects holding different values for the same subject is
the normal case, not a conflict — one client pays in 14 days and another in 30,
and a system that flags that as a contradiction is one the user learns to
ignore. So a conflict requires the *same* scope, and a global fact is checked
against global facts only.

The detector is deliberately narrow. It reads simple assertions — "X is Y" —
and nothing else. A wider net would produce false conflicts, and a false
conflict is expensive: it interrupts the user to ask about something that was
never wrong, and an interruption that is usually noise trains people to dismiss
the one that matters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

__all__ = ["Assertion", "Conflict", "read_assertion", "find_conflicts"]


#: Words that carry no identity and would otherwise make two different subjects
#: look alike, or the same subject look different across two phrasings.
_LEADING = re.compile(
    r"^(?:the|my|our|their|his|her|its|a|an)\s+", re.IGNORECASE
)

#: "X is Y", "X are Y", "X = Y", "X: Y". The copula set is closed on purpose —
#: "X should be Y" is an intention and "X was Y" is history, and neither is a
#: statement of what is currently true.
_ASSERTION = re.compile(
    r"^\s*(?P<subject>[^=:]{2,60}?)\s*(?:\bis\b|\bare\b|=|:)\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)

#: "I prefer X" / "the user prefers X" — common enough in captured facts to be
#: worth reading, and it has an implied subject that the pattern above misses.
_PREFERENCE = re.compile(
    r"^\s*(?:i|the\s+user|user)\s+prefers?\s+(?P<value>.+?)\s*$", re.IGNORECASE
)

#: Hedges. A sentence carrying one is not asserting a current fact, so it
#: neither creates a conflict nor is contradicted by one.
_HEDGED = re.compile(
    r"\b(?:maybe|might|may|could|possibly|perhaps|considering|thinking\s+about|"
    r"used\s+to|previously|formerly|sometimes|usually|often)\b",
    re.IGNORECASE,
)


def _normalise(text: str) -> str:
    """Compare on meaning-bearing words, not on punctuation and articles."""
    lowered = text.strip().strip(".!?;,").lower()
    lowered = _LEADING.sub("", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


@dataclass(frozen=True)
class Assertion:
    """A statement of the form "this subject currently has this value"."""

    subject: str
    value: str
    #: The sentence it was read from, kept so a question can quote it.
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return {"subject": self.subject, "value": self.value, "text": self.text}


def read_assertion(content: str) -> Optional[Assertion]:
    """Read a simple assertion, or return None.

    None is the common case and is not a failure. Most stored facts are not
    assertions of a single current value, and treating them as though they were
    is what generates false conflicts.
    """
    if not content or _HEDGED.search(content):
        return None

    text = content.strip()
    preference = _PREFERENCE.match(text)
    if preference:
        value = _normalise(preference.group("value"))
        return Assertion(subject="preference", value=value, text=text) if value else None

    match = _ASSERTION.match(text)
    if not match:
        return None
    subject = _normalise(match.group("subject"))
    value = _normalise(match.group("value"))
    if not subject or not value:
        return None
    return Assertion(subject=subject, value=value, text=text)


@dataclass(frozen=True)
class Conflict:
    """Two facts that cannot both be current, and the question that settles it.

    There is no `resolution` field and no `winner`. This object exists to be
    shown to a person; the moment it carries a decision, something will start
    applying that decision without asking.
    """

    existing_id: str
    existing_content: str
    incoming_content: str
    subject: str
    existing_value: str
    incoming_value: str
    scope: str
    question: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "existing_id": self.existing_id,
            "existing_content": self.existing_content,
            "incoming_content": self.incoming_content,
            "subject": self.subject,
            "existing_value": self.existing_value,
            "incoming_value": self.incoming_value,
            "scope": self.scope,
            "question": self.question,
        }


def _values_differ(left: str, right: str) -> bool:
    """Whether two values are genuinely different.

    Containment is treated as agreement rather than conflict: "net 30" and
    "net 30 from invoice date" are the same term stated at two levels of
    detail, and flagging that pair teaches the user that conflicts are noise.
    """
    if left == right:
        return False
    return left not in right and right not in left


def find_conflicts(
    incoming_content: str,
    existing: Iterable[Any],
    *,
    scope: str = "global",
) -> List[Conflict]:
    """Existing facts that the incoming one contradicts.

    `existing` is any iterable of objects carrying `id`, `content`, `scope` and
    the supersession fields — `MemoryRecord` in production, and anything with
    those attributes in a test. Typed structurally rather than by import so
    this module does not reach back into the runtime that calls it.

    Returns an empty list far more often than not. That is the intended
    behaviour, not a weak detector: the cost of a missed conflict is one stale
    fact the user can still correct by hand, and the cost of a false one is an
    interruption that makes every future interruption easier to dismiss.
    """
    incoming = read_assertion(incoming_content)
    if incoming is None:
        return []

    conflicts: List[Conflict] = []
    for record in existing:
        # A fact already corrected is out of recall and is history. Raising it
        # again would ask the user to re-decide something they have decided.
        if getattr(record, "superseded_by", None):
            continue
        # Rule 7i. Different scopes are different questions — one client's
        # terms are not a contradiction of another's.
        record_scope = getattr(record, "scope", "global") or "global"
        if record_scope != scope:
            continue

        content = getattr(record, "content", "") or ""
        stored = read_assertion(content)
        if stored is None or stored.subject != incoming.subject:
            continue
        if not _values_differ(stored.value, incoming.value):
            continue

        conflicts.append(
            Conflict(
                existing_id=getattr(record, "id", ""),
                existing_content=content,
                incoming_content=incoming_content.strip(),
                subject=incoming.subject,
                existing_value=stored.value,
                incoming_value=incoming.value,
                scope=scope,
                question=(
                    f"You told me {stored.subject} is “{stored.value}”, and this "
                    f"says “{incoming.value}”. Which is right now?"
                ),
            )
        )
    return conflicts
