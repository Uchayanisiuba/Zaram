"""Turning a domain into the facts recall is allowed to see.

**This is the module that makes a domain a scope rather than a label.**
`CLAUDE.md`: a domain is a retrieval scope, not a folder — "if it only groups
files it is a filter, and it has to change answers". Everything in
`domains.py` exists so this function can be written.

The chain is `domain → sources → outcomes → fact ids`, and the middle link is
why this lives here rather than in either store. `KnowledgeDomains` knows which
sources are in a domain and nothing about ingestion; `IngestRecords` knows which
facts each file produced and nothing about domains. Joining them inside either
one would give that store a second owner.

**Why fact ids and not a metadata filter.** Facts carry `source_path` and
`source_name`, not a source id — so filtering on metadata would mean matching
paths, and a scanned folder nests, so a document's parent directory is not its
source's root. `ingest.db` already records exactly which facts came from which
source and is the authority on it. Resolving through it is the answer that
cannot drift.

**Where the filter is applied matters more than how.** It goes in
`retrieval.py`, at the same single point that enforces rule 7i's scope, and for
the reason written there: `_vector_search` never passes through the store's
filters, so a semantic hit walks straight past anything applied in the store.
A boundary enforced per code path is a boundary with a hole in it per code path.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class _Records(Protocol):
    """The slice of `IngestRecords` this needs, named so it can be faked."""

    def outcomes(
        self, source_id: str | None = ..., problems_only: bool = ...
    ) -> list[dict[str, Any]]: ...


class _Domains(Protocol):
    def source_ids(self, domain_id: str) -> list[str]: ...


def fact_ids_for(
    domains: _Domains, records: _Records, domain_ids: list[str]
) -> frozenset[str]:
    """Every fact id reachable from these domains.

    A union, not an intersection. Asking across *Clients* and *Legal* means
    "anything in either", which is what selecting two of something means
    everywhere else in an interface — and an intersection would return almost
    nothing, since a document is rarely in every domain chosen.

    An empty result is meaningful and is not the same as "no restriction": a
    domain with no sources yet can answer from nothing, and the caller has to
    tell those two apart. `None` is the caller's way of saying unrestricted;
    this function never returns it.
    """
    source_ids: set[str] = set()
    for domain_id in domain_ids:
        source_ids.update(domains.source_ids(domain_id))

    if not source_ids:
        return frozenset()

    fact_ids: set[str] = set()
    for source_id in source_ids:
        for outcome in records.outcomes(source_id=source_id):
            fact_ids.update(outcome.get("fact_ids") or ())
    return frozenset(fact_ids)


def describe(all_domains: list[dict[str, Any]], domain_ids: list[str]) -> str:
    """One phrase naming where an answer was allowed to come from.

    Written for the end of a sentence — *"answered from your Investing
    domain"* — because a reply that narrowed its own sources has to say so.
    Rule: disabled capabilities are visible, not silent, and a question answered
    from one domain is a question that did not look at the rest.

    Takes the domain records rather than the store: naming what was chosen is a
    question about the rows in hand, and a second parameter the body never read
    made the call site pass the same object twice with one of them ignored.
    """
    chosen = [d["name"] for d in all_domains if d["id"] in set(domain_ids)]
    if not chosen:
        return ""
    if len(chosen) == 1:
        return f"your {chosen[0]} domain"
    if len(chosen) == 2:
        return f"your {chosen[0]} and {chosen[1]} domains"
    return f"your {', '.join(chosen[:-1])} and {chosen[-1]} domains"
