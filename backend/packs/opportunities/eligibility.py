"""The eligibility gate. No model, no score, no network.

**Why this is the most valuable thing in the pack.** For grants the bottleneck
is not writing and not discovery — it is that most people do not know what they
can apply for, and finding out the hard way costs a fortnight per mistake. A
gate that says *"not this one, and here is the sentence that says so"* is worth
more than any drafting feature, and it is the half that needs no model at all.

**Three properties, each of which is load-bearing.**

*It filters, it does not rank.* `CLAUDE.md` records a score built for ranking
being used to decide costing this codebase three separate bugs — a citation
floor compared against a ranking blend, a shortlist selected on that blend
discarding the best document at rank 43, and an eval that graded itself. This
is the fourth domain that error could arrive in, so the gate returns a
`Verdict` and never a number. There is nothing here that *could* be compared
against a threshold.

*It is deterministic.* Same opportunity, same profile, same answer, every time,
with no model in the path. A refusal a user disputes has to be reproducible, or
the correction loop has nothing to bite on.

*Unknown is not no.* A criterion with no fact behind it becomes a question.
The temptation is to treat missing as failing so the list stays short; that
silently hides opportunities on the basis of a fact nobody was ever asked for,
and the user never learns it happened.

**What this module does not do.** It does not decide whether an opportunity is
a *good* match — that is relevance, it is a separate question, and it is
allowed to use a blend because ordering is a presentation choice. Membership in
the shortlist is decided here, on eligibility alone.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Set, Tuple

from .contracts import (
    Criterion,
    EligibilityReport,
    Finding,
    Opportunity,
    Profile,
    Requirement,
    Verdict,
)

__all__ = ["assess", "missing_criteria", "eligible_only"]


def _fold(value: str) -> str:
    """Case-folded and trimmed. The only normalisation performed.

    No stemming, no synonyms, no fuzzy distance. "Close enough" on an
    eligibility filter is how somebody is told they qualify for something they
    do not, and the cost of that mistake is a fortnight of their work.
    """
    return (value or "").strip().casefold()


def _folded_set(values: Iterable[str]) -> Set[str]:
    return {_fold(v) for v in values if _fold(v)}


def _held(profile: Profile, criterion: Criterion) -> Set[str]:
    """What the applicant holds for this criterion, folded.

    Returns a set because two of the criteria are genuinely plural — somebody
    may work in three sectors and hold the right to work in two countries —
    and collapsing those to one value would exclude people who qualify twice.
    """
    if criterion is Criterion.COUNTRY:
        return _folded_set([profile.country or ""])
    if criterion is Criterion.ORG_TYPE:
        return _folded_set([profile.org_type or ""])
    if criterion is Criterion.CAREER_STAGE:
        return _folded_set([profile.career_stage or ""])
    if criterion is Criterion.INSTITUTIONAL_HOST:
        if profile.has_institutional_host is None:
            return set()
        return {"yes"} if profile.has_institutional_host else {"no"}
    if criterion is Criterion.SECTOR:
        return _folded_set(profile.sectors)
    if criterion is Criterion.WORK_AUTHORISATION:
        return _folded_set(profile.work_authorisation)
    return set()


#: How a criterion is named to a person. The gate's output is a sentence, and
#: a sentence needs words rather than enum members.
_CRITERION_WORDS = {
    Criterion.COUNTRY: "where you are based",
    Criterion.ORG_TYPE: "what kind of organisation you are",
    Criterion.CAREER_STAGE: "your career stage",
    Criterion.INSTITUTIONAL_HOST: "whether an institution hosts the award",
    Criterion.SECTOR: "your sector",
    Criterion.WORK_AUTHORISATION: "your right to work there",
}


def _requires_host(requirement: Requirement) -> bool:
    return Criterion.INSTITUTIONAL_HOST is requirement.criterion


def _check(requirement: Requirement, profile: Profile) -> Finding:
    """One requirement against the profile.

    The three-way answer in one place, so the precedence cannot drift between
    callers: no fact is `UNKNOWN`; an exclusion the applicant matches is
    `INELIGIBLE`; a positive requirement the applicant does not match is
    `INELIGIBLE`; otherwise `ELIGIBLE`.
    """
    criterion = requirement.criterion
    words = _CRITERION_WORDS.get(criterion, criterion.value)

    if not profile.known(criterion):
        return Finding(
            criterion=criterion,
            verdict=Verdict.UNKNOWN,
            reason=f"This one depends on {words}, and Zaram does not know that yet.",
            source=requirement.source,
        )

    held = _held(profile, criterion)
    wanted = _folded_set(requirement.values)
    overlap = held & wanted

    if requirement.excludes:
        if overlap:
            shown = ", ".join(sorted(overlap))
            return Finding(
                criterion=criterion,
                verdict=Verdict.INELIGIBLE,
                reason=f"Not open where {words} is {shown}.",
                source=requirement.source,
            )
        return Finding(
            criterion=criterion,
            verdict=Verdict.ELIGIBLE,
            reason=f"The exclusion on {words} does not apply to you.",
            source=requirement.source,
        )

    if overlap:
        return Finding(
            criterion=criterion,
            verdict=Verdict.ELIGIBLE,
            reason=f"Matches on {words}.",
            source=requirement.source,
        )

    held_shown = ", ".join(sorted(held)) or "nothing recorded"
    wanted_shown = ", ".join(sorted(wanted))
    return Finding(
        criterion=criterion,
        verdict=Verdict.INELIGIBLE,
        reason=f"Needs {words} to be {wanted_shown}; yours is {held_shown}.",
        source=requirement.source,
    )


def assess(opportunity: Opportunity, profile: Profile) -> EligibilityReport:
    """Check every stated requirement and report what was found.

    **Failure dominates uncertainty.** One definite exclusion settles the
    question however many criteria remain unanswered, so a single `INELIGIBLE`
    finding makes the whole report `INELIGIBLE` — there is no point asking
    somebody four questions to establish something already ruled out.

    **An opportunity with no parsed requirements is not declared eligible on
    that basis.** It reports `UNKNOWN` with nothing checked, because "no
    requirement was read" and "there is no requirement" are different claims
    and only the first one is true. Reporting the second would be rendering an
    invented value — the interface rule that says a field which can only say
    one thing today says one thing today.
    """
    findings: List[Finding] = [_check(r, profile) for r in opportunity.requirements]

    if not findings:
        return EligibilityReport(verdict=Verdict.UNKNOWN, findings=(), missing=())

    missing = tuple(
        dict.fromkeys(f.criterion for f in findings if f.verdict is Verdict.UNKNOWN)
    )

    if any(f.verdict is Verdict.INELIGIBLE for f in findings):
        verdict = Verdict.INELIGIBLE
    elif missing:
        verdict = Verdict.UNKNOWN
    else:
        verdict = Verdict.ELIGIBLE

    return EligibilityReport(verdict=verdict, findings=tuple(findings), missing=missing)


def missing_criteria(
    opportunities: Sequence[Opportunity], profile: Profile
) -> Tuple[Criterion, ...]:
    """Every criterion the current batch needs and the profile cannot answer.

    Gathered across the whole batch rather than per opportunity so the user is
    asked *once* — "which country are you based in?" — instead of once per
    call. Rule 7e's posture applied to a question the system genuinely cannot
    answer from behaviour: it is still the user who has to say, but they say it
    one time.

    Ordered by first appearance rather than sorted, so the question the most
    opportunities are waiting on tends to come first.
    """
    seen: List[Criterion] = []
    for opportunity in opportunities:
        for requirement in opportunity.requirements:
            criterion = requirement.criterion
            if not profile.known(criterion) and criterion not in seen:
                seen.append(criterion)
    return tuple(seen)


def eligible_only(
    opportunities: Sequence[Opportunity],
    profile: Profile,
    *,
    include_unknown: bool = True,
) -> List[Tuple[Opportunity, EligibilityReport]]:
    """The shortlist, decided on eligibility alone.

    **This is membership, and membership is never decided by a blend.** What
    order these are shown in is a different question and may use whatever is
    useful — deadline proximity, award size, how well the call matches the
    user's work. That ordering happens after this, to the survivors.

    `include_unknown` defaults to True and should stay that way in the product.
    Dropping the unknowns makes a tidier list by hiding opportunities on facts
    nobody was asked for — and the user never finds out. Setting it False is
    for a caller that has already asked the questions.
    """
    kept: List[Tuple[Opportunity, EligibilityReport]] = []
    for opportunity in opportunities:
        report = assess(opportunity, profile)
        if report.verdict is Verdict.INELIGIBLE:
            continue
        if report.verdict is Verdict.UNKNOWN and not include_unknown:
            continue
        kept.append((opportunity, report))
    return kept
