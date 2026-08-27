"""HTTP for the session store.

Thin on purpose. Every decision that matters — what a title is, what deletion
takes with it, how `""` differs from `None` when scoping — lives in
`records.py` where it can be tested without a client. This layer converts
between HTTP and that, and does nothing else.

**Mounted in `main.py` and asserted in `tests/test_routes_are_mounted.py`.**
A router with its own passing tests and no `include_router` is this
repository's most expensive recurring shape: `providers/api.py` answered 404 on
the running product for the whole life of the provider layer while its unit
tests passed, because they build their own app. Adding a route here without
adding it there recreates that exactly.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .records import ConversationRecords, UnknownConversation

router = APIRouter(prefix="/conversations", tags=["conversations"])

_RECORDS: Optional[ConversationRecords] = None


def set_records(records: ConversationRecords) -> None:
    """Attach the live store (called from `main.py`)."""
    global _RECORDS
    _RECORDS = records


def _records() -> ConversationRecords:
    if _RECORDS is None:
        raise HTTPException(status_code=503, detail="conversation store not initialized")
    return _RECORDS


def _conversation_dict(conversation) -> dict:
    return {
        "id": conversation.id,
        "title": conversation.title,
        "project_id": conversation.project_id,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "message_count": conversation.message_count,
    }


def _message_dict(message) -> dict:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "seq": message.seq,
        "role": message.role,
        "text": message.text,
        "created_at": message.created_at,
        # Empty rather than null, and empty means "not recorded" rather than
        # "local" — the same three-valued discipline `locality_of` keeps.
        "model": message.model,
        "locality": message.locality,
    }


class StartConversation(BaseModel):
    #: Rule 7i. ``""`` is a real answer — a conversation outside any project.
    project_id: str = ""
    #: Normally empty. The first user message names it; see `title_from`.
    title: str = ""


class RenameConversation(BaseModel):
    title: str


@router.get("")
async def list_conversations(
    project_id: Optional[str] = Query(
        default=None,
        description=(
            "Omit for every conversation. Pass an empty string for the ones "
            "belonging to no project — two different questions."
        ),
    ),
    limit: int = Query(default=50, ge=1, le=500),
) -> List[dict]:
    """Conversations by last activity, most recent first.

    ``project_id`` absent and ``project_id=""`` are deliberately different, and
    FastAPI preserves the distinction: a missing query parameter arrives as
    ``None``, an empty one as ``""``. Collapsing them is how "show me
    everything" quietly becomes "show me the unscoped ones".
    """
    records = _records()
    return [_conversation_dict(c) for c in records.list(project_id=project_id, limit=limit)]


@router.post("")
async def start_conversation(body: StartConversation) -> dict:
    records = _records()
    return _conversation_dict(records.start(project_id=body.project_id, title=body.title))


@router.get("/{conversation_id}")
async def read_conversation(conversation_id: str) -> dict:
    """One conversation and its whole transcript.

    Messages come with it rather than from a second route. A transcript is what
    a conversation *is*, and a client that has to ask twice renders an empty
    thread for one paint while the second request is in flight.
    """
    records = _records()
    try:
        conversation = records.get(conversation_id)
        messages = records.messages(conversation_id)
    except UnknownConversation:
        raise HTTPException(status_code=404, detail="No such conversation")
    return {
        **_conversation_dict(conversation),
        "messages": [_message_dict(m) for m in messages],
    }


@router.patch("/{conversation_id}")
async def rename_conversation(conversation_id: str, body: RenameConversation) -> dict:
    records = _records()
    try:
        return _conversation_dict(records.rename(conversation_id, body.title))
    except UnknownConversation:
        raise HTTPException(status_code=404, detail="No such conversation")
    except ValueError as exc:
        # A blank title is a bad request, not a server fault. Said as a
        # sentence, because it reaches a person.
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict:
    """Rule 4, on the transcript.

    Facts the Spine took from this conversation are **not** removed, and the
    response says so rather than leaving the caller to assume either way. They
    are scoped, sourced and correctable in their own right, and deleting them
    here would make a delete larger than the one that was asked for.
    """
    records = _records()
    try:
        records.delete(conversation_id)
    except UnknownConversation:
        raise HTTPException(status_code=404, detail="No such conversation")
    return {
        "deleted": conversation_id,
        "facts_removed": 0,
        "note": (
            "The transcript is gone. Facts Zaram remembered from it are still "
            "in Memory, where they can be corrected or deleted individually."
        ),
    }
