"""Reading an answer into the fields a document is made of.

**Why this exists.** `ArtifactService` can already produce a real invoice — a
line-item table, totals it computes itself, a due date derived from the terms, a
letterhead — and a real spreadsheet, and a real deck. `POST /artifacts/generate`
reaches all three. The conversation reached none of them: `DocumentsRuntime`
called `create_document` for every kind, so "make me an invoice" produced a
`.docx` containing the model's prose with the word *invoice* in the filename,
and "make me a PowerPoint" produced a `.docx`, because DECK was not even in the
list of words that pick a kind.

That is the same shape this codebase keeps finding — a complete, tested
component that nothing calls — and it is the one the maintainer reported as
"Zaram simply creates an unformatted document".

What this is, and what it is not
--------------------------------
**It reads the answer that was already produced; it does not write a new one.**
`DocumentsRuntime`'s standing rule is that the file must be the answer the user
just read, because re-asking produces a different document from the one they
approved of. Extraction respects that: the model is shown text that already
exists and asked which parts of it are the client, the line items, the rates. A
second generation would be a different document; a reading is the same one.

**It refuses rather than fills in.** Rule 9, and it is the whole reason this
returns a `Missing` instead of raising or defaulting. An invoice with an
invented rate is confident, plausible and wrong, and unlike a chat reply it gets
sent to a client. Every field that cannot be read from the text is named back to
the user so they can supply it — `invoice.py` already refuses the same way with
`InvoiceIncomplete`, and this is that refusal moved one step earlier, where the
message can still be conversational.

**Arithmetic is never taken from the model.** Only descriptions, quantities and
unit prices are read. `total_of` multiplies and sums, because a language model
producing a subtotal is a language model guessing at multiplication, and the one
number a client checks is the total.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

#: Asks a model something and returns its whole reply. Injected rather than
#: imported for the reason every other callable in this codebase is: the
#: artifacts layer must not acquire a dependency on the models runtime.
Ask = Callable[[str, str], str]


@dataclass
class Missing:
    """What could not be read, phrased for the person who has to supply it."""

    fields: List[str] = field(default_factory=list)

    def sentence(self, what: str) -> str:
        """A refusal that names the gap and asks for it.

        Deliberately not "extraction failed". The user cannot act on that, and
        the failure is usually theirs to fix in one line — they did not say the
        rate, or who it is for.
        """
        if not self.fields:
            return (
                f"I couldn't put together {what} from this conversation. "
                f"Tell me the details and I'll make it."
            )
        gaps = ", ".join(self.fields)
        return (
            f"I can't make {what} yet — I don't have {gaps}. "
            f"Tell me and I'll write it up properly rather than guess."
        )


#: The instruction every extraction shares.
#:
#: Explicit about the refusal because the alternative is a model being helpful:
#: asked for a rate that is not in the text, an obliging model supplies a
#: plausible one, and that is precisely the failure rule 9 names.
_SYSTEM = (
    "You extract structured data from text that already exists. You never "
    "invent a value. If the text does not state something, use null — a "
    "missing field is a correct answer and a guessed one is not. Reply with "
    "JSON only: no explanation, no markdown fence, no commentary."
)


def _json_from(reply: str) -> Optional[Dict[str, Any]]:
    """The first JSON object in a reply, or ``None``.

    Small models wrap JSON in prose and in ``` fences however firmly they are
    told not to, so the object is found rather than assumed. Nothing is
    repaired: a malformed object becomes ``None`` and the caller refuses, which
    is the safe direction — a half-parsed invoice is worse than no invoice.
    """
    if not reply:
        return None
    text = reply.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _amount(value: Any) -> Optional[str]:
    """A quantity or a price as *text*, or ``None`` — never a default.

    **Text, not a float, and that is not a style choice.** `invoice.py` refuses
    a float outright — "cannot represent money exactly. Send it as a string" —
    because it works in `Decimal`, and 0.1 + 0.2 on an invoice is a number a
    client can see is wrong. Returning a float here would have that refusal
    fire on every well-formed invoice, which is how a correct guard comes to
    look like a bug.

    Strings arrive with currency symbols and separators attached because that
    is how they appear in the text being read. ``0`` is preserved as a real
    value: a zero-rated line exists, and coercing it to ``None`` would refuse a
    valid invoice.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Already lossy by the time it reached here — JSON gave us a float —
        # but `repr` keeps every digit Python has, so nothing further is lost
        # and `Decimal` parses it exactly as printed.
        return repr(value)
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        float(cleaned)  # parseable, and then discarded — the text is the value
    except ValueError:
        return None
    return cleaned


def _strings(value: Any) -> List[str]:
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, Sequence):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


# ------------------------------------------------------------------- invoice


@dataclass
class InvoiceDraft:
    """Everything `create_invoice` needs, and nothing it can compute itself."""

    items: List[Dict[str, Any]]
    bill_to: List[str] = field(default_factory=list)
    currency: str = ""
    terms_days: Optional[int] = None
    notes: str = ""


_INVOICE_PROMPT = """Read the text below and extract the invoice details.

Return JSON of exactly this shape:
{{
  "bill_to": ["client name", "any address lines"],
  "currency": "the currency symbol or code, or null",
  "terms_days": 14,
  "items": [
    {{"description": "what the work was",
      "quantity": 3,
      "unit": "days",
      "unit_price": 400}}
  ]
}}

Rules:
- quantity and unit_price are plain numbers. No symbols, no commas.
- Do not compute totals. Do not add a subtotal line to items.
- Anything the text does not state is null. Never invent a client or a price.
- terms_days is a whole number of days, or null if payment terms are not given.

The request was:
{request}

The text:
{answer}
"""


def invoice_from(answer: str, request: str, ask: Ask) -> InvoiceDraft | Missing:
    """Line items and who they are for, read out of an answer.

    Returns `Missing` naming the gaps rather than an invoice with holes in it.
    The two fields that make an invoice an invoice are the line items and who
    it bills, so those are the two it insists on.
    """
    try:
        reply = ask(_INVOICE_PROMPT.format(request=request, answer=answer), _SYSTEM)
    except Exception as exc:
        logger.warning("invoice extraction failed: %s", exc)
        return Missing(["the details — I couldn't read them back from what we discussed"])

    parsed = _json_from(reply)
    if parsed is None:
        logger.info("invoice extraction produced no JSON: %r", (reply or "")[:200])
        return Missing()

    items: List[Dict[str, Any]] = []
    for raw in parsed.get("items") or []:
        if not isinstance(raw, dict):
            continue
        description = str(raw.get("description") or "").strip()
        quantity = _amount(raw.get("quantity"))
        unit_price = _amount(raw.get("unit_price"))
        # All three or none. A line with a description and no price is the
        # shape that becomes an invoice quietly missing a charge.
        if not description or quantity is None or unit_price is None:
            continue
        items.append(
            {
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "unit": str(raw.get("unit") or "").strip(),
            }
        )

    bill_to = _strings(parsed.get("bill_to"))
    gaps: List[str] = []
    if not items:
        gaps.append("the line items — what the work was, how much of it, and the rate")
    if not bill_to:
        gaps.append("who it is for")
    if gaps:
        return Missing(gaps)

    terms = parsed.get("terms_days")
    terms_days = int(terms) if isinstance(terms, (int, float)) and not isinstance(terms, bool) else None

    return InvoiceDraft(
        items=items,
        bill_to=bill_to,
        currency=str(parsed.get("currency") or "").strip(),
        terms_days=terms_days,
        notes=str(parsed.get("notes") or "").strip(),
    )


# --------------------------------------------------------------- spreadsheet


@dataclass
class TableDraft:
    header: List[str]
    rows: List[List[str]]


_TABLE_PROMPT = """Read the text below and extract its table.

Return JSON of exactly this shape:
{{"header": ["Column", "Column"], "rows": [["cell", "cell"]]}}

Rules:
- Every row has exactly as many cells as the header has columns.
- Use only values present in the text. Never invent a row.
- If the text holds no tabular data at all, return {{"header": [], "rows": []}}.

The request was:
{request}

The text:
{answer}
"""


def table_from(answer: str, request: str, ask: Ask) -> TableDraft | Missing:
    """A header and rows, or a refusal naming what is absent.

    Ragged rows are padded rather than rejected: a short row is a cell the
    model did not repeat, and `create_spreadsheet` needs a rectangle. A row
    *longer* than the header is truncated — extra cells have no column, and
    inventing a heading for them would be inventing a claim about the data.
    """
    try:
        reply = ask(_TABLE_PROMPT.format(request=request, answer=answer), _SYSTEM)
    except Exception as exc:
        logger.warning("table extraction failed: %s", exc)
        return Missing(["the figures — I couldn't read them back as a table"])

    parsed = _json_from(reply)
    if parsed is None:
        return Missing()

    header = _strings(parsed.get("header"))
    raw_rows = parsed.get("rows") or []
    rows: List[List[str]] = []
    for raw in raw_rows:
        if not isinstance(raw, Sequence) or isinstance(raw, str):
            continue
        cells = [str(c).strip() for c in raw]
        if not any(cells):
            continue
        cells = cells[: len(header)] + [""] * max(0, len(header) - len(cells))
        rows.append(cells)

    if not header or not rows:
        return Missing(["anything tabular — this answer is prose rather than rows"])
    return TableDraft(header=header, rows=rows)


# ---------------------------------------------------------------------- deck


@dataclass
class DeckDraft:
    slides: List[tuple[str, List[str]]]


_DECK_PROMPT = """Turn the text below into a slide outline.

Return JSON of exactly this shape:
{{"slides": [{{"heading": "Slide title", "bullets": ["point", "point"]}}]}}

Rules:
- Use only what the text says. Never add a slide about something absent.
- Bullets are short phrases, not paragraphs.
- Between 2 and 12 slides.

The request was:
{request}

The text:
{answer}
"""


def deck_from(answer: str, request: str, ask: Ask) -> DeckDraft | Missing:
    """An outline, one heading per slide.

    The loosest of the three, and legitimately so: a deck *is* a restatement of
    prose, so nothing here can be invented that was not already in the answer.
    An invoice is different in kind — its numbers are claims about money.
    """
    try:
        reply = ask(_DECK_PROMPT.format(request=request, answer=answer), _SYSTEM)
    except Exception as exc:
        logger.warning("deck extraction failed: %s", exc)
        return Missing(["enough structure to make slides from"])

    parsed = _json_from(reply)
    if parsed is None:
        return Missing()

    slides: List[tuple[str, List[str]]] = []
    for raw in parsed.get("slides") or []:
        if not isinstance(raw, dict):
            continue
        heading = str(raw.get("heading") or "").strip()
        bullets = _strings(raw.get("bullets"))
        if not heading:
            continue
        slides.append((heading, bullets))

    if not slides:
        return Missing(["enough structure to make slides from"])
    return DeckDraft(slides=slides)


@dataclass
class CvEntry:
    """One dated thing a person did.

    The same shape serves employment and education, because on the page they
    are the same object — a role, where it happened, when, and what came of it.
    Two dataclasses would be two renderers and two extraction prompts for one
    visual pattern.
    """

    role: str
    organisation: str = ""
    dates: str = ""
    bullets: List[str] = field(default_factory=list)


@dataclass
class CvDraft:
    """A CV, as fields rather than as paragraphs.

    ``name`` is the only required one. A CV with no name is not a CV with a
    hole in it, it is somebody else's — so `cv_from` refuses rather than
    heading the page with the title of the conversation.
    """

    name: str
    headline: str = ""
    contact: List[str] = field(default_factory=list)
    summary: str = ""
    experience: List[CvEntry] = field(default_factory=list)
    education: List[CvEntry] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)


_CV_PROMPT = """Read the text below into the fields of a CV.

Return JSON of exactly this shape:
{{"name": "Full name",
  "headline": "Their profession in a few words",
  "contact": ["city", "email", "phone"],
  "summary": "Two or three sentences",
  "experience": [{{"role": "Job title", "organisation": "Employer",
                  "dates": "2023 - present", "bullets": ["what they did"]}}],
  "education": [{{"role": "Qualification", "organisation": "Institution",
                 "dates": "2019"}}],
  "skills": ["skill", "skill"]}}

Rules:
- Use only what the text says. Never invent an employer, a date or a
  qualification. A CV is read by someone deciding whether to believe it.
- Leave a field out entirely rather than filling it with a guess.
- Dates exactly as the text gives them. Do not normalise or complete them.
- Most recent first.

The request was:
{request}

The text:
{answer}
"""


def _entries(value: Any) -> List[CvEntry]:
    """Entries from whatever the model returned, skipping anything unusable.

    An entry with no role is dropped rather than rendered as a dated blank —
    on a CV that reads as a gap the person is hiding, which is a worse failure
    than the entry being absent.
    """
    entries: List[CvEntry] = []
    for raw in value or []:
        if not isinstance(raw, dict):
            continue
        role = str(raw.get("role") or "").strip()
        if not role:
            continue
        entries.append(
            CvEntry(
                role=role,
                organisation=str(raw.get("organisation") or "").strip(),
                dates=str(raw.get("dates") or "").strip(),
                bullets=_strings(raw.get("bullets")),
            )
        )
    return entries


def cv_from(answer: str, request: str, ask: Ask) -> CvDraft | Missing:
    """A CV read into fields, or a refusal naming what was not there.

    **Rule 9 applies here about as hard as it does to an invoice.** A CV is a
    set of claims about a person that they will send to someone deciding
    whether to employ them, and a plausible invented employer is worse than a
    missing one — it is the kind of error that ends an application when it is
    caught, and the kind that follows someone when it is not.

    So there is no prose fallback and no completion of a partial date. What was
    not in the text does not appear in the file.
    """
    try:
        reply = ask(_CV_PROMPT.format(request=request, answer=answer), _SYSTEM)
    except Exception as exc:
        logger.warning("cv extraction failed: %s", exc)
        return Missing(["the details of the CV"])

    parsed = _json_from(reply)
    if parsed is None:
        return Missing()

    name = str(parsed.get("name") or "").strip()
    if not name:
        # The one field with no honest default. Heading a CV with the
        # conversation's title would put a stranger's name on somebody's
        # career, which is the worst available outcome for this document.
        return Missing(["whose CV this is"])

    draft = CvDraft(
        name=name,
        headline=str(parsed.get("headline") or "").strip(),
        contact=_strings(parsed.get("contact")),
        summary=str(parsed.get("summary") or "").strip(),
        experience=_entries(parsed.get("experience")),
        education=_entries(parsed.get("education")),
        skills=_strings(parsed.get("skills")),
    )

    if not (draft.experience or draft.education or draft.summary):
        return Missing(["anything to put on the CV"])
    return draft
