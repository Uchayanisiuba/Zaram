"""Learning a company's document identity from a document they already send.

The user uploads an invoice they wrote in Word two years ago, and every
document Zaram generates afterwards carries their masthead, their terms and
their numbering. That is the ask. What follows is the shape of it that is
honest to build.

**Layout is not cloned, and that is the load-bearing decision.** Reproducing an
arbitrary `.docx` means reimplementing Word's layout engine, which is the same
reason an office engine was never embedded; a PDF carries no structure to
reproduce at all, only positioned glyphs. And the failure mode of trying is the
specific one that hurts: a *near* miss. A document ninety per cent in the house
style is worse than one obviously Zaram's, because the client notices the wrong
font on something wearing their letterhead.

So this extracts **identity** (name, address, logo, accent), **boilerplate**
and **conventions** (payment terms, currency, numbering) — and leaves layout to
`render_document`, where one HTML pipeline already produces every format.

**Nothing here is adopted automatically.** Extraction returns a *proposal*:
every field carries the text it was read from and how sure the reader is, and a
person confirms it before a single document is generated with it. That is rule
4's correction loop moved to the one moment it is cheapest to be corrected —
before the first invoice goes out, rather than after a client has seen the
wrong address.

**Nothing here is a schema for someone's business.** `Letterhead.lines` is
deliberately unparsed, because an address format that is right in Lagos is
wrong in Berlin. This module finds *which lines* are the address block; it does
not decide what a postcode is.

The reader is format-agnostic on purpose: it takes text and embedded images,
not a file. `.docx` and PDF supply those differently and both plug into one
interface, which is the same arrangement the ingest parsers already use so the
library underneath stays replaceable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .letterhead import ALLOWED_LOGO_TYPES, Letterhead, LogoRejected, logo_data_uri

__all__ = [
    "ProposedField",
    "Missing",
    "MissingField",
    "TemplateProposal",
    "extract_template_profile",
]


@dataclass(frozen=True)
class ProposedField:
    """One thing read out of the document, with what it was read from.

    `evidence` is not decoration. A user confirming "yes, that is my address"
    is answering a different and much easier question than "what is your
    address" — but only if they can see the line it came from. Rule 2 applied
    to onboarding.
    """

    value: str
    evidence: str
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "evidence": self.evidence,
            "confidence": self.confidence,
        }


class Missing(str, Enum):
    """Why something expected is not in the proposal.

    A named absence rather than an empty field, because "there is no logo in
    this document" and "there is a logo and I could not use it" need different
    sentences in front of the user, and only the second is worth asking about.
    """

    #: Nothing in the document looked like this field.
    NOT_PRESENT = "not_present"
    #: Found, and unusable — the logo case, where a bad crop must not be
    #: quietly shipped into a client-facing invoice.
    UNUSABLE = "unusable"
    #: Found more than one candidate and none was clearly right.
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class MissingField:
    name: str
    reason: Missing
    #: What to ask the user, written for a person.
    question: str

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "reason": self.reason.value, "question": self.question}


@dataclass(frozen=True)
class TemplateProposal:
    """What Zaram thinks this company's documents look like. Not yet in use.

    Deliberately not a `Letterhead`. A `Letterhead` is something documents are
    generated with, and turning a proposal into one is the confirmation step —
    keeping them the same type would make "extracted" and "approved"
    indistinguishable, which is precisely the distinction the review exists to
    hold.
    """

    name: Optional[ProposedField] = None
    address_lines: Sequence[ProposedField] = field(default_factory=tuple)
    logo: Optional[ProposedField] = None
    #: No `accent` field, deliberately. The accent colour is real and wanted,
    #: but the only honest source for it is the dominant non-neutral colour of
    #: the logo, which needs an image library this module does not depend on.
    #: A field that could only ever be `None` would advertise a capability that
    #: does not exist — the same failure as a status indicator over hardcoded
    #: data. It arrives with the code that can fill it.
    #: Payment terms in days, where the document states them.
    terms_days: Optional[ProposedField] = None
    currency: Optional[ProposedField] = None
    #: e.g. "INVOICE 0042" -> prefix "INVOICE ", width 4, last 42.
    numbering: Optional[ProposedField] = None
    #: Everything that could not be read, with the question that would settle it.
    missing: Sequence[MissingField] = field(default_factory=tuple)

    def as_letterhead(self) -> Letterhead:
        """The confirmation step: a proposal becomes something usable.

        Called after a person has reviewed it. Nothing in this module calls it,
        on purpose — the only route from "extracted" to "used" runs through the
        interface, so a generated document can never carry an identity nobody
        approved.
        """
        return Letterhead(
            name=self.name.value if self.name else "",
            lines=tuple(line.value for line in self.address_lines),
            logo=self.logo.value if self.logo else "",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name.to_dict() if self.name else None,
            "address_lines": [line.to_dict() for line in self.address_lines],
            # The logo is a data URI and can be hundreds of kilobytes. The
            # review interface needs to *show* it, so it is not summarised
            # away here — but its evidence is, since the evidence for an image
            # is a second copy of the image.
            "logo": self.logo.to_dict() if self.logo else None,
            "terms_days": self.terms_days.to_dict() if self.terms_days else None,
            "currency": self.currency.to_dict() if self.currency else None,
            "numbering": self.numbering.to_dict() if self.numbering else None,
            "missing": [item.to_dict() for item in self.missing],
        }


#: "net 30", "payment terms: 14 days", "due within 30 days"
_TERMS = re.compile(
    r"\bnet[\s\-]?(?P<net>\d{1,3})\b"
    r"|\b(?:within|after)\s+(?P<within>\d{1,3})\s+(?:calendar\s+|working\s+|business\s+)?days?\b"
    r"|\bterms?\b[^\n]{0,20}?\b(?P<terms>\d{1,3})\s*days?\b",
    re.IGNORECASE,
)

_DUE_ON_RECEIPT = re.compile(r"\b(?:due|payable)\s+(?:up)?on\s+receipt\b", re.IGNORECASE)

_CURRENCY_SYMBOL = {"£": "GBP", "$": "USD", "€": "EUR", "₦": "NGN"}
_CURRENCY_CODE = re.compile(
    r"\b(?P<code>GBP|USD|EUR|NGN|CAD|AUD|ZAR|KES|GHS|INR)\b(?=\s?\d)"
)
_CURRENCY_SYM = re.compile(r"(?P<symbol>[£$€₦])\s?\d")

#: "INVOICE 0042", "Invoice No. INV-0042", "#0042"
_NUMBERING = re.compile(
    r"\b(?:invoice|quote|estimate)\b[^\n]{0,12}?"
    r"(?P<prefix>[A-Z]{0,6}[-/]?)(?P<digits>\d{2,8})\b",
    re.IGNORECASE,
)

#: A line that is mostly money, dots or column rules is a line item, not an
#: address. Address detection is otherwise very easy to fool with a table.
_LINE_ITEM = re.compile(r"[.]{3,}|\s{4,}|[£$€₦]\s?\d|\b\d+[.,]\d{2}\b")

#: Words that mark a line as body copy rather than a masthead.
_BODY_CUE = re.compile(
    r"\b(?:invoice|quote|estimate|date[d]?|issued|due|terms?|payment|total|"
    r"subtotal|vat|tax|description|qty|quantity|amount|bill(?:ed)?\s+to|to:)\b",
    re.IGNORECASE,
)


def _clean_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines()]


def _looks_like_a_name(line: str) -> bool:
    """A trading name: short, wordy, not a heading about the document itself."""
    if not line or len(line) > 60:
        return False
    if _BODY_CUE.search(line) or _LINE_ITEM.search(line):
        return False
    letters = sum(character.isalpha() for character in line)
    return letters >= 3 and letters / len(line) > 0.5


def _extract_identity(
    lines: Sequence[str],
) -> Tuple[Optional[ProposedField], List[ProposedField], List[MissingField]]:
    """Name and address, from the top of the document.

    The masthead is positional — it is the first block of the page, above
    anything that talks about the document. That is a far more robust signal
    than trying to recognise an address, which differs by country and is what
    `Letterhead.lines` refuses to model.
    """
    missing: List[MissingField] = []
    head: List[Tuple[int, str]] = []
    for index, line in enumerate(lines[:12]):
        if not line:
            if head:
                break  # a blank line closes the masthead block
            continue
        if _BODY_CUE.search(line) or _LINE_ITEM.search(line):
            break
        head.append((index, line))

    if not head:
        missing.append(
            MissingField(
                "name",
                Missing.NOT_PRESENT,
                "I couldn't find a business name at the top of this document. "
                "What should appear on your letterhead?",
            )
        )
        return None, [], missing

    first_index, first_line = head[0]
    name: Optional[ProposedField] = None
    if _looks_like_a_name(first_line):
        # An all-caps or title-cased first line of a masthead is the trading
        # name in nearly every commercial document. Confidence is high but
        # never 1.0 — this is a positional guess, and the review step is what
        # makes a guess acceptable here.
        name = ProposedField(value=first_line, evidence=first_line, confidence=0.85)
    else:
        missing.append(
            MissingField(
                "name",
                Missing.AMBIGUOUS,
                f"Is “{first_line}” your business name, or should the letterhead "
                "say something else?",
            )
        )

    address = [
        ProposedField(value=line, evidence=line, confidence=0.7)
        for _, line in head[1:]
    ]
    if not address:
        missing.append(
            MissingField(
                "address_lines",
                Missing.NOT_PRESENT,
                "I couldn't find an address or contact block. What should sit "
                "under your name?",
            )
        )
    return name, address, missing


def _extract_terms(text: str) -> Optional[ProposedField]:
    if _DUE_ON_RECEIPT.search(text):
        match = _DUE_ON_RECEIPT.search(text)
        assert match is not None
        return ProposedField(value="0", evidence=match.group().strip(), confidence=0.9)
    match = _TERMS.search(text)
    if not match:
        return None
    days = match.group("net") or match.group("within") or match.group("terms")
    if days is None:  # pragma: no cover - one branch always matches
        return None
    return ProposedField(value=str(int(days)), evidence=match.group().strip(), confidence=0.85)


def _extract_currency(text: str) -> Optional[ProposedField]:
    code = _CURRENCY_CODE.search(text)
    if code:
        return ProposedField(
            value=code.group("code").upper(), evidence=code.group().strip(), confidence=0.9
        )
    symbol = _CURRENCY_SYM.search(text)
    if symbol:
        found = symbol.group("symbol")
        return ProposedField(
            value=_CURRENCY_SYMBOL[found], evidence=symbol.group().strip(), confidence=0.8
        )
    return None


def _extract_numbering(text: str) -> Optional[ProposedField]:
    """The numbering scheme, so the next document continues the sequence.

    Stored as `prefix:width:last` rather than as the next number, because the
    next number is a derived value and storing derived values is how two
    documents end up sharing one invoice number.
    """
    match = _NUMBERING.search(text)
    if not match:
        return None
    digits = match.group("digits")
    prefix = (match.group("prefix") or "").upper()
    return ProposedField(
        value=f"{prefix}:{len(digits)}:{int(digits)}",
        evidence=match.group().strip(),
        confidence=0.75,
    )


def _extract_logo(
    images: Sequence[Tuple[bytes, str]],
) -> Tuple[Optional[ProposedField], Optional[MissingField]]:
    """The first usable embedded image, or an honest refusal.

    Refusal rather than approximation is the rule here. A logo that is wrong,
    stretched or half-cropped goes onto every invoice the user sends, and they
    will not notice until a client does. Asking for the file is a five-second
    interruption; the alternative is a year of subtly broken paperwork.
    """
    if not images:
        return None, MissingField(
            "logo",
            Missing.NOT_PRESENT,
            "I couldn't find a logo in this document. Upload one and it will go "
            "on everything Zaram generates.",
        )

    reasons: List[str] = []
    for data, content_type in images:
        try:
            uri = logo_data_uri(data, content_type)
        except LogoRejected as rejected:
            reasons.append(str(rejected))
            continue
        return (
            ProposedField(
                value=uri,
                evidence=f"embedded image, {content_type}, {len(data) / 1024:.0f} KB",
                confidence=0.6,
            ),
            None,
        )

    # Every candidate failed. Say why the first one did rather than inventing a
    # summary — the reasons from `logo_data_uri` are already written for a user.
    return None, MissingField(
        "logo",
        Missing.UNUSABLE,
        f"{reasons[0]} Upload your logo and it will go on everything Zaram generates.",
    )


def extract_template_profile(
    text: str,
    *,
    images: Sequence[Tuple[bytes, str]] = (),
) -> TemplateProposal:
    """Read a company's document identity out of one of their documents.

    `images` are `(bytes, content_type)` pairs pulled from the file by whatever
    parsed it — `.docx` exposes them directly, a PDF exposes embedded XObjects.
    Passing them in rather than reading the file keeps this readable by both
    without either format leaking into it.

    Returns a proposal. It is never applied by this function, and
    `as_letterhead()` is the only route out — which a person triggers.
    """
    lines = _clean_lines(text)
    name, address, missing = _extract_identity(lines)
    logo, logo_missing = _extract_logo(images)
    if logo_missing is not None:
        missing.append(logo_missing)

    return TemplateProposal(
        name=name,
        address_lines=tuple(address),
        logo=logo,
        terms_days=_extract_terms(text),
        currency=_extract_currency(text),
        numbering=_extract_numbering(text),
        missing=tuple(missing),
    )
