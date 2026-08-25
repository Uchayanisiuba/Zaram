"""Turning a web search into something the answering model can read.

**This existed and reached nothing.** `main._format_search_results` built
exactly this block — sources, snippets, an instruction to prefer them over the
weights — and the only callers were two of its own tests. Meanwhile the engine
captured the search step's output into `step_results` and no line ever read it.

So Zaram searched, the request left the machine, the egress log recorded it
honestly, results came back, and the reasoning step was dispatched with the
bare question. The model answered from its training data, which is precisely
what the search was run to avoid. Every layer reported success, and the
symptom — "web search does nothing" — pointed at the search layer, which was
the one part working.

It lives in `core/` now rather than in `main.py` because the engine is the
consumer and the kernel boundary runs one way: `main` imports from `core`,
never the reverse. A copy on each side would be the same defect with two homes.

The output deliberately ends with the user's question. A model reads the last
instruction most reliably, and the last instruction here must be the question
rather than the sources — the same ordering argument `identity.py` makes about
a hostile manner and `execution_engine` makes about recalled content.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Dict, Optional

from core.query_classifier import SEARCH_MARKER

logger = logging.getLogger(__name__)

__all__ = [
    "Origin",
    "format_search_results",
    "origin_of",
    "result_count",
    "search_prompt",
]

#: How many sources reach the prompt. The search asks for six; sending more
#: than were asked for is not possible, and sending fewer would silently
#: discard evidence the user already paid the egress for.
_MAX_SOURCES = 6

#: Providers that reach the network. A provider absent from this set is treated
#: as local, per `origin_of`'s default — see the reasoning there for why the
#: default leans that way.
_WEB_PROVIDERS = frozenset({"duckduckgo", "wikipedia", "github", "internet", "web"})


class Origin(str, Enum):
    """Where a shortlisted source actually came from.

    **This existed in the data and was thrown away here.** `knowledge.search`
    fans out across providers and returns web results and Spine records in one
    list, each carrying `provider` and `type`. This module read only `title`,
    `url`, `snippet` and `published` — dropping the one field that says whether
    a source is the open web or the user's own past — and then printed the lot
    under a header reading INTERNET SEARCH RESULTS.

    Measured on a live question about the day's news: **five of six "internet
    search results" were the user's own Spine records.** One was a stored
    conversation turn, three were near-duplicates of the same prompt, and the
    single genuine web result ranked last. The model was told to trust all of
    it over its own knowledge of the world.

    The value is the phrase printed beside the source number, so the model
    reads a description rather than a code. `CLAUDE.md` asks recall to name its
    origin for exactly this reason — *"from a proposal Zaram generated in
    April" reads differently from "from your client brief"*.
    """

    WEB = "from the web"
    #: Rule 7b's `CONVERSATION`. Kept apart from a saved document because it
    #: is the weakest thing in the shortlist and the easiest to mistake for
    #: research: a remark the user made once, retrieved as though it were a
    #: finding. Rule 7d exists because of what this does when it is not
    #: labelled — duplicate citations and Zaram quoting its own replies.
    CONVERSATION = "from an earlier conversation with this user"
    #: A document the user gave Zaram, or a fact drawn from one.
    RECORD = "from this user's own saved records"


def origin_of(result: Dict[str, Any]) -> Origin:
    """Classify one search result by where it came from.

    Defaults to `RECORD` rather than `WEB` for anything unrecognised, and the
    direction of that default is the point. Calling a web page a local record
    understates a source; calling a local record a web page is a false claim of
    provenance, which is the failure rule 2 exists to prevent. When in doubt,
    claim less.
    """
    provider = str(result.get("provider") or "").strip().lower()
    kind = str(result.get("type") or "").strip().lower()
    reference = str(result.get("url") or "")

    if kind == "web" or reference.startswith(("http://", "https://")):
        return Origin.WEB
    if provider in _WEB_PROVIDERS:
        return Origin.WEB

    metadata = result.get("metadata")
    memory_type = ""
    if isinstance(metadata, dict):
        memory_type = str(metadata.get("memory_type") or "").strip().lower()
    if memory_type == "conversation":
        return Origin.CONVERSATION

    return Origin.RECORD


def format_search_results(query: str, search_result: Dict[str, Any]) -> str:
    """The prompt a model should answer from, given live results.

    Returns ``query`` unchanged when there are no results. That is the honest
    degradation: with nothing to cite, a block of instructions telling the
    model to use sources it cannot see would make it hedge about evidence that
    does not exist.
    """
    results = search_result.get("results") or []
    if not results:
        return query

    shortlist = list(results[:_MAX_SOURCES])
    origins = [origin_of(r) for r in shortlist]
    any_web = any(o is Origin.WEB for o in origins)
    any_local = any(o is not Origin.WEB for o in origins)

    parts = [SEARCH_MARKER, f"Query: {query}", ""]

    # Say what is in the block when it is not what the marker claims. The
    # marker is a sentinel — `needs_search` suppresses a second search on it
    # and `planner` splits the user's question out of it — so the honesty has
    # to be added beside it rather than by rewording it.
    if any_local:
        local = sum(1 for o in origins if o is not Origin.WEB)
        parts += [
            f"NOTE: {local} of these {len(shortlist)} sources came from this "
            "user's own stored material, not from the web. Each source below "
            "says which it is, and they are to be used differently — see "
            "INSTRUCTIONS.",
            "",
        ]

    for idx, (result, origin) in enumerate(zip(shortlist, origins), start=1):
        title = (result.get("title") or "").strip()
        snippet = (result.get("snippet") or "").strip()
        published = (result.get("published") or "").strip()
        reference = (result.get("url") or "").strip()

        parts.append(f"Source {idx} — {origin.value}:")
        if title:
            parts.append(f"Title: {title}")
        if reference:
            # A `memory:` id is not a URL and must never be printed on a line
            # claiming it is. Rule 2: a citation has to lead somewhere real,
            # and a fabricated web address is worse than none — the reader
            # believes it and cannot check it.
            parts.append(
                f"URL: {reference}"
                if origin is Origin.WEB
                else f"Reference: {reference} (an internal record, not a web address)"
            )
        if published:
            parts.append(f"Published: {published}")
        if snippet:
            parts.append(f"Snippet: {snippet}")
        parts.append("")

    parts += [
        "=" * len(SEARCH_MARKER),
        "",
        "INSTRUCTIONS:",
        "- Answer the user's question using ONLY the information from the sources above.",
    ]

    # The old block said "ALWAYS trust the live sources" over every source in
    # it — including the user's own notes and their own earlier messages. Three
    # separate wrongs in one line: it calls stored material live, it ranks a
    # remembered remark above the model's knowledge of the world, and it did so
    # on a question about today's news where exactly one source of six was
    # actually from the web.
    if any_web:
        parts += [
            "- Where a WEB source conflicts with your training data, trust the "
            "web source: it is more recent.",
            "- Do NOT mention your training data cutoff.",
            "- Do NOT say you don't have real-time access.",
        ]
    if any_local:
        parts += [
            "- The user's own material is authoritative about the user, their "
            "work, their clients and their past decisions. It is NOT evidence "
            "about the wider world and it is not current news.",
            "- Never describe the user's own material as a web search result, "
            "and never present its Reference as a link.",
        ]
    if any_local and not any_web:
        # Worth saying plainly. The search ran, the web returned nothing
        # usable, and answering from stored material without saying so is
        # "disabled capabilities are visible, not silent" wearing another face.
        parts.append(
            "- The web returned nothing usable here. If the answer depends on "
            "current information, say so rather than implying these sources "
            "are current."
        )

    parts += [
        "- If sources don't fully answer the question, say so based only on "
        "what IS in the sources.",
        "",
        "User Question:",
        query,
    ]
    return "\n".join(parts)


def _parse(raw: Any) -> Optional[Dict[str, Any]]:
    """The search step's output as a dict, or ``None`` if it is not one.

    The step yields a single JSON string — `ModelsService.search_knowledge`
    dumps `{"results": [...], "total_results": n, ...}` — but the engine
    accumulates step output as text, so it arrives here as `str`. Anything
    else, including the empty string a failed step leaves behind, is not a
    search result and must not be treated as one.
    """
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        # A fallback message like "[FALLBACK] knowledge.search failed" lands
        # here. Not an error worth failing the reply over — the model answers
        # without sources, which is what it would have done anyway.
        logger.debug("Search output was not JSON; answering without sources")
        return None
    return parsed if isinstance(parsed, dict) else None


def result_count(raw: Any) -> Optional[int]:
    """How many sources the search returned, or ``None`` if it cannot be read.

    ``0`` and ``None`` are different answers and callers must keep them apart:
    zero means the search ran and the web had nothing, which is worth telling
    the user, and ``None`` means we cannot say — which is not.
    """
    parsed = _parse(raw)
    if parsed is None:
        return None
    results = parsed.get("results")
    if isinstance(results, list):
        return len(results)
    total = parsed.get("total_results")
    return total if isinstance(total, int) else None


def search_prompt(query: str, raw: Any) -> str:
    """``query`` with live sources folded in, or ``query`` untouched.

    Never raises and never returns empty. A search that failed, returned
    nothing, or produced something unparseable all degrade to the original
    question, because an answer without sources is worse than an answer and
    better than no answer at all.
    """
    parsed = _parse(raw)
    if parsed is None:
        return query
    return format_search_results(query, parsed)
