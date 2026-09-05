"""Reading commitments out of a document, without inventing any.

Deterministic and model-free, on purpose. Three reasons, in order of how much
they matter:

**A wrong date is not a wrong answer, it is a missed deadline.** A generative
model asked to find obligations will produce plausible ones, and plausible is
exactly the failure mode rule 9 was written for — the "Project Phoenix"
proposal that read perfectly and was about nobody. A regex that finds nothing
is visibly useless; a model that finds a deadline that was never in the
contract is invisibly harmful.

**Reproducibility is the whole correction loop.** The user is going to correct
what this produces. A correction is only worth storing if the same document
extracts the same way tomorrow, and a sampled model does not promise that.

**It costs nothing.** Extraction runs on every ingested document, and the
product does not buy inference (rule 1).

The limits are real and are not hidden: this reads clauses that state their
terms in more or less standard commercial English. It will miss commitments
phrased obliquely, and the answer to that is a wider pattern set with tests,
or an offer to have a model read a specific document when the user asks —
never a model reading everything by default.

**What it refuses to do is the interesting part.** A date it cannot pin down
does not become a commitment with a guessed date and does not vanish: it comes
back as `UnresolvedObligation` with the question that would settle it. The
clearest case is `03/04/2026`, which is 3 April to most of the world and 4
March in the United States. There is no correct default — a locale setting
would only move the guess somewhere the user cannot see it — and the two
readings are a month apart, which on a payment deadline is the difference
between early and late.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, List, Optional, Sequence, Tuple

from .contracts import (
    Clause,
    Direction,
    Obligation,
    ObligationKind,
    Unresolved,
    UnresolvedObligation,
)

__all__ = ["extract_obligations", "ExtractionResult"]


_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))

#: "15 March 2026", "15th March 2026", "15 Mar 26"
_DATE_DMY = re.compile(
    rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<month>{_MONTH_ALT})\.?"
    rf"(?:,?\s+(?P<year>\d{{4}}|\d{{2}}))?\b",
    re.IGNORECASE,
)

#: "March 15, 2026", "Mar 15 2026"
_DATE_MDY = re.compile(
    rf"\b(?P<month>{_MONTH_ALT})\.?\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?"
    rf"(?:,?\s+(?P<year>\d{{4}}|\d{{2}}))?\b",
    re.IGNORECASE,
)

#: "2026-03-15". Unambiguous by construction — a four-digit year leads.
_DATE_ISO = re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b")

#: "15/03/2026", "3.4.26". Ambiguous unless one component exceeds 12.
_DATE_NUMERIC = re.compile(
    r"\b(?P<first>\d{1,2})[/.\-](?P<second>\d{1,2})[/.\-](?P<year>\d{4}|\d{2})\b"
)

#: "net 30", "net-30", "net 30 days"
_TERMS_NET = re.compile(r"\bnet[\s\-]?(?P<days>\d{1,3})\b", re.IGNORECASE)

#: "within 30 days", "within 14 days of receipt", "30 days from the invoice date"
_TERMS_WITHIN = re.compile(
    r"\b(?:within|after|from)?\s*(?P<days>\d{1,3})\s+(?:calendar\s+|working\s+|business\s+)?days?\b",
    re.IGNORECASE,
)

#: "due on receipt", "payable immediately"
_TERMS_IMMEDIATE = re.compile(
    r"\b(?:due|payable)\s+(?:up)?on\s+receipt\b|\bpayable\s+immediately\b", re.IGNORECASE
)

#: Money. Symbol-first ("£2,400.00") or code-first ("NGN 500,000").
_AMOUNT = re.compile(
    r"(?P<symbol>[£$€₦])\s?(?P<sym_value>\d[\d,]*(?:\.\d{1,2})?)"
    r"|(?P<code>\b(?:GBP|USD|EUR|NGN|CAD|AUD|ZAR|KES|GHS|INR)\b)\s?(?P<code_value>\d[\d,]*(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

_SYMBOL_TO_CODE = {"£": "GBP", "$": "USD", "€": "EUR", "₦": "NGN"}

#: Cue words, most specific kind first. A renewal clause almost always also
#: says "payment", and an expiry clause almost always says "valid" near a
#: price — so the order here is doing real work, and PAYMENT sits last among
#: the money-ish kinds rather than first.
_CUES: Sequence[Tuple[ObligationKind, re.Pattern]] = (
    (
        ObligationKind.RENEWAL,
        re.compile(
            r"\b(?:auto[\-\s]?renew\w*|renew\w*|rolls?\s+over|continues?\s+automatically)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObligationKind.EXPIRY,
        re.compile(
            r"\b(?:valid\s+(?:un)?til|expir\w+|lapses?|no\s+longer\s+valid|"
            r"offer\s+(?:ends|closes)|quote\s+is\s+valid)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObligationKind.DELIVERABLE,
        re.compile(
            r"\b(?:deliver\w*|submit\w*|hand\s+over|complete\w*\s+by|final\s+(?:files|assets|draft)|"
            r"milestone|due\s+for\s+delivery)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObligationKind.PAYMENT,
        re.compile(
            r"\b(?:payment|payable|pay\b|remit\w*|invoice\w*|balance|deposit|"
            r"amount\s+due|settle\w*)\b",
            re.IGNORECASE,
        ),
    ),
)

#: A sentence needs one of these as well as a cue before a date in it is read
#: as a deadline. Without it, "we met on 3 March" and "the logo was approved on
#: 12 April" become obligations — every document is full of dates that commit
#: nobody to anything.
_COMMITMENT = re.compile(
    r"\b(?:due|by|before|no\s+later\s+than|deadline|within|net\b|until|expir\w+|"
    r"renew\w*|payable|deliver\w*|submit\w*|valid)\b",
    re.IGNORECASE,
)

#: Sentence terminators, and the reason this is not simply `[.!?;]`.
#:
#: A naive split on the full stop cuts `£2,400.00` in half, which loses the
#: amount *and* the clause — "Payment of £2,400." and "00 is due by 15 March
#: 2026." Neither half reads as a commitment with a sum attached, so an invoice
#: stating a precise figure extracted nothing at all while one stating a round
#: figure worked. That is the worst shape of bug available here: it fails on
#: the realistic input and passes on the example.
#:
#: So a period *followed by* a digit is not a terminator. The lookahead alone
#: is the whole rule: `2,400.00` is protected because a digit follows, while
#: `15 March 2026.` still ends a sentence even though a digit precedes it.
#: Guarding both sides instead swallows every clause that ends in a year.
#: Newlines terminate too, because clause lists in contracts are frequently
#: line-broken rather than punctuated.
_TERMINATOR = re.compile(r"[.!?;](?!\d)|[\r\n]+")


class ExtractionResult:
    """What one document yielded.

    Two lists rather than one with a status field, because the caller does
    genuinely different things with them: obligations are shown for review,
    unresolved ones are shown as questions. Merging them produces an interface
    that has to branch on every item anyway.
    """

    __slots__ = ("obligations", "unresolved")

    def __init__(
        self,
        obligations: List[Obligation],
        unresolved: List[UnresolvedObligation],
    ) -> None:
        self.obligations = obligations
        self.unresolved = unresolved

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"ExtractionResult(obligations={len(self.obligations)}, "
            f"unresolved={len(self.unresolved)})"
        )


def _year(raw: Optional[str], anchor: Optional[date]) -> Optional[int]:
    """Resolve a written year, including the two-digit form.

    A missing year is taken from the anchor when there is one. That is a real
    assumption and it is made only where it is safe: an invoice that says
    "due 15 March" was almost certainly issued in the same year it is read in,
    and the anchor *is* that year. With no anchor there is nothing to assume
    from, so the caller gets no date rather than the current year — which would
    be Zaram's clock deciding a contract term.
    """
    if raw is None:
        return anchor.year if anchor else None
    value = int(raw)
    if len(raw) == 2:
        # Two-digit years are 20xx. A commercial document dated '26 is 2026;
        # nothing in this product's use is reading 1926 contracts.
        return 2000 + value
    return value


def _build(day: int, month: int, year: Optional[int]) -> Tuple[Optional[date], Optional[Unresolved]]:
    if year is None:
        return None, Unresolved.NO_ANCHOR_DATE
    try:
        return date(year, month, day), None
    except ValueError:
        # 31 February, or a month of 13. Real, and usually a typo in the
        # source document rather than a parsing failure — which is worth
        # telling the user about rather than swallowing.
        return None, Unresolved.IMPOSSIBLE_DATE


def _scan_dates(
    text: str, anchor: Optional[date]
) -> List[Tuple[Optional[date], Optional[Unresolved], int, int]]:
    """Every date-like run in `text`, resolved where that is honest.

    Returns `(value, reason, start, end)`. Exactly one of value/reason is set.
    Ordered by position, and overlapping matches are dropped so that a single
    date is never reported twice by two patterns.
    """
    found: List[Tuple[Optional[date], Optional[Unresolved], int, int]] = []
    taken: List[Tuple[int, int]] = []

    def overlaps(start: int, end: int) -> bool:
        return any(start < e and end > s for s, e in taken)

    # ISO first: it is the only wholly unambiguous numeric form, so claiming
    # those spans before the ambiguous numeric pattern sees them is what keeps
    # 2026-03-15 from being read as a day/month pair.
    for match in _DATE_ISO.finditer(text):
        value, reason = _build(
            int(match.group("day")), int(match.group("month")), int(match.group("year"))
        )
        found.append((value, reason, match.start(), match.end()))
        taken.append((match.start(), match.end()))

    for pattern in (_DATE_DMY, _DATE_MDY):
        for match in pattern.finditer(text):
            if overlaps(match.start(), match.end()):
                continue
            month = _MONTHS[match.group("month").lower()]
            value, reason = _build(
                int(match.group("day")), month, _year(match.group("year"), anchor)
            )
            found.append((value, reason, match.start(), match.end()))
            taken.append((match.start(), match.end()))

    for match in _DATE_NUMERIC.finditer(text):
        if overlaps(match.start(), match.end()):
            continue
        first, second = int(match.group("first")), int(match.group("second"))
        year = _year(match.group("year"), anchor)
        if first > 12 and second <= 12:
            value, reason = _build(first, second, year)          # day first
        elif second > 12 and first <= 12:
            value, reason = _build(second, first, year)          # month first
        elif first > 12 and second > 12:
            value, reason = None, Unresolved.IMPOSSIBLE_DATE
        else:
            # Both plausible as either. This is the case worth refusing.
            value, reason = None, Unresolved.AMBIGUOUS_DATE
        found.append((value, reason, match.start(), match.end()))
        taken.append((match.start(), match.end()))

    found.sort(key=lambda item: item[2])
    return found


def _scan_amount(text: str) -> Tuple[Optional[Decimal], str]:
    match = _AMOUNT.search(text)
    if not match:
        return None, ""
    if match.group("symbol"):
        raw, code = match.group("sym_value"), _SYMBOL_TO_CODE[match.group("symbol")]
    else:
        raw, code = match.group("code_value"), match.group("code").upper()
    try:
        return Decimal(raw.replace(",", "")), code
    except InvalidOperation:  # pragma: no cover - the pattern already constrains this
        return None, ""


def _classify(sentence: str) -> Optional[ObligationKind]:
    for kind, pattern in _CUES:
        if pattern.search(sentence):
            return kind
    return None


def _relative_days(sentence: str) -> Optional[int]:
    """Days from an anchor, where the clause states a term rather than a date."""
    if _TERMS_IMMEDIATE.search(sentence):
        return 0
    net = _TERMS_NET.search(sentence)
    if net:
        return int(net.group("days"))
    within = _TERMS_WITHIN.search(sentence)
    if within:
        return int(within.group("days"))
    return None


def _summarise(kind: ObligationKind, amount: Optional[Decimal], currency: str) -> str:
    """One line for a person, assembled from what was found and nothing else.

    Deliberately not prose about the clause. Anything more descriptive would
    have to be composed from the sentence, and a summary that reads like a
    restatement invites being trusted instead of the clause it sits next to.
    """
    if amount is not None and currency:
        money = f"{currency} {amount:,.2f}"
        if kind is ObligationKind.PAYMENT:
            return f"Payment of {money} due"
        return f"{kind.value.capitalize()} — {money}"
    return {
        ObligationKind.PAYMENT: "Payment due",
        ObligationKind.DELIVERABLE: "Deliverable due",
        ObligationKind.EXPIRY: "Expires",
        ObligationKind.RENEWAL: "Renews",
    }[kind]


def _sentences(text: str) -> Iterable[Tuple[str, int, int]]:
    """Each clause, with offsets that still index into `text`.

    Punctuation is kept on the clause and a newline is not, so a quoted clause
    reads as a sentence rather than as a fragment missing its full stop.
    """

    def emit(raw: str, base: int) -> Optional[Tuple[str, int, int]]:
        stripped = raw.strip()
        if not stripped:
            return None
        offset = base + (len(raw) - len(raw.lstrip()))
        return stripped, offset, offset + len(stripped)

    position = 0
    for match in _TERMINATOR.finditer(text):
        ends_sentence = match.group()[0] in ".!?;"
        raw = text[position : match.end() if ends_sentence else match.start()]
        found = emit(raw, position)
        if found:
            yield found
        position = match.end()

    tail = emit(text[position:], position)
    if tail:
        yield tail


def extract_obligations(
    text: str,
    *,
    document_id: str = "",
    anchor_date: Optional[date] = None,
    scope: str = "global",
    direction: Direction = Direction.UNKNOWN,
) -> ExtractionResult:
    """Read every dated commitment in `text`.

    `anchor_date` is what relative terms count from — the issue date of an
    invoice, the signature date of a contract. Without it, "net 30" cannot
    become a date, and this returns the clause as a question instead of
    inventing one.

    `direction` is passed through rather than inferred. The sentence cannot
    tell you whether the user owes the money or is owed it; where the document
    came from can, and the caller knows that.
    """
    obligations: List[Obligation] = []
    unresolved: List[UnresolvedObligation] = []

    for sentence, start, end in _sentences(text):
        kind = _classify(sentence)
        if kind is None:
            continue

        # A relative term is itself a commitment, and requiring `_COMMITMENT`
        # as well silently lost the single most common clause on a real
        # invoice. **"Payment terms: 30 days from the invoice date"** carries
        # none of `due`, `by`, `within` or `net`, so it was dropped at this
        # gate — classified as a payment, its thirty days parsed, and then
        # discarded with no obligation and no unresolved question. That exact
        # sentence is what `tests/test_recall_eval.py` uses as its sample
        # invoice, so the repository's own canonical example was the one it
        # could not read.
        #
        # Checking `_relative_days` rather than widening the regex keeps the
        # gate tight. The regex exists so that "we met on 3 March" does not
        # become a deadline, and adding a word like "terms" to it would let
        # every sentence mentioning terms through. A parsed span of days plus a
        # payment or delivery cue is a deadline by construction.
        if not _COMMITMENT.search(sentence) and _relative_days(sentence) is None:
            continue

        clause = Clause(text=sentence, start=start, end=end)
        amount, currency = _scan_amount(sentence)
        dates = _scan_dates(sentence, anchor_date)
        absolute = [item for item in dates if item[0] is not None]

        if absolute:
            value = absolute[0][0]
            assert value is not None  # narrowed by the filter above
            obligations.append(
                Obligation(
                    id=str(uuid.uuid4()),
                    kind=kind,
                    summary=_summarise(kind, amount, currency),
                    due=value,
                    source_clause=clause,
                    source_document_id=document_id,
                    direction=direction,
                    amount=amount,
                    currency=currency,
                    scope=scope,
                    confidence=0.9,
                )
            )
            continue

        days = _relative_days(sentence)
        if days is not None:
            if anchor_date is None:
                unresolved.append(
                    UnresolvedObligation(
                        kind=kind,
                        source_clause=clause,
                        reason=Unresolved.NO_ANCHOR_DATE,
                        question=(
                            f"This says it falls due {days} days after the document "
                            "date, but I don't know what that date is. When was it "
                            "issued?"
                        ),
                        source_document_id=document_id,
                        scope=scope,
                    )
                )
                continue
            obligations.append(
                Obligation(
                    id=str(uuid.uuid4()),
                    kind=kind,
                    summary=_summarise(kind, amount, currency),
                    due=anchor_date + timedelta(days=days),
                    source_clause=clause,
                    source_document_id=document_id,
                    direction=direction,
                    amount=amount,
                    currency=currency,
                    scope=scope,
                    # Lower than an absolute date, because it rests on the
                    # anchor being right as well as the clause being read
                    # right. Two things to be wrong about, not one.
                    confidence=0.75,
                )
            )
            continue

        # A date was seen and could not be resolved. Report the first reason;
        # reporting all of them would list the same question repeatedly for a
        # clause that only needs answering once.
        blocked = [item for item in dates if item[1] is not None]
        if blocked:
            reason = blocked[0][1]
            assert reason is not None
            unresolved.append(
                UnresolvedObligation(
                    kind=kind,
                    source_clause=clause,
                    reason=reason,
                    question=_question_for(reason, sentence, blocked[0][2], blocked[0][3]),
                    source_document_id=document_id,
                    scope=scope,
                )
            )

    return ExtractionResult(obligations, unresolved)


def _question_for(reason: Unresolved, sentence: str, start: int, end: int) -> str:
    written = sentence[start - 0 : end] if 0 <= start < end <= len(sentence) else ""
    written = written.strip() or "that date"
    if reason is Unresolved.AMBIGUOUS_DATE:
        return (
            f"“{written}” could be two different days — day/month or month/day. "
            "Which is it?"
        )
    if reason is Unresolved.IMPOSSIBLE_DATE:
        return f"“{written}” isn't a real date. What should it be?"
    return "I couldn't work out what date this refers to. What is it?"
