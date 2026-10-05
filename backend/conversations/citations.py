"""Citations as history: what a past answer leaned on, checked against today.

`chatStore.resumeConversation` refused to restore sources, and the reason was
good: a citation is a live claim that *this* answer used *that* fact, and the
fact may since have been corrected or deleted (rule 4). Rendering yesterday's
citation against today's Spine shows provenance that no longer holds, which is
worse than showing none.

The refusal was right and it was also the whole answer, which it should not have
been. The better one is the one this module gives: keep the **reference**, and on
reopen **look again**.

What a reference resolves to
----------------------------
``live``
    The fact is still there and unchanged. Shown with its current wording.
``corrected``
    The fact was corrected after the answer. Shown with what it says *now*, and
    marked, because the answer was written from the earlier wording and the
    person is owed knowing the two differ.
``deleted``
    The fact is gone. Shown as deleted, with no text -- the citation records
    that the answer once leaned on something, never what it said, because the
    person removed the what.
``recorded``
    A web page. Not a claim about the Spine at all: a record that a page was
    read and bytes left, linked to its egress row.
``unchecked``
    Could not be looked up -- the Spine was not available, or the reference is
    to a kind this does not know how to find (a document). **Never "deleted".**
    Saying a fact is gone because the lookup failed would be an invented value
    about the user's own data, and the opposite error to the one this exists to
    prevent.

Nothing here writes. Reading a fact to display it is not recalling it (the store
keeps those apart), so reopening a conversation does not make facts look used.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

__all__ = ["FactLookupUnavailable", "resolve_sources"]

#: Characters of a fact shown as a citation's title, matching what a live
#: citation carries (`execution_engine` cuts at 120).
TITLE_CHARS = 120

MEMORY_PREFIX = "memory:"


class FactLookupUnavailable(RuntimeError):
    """The Spine could not be consulted. Distinct from "the fact is not there"."""


FactLookup = Callable[[str], Awaitable[Optional[Any]]]


def _record_id(ref: Dict[str, Any]) -> Optional[str]:
    explicit = ref.get("recordId")
    if isinstance(explicit, str) and explicit:
        return explicit
    url = ref.get("url")
    if isinstance(url, str) and url.startswith(MEMORY_PREFIX):
        return url[len(MEMORY_PREFIX):] or None
    return None


def _title(record: Any) -> str:
    return " ".join(str(getattr(record, "content", "") or "").split())[:TITLE_CHARS]


async def _state_of(record_id: str, lookup: FactLookup) -> Dict[str, Any]:
    try:
        record = await lookup(record_id)
    except FactLookupUnavailable:
        return {"state": "unchecked"}
    except Exception:  # noqa: BLE001 - a transcript must open whatever the Spine does
        logger.debug("citation lookup failed for %s", record_id, exc_info=True)
        return {"state": "unchecked"}

    if record is None:
        return {"state": "deleted"}

    successor_id = getattr(record, "superseded_by", None)
    if not successor_id:
        return {"state": "live", "title": _title(record)}

    # Followed to the end of the chain, bounded: a corrected fact can have been
    # corrected again, and the person is owed what it says now.
    current = None
    seen = {record_id}
    for _ in range(20):
        if not successor_id or successor_id in seen:
            break
        seen.add(successor_id)
        try:
            nxt = await lookup(successor_id)
        except Exception:  # noqa: BLE001
            nxt = None
        if nxt is None:
            # The correction itself was deleted: nothing current to show, and
            # that is a deletion, not an unknown -- the chain was read.
            return {"state": "deleted"}
        current = nxt
        successor_id = getattr(nxt, "superseded_by", None)
    return {"state": "corrected", "title": _title(current) if current is not None else ""}


async def resolve_sources(
    refs: Sequence[Dict[str, Any]],
    lookup: Optional[FactLookup],
) -> List[Dict[str, Any]]:
    """References in, citations out -- in the shape the renderer already draws.

    Camel-cased and keyed like `ChatSource`, because a restored citation that
    needed a different mapping would be a second place deciding one thing. The
    extra field is `history`, which a live citation never has and a restored one
    always does.
    """
    out: List[Dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        kind = ref.get("kind") or ""
        record_id = _record_id(ref)

        if kind == "web":
            history: Dict[str, Any] = {"state": "recorded"}
            title = ref.get("title") or None
        elif record_id and lookup is not None:
            history = await _state_of(record_id, lookup)
            title = history.pop("title", None) or None
        else:
            history = {"state": "unchecked"}
            title = None

        out.append(
            {
                "kind": kind,
                "url": ref.get("url"),
                "title": title,
                # Never restored: the passage that bore on the answer is the
                # user's own text.
                "excerpt": None,
                "relevance": ref.get("relevance"),
                "cited": bool(ref.get("cited", True)),
                "number": ref.get("number"),
                "egressId": ref.get("egressId"),
                "bytesSent": ref.get("bytesSent"),
                "origin": ref.get("origin"),
                "recordId": record_id,
                "history": history,
            }
        )
    return out
