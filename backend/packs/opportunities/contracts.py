"""What an opportunity is, and what it means to be eligible for one.

Jobs and grants are one pipeline with the weights moved — `docs/PACK-OPPORTUNITIES.md`
has the table. So there is one `Opportunity`, with a `kind` that says which,
rather than two near-identical records that drift apart in a month.

**The two rules this module exists to hold:**

*Eligibility is a gate, never a ranking.* `CLAUDE.md` says it for model
capability — *"a binary precondition, never a score"* — and the shape is
identical here. A grant that needs a university affiliation the user does not
have is not a worse match, it is not a match. Blend it into a relevance score
and somebody spends a fortnight on a call they were never able to win. That is
the error this codebase has already paid for three times, arriving in a fourth
domain, and it is written down before the matcher rather than after it.

*Unknown is a third answer and is not "no".* A criterion nobody has a fact for
comes back as a question. This is the same shape `obligations.Unresolved`
takes, for the same reason: dropping it silently loses a real opportunity,
guessing at it invents a refusal, and returning it is the only option that does
neither. Defaulting to "not eligible" is how a product quietly stops showing
somebody the thing they needed and never says that it did.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, Optional, Tuple


class OpportunityKind(str, Enum):
    """Which half of the pack this is.

    Two values, and they earn the distinction by changing what Zaram *does*:
    a grant is gated on eligibility before anything else is worth doing, a job
    is gated on nothing and lives or dies on the draft. The pipeline is shared;
    the weights are not.
    """

    JOB = "job"
    GRANT = "grant"


class FeedKind(str, Enum):
    """How an opportunity arrives.

    The poller takes *feeds*, never a list of websites. A hardcoded site list
    makes adding a funder a release, and silently makes the product useless
    outside whichever countries somebody remembered — which for grants, where
    funding is intensely geographic, is most of the world.
    """

    #: A documented REST endpoint — Grants.gov, EU Funding & Tenders.
    JSON = "json"
    #: Any board's RSS.
    RSS = "rss"
    #: One company's Greenhouse / Lever / Ashby board.
    ATS = "ats"
    #: A label in the user's own inbox where alert mail lands. The answer to
    #: "why can't it search LinkedIn": LinkedIn will happily send the user
    #: alerts, and reading the user's own mail breaks nobody's terms, trips no
    #: bot detection and cannot get their account restricted.
    MAIL = "mail"


class Criterion(str, Enum):
    """The things a call can require that are answerable from stored facts.

    Deliberately short, and each value earns its place the way
    `ObligationKind`'s do — by being a filter that actually excludes people,
    stated in the call text often enough to be worth parsing, and answerable
    from a fact the user has already given.

    Anything subtler than this is not a criterion, it is the *match*, and the
    match is a separate question decided by relevance.
    """

    #: Where the applicant must be resident or registered.
    COUNTRY = "country"
    #: Sole trader, company, registered non-profit, individual.
    ORG_TYPE = "org_type"
    #: Student, early career, postdoctoral, senior — the ladder rung.
    CAREER_STAGE = "career_stage"
    #: Whether a university or institution must host the award.
    INSTITUTIONAL_HOST = "institutional_host"
    #: A field the call is restricted to.
    SECTOR = "sector"
    #: The right to work in the job's jurisdiction.
    WORK_AUTHORISATION = "work_authorisation"


class Verdict(str, Enum):
    """Three answers, and the third is the point.

    `UNKNOWN` is not a soft `INELIGIBLE`. It means Zaram has no fact to check
    against, which is a question to ask the user — never an exclusion applied
    on their behalf and never reported as one.
    """

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Requirement:
    """One thing a call requires, and the sentence that says so.

    `source` has **no default**, exactly as `obligations.Obligation.source` has
    none, and for the identical reason: a requirement with no clause is not a
    lower-quality requirement, it is a different kind of object, and an
    optional field lets one be constructed by forgetting rather than by
    deciding. The clause is what makes the refusal arguable, which is what
    makes rule 4 reach this gate at all — a verdict the user cannot contest is
    a verdict they route around.

    `values` is what satisfies it. Matching is case-folded and exact against
    this set; there is no fuzzy matching here on purpose, because "close
    enough" on an eligibility filter is how somebody is told they qualify for
    something they do not.
    """

    criterion: Criterion
    values: Tuple[str, ...]
    source: str
    #: True when holding one of `values` *disqualifies* rather than qualifies —
    #: "not open to applicants in X". Read from the clause, never inferred from
    #: the absence of a positive statement.
    excludes: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion": self.criterion.value,
            "values": list(self.values),
            "source": self.source,
            "excludes": self.excludes,
        }


@dataclass(frozen=True)
class Opportunity:
    """A job or a call for proposals, as it arrived, plus where it came from.

    Frozen, like `Obligation`, so that a correction produces a new record
    rather than mutating this one and "what did Zaram think last week" stays
    answerable.

    `url` is not decoration — it is the provenance (rule 2). Every claim Zaram
    makes about an opportunity has to be checkable against the page it was read
    from, and a shortlist the user cannot verify is a shortlist they cannot
    act on.

    `closes` is `None` when the call is rolling or the date could not be read,
    and those two are not distinguished here on purpose: neither of them is a
    deadline, and inventing one would put a date in somebody's calendar that
    nobody wrote. When a date *is* read it becomes an obligation through
    `obligations/`, which already does dated commitments with a source clause.
    """

    id: str
    kind: OpportunityKind
    title: str
    #: Employer or funder. Empty when the feed genuinely does not say, which
    #: happens on aggregators and is worth showing as absent rather than filled.
    organisation: str
    url: str
    #: Which feed produced it, for the egress log and for "stop showing me this
    #: source".
    feed_id: str
    summary: str = ""
    #: Full text when the feed gave one. Untrusted third-party text: it is
    #: written by a stranger and lands beside the model's decision, so it goes
    #: through `core/untrusted.py` like a tool description before it is used.
    body: str = ""
    closes: Optional[date] = None
    posted: Optional[date] = None
    location: str = ""
    #: What the call requires, as parsed. Empty means nothing was *read*, which
    #: is not the same as nothing being required — see `EligibilityReport`.
    requirements: Tuple[Requirement, ...] = ()
    #: Whatever else the source carried, kept rather than discarded so a later
    #: adapter change does not need a re-fetch.
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "title": self.title,
            "organisation": self.organisation,
            "url": self.url,
            "feed_id": self.feed_id,
            "summary": self.summary,
            "closes": self.closes.isoformat() if self.closes else None,
            "posted": self.posted.isoformat() if self.posted else None,
            "location": self.location,
            "requirements": [r.to_dict() for r in self.requirements],
        }


@dataclass(frozen=True)
class Profile:
    """The facts about the applicant that eligibility is checked against.

    A view over facts that live in the Spine, assembled per check rather than
    stored twice — a second copy would be a second place to correct, and rule 4
    says a correction changes the answers.

    **Every field is optional and absence is meaningful.** A missing field
    produces `UNKNOWN` for the criteria that need it, which becomes a question.
    It never produces `INELIGIBLE`, because excluding somebody on a fact they
    were never asked for is a decision made by an omission — the same class of
    bug as a record rebuilt field by field.
    """

    country: Optional[str] = None
    org_type: Optional[str] = None
    career_stage: Optional[str] = None
    #: Whether the applicant *has* an institutional host, not whether they want
    #: one.
    has_institutional_host: Optional[bool] = None
    sectors: Tuple[str, ...] = ()
    work_authorisation: Tuple[str, ...] = ()

    def known(self, criterion: Criterion) -> bool:
        """Whether there is a fact to check this criterion against."""
        if criterion is Criterion.COUNTRY:
            return bool(self.country)
        if criterion is Criterion.ORG_TYPE:
            return bool(self.org_type)
        if criterion is Criterion.CAREER_STAGE:
            return bool(self.career_stage)
        if criterion is Criterion.INSTITUTIONAL_HOST:
            return self.has_institutional_host is not None
        if criterion is Criterion.SECTOR:
            return bool(self.sectors)
        if criterion is Criterion.WORK_AUTHORISATION:
            return bool(self.work_authorisation)
        return False


@dataclass(frozen=True)
class Finding:
    """One requirement, checked, with the clause that produced the verdict."""

    criterion: Criterion
    verdict: Verdict
    #: Plain language, for the interface. Never a number: the whole point of
    #: this gate is that it is arguable, and a score cannot be argued with.
    reason: str
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criterion": self.criterion.value,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "source": self.source,
        }


@dataclass(frozen=True)
class EligibilityReport:
    """The gate's answer: a verdict, and every finding behind it.

    `verdict` is the whole report's: `INELIGIBLE` if anything failed,
    `UNKNOWN` if nothing failed but something could not be checked, otherwise
    `ELIGIBLE`. Failure dominates uncertainty, because one definite exclusion
    settles it however many questions remain.

    **`ELIGIBLE` on an opportunity with no parsed requirements is a claim this
    report does not make.** `checked` counts what was actually read. Zero means
    *nothing was found to check*, which is honest, and is why the interface
    shows "no stated requirements" rather than a green tick.
    """

    verdict: Verdict
    findings: Tuple[Finding, ...]
    #: Criteria that need a fact the user has not given. These are the
    #: questions worth asking — and they are asked once and remembered, not
    #: re-asked per opportunity.
    missing: Tuple[Criterion, ...] = ()

    @property
    def checked(self) -> int:
        return len(self.findings)

    @property
    def blocking(self) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.verdict is Verdict.INELIGIBLE)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "checked": self.checked,
            "findings": [f.to_dict() for f in self.findings],
            "missing": [c.value for c in self.missing],
        }


@dataclass(frozen=True)
class Feed:
    """One source the user switched on, by name.

    Rule 5 is default-deny, so this *is* the per-item decision: a feed in the
    list is a host the poller may reach, and a host nobody named is refused.
    Revocable in Settings like any other policy.

    `host` is stored separately from `url` because the egress policy is about
    the host and the log is about the host, and re-deriving it from the URL at
    three call sites is three chances to derive it differently.
    """

    id: str
    kind: FeedKind
    label: str
    #: The endpoint, board token, or mail label, depending on `kind`.
    target: str
    produces: OpportunityKind = OpportunityKind.GRANT
    host: str = ""
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "label": self.label,
            "target": self.target,
            "produces": self.produces.value,
            "host": self.host,
            "enabled": self.enabled,
        }


__all__ = [
    "Criterion",
    "EligibilityReport",
    "Feed",
    "FeedKind",
    "Finding",
    "Opportunity",
    "OpportunityKind",
    "Profile",
    "Requirement",
    "Verdict",
]
