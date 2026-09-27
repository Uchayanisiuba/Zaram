"""A job posting, read into fields.

The first piece of the job-hunt pack, and the pack's *parser* — the part
`CLAUDE.md` names first when it says a pack is "parsers, tools, output
templates, and routing exemplars". Everything else the hunt does stands on
this: a deadline cannot become an obligation, and a cover letter cannot name
the stack, until somebody has turned a wall of prose into fields.

Deterministic, not a model call
-------------------------------
A posting could be handed to the local 14B with "extract the fields as JSON".
That was rejected for three reasons and the third is the one that decides it.
It is **slow** — seconds per posting against milliseconds, and a weekly run
reads dozens. It **costs the card**, which is the scarce thing on this machine
and is wanted by the thing that actually needs a model. And it is
**non-deterministic**: the same posting parsed twice gives two answers, so a
wrong field cannot be reproduced, and a fix cannot be proven. A regex that is
wrong is wrong the same way every time, which is what makes it fixable.

The model still has work here — reading the posting, judging the fit, writing
the letter. It should not be doing the clerical part.

Unknown, never a guess
----------------------
Every field is `None` until something in the text supports it. This is the
posture `vram_bytes` already takes, for the same reason: a caller can check
for `None`, and cannot check a confident wrong answer. Rule 9 says generation
must fail rather than invent, and a salary invented from a "competitive
package" line would be laundered into a cover letter three steps later.

The ambiguous-date decision, stated
-----------------------------------
`03/04/2026` is 3 April to most of the world and 4 March in the United States,
and a posting rarely says which it means. The rule here is **day-first**,
because the maintainer's market is day-first, and it is recorded rather than
implied — a closing date wrong by a month is a missed application, which is
exactly the failure the obligations layer exists to prevent. A date whose day
is above 12 is unambiguous either way and is read as written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Sequence, Tuple

__all__ = ["Posting", "Salary", "Workplace", "parse_posting"]


class Workplace:
    """Where the work happens. Strings rather than an enum member, because
    these travel into a fact sentence and into a document."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "on-site"


@dataclass(frozen=True)
class Salary:
    """What the posting says it pays.

    ``raw`` is kept verbatim. The numbers are a convenience; the sentence is
    the evidence, and it is what a person reads when the parse looks wrong.

    ``Decimal``, never float — the same rule the invoice module holds to. A
    day rate of 0.1 is not a rounding curiosity when it reaches a document.
    """

    raw: str
    currency: str = ""
    low: Optional[Decimal] = None
    high: Optional[Decimal] = None
    #: "year", "day", "hour", "month" — or "" when the posting does not say.
    period: str = ""


@dataclass(frozen=True)
class Posting:
    """One job, as fields. Every optional field is `None` when unsupported."""

    title: str = ""
    company: str = ""
    location: str = ""
    workplace: Optional[str] = None
    salary: Optional[Salary] = None
    closes: Optional[date] = None
    posted: Optional[date] = None
    apply_url: str = ""
    source_url: str = ""
    skills: Sequence[str] = ()
    seniority: str = ""
    #: The text the parse was made from, trimmed. Kept because provenance is
    #: rule 2 and a field with no excerpt behind it cannot be checked.
    excerpt: str = ""

    def facts(self) -> List[str]:
        """The posting as sentences, for the Spine.

        One fact per claim rather than one fact per posting, because rule 4
        says the user can correct or delete any stored fact — and a single
        blob means correcting the salary deletes the deadline.
        """
        out: List[str] = []
        who = self.company or "an unnamed company"
        if self.title:
            out.append(f"{who} is hiring a {self.title}.")
        if self.workplace:
            where = f"{self.workplace}"
            if self.location:
                where += f", based in {self.location}"
            out.append(f"The {self.title or 'role'} at {who} is {where}.")
        elif self.location:
            out.append(f"The {self.title or 'role'} at {who} is in {self.location}.")
        if self.salary:
            out.append(f"{who} states the pay as {self.salary.raw}.")
        if self.closes:
            out.append(
                f"Applications for the {self.title or 'role'} at {who} close on "
                f"{self.closes.isoformat()}."
            )
        if self.skills:
            out.append(f"The {self.title or 'role'} at {who} asks for {', '.join(self.skills)}.")
        return out


