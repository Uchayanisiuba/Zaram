"""What a commitment is, once Zaram has read one out of a document.

The rule this module exists to obey: **never silently create a commitment.**
A missed deadline is worse than no reminder, because trust does not recover —
but an *invented* deadline is worse than both, because the user reorganises
their week around it and only finds out it was never in the contract when they
go looking for the clause. So every obligation here carries the sentence it was
read from, and nothing in this module is allowed to produce one without it.

That is why `Obligation` has no default for `source`. A commitment with no
clause is not a lower-quality commitment, it is a different kind of object, and
making the field optional would let one be constructed by forgetting rather
than by deciding.

The other half is `Unresolved`. Extraction that cannot pin a date down does not
drop the sentence and does not guess at it: it returns the clause, says which
question it could not answer, and lets the caller ask. Dropping it silently
loses a real deadline; guessing at it invents one. Returning it is the only
option that does neither.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional


class ObligationKind(str, Enum):
    """What sort of commitment it is.

    Deliberately short. Each value earns its place by changing what Zaram would
    *do* about it — a payment can be chased, an expiry cannot; a renewal needs
    a decision before the date, a deliverable needs work before it. A taxonomy
    finer than that would be a classification exercise with no consequence.
    """

    #: Money owed, in either direction.
    PAYMENT = "payment"
    #: Work promised by a date.
    DELIVERABLE = "deliverable"
    #: Something that lapses if nothing is done — a quote, a licence, an offer.
    EXPIRY = "expiry"
    #: Something that continues, and costs money, unless it is stopped.
    RENEWAL = "renewal"


class Direction(str, Enum):
    """Who owes whom.

    ``UNKNOWN`` is the default and is not a failure. Direction is very rarely
    recoverable from the sentence alone — "payment is due within 30 days" reads
    identically on an invoice the user sent and one they received. What settles
    it is where the document came from, which is rule 7b's ``Origin`` and is
    known to the caller rather than to the parser.

    Guessing here would be the expensive kind of wrong: telling a freelancer
    they owe money they are in fact owed.
    """

    #: The user must do something.
    OWED_BY_USER = "owed_by_user"
    #: Someone must do something for the user.
    OWED_TO_USER = "owed_to_user"
    #: Not determinable from the document alone.
    UNKNOWN = "unknown"


class ObligationStatus(str, Enum):
    """Where the commitment stands.

    ``DISMISSED`` is kept rather than deleted, because rule 4 is about the user
    being able to correct what Zaram believes, and "this was never an
    obligation" is a correction worth remembering — otherwise the next ingest
    of the same document extracts it again and asks again.
    """

    OPEN = "open"
    MET = "met"
    DISMISSED = "dismissed"


@dataclass(frozen=True)
class Clause:
    """The sentence an obligation was read from, and where it sits.

    ``start`` and ``end`` are character offsets into the document text that was
    parsed, so an interface can highlight the clause in place rather than show
    it as a detached quotation. They are offsets into the *extracted text*, not
    the original PDF, which is the only thing the parsers can honestly offer.

    ``text`` is stored as well as the offsets, deliberately duplicating. The
    offsets go stale if a document is re-parsed by a different parser — the
    ingest layer explicitly allows that when an extra is installed — and a
    citation that silently points at the wrong sentence is worse than one that
    cannot be located in the current text. The text is what is shown; the
    offsets are an optimisation for highlighting.
    """

    text: str
    start: int = -1
    end: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return {"text": self.text, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class Obligation:
    """A dated commitment, and the clause that says so.

    Frozen. A correction produces a new obligation rather than mutating this
    one, so that "what did Zaram think last week" stays answerable and a
    correction is a visible event rather than a field changing underneath the
    interface.
    """

    id: str
    kind: ObligationKind
    #: One line, as a person would say it. Not the clause — the clause is often
    #: a paragraph of contract English and is carried separately.
    summary: str
    #: The date it falls due. Always absolute: a relative term is resolved
    #: against an anchor before an Obligation exists, or it does not become one.
    due: date
    #: The sentence this was read from. No default, on purpose.
    source_clause: Clause
    #: Which document it came from, as the ingest layer identifies it.
    source_document_id: str = ""
    direction: Direction = Direction.UNKNOWN
    status: ObligationStatus = ObligationStatus.OPEN
    #: Money, where the clause names an amount. `None` means the clause did not
    #: state one — never zero, which is a figure.
    amount: Optional[Decimal] = None
    currency: str = ""
    #: Rule 7i. Defaults to global only because a caller outside a project has
    #: nothing better to say; the ingest path passes the project through.
    scope: str = "global"
    #: How sure the extractor is, 0..1. This orders what the user reviews first
    #: and nothing else. It is not a gate: rule "a retrieval score authorises
    #: nothing" applies here too, and a confidence number must never be what
    #: decides that a commitment is real enough to act on.
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "summary": self.summary,
            "due": self.due.isoformat(),
            "source_clause": self.source_clause.to_dict(),
            "source_document_id": self.source_document_id,
            "direction": self.direction.value,
            "status": self.status.value,
            "amount": str(self.amount) if self.amount is not None else None,
            "currency": self.currency,
            "scope": self.scope,
            "confidence": self.confidence,
        }


class Unresolved(str, Enum):
    """Why a clause that clearly states a commitment did not become one."""

    #: A relative term with nothing to count from — "net 30" on a document
    #: whose issue date was not supplied.
    NO_ANCHOR_DATE = "no_anchor_date"
    #: A numeric date that means two different days depending on where the
    #: writer lives. 03/04/2026 is either 3 April or 4 March, and the two are a
    #: month apart.
    AMBIGUOUS_DATE = "ambiguous_date"
    #: A date that does not exist — 31 February, or a typo'd year.
    IMPOSSIBLE_DATE = "impossible_date"


@dataclass(frozen=True)
class UnresolvedObligation:
    """A commitment Zaram can see but cannot date.

    This is the shape of rule 9 in this module. The alternative designs are
    both worse: dropping the clause loses a real deadline the user is exposed
    to, and defaulting the date invents one. Returning it unresolved is what
    lets the interface say "this says payment is due 30 days after issue, but I
    don't know when it was issued — when was it?" — which is a question worth
    asking, because the system genuinely cannot answer it from behaviour.
    """

    kind: ObligationKind
    source_clause: Clause
    reason: Unresolved
    #: What the interface should ask, written for a person.
    question: str
    source_document_id: str = ""
    scope: str = "global"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "source_clause": self.source_clause.to_dict(),
            "reason": self.reason.value,
            "question": self.question,
            "source_document_id": self.source_document_id,
            "scope": self.scope,
        }
