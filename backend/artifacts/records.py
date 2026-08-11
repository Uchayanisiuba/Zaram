"""Where artifact records live. The files live next door, in ``store.py``.

Two stores, deliberately, because they hold different things and have different
rules. ``ArtifactStore`` creates files and cannot unmake them. This holds the
record — provenance, the conversation that produced it, the HTML it was rendered
from — and is what Work reads.

What this store will not do
---------------------------
There is no general ``update``. The module this package replaced kept artifacts
in a dict and exposed an ``update()`` that ``setattr``'d any attribute passed to
it, and that is how a provenance record silently becomes wrong: nothing in the
signature says which fields are safe to move. So mutation here is one named
method for the one field the user actually controls
(:meth:`set_remember_override`), and adding a second requires writing a second
named method — which is a conversation, rather than a keyword argument nobody
reviews.

There is no ``delete`` either, and that is a narrower claim than it sounds.
CLAUDE.md's rule 4 is about *facts*: the user can correct or delete anything in
the Spine and the answers change. An artifact is not a fact — it is a file that
exists on disk, and a record saying "this file came from that conversation"
stops being true the moment it is removed while the file remains. Removing the
*file* is the operating system's job, and Zaram deliberately has no capability
to do it. So the honest shape is a record that outlives the session, and a
"don't remember this" override for the question the user is actually asking,
which is whether the contents feed recall.

``html`` is stored, and it is the largest column by far. It is here because it
is the source of truth for every re-export: a user asking for the PDF version of
a document generated last month must not get a re-render from a model that has
since changed its mind. The file on disk is one rendering; this is what it was
rendered from.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from .contracts import Artifact, ArtifactKind, ArtifactSource, Claim, Origin

logger = logging.getLogger(__name__)

DEFAULT_DB_NAME = "artifacts.db"


class ArtifactRecords:
    """Artifact records on SQLite. Insert, read, and one narrow flag."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_schema()

    # ---------------------------------------------------------------- schema

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=10)
        conn.row_factory = sqlite3.Row
        # Same reason as the egress log: Work reading must not block a
        # generation writing. A surface that stalls the thing it displays gets
        # read as the generation having failed.
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id                 TEXT    PRIMARY KEY,
                    filename           TEXT    NOT NULL,
                    kind               TEXT    NOT NULL,
                    project_id         TEXT    NOT NULL DEFAULT '',
                    origin             TEXT    NOT NULL,
                    created_at         REAL    NOT NULL,
                    size_bytes         INTEGER NOT NULL DEFAULT 0,
                    path               TEXT,
                    html               TEXT    NOT NULL DEFAULT '',
                    conversation_id    TEXT    NOT NULL DEFAULT '',
                    conversation_title TEXT    NOT NULL DEFAULT '',
                    sources            TEXT    NOT NULL DEFAULT '[]',
                    claims             TEXT    NOT NULL DEFAULT '[]',
                    indexed            INTEGER NOT NULL DEFAULT 0,
                    remember_override  INTEGER
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifacts_created "
                "ON artifacts(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifacts_project "
                "ON artifacts(project_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifacts_conversation "
                "ON artifacts(conversation_id)"
            )

    # ---------------------------------------------------------------- writing

    def put(self, artifact: Artifact) -> Artifact:
        """Store a record. Fails rather than replacing one that already exists.

        `INSERT` and not `INSERT OR REPLACE`, for the same reason the file path
        uses `open(path, "xb")`: a silent replace turns a bug upstream into lost
        provenance, and the loss is discovered later by someone reading a
        document whose citations point at the wrong conversation.
        """
        with self._lock, self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO artifacts (
                        id, filename, kind, project_id, origin, created_at,
                        size_bytes, path, html, conversation_id,
                        conversation_title, sources, claims, indexed,
                        remember_override
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        artifact.id,
                        artifact.filename,
                        artifact.kind.value,
                        artifact.project_id,
                        artifact.origin.value,
                        artifact.created_at,
                        artifact.size_bytes,
                        artifact.path,
                        artifact.html,
                        artifact.conversation_id,
                        artifact.conversation_title,
                        json.dumps([s.to_dict() for s in artifact.sources]),
                        json.dumps([c.to_dict() for c in artifact.claims]),
                        int(artifact.indexed),
                        None
                        if artifact.remember_override is None
                        else int(artifact.remember_override),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise DuplicateArtifact(
                    f"an artifact with id {artifact.id!r} is already stored"
                ) from error

        return artifact

    def set_remember_override(self, artifact_id: str, remember: Optional[bool]) -> bool:
        """The "Don't remember this" control on the file card.

        `None` is not the same as `False`: None means the user has not expressed
        a preference and the default applies, False is a refusal. Collapsing the
        two would make "I haven't decided" and "no" indistinguishable, and the
        default is allowed to change while a refusal is not.
        """
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE artifacts SET remember_override = ? WHERE id = ?",
                (None if remember is None else int(remember), artifact_id),
            )
            return cursor.rowcount > 0

    def set_project(self, artifact_id: str, project_id: str) -> bool:
        """Move an artifact into a project, out of one, or between two.

        The empty string means *no project*, which is the same value a file
        gets when it is generated outside one — so unassigning restores the
        original state rather than inventing a third one. There is no "None"
        here for the same reason `project_id` is `NOT NULL DEFAULT ''`: two
        spellings of "nowhere" is one more than the filter can ask about.

        Whether the destination project exists is not this layer's question.
        Records store what they are told; the route validates, because that is
        where the caller can be answered with a 400 that says why.
        """
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE artifacts SET project_id = ? WHERE id = ?",
                (project_id, artifact_id),
            )
            return cursor.rowcount > 0

    # ---------------------------------------------------------------- reading

    def get(self, artifact_id: str) -> Optional[Artifact]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE id = ?", (artifact_id,)
            ).fetchone()
        return _from_row(row) if row else None

    def list(
        self,
        *,
        project_id: Optional[str] = None,
        kind: Optional[str] = None,
        conversation_id: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Artifact]:
        """Newest first, which is the order Work shows and the only one asked for."""
        clauses: List[str] = []
        params: List[Any] = []

        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if conversation_id:
            clauses.append("conversation_id = ?")
            params.append(conversation_id)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params += [limit, offset]

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM artifacts{where} "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()

        return [_from_row(row) for row in rows]

    def count(
        self, *, project_id: Optional[str] = None, kind: Optional[str] = None
    ) -> int:
        clauses: List[str] = []
        params: List[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            return int(
                conn.execute(
                    f"SELECT COUNT(*) FROM artifacts{where}", params
                ).fetchone()[0]
            )

    def projects(self) -> List[Dict[str, Any]]:
        """The projects that actually have artifacts, with their counts.

        Derived rather than stored. A projects table would be a second place for
        the same truth, and the first thing it would do is disagree — Work would
        offer a filter for a project with nothing in it.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT project_id, COUNT(*) AS n FROM artifacts "
                "WHERE project_id != '' GROUP BY project_id ORDER BY project_id"
            ).fetchall()

        return [{"id": row["project_id"], "count": row["n"]} for row in rows]

    def count_for_project(self, project_id: str) -> int:
        """How many artifacts are assigned to a project.

        Read before deleting one, so the confirmation can say what is in it.
        Counted here rather than cached on the project record, because a count
        stored in two places is a count that disagrees with itself.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM artifacts WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return int(row["n"])


class DuplicateArtifact(ValueError):
    """That id is already stored. Records are written once."""


def _from_row(row: sqlite3.Row) -> Artifact:
    return Artifact(
        id=row["id"],
        filename=row["filename"],
        kind=_kind(row["kind"]),
        project_id=row["project_id"],
        origin=Origin(row["origin"]),
        created_at=row["created_at"],
        size_bytes=row["size_bytes"],
        path=row["path"],
        html=row["html"],
        conversation_id=row["conversation_id"],
        conversation_title=row["conversation_title"],
        sources=[ArtifactSource(**item) for item in json.loads(row["sources"])],
        claims=[Claim(**item) for item in json.loads(row["claims"])],
        indexed=bool(row["indexed"]),
        remember_override=(
            None if row["remember_override"] is None else bool(row["remember_override"])
        ),
    )


def _kind(value: str) -> ArtifactKind:
    """A stored kind this build does not recognise falls back to `document`.

    A future version adding a kind, then the user rolling back, must not make
    Work unopenable — one unreadable row would take the whole surface with it.
    Reading it as a document is wrong in the label and right in every other
    field, which is the better failure.
    """
    try:
        return ArtifactKind(value)
    except ValueError:
        logger.warning("Unknown artifact kind %r; showing it as a document", value)
        return ArtifactKind.DOCUMENT


def default_db_path() -> str:
    """Beside the other stores, overridable for tests and packaging."""
    override = os.getenv("ZARAM_ARTIFACTS_DB")
    if override:
        return override
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", DEFAULT_DB_NAME)