# --- the vocabulary ---------------------------------------------------------

#: Skills worth naming, lowercase, matched on word boundaries.
#:
#: Deliberately **not** every technology in the world. A pack is domain
#: knowledge, and this list is aimed at the work the maintainer does — a
#: general scraper would match "art" in "smart" and report it as a skill.
#: Aliases map onto one canonical name so "UE5" and "Unreal Engine" do not
#: become two different facts about the same requirement.
_SKILLS: Sequence[Tuple[str, str]] = (
    (r"unreal(?:\s+engine)?(?:\s*5)?|\bue5\b|\bue4\b", "Unreal Engine"),
    (r"\bblender\b", "Blender"),
    (r"\bmaya\b", "Maya"),
    (r"\bhoudini\b", "Houdini"),
    (r"\bnuke\b", "Nuke"),
    (r"substance(?:\s+(?:painter|designer))?", "Substance"),
    (r"\bzbrush\b", "ZBrush"),
    (r"\bmarvelous\s+designer\b", "Marvelous Designer"),
    (r"\bmotionbuilder\b", "MotionBuilder"),
    (r"\bunity\b", "Unity"),
    (r"\busd\b|universal\s+scene\s+description", "USD"),
    (r"\bpython\b", "Python"),
    (r"\bc\+\+\b", "C++"),
    (r"\bc#\b|\bcsharp\b", "C#"),
    (r"\bhlsl\b|\bglsl\b|shader\s+(?:writing|authoring)", "shaders"),
    (r"\brigging\b|\brigger\b", "rigging"),
    (r"\banimation\b|\banimator\b", "animation"),
    (r"look\s?dev|lookdev", "lookdev"),
    (r"\bcompositing\b", "compositing"),
    (r"\bpipeline\b", "pipeline"),
    (r"\bperforce\b|\bp4v\b", "Perforce"),
    (r"\bgit\b", "Git"),
)

_SENIORITY: Sequence[Tuple[str, str]] = (
    (r"\bprincipal\b", "Principal"),
    (r"\blead\b|\bhead\s+of\b", "Lead"),
    (r"\bsenior\b|\bsnr\b|\bsr\.?\b", "Senior"),
    (r"\bmid[-\s]?(?:level|weight)\b", "Mid"),
    (r"\bjunior\b|\bjnr\b|\bgraduate\b|\bentry[-\s]level\b", "Junior"),
)

