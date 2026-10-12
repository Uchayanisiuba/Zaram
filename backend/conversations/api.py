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

from typing import Callable, List, Optional, Sequence

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from .citations import FactLookup, resolve_sources
from .pictures import ConversationPictures, media_type_of
from .records import ConversationRecords, UnknownConversation

router = APIRouter(prefix="/conversations", tags=["conversations"])

_RECORDS: Optional[ConversationRecords] = None


def set_records(records: ConversationRecords) -> None:
    """Attach the live store (called from `main.py`)."""
    global _RECORDS
    _RECORDS = records


_FACT_LOOKUP: Optional[FactLookup] = None


def set_fact_lookup(lookup: Optional[FactLookup]) -> None:
    """Attach the way to find a fact by id (called from `main.py`).

    Injected rather than imported: this package must not depend on the memory
    runtime, and a transcript has to open when the Spine cannot be reached.
    """
    global _FACT_LOOKUP
    _FACT_LOOKUP = lookup


_PICTURES: Optional[ConversationPictures] = None
_ON_PICTURES_REMOVED: Optional[Callable[[Sequence[str]], None]] = None


def set_pictures(
    pictures: Optional[ConversationPictures],
    *,
    on_removed: Optional[Callable[[Sequence[str]], None]] = None,
) -> None:
    """Attach the folder of kept pictures (called from `main.py`).

    ``on_removed`` is told the attachment ids whose kept copies were just
    removed, so the live session can let go of its own working copies too.
    Without that, "remove this conversation's pictures" would leave the same
    picture still showing on a page until the next restart -- a removal that
    looks like it did nothing. Injected rather than imported: this package does
    not depend on the attachment store.
    """
    global _PICTURES, _ON_PICTURES_REMOVED
    _PICTURES = pictures
    _ON_PICTURES_REMOVED = on_removed


def pictures_store() -> Optional[ConversationPictures]:
    """The kept pictures, or ``None`` where none are attached (a bare test app)."""
    return _PICTURES


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
        # Kept at the top of the list. The one thing recency ordering
        # cannot express — see `Conversation.pinned`.
        "pinned": conversation.pinned,
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
        # What the reply *did*. Camel-cased because these cross to the
        # renderer as the `ChatToolCall` and `ChatPlan` shapes it already
        # builds for a live reply, and a restored message that needed a
        # different mapping would be a second place deciding one thing.
        "toolCalls": [dict(c) for c in message.tool_calls],
        "plan": message.plan,
        "artifactIds": list(message.artifact_ids),
        # References, as stored. Resolved against the Spine by the route that
        # reads a whole conversation, not here: this is also what the list and
        # export paths see, and they have no business looking facts up.
        "sources": [dict(s) for s in message.sources],
        # The pictures that went with a user message -- names and ids only. The
        # bytes are fetched from `/conversations/{id}/pictures/{attachment_id}`
        # when a page that uses one is shown.
        "attachments": [dict(a) for a in message.attachments],
    }


class StartConversation(BaseModel):
    #: Rule 7i. ``""`` is a real answer — a conversation outside any project.
    project_id: str = ""
    #: Normally empty. The first user message names it; see `title_from`.
    title: str = ""


class RenameConversation(BaseModel):
    #: Optional, so one route can rename, pin, or both. A `None` means
    #: *leave it alone*, which is what lets the pin toggle send only the
    #: pin — a client that had to resend the title would overwrite one
    #: the person had just edited in another window.
    title: Optional[str] = None
    pinned: Optional[bool] = None


