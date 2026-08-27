"""The session store: what was said, kept, so it is there tomorrow.

**This is the half of rule 7d that was never built.** The rule reads
*"Conversation is ephemeral; entering the Spine is a decision the system makes,
not the user"* — and, in the same breath, *"Session state and long-term memory
are separate stores."* Zaram had the second and not the first. Every table
across all seven databases was checked on 27 August 2026: ``artifacts``,
``egress``, ``sources``, ``outcomes``, ``domains``, ``domain_sources``,
``obligations``, ``unresolved``, ``projects``, ``files``, ``cache``,
``memories``. Nothing held a message. Closing the window lost the conversation.

So this **implements** 7d rather than bending it, and the distinction it draws
is the one the rule is about:

- A **message** lands here, always, because a person said it and may look for
  it later. That is bookkeeping, not memory.
- A **fact** lands in the Spine, when the system decides it should, carrying
  provenance and a scope. That is memory, and nothing in this file may put one
  there.

Keeping those apart is what avoids the failure 7d was written from — duplicate
citations, and Zaram quoting its own replies back as sources. A transcript held
here is not a source: never embedded, never recalled, never cited.
``runtimes/memory`` decides what is worth remembering and does not read this
module.

What deletion means here
------------------------
Deleting a conversation deletes the transcript and nothing else. Facts the
Spine took from it stay, because they are scoped, sourced and correctable in
their own right — rule 4 is about the *fact* and the answers built on it, and
that machinery lives where the fact does. Someone who wants the fact gone
deletes the fact; someone who wants the transcript gone gets exactly that. Two
different requests, and merging them silently makes a delete larger than it was
asked to be. Artifacts likewise: a file generated during a conversation was
written to the output directory and belongs to the user, not to a row here.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_NAME = "conversations.db"

#: Roles a stored message may carry. Two, and no ``system``.
#:
#: The system prompt is composed fresh on every request from identity, the
#: user's character settings and the date, so storing one would preserve a
#: string that was true at the time and becomes a lie the moment they rename
#: the assistant or the model changes underneath. The transcript is what the
#: two parties said.
USER = "user"
ASSISTANT = "assistant"
_ROLES = frozenset({USER, ASSISTANT})

#: How much of the first message becomes the title. Long enough to tell two
#: conversations apart in a list, short enough to sit on one line beside a date.
_TITLE_CHARS = 60


class UnknownConversation(KeyError):
    """No conversation with that id."""


@dataclass(frozen=True)
class Message:
    id: str
    conversation_id: str
    #: Position within the conversation, from 1. Explicit rather than implied
    #: by ``created_at``: two messages written inside one clock tick would
    #: otherwise sort arbitrarily, and a reply rendering above the question
    #: that produced it is the kind of bug nobody reproduces on demand.
    seq: int
    role: str
    text: str
    created_at: float
    #: Which model produced an assistant message, and where it ran. Empty for a
    #: user message — and empty is a real answer for an assistant one too.
    #: ``locality_of`` returns ``None`` for a model it cannot place, and this
    #: inherits that rather than guessing local: *"runs on this machine" would
    #: be a confident false claim on the one thing the user is most likely to
    #: check.*
    model: str = ""
    locality: str = ""


@dataclass(frozen=True)
class Conversation:
    id: str
    #: Derived from the first thing the user said. Never asked for.
    title: str
    #: Rule 7i, the same field the Spine and Knowledge carry. ``""`` is a real
    #: answer: a question asked outside any project is not about one.
    project_id: str
    created_at: float
    #: Bumped on every message, so the list orders by *last activity* rather
    #: than by creation — which is what a person means by "the one I was just
    #: in".
    updated_at: float
    message_count: int = 0


def title_from(text: str) -> str:
    """A conversation's name, taken from the first thing the user typed.

    **Not a summary, and deliberately not model-generated.** A generated title
    spends an inference call on a label, on the path where the product's whole
    speed argument lives, and it invents wording the user never used — so the
    list becomes searchable by everything except the words they remember
    typing. Rule 7e's reasoning applies to the system as much as to the person:
    do not ask a question the first line already answers.

    Cut at a word boundary, because a title ending mid-word reads as damage
    rather than as truncation.
    """
    clean = " ".join((text or "").split())
    if not clean:
        return "Untitled"
    if len(clean) <= _TITLE_CHARS:
        return clean
    cut = clean[:_TITLE_CHARS]
    spaced = cut.rsplit(" ", 1)[0]
    # A single word longer than the limit has no boundary to cut at, and
    # returning "" there would title the conversation with an ellipsis alone.
    return (spaced or cut) + "…"


class ConversationRecords:
    """Conversations and their messages on SQLite.

    Start, append, list, read, rename, delete. There is deliberately no
    edit-a-message: a transcript that can be rewritten after the fact is not a
    record of what happened, and the product's provenance argument rests on the
    difference.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        # Messages go when their conversation goes. Enforced by the database
        # rather than by remembering to do it in `delete`, because the one path
        # that forgets leaves rows pointing at a conversation that is not
        # there — invisible until something counts them.
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL DEFAULT '',
                    project_id  TEXT NOT NULL DEFAULT '',
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id              TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL
                        REFERENCES conversations(id) ON DELETE CASCADE,
                    seq             INTEGER NOT NULL,
                    role            TEXT NOT NULL,
                    text            TEXT NOT NULL,
                    created_at      REAL NOT NULL,
                    model           TEXT NOT NULL DEFAULT '',
                    locality        TEXT NOT NULL DEFAULT ''
                )
                """
            )
            # The two orderings anything actually reads: one conversation's
            # messages in sequence, and the list by recency.
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_conv "
                "ON messages(conversation_id, seq)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversations_updated "
                "ON conversations(updated_at DESC)"
            )

    # ----------------------------------------------------------------- write

    def start(self, *, project_id: str = "", title: str = "") -> Conversation:
        """Open a conversation. The title may be empty and usually is.

        An empty title is filled by the first user message rather than left
        blank — see `append`. Passing one is for a caller restoring or
        importing, not for the chat path.
        """
        now = time.time()
        record = Conversation(
            id=f"conv_{uuid.uuid4().hex[:12]}",
            title=title.strip(),
            project_id=project_id.strip(),
            created_at=now,
            updated_at=now,
            message_count=0,
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO conversations "
                "(id, title, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.title,
                    record.project_id,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def append(
        self,
        conversation_id: str,
        role: str,
        text: str,
        *,
        model: str = "",
        locality: str = "",
    ) -> Message:
        """Add one message and bump the conversation's activity time.

        ``seq`` is allocated inside the same transaction as the insert, under
        the instance lock. Two messages racing for one number is not
        hypothetical here: the chat path writes the question and the reply from
        different points in a single request, and a second window makes them
        genuinely concurrent.
        """
        if role not in _ROLES:
            raise ValueError(f"role must be one of {sorted(_ROLES)}, not {role!r}")

        now = time.time()
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if row is None:
                raise UnknownConversation(conversation_id)

            seq = int(
                conn.execute(
                    "SELECT COALESCE(MAX(seq), 0) + 1 FROM messages "
                    "WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()[0]
            )

            message = Message(
                id=f"msg_{uuid.uuid4().hex[:12]}",
                conversation_id=conversation_id,
                seq=seq,
                role=role,
                text=text,
                created_at=now,
                model=model,
                locality=locality,
            )
            conn.execute(
                "INSERT INTO messages "
                "(id, conversation_id, seq, role, text, created_at, model, locality) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    message.id,
                    message.conversation_id,
                    message.seq,
                    message.role,
                    message.text,
                    message.created_at,
                    message.model,
                    message.locality,
                ),
            )

            # The title arrives with the first *user* message, not at creation
            # and never from a reply. A conversation whose first stored row is
            # an assistant message is a bug somewhere else, and titling it with
            # Zaram's own words would hide that behind a plausible label.
            if not str(row["title"] or "").strip() and role == USER:
                conn.execute(
                    "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                    (title_from(text), now, conversation_id),
                )
            else:
                conn.execute(
                    "UPDATE conversations SET updated_at = ? WHERE id = ?",
                    (now, conversation_id),
                )
        return message

    def rename(self, conversation_id: str, title: str) -> Conversation:
        """Give a conversation a name of the user's choosing.

        Does not touch ``updated_at``. Renaming is not activity, and counting
        it as such would jump a conversation to the top of the list for a
        change to its label.
        """
        clean = title.strip()
        if not clean:
            raise ValueError("A conversation needs a title.")
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ?",
                (clean, conversation_id),
            ).rowcount
        if not changed:
            raise UnknownConversation(conversation_id)
        return self.get(conversation_id)

    def delete(self, conversation_id: str) -> None:
        """Remove a conversation and its messages. Rule 4, on the transcript.

        Facts the Spine took from it are untouched, and that is the honest
        behaviour rather than an omission — see this module's docstring.
        """
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            ).rowcount
        if not changed:
            raise UnknownConversation(conversation_id)

    # ------------------------------------------------------------------ read

    def list(
        self, *, project_id: Optional[str] = None, limit: int = 50
    ) -> List[Conversation]:
        """Conversations by last activity, most recent first.

        ``project_id=None`` means every conversation; ``""`` means the ones
        belonging to no project. Two different questions, and the signature
        keeps them apart — collapsing them is how "show me everything" quietly
        becomes "show me the unscoped ones".
        """
        where, params = "", []
        if project_id is not None:
            where = "WHERE c.project_id = ?"
            params.append(project_id)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT c.*, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                {where}
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (*params, max(1, int(limit))),
            ).fetchall()
        return [_conversation_from(row) for row in rows]

    def get(self, conversation_id: str) -> Conversation:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT c.*, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                WHERE c.id = ?
                GROUP BY c.id
                """,
                (conversation_id,),
            ).fetchone()
        if row is None:
            raise UnknownConversation(conversation_id)
        return _conversation_from(row)

    def messages(self, conversation_id: str) -> List[Message]:
        """Every message, in order. Raises if the conversation is unknown.

        Raises rather than returning ``[]``, because an empty conversation and
        one that does not exist are different answers — and a caller handed
        ``[]`` for a bad id renders an empty transcript as though it were real.
        """
        with self._connect() as conn:
            known = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if known is None:
                raise UnknownConversation(conversation_id)
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY seq",
                (conversation_id,),
            ).fetchall()
        return [_message_from(row) for row in rows]


def _conversation_from(row: sqlite3.Row) -> Conversation:
    keys = row.keys()
    return Conversation(
        id=row["id"],
        title=row["title"],
        project_id=row["project_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        message_count=int(row["message_count"]) if "message_count" in keys else 0,
    )


def _message_from(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"],
        conversation_id=row["conversation_id"],
        seq=int(row["seq"]),
        role=row["role"],
        text=row["text"],
        created_at=row["created_at"],
        model=row["model"],
        locality=row["locality"],
    )


def default_db_path() -> str:
    """Where the session store lives.

    Its own variable first, then ``ZARAM_DATA_DIR``, then the platform
    default — the precedence `core.paths.in_data_dir` keeps for every store, so
    "which variable moves this one" has one answer.
    """
    from core.paths import in_data_dir

    return in_data_dir(DEFAULT_DB_NAME, "ZARAM_CONVERSATIONS_DB")