#: Ordered: the first match wins, so "hybrid" is read before the bare "remote"
#: that a hybrid posting also contains. Getting this backwards reports every
#: hybrid role as remote, which is the single most consequential field for
#: somebody applying from another country.
_WORKPLACE: Sequence[Tuple[str, str]] = (
    (r"\bhybrid\b", Workplace.HYBRID),
    (r"\bfully\s+remote\b|\bremote[-\s]first\b|\b100%\s+remote\b", Workplace.REMOTE),
    (r"\bon[-\s]?site\b|\bin[-\s]?office\b|\bon\s+location\b", Workplace.ONSITE),
    (r"\bremote\b|\bwork\s+from\s+home\b|\bwfh\b", Workplace.REMOTE),
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_CURRENCIES = {"£": "GBP", "$": "USD", "€": "EUR", "₦": "NGN"}

#: The same currencies written as codes. Postings outside the symbol-using
#: world write "400 GBP per day" or "NGN 2,500,000" at least as often as they
#: write the symbol, and a parser that only knows symbols reports no salary for
#: exactly the market the maintainer is in.
_CURRENCY_CODES = ("GBP", "USD", "EUR", "NGN")

_PERIODS: Sequence[Tuple[str, str]] = (
    (r"per\s+annum|/\s*(?:yr|year)|\bp\.?a\.?\b|\bannually\b|\bper\s+year\b", "year"),
    (r"per\s+day|/\s*day|\bday\s+rate\b|\bdaily\b", "day"),
    (r"per\s+hour|/\s*(?:hr|hour)|\bhourly\b", "hour"),
    (r"per\s+month|/\s*(?:mo|month)|\bmonthly\b", "month"),
)


# --- the parse ---------------------------------------------------------------


def _clean(text: str) -> str:
    """Collapse whitespace without losing line structure.

    Lines matter: a posting's first line is usually its title, and the label
    patterns below are anchored to a line rather than to a paragraph.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines)


def _labelled(text: str, *labels: str) -> str:
    """The value after a `Label:` on its own line, or empty."""
    for label in labels:
        match = re.search(
            rf"^\s*{label}\s*[:\-—]\s*(.+)$", text, re.IGNORECASE | re.MULTILINE
        )
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return ""


def _first(text: str, table: Sequence[Tuple[str, str]]) -> str:
    for pattern, name in table:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    return ""


def _skills(text: str) -> List[str]:
    found: List[str] = []
    for pattern, name in _SKILLS:
        if name not in found and re.search(pattern, text, re.IGNORECASE):
            found.append(name)
    return found


def _amount(raw: str) -> Optional[Decimal]:
    """`75,000`, `75k`, `£75K` → Decimal. None when it is not a number."""
    cleaned = raw.replace(",", "").replace(" ", "").strip()
    multiplier = Decimal(1)
    if cleaned[-1:].lower() == "k":
        cleaned, multiplier = cleaned[:-1], Decimal(1000)
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned) * multiplier
    except InvalidOperation:
        return None


def _salary(text: str) -> Optional[Salary]:
    """The pay, when the posting states a number.

    "Competitive salary" and "DOE" return None on purpose. They are not a
    number, and turning them into one is the invention rule 9 forbids.
    """
    # `(?:/\w+)?` after each number is the reason this is not the obvious
    # regex: LinkedIn writes "$90,000/yr - $120,000/yr", and a pattern that
    # expects the separator immediately after the first number reads the low
    # end and reports no upper bound — a salary range silently halved.
    amount = r"\d[\d,]*(?:\.\d+)?k?"
    symbols = r"[£$€₦]"
    codes = "|".join(_CURRENCY_CODES)
    pattern = (
        rf"(?:(?P<sym>{symbols})|(?P<code_before>{codes})\s)\s?(?P<low>{amount})"
        rf"(?:\s*(?P<code_after>{codes}))?(?:\s*/\s*\w+)?"
        rf"(?:\s*(?:-|–|—|to)\s*(?:{symbols})?\s?(?P<high>{amount}))?"
    )
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        # The number-first form: "400 GBP per day".
        match = re.search(
            rf"(?P<low>{amount})\s*(?P<code_after>{codes})\b"
            rf"(?:\s*(?:-|–|—|to)\s*(?P<high>{amount}))?",
            text,
            re.IGNORECASE,
        )
    if not match:
        return None

    groups = match.groupdict()
    symbol = groups.get("sym") or ""
    code = (groups.get("code_before") or groups.get("code_after") or "").upper()
    low_raw, high_raw = groups.get("low"), groups.get("high")
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    raw = text[line_start : line_end if line_end != -1 else len(text)].strip()

    low = _amount(low_raw)
    high = _amount(high_raw) if high_raw else None
    # A range written "£60k - £75k" and one written "£60,000 to £75,000" are
    # the same fact; a lone "£75k" has no upper bound rather than an equal one.
    return Salary(
        raw=raw,
        currency=_CURRENCIES.get(symbol, "") or code,
        low=low,
        high=high,
        period=_first(raw, _PERIODS) or _first(text, _PERIODS),
    )


def _date(text: str, today: Optional[date] = None) -> Optional[date]:
    """One date out of a phrase, or None.

    Three shapes, in the order they are trusted: a named month is
    unambiguous, an ISO date is unambiguous, and a slashed date is read
    **day-first** for the reason in the module docstring.
    """
    today = today or date.today()

    named = re.search(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?"
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
        r"(?:\s+(\d{4}))?",
        text,
        re.IGNORECASE,
    )
    if named:
        day, month, year = named.groups()
        return _make(int(year) if year else None, _MONTHS[month.lower()[:3]], int(day), today)

    named_first = re.search(
        r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+"
        r"(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?",
        text,
        re.IGNORECASE,
    )
    if named_first:
        month, day, year = named_first.groups()
        return _make(int(year) if year else None, _MONTHS[month.lower()[:3]], int(day), today)

    iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", text)
    if iso:
        year, month, day = (int(g) for g in iso.groups())
        return _make(year, month, day, today)

    slashed = re.search(r"\b(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\b", text)
    if slashed:
        first, second, year_raw = slashed.groups()
        day, month = int(first), int(second)
        if month > 12 and day <= 12:
            # Written month-first. Unambiguous, because 15 cannot be a month.
            day, month = month, day
        year = int(year_raw) if year_raw else None
        if year is not None and year < 100:
            year += 2000
        return _make(year, month, day, today)

    return None


def _make(year: Optional[int], month: int, day: int, today: date) -> Optional[date]:
    """Build the date, filling a missing year with the next occurrence.

    A posting that says "closes 15 October" in November means next October,
    not one three weeks gone. Guessing the current year would produce a
    deadline already past, which the obligations layer would then quietly
    drop.
    """
    try:
        if year is not None:
            return date(year, month, day)
        candidate = date(today.year, month, day)
        return candidate if candidate >= today else date(today.year + 1, month, day)
    except ValueError:
        return None


def _title(text: str) -> str:
    """The role. A `Role:`/`Job title:` label first, then the first line.

    The first line is the convention on every board worth reading, and when
    it is not the title it is usually the company — which the caller can see
    and correct, unlike a title silently taken from the middle of the body.
    """
    labelled = _labelled(text, "role", "job title", "title", "position", "vacancy")
    if labelled:
        return _trim_title(labelled)
    for line in text.split("\n"):
        if line.strip():
            return _trim_title(line.strip())
    return ""


#: Where a role stops and the advertisement starts. A posting that opens
#: "Freelance 3D Animator needed for a six-week project starting in November."
#: has its title in the first four words and a sentence after it, and storing
#: the sentence as the title puts it in the subject line of a cover letter.
_TITLE_ENDS = re.compile(
    r"\s+(?:needed|wanted|required|sought)\b|\s+[-–—|]\s+|\s+(?:to\s+join|for\s+a)\b",
    re.IGNORECASE,
)


def _trim_title(line: str) -> str:
    cut = _TITLE_ENDS.search(line)
    if cut:
        line = line[: cut.start()]
    return line.strip(" .,:;-–—").strip()[:120]


def _url(text: str, *, prefer: str = "") -> str:
    urls = re.findall(r"https?://[^\s<>\"')]+", text)
    if prefer:
        for url in urls:
            if prefer in url.lower():
                return url
    return urls[0] if urls else ""


def parse_posting(text: str, *, source_url: str = "", today: Optional[date] = None) -> Posting:
    """Read a posting into fields. Never raises on bad input."""
    if not text or not text.strip():
        return Posting(source_url=source_url)

    cleaned = _clean(text)

    closes_line = _labelled(
        cleaned, "closing date", "closes", "applications close", "deadline", "apply by"
    )
    posted_line = _labelled(cleaned, "posted", "date posted", "published")

    return Posting(
        title=_title(cleaned),
        company=_labelled(cleaned, "company", "employer", "studio", "organisation", "organization"),
        location=_labelled(cleaned, "location", "based in", "where"),
        workplace=_first(cleaned, _WORKPLACE) or None,
        salary=_salary(cleaned),
        closes=_date(closes_line, today) if closes_line else None,
        posted=_date(posted_line, today) if posted_line else None,
        apply_url=_url(cleaned, prefer="apply") or source_url,
        source_url=source_url,
        skills=tuple(_skills(cleaned)),
        seniority=_first(cleaned, _SENIORITY),
        excerpt=cleaned[:600],
    )