@router.get("")
async def list_conversations(
    project_id: Optional[str] = Query(
        default=None,
        description=(
            "Omit for every conversation. Pass an empty string for the ones "
            "belonging to no project — two different questions."
        ),
    ),
    q: Optional[str] = Query(
        default=None,
        description=(
            "Find conversations whose title or messages contain this. "
            "Searches message text as well as titles, because a title is "
            "the first thing somebody typed and is often not what they "
            "remember about the conversation."
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
    if q and q.strip():
        # Search ignores `project_id` on purpose: somebody who types a word
        # is looking for a conversation, and silently hiding the matches
        # outside the project they happen to have open is the kind of empty
        # result that reads as "Zaram did not keep it".
        return [_conversation_dict(c) for c in records.search(q, limit=limit)]
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
    out_messages = []
    for m in messages:
        item = _message_dict(m)
        # Looked up now, against the Spine as it is now -- see `citations.py`.
        # Only assistant replies carry any; the loop costs nothing otherwise.
        if item["sources"]:
            item["sources"] = await resolve_sources(item["sources"], _FACT_LOOKUP)
        out_messages.append(item)
    return {
        **_conversation_dict(conversation),
        "messages": out_messages,
    }


@router.patch("/{conversation_id}")
async def update_conversation(conversation_id: str, body: RenameConversation) -> dict:
    """Rename a conversation, pin it, or both.

    Each field is applied only when it was sent, so a pin toggle does not
    have to resend a title — and cannot overwrite one the person edited in
    another window a second earlier.
    """
    records = _records()
    try:
        conversation = records.get(conversation_id)
        if body.title is not None:
            conversation = records.rename(conversation_id, body.title)
        if body.pinned is not None:
            conversation = records.set_pinned(conversation_id, body.pinned)
        return _conversation_dict(conversation)
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
    # Read before the rows go: the ids of the pictures it held are on the
    # messages that are about to be deleted.
    picture_ids = _picture_ids(records, conversation_id)
    try:
        records.delete(conversation_id)
    except UnknownConversation:
        raise HTTPException(status_code=404, detail="No such conversation")
    # The pictures kept beside it go with it -- they are part of the transcript.
    _forget_pictures(conversation_id, picture_ids)
    return {
        "deleted": conversation_id,
        "facts_removed": 0,
        "note": (
            "The transcript and the pictures kept with it are gone. Facts Zaram "
            "remembered from it are still in Memory, where they can be corrected "
            "or deleted individually."
        ),
    }


def _picture_ids(records: ConversationRecords, conversation_id: str) -> List[str]:
    """Every attachment id this conversation kept, from the folder and the messages."""
    found = set(_PICTURES.ids(conversation_id)) if _PICTURES is not None else set()
    try:
        for message in records.messages(conversation_id):
            found.update(str(a.get("id")) for a in message.attachments if a.get("id"))
    except UnknownConversation:
        pass
    return sorted(found)


def _forget_pictures(conversation_id: str, picture_ids: Sequence[str]) -> tuple:
    """Remove the kept copies and let the live session drop its own. ``(files, bytes)``."""
    removed = (0, 0)
    if _PICTURES is not None:
        removed = _PICTURES.remove_conversation(conversation_id)
    if _ON_PICTURES_REMOVED is not None and picture_ids:
        try:
            _ON_PICTURES_REMOVED(list(picture_ids))
        except Exception:  # noqa: BLE001 - the removal itself is done; this is tidying
            pass
    return removed


@router.get("/{conversation_id}/pictures/{attachment_id}")
async def read_conversation_picture(conversation_id: str, attachment_id: str):
    """A picture kept with this conversation, for a page that uses it.

    Served to the window and nowhere else: never indexed, never recalled. The
    conversation has to exist and the picture has to be in *its* folder -- an
    id from another conversation, or one that is not an attachment id at all,
    answers 404. The media type is read from the bytes, never from a file name,
    because it ends up in a `data:` URI a browser honours. Working data, so
    `no-store`.
    """
    records = _records()
    try:
        records.get(conversation_id)
    except UnknownConversation:
        raise HTTPException(status_code=404, detail="No such conversation")
    raw = _PICTURES.read(conversation_id, attachment_id) if _PICTURES is not None else None
    if raw is None:
        raise HTTPException(status_code=404, detail="That picture is no longer kept.")
    media_type = media_type_of(raw)
    if media_type is None:
        raise HTTPException(status_code=415, detail="That picture is in a format a page cannot show.")
    return Response(content=raw, media_type=media_type, headers={"Cache-Control": "no-store"})


@router.delete("/{conversation_id}/pictures")
async def remove_conversation_pictures(conversation_id: str) -> dict:
    """Remove the pictures kept with a conversation and nothing else.

    The way a person shortens retention without losing the conversation (see
    `pictures.py`). The transcript and its pages stay; a page that used a
    picture shows the "no longer attached" placeholder, which says so.
    """
    records = _records()
    picture_ids = _picture_ids(records, conversation_id)
    try:
        records.get(conversation_id)
    except UnknownConversation:
        raise HTTPException(status_code=404, detail="No such conversation")
    files, size = _forget_pictures(conversation_id, picture_ids)
    return {"conversation_id": conversation_id, "removed": files, "bytes": size}
