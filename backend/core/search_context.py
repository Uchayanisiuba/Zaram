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
from typing import Any, Dict, Optional

from core.query_classifier import SEARCH_MARKER

logger = logging.getLogger(__name__)

__all__ = ["format_search_results", "search_prompt", "result_count"]

#: How many sources reach the prompt. The search asks for six; sending more
#: than were asked for is not possible, and sending fewer would silently
#: discard evidence the user already paid the egress for.
_MAX_SOURCES = 6


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

    parts = [SEARCH_MARKER, f"Query: {query}", ""]
    for idx, r in enumerate(results[:_MAX_SOURCES], start=1):
        url = r.get("url") or ""
        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        published = (r.get("published") or "").strip()
        parts.append(f"Source {idx}:")
        if title:
            parts.append(f"Title: {title}")
        if url:
            parts.append(f"URL: {url}")
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
        "- If the sources conflict with your training data, ALWAYS trust the live sources.",
        "- Do NOT mention your training data cutoff.",
        "- Do NOT say you don't have real-time access.",
        "- If sources don't fully answer the question, say so based only on what IS in the sources.",
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
