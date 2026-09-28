"""The opportunities pack: jobs and grants, which are one pipeline.

`docs/PACK-OPPORTUNITIES.md` is the design. The short version:

**Automate discovery, eligibility and the first draft. Never automate
submission.** That is not caution — it is where the funders themselves drew
the line. Grants.gov's API documentation says write operations are unsupported
and applications cannot be submitted through it; the EU Funding & Tenders
Portal has a search API and no submission endpoint. Rules 6, 9 and the mutative
tier land on the same line independently.

**Jobs and grants are one pipeline with the weights moved.** For jobs
discovery is easy and every application is generic, so the bottleneck is the
draft. For grants it inverts: the bottleneck is *eligibility*, because most
people do not know what they can apply for and finding out the hard way costs
a fortnight each time. One pack, two project types.

**Eligibility is a gate, never a ranking** — `CLAUDE.md`'s capability rule in a
new domain, written down before the matcher rather than after the fourth
recurrence. And **unknown is not no**: a criterion with no fact behind it is a
question to ask, never an exclusion applied on the user's behalf.

This is the second pack built by hand, which is what `CLAUDE.md` asks for
before anybody designs the pack *system*: two real examples and the friction
between them. The friction is in the table in the design doc.
"""

from .contracts import (
    Criterion,
    EligibilityReport,
    Feed,
    FeedKind,
    Finding,
    Opportunity,
    OpportunityKind,
    Profile,
    Requirement,
    Verdict,
)
from .eligibility import assess, eligible_only, missing_criteria
from .requirements import read_requirements
from .sources import BUILT_IN_MAPS, FieldMap, from_json, from_rss, host_of, parse_date
from .tools import CHECK_ELIGIBILITY, READ_CRITERIA, SERVER_ID, OpportunityTools

__all__ = [
    "BUILT_IN_MAPS",
    "CHECK_ELIGIBILITY",
    "Criterion",
    "EligibilityReport",
    "Feed",
    "FeedKind",
    "FieldMap",
    "Finding",
    "Opportunity",
    "OpportunityKind",
    "OpportunityTools",
    "Profile",
    "READ_CRITERIA",
    "Requirement",
    "SERVER_ID",
    "Verdict",
    "assess",
    "eligible_only",
    "from_json",
    "from_rss",
    "host_of",
    "missing_criteria",
    "parse_date",
    "read_requirements",
]
