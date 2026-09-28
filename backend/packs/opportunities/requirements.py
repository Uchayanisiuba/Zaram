"""Reading eligibility criteria out of a call, without a model.

**It finds few and invents none.** That asymmetry is the whole design. A
requirement this misses becomes an opportunity shown to somebody who cannot
win it, which costs them a read. A requirement this *invents* becomes an
opportunity hidden from somebody who could have won it — and they never find
out, because a thing that was filtered out leaves no trace in front of the
user. The second failure is silent, so the parser is biased hard against it.

**Every requirement carries the sentence it was read from.** `Requirement.source`
has no default for the same reason `obligations.Obligation.source` has none:
the clause is what makes the gate's refusal arguable, and rule 4 needs
something to argue with. A verdict nobody can contest is a verdict people
route around.

**Why deterministic rather than a model.** Three reasons, in order:

1. A refusal the user disputes has to reproduce. A model-read criterion that
   comes out differently on the second pass cannot be corrected, only
   re-rolled.
2. A call's text is **untrusted third-party text**, written by a stranger, and
   `CLAUDE.md` is explicit that nothing retrieved may widen what is permitted.
   Handing it to a model that then decides who is eligible puts a stranger's
   prose in the permission path.
3. It costs nothing and needs no VRAM, so it runs on the poller's schedule on
   any machine.

A model-assisted pass is a reasonable later addition — the phrasings here are
a fraction of what funders write. It would have to obey the same contract:
produce a clause or produce nothing, and never be the thing that excludes.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence, Tuple

from .contracts import Criterion, Requirement

__all__ = ["read_requirements", "SENTENCE_SPLIT"]


#: Sentence-ish. Calls are written in prose, bullets and tables, so this splits
#: on terminators *and* on newlines — a bullet list has no full stops in it and
#: treating the whole list as one sentence would quote a paragraph as the
#: clause behind a single criterion.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

#: A sentence is only considered when it is *about* eligibility. Without this
#: the country vocabulary matches "our offices are in Germany" and the parser
#: invents a residency requirement out of a sentence describing the funder.
#: This is the main guard against the silent failure.
_ELIGIBILITY_MARKERS = (
    "eligib",
    "eligibility",
    "open to",
    "open only to",
    "restricted to",
    "limited to",
    "applicants must",
    "applicant must",
    "you must",
    "must be",
    "must have",
    "must hold",
    "requires",
    "required to",
    "not open to",
    "excluded",
    "ineligible",
    "who can apply",
    "who may apply",
)

#: Phrases that flip a requirement from "must match" to "must not match".
_EXCLUSION_MARKERS = (
    "not open to",
    "not eligible",
    "ineligible",
    "excluded",
    "excluding",
    "may not apply",
    "cannot apply",
)

#: What each criterion's values look like in a call's prose.
#:
#: Values are what gets written into `Requirement.values` and later compared,
#: case-folded and exact, against the profile. The vocabulary is deliberately
#: small: a term here that is ambiguous in ordinary prose produces invented
#: requirements, which is the failure this module is built to avoid.
_VOCABULARY: Dict[Criterion, Tuple[Tuple[str, str], ...]] = {
    # (phrase as written in calls, the value it means)
    Criterion.ORG_TYPE: (
        ("registered non-profit", "non-profit"),
        ("registered nonprofit", "non-profit"),
        ("non-profit", "non-profit"),
        ("nonprofit", "non-profit"),
        ("not-for-profit", "non-profit"),
        ("charity", "non-profit"),
        ("charitable organisation", "non-profit"),
        ("sole trader", "sole-trader"),
        ("sole proprietor", "sole-trader"),
        ("self-employed", "sole-trader"),
        ("limited company", "company"),
        ("registered company", "company"),
        ("incorporated", "company"),
        ("small and medium-sized enterprise", "sme"),
        ("sme", "sme"),
        ("individual applicant", "individual"),
        ("individuals", "individual"),
    ),
    Criterion.CAREER_STAGE: (
        ("early career", "early-career"),
        ("early-career", "early-career"),
        ("postdoctoral", "postdoctoral"),
        ("post-doctoral", "postdoctoral"),
        ("phd student", "student"),
        ("doctoral student", "student"),
        ("undergraduate", "student"),
        ("graduate student", "student"),
        ("student", "student"),
        ("mid-career", "mid-career"),
        ("senior researcher", "senior"),
        ("established researcher", "senior"),
    ),
    Criterion.INSTITUTIONAL_HOST: (
        ("host institution", "yes"),
        ("hosting institution", "yes"),
        ("institutional host", "yes"),
        ("must be affiliated with a university", "yes"),
        ("university affiliation", "yes"),
        ("affiliated with a recognised institution", "yes"),
        ("no institutional affiliation is required", "no"),
        ("no affiliation required", "no"),
    ),
    Criterion.WORK_AUTHORISATION: (
        ("right to work", "required"),
        ("must be authorised to work", "required"),
        ("must be authorized to work", "required"),
        ("visa sponsorship is not available", "required"),
        ("we cannot sponsor", "required"),
        ("no sponsorship", "required"),
    ),
}

#: Countries and blocs, kept apart from `_VOCABULARY` because they are matched
#: on word boundaries rather than as substrings — "us" inside "thus" and
#: "focus" is the obvious trap, and it is exactly the class of bug `CLAUDE.md`
#: records from `TASK_MARKERS` matching "code" but not "coding".
_PLACES: Tuple[Tuple[str, str], ...] = (
    (r"united states", "united states"),
    (r"\bu\.?s\.?a?\b", "united states"),
    (r"united kingdom", "united kingdom"),
    (r"\bu\.?k\.?\b", "united kingdom"),
    (r"european union", "european union"),
    (r"\be\.?u\.?\b", "european union"),
    (r"nigeria", "nigeria"),
    (r"ghana", "ghana"),
    (r"kenya", "kenya"),
    (r"south africa", "south africa"),
    (r"canada", "canada"),
    (r"australia", "australia"),
    (r"germany", "germany"),
    (r"france", "france"),
    (r"india", "india"),
)


def _is_about_eligibility(sentence: str) -> bool:
    lowered = sentence.casefold()
    return any(marker in lowered for marker in _ELIGIBILITY_MARKERS)


def _is_exclusion(sentence: str) -> bool:
    lowered = sentence.casefold()
    return any(marker in lowered for marker in _EXCLUSION_MARKERS)


def _clause(sentence: str, limit: int = 300) -> str:
    """The sentence as it will be shown, collapsed and bounded.

    Bounded because the clause is rendered in a card beside the verdict and an
    unbounded one is a wall of text where a reason should be. Collapsed because
    a clause pulled out of a PDF carries the original line breaks, and those
    are the parser's business rather than the reader's.
    """
    collapsed = " ".join(sentence.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def _values_in(sentence: str, vocabulary: Sequence[Tuple[str, str]]) -> Tuple[str, ...]:
    lowered = sentence.casefold()
    found: List[str] = []
    for phrase, value in vocabulary:
        if phrase in lowered and value not in found:
            found.append(value)
    return tuple(found)


def _places_in(sentence: str) -> Tuple[str, ...]:
    lowered = sentence.casefold()
    found: List[str] = []
    for pattern, value in _PLACES:
        if re.search(pattern, lowered) and value not in found:
            found.append(value)
    return tuple(found)


def read_requirements(text: str) -> Tuple[Requirement, ...]:
    """Every criterion the text states plainly, each with its sentence.

    Only sentences that are *about* eligibility are considered, which is what
    stops "our offices are in Germany" becoming a residency requirement. A call
    that states a criterion somewhere this parser does not recognise yields
    nothing for it, and the gate reports `UNKNOWN` rather than a green tick —
    which is the correct answer to "we did not read one".

    Duplicates across sentences are merged onto the first clause that produced
    them, so a call that repeats its residency rule in three places gives one
    requirement rather than three identical cards.
    """
    if not text or not text.strip():
        return ()

    by_criterion: Dict[Tuple[Criterion, bool], Requirement] = {}

    for sentence in SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if not sentence or not _is_about_eligibility(sentence):
            continue

        excludes = _is_exclusion(sentence)
        clause = _clause(sentence)

        candidates: List[Tuple[Criterion, Tuple[str, ...]]] = [
            (criterion, _values_in(sentence, vocabulary))
            for criterion, vocabulary in _VOCABULARY.items()
        ]
        candidates.append((Criterion.COUNTRY, _places_in(sentence)))

        for criterion, values in candidates:
            if not values:
                continue
            key = (criterion, excludes)
            if key in by_criterion:
                merged = tuple(
                    dict.fromkeys(by_criterion[key].values + values)
                )
                by_criterion[key] = Requirement(
                    criterion=criterion,
                    values=merged,
                    source=by_criterion[key].source,
                    excludes=excludes,
                )
                continue
            by_criterion[key] = Requirement(
                criterion=criterion,
                values=values,
                source=clause,
                excludes=excludes,
            )

    return tuple(by_criterion.values())
