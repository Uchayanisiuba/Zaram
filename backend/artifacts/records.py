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

There is no hard ``delete``, and the reasoning for that has been revised rather
than abandoned — 7 September 2026, at the maintainer's request for a Work
surface where files can be selected and removed.

What this paragraph used to say was that removing the *file* is the operating
system's job and Zaram has no capability to do it, so a record must outlive the
session. Half of that still stands and half of it was doing the wrong job. It
was right that **generation** must never be able to destroy a document — that
is `store.py`'s property, enforced by a source scan, and it is untouched. It was
wrong as an answer to the *user*, who has rule 4 on their side and who
reasonably expects a screen listing their files to be able to remove one.

So there is a `set_trashed` and a `restore`, and no statement anywhere that
unlinks. Neither is named for deletion, and that is this store's own guard
speaking rather than a style choice — `TestTheRecordStoreHasNoGeneralMutation`
refuses a method whose name contains *delete* or *remove*, and it was right to:
nothing here removes anything. The file has been moved to a trash folder by
`artifacts.trash` and these set and clear the flag that says so, which is a
different fact from "gone".

The record is **marked**, never dropped, because undo needs something to restore
*to*:
without the record there is no provenance, no conversation and no claims, and
"undo" would mean rebuilding a record from a filename — the invented value this
codebase refuses everywhere else. Every read filters the marked ones out, as a
base clause rather than as something callers remember.

`forget_at_path` remains a different thing and stays narrow: that is the staging
sweeper dropping the record of a file that was never kept.

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
import time
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

            # When the user put it in the trash, or NULL. Added rather than included in
            # the CREATE, because `CREATE TABLE IF NOT EXISTS` does nothing at
            # all to a table that already exists — every database written
            # before this column would keep the old shape and every query
            # naming it would fail on exactly the machines that have work in
            # them. Checked and added is the migration; there is no framework
            # here and one column does not earn one.
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
            }
            if "trashed_at" not in columns:
                conn.execute("ALTER TABLE artifacts ADD COLUMN trashed_at REAL")

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

    def set_location(self, artifact_id: str, path: str, filename: str) -> bool:
        """Where the file is now, after it moved out of staging.

        The one thing that legitimately changes a record's path. `put` refuses
        to replace a row for good reasons — a silent replace turns a bug
        upstream into lost provenance — so keeping an image is a narrow update
        here rather than a re-insert, and the id, the sources and the claims
        survive it. The user kept *this* picture, not a copy of it.

        Filename travels with the path because `write_new` increments on
        collision: the kept file may be `blue-2.png` where the staged one was
        `blue.png`, and a record naming a file that is not there is what makes
        Work show a card that opens onto nothing.
        """
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE artifacts SET path = ?, filename = ? WHERE id = ?",
                (path, filename, artifact_id),
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

    def forget_at_path(self, path: str) -> int:
        """Drop the record for a file that has been cleared from staging.

        **The only removal in this class, and it is narrow on purpose.** It
        deletes by *path* rather than by id so it cannot be aimed: the sweeper
        has just unlinked a file and is naming the thing it removed, and there
        is no call shape here that lets anything delete an arbitrary record.

        This is not a hole in the no-delete rule. That rule is about the write
        path in `store.py`, which still cannot remove a file from the output
        folder. What is being forgotten here is the record of something that
        was never saved — an image the user was shown a countdown for and did
        not keep. A record outliving its file is what makes Work show a card
        that opens onto nothing.
        """
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM artifacts WHERE path = ?", (path,))
            return cursor.rowcount

    def set_trashed(self, artifact_id: str, when: Optional[float] = None) -> bool:
        """Mark a record as put in the trash by the user. Returns whether one was.

        **Named for what it does rather than for what it is for**, and the
        rename was forced by this store's own guard —
        `TestTheRecordStoreHasNoGeneralMutation` refuses a function whose name
        contains *delete* or *remove*. It was right to: nothing here removes
        anything. The file has been moved to a trash folder by
        `artifacts.trash` and this sets the flag that says so, which is a
        different fact from "gone" and has to read as one to anybody scanning
        the method list.

        **Marked, not dropped, and that is what makes undo possible at all.**
        The file itself is moved to the trash by `artifacts.trash`; if the
        record went with it there would be nothing left to restore *to* — no
        provenance, no conversation, no claims — and "undo" would mean
        recreating a record from a filename, which is the invented value this
        codebase refuses everywhere else.

        Distinct from `forget_at_path`, which is the staging sweeper dropping
        the record of a file that was never kept. That one is a record with no
        file; this is a file the user put away.
        """
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE artifacts SET trashed_at = ? WHERE id = ? AND trashed_at IS NULL",
                (float(when if when is not None else time.time()), artifact_id),
            )
            return cursor.rowcount > 0

    def restore(self, artifact_id: str) -> bool:
        """Undo a `set_trashed`. Returns whether anything changed."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE artifacts SET trashed_at = NULL "
                "WHERE id = ? AND trashed_at IS NOT NULL",
                (artifact_id,),
            )
            return cursor.rowcount > 0

    # ---------------------------------------------------------------- reading

    def get(self, artifact_id: str, *, include_trashed: bool = False) -> Optional[Artifact]:
        """One record.

        Deleted ones are hidden by default and reachable by asking, because the
        two callers want opposite things: Work wants the listing a user sees,
        and restore has to read a record precisely *because* it is deleted. A
        single answer would make one of them wrong, and the dangerous direction
        is the default — a `get` that returned deleted records to everything
        would put removed files back in the picker.
        """
        clause = "" if include_trashed else " AND trashed_at IS NULL"
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM artifacts WHERE id = ?{clause}", (artifact_id,)
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
        # Removed records never appear in a listing. Applied as a base
        # clause rather than left to callers, because "did you remember to
        # exclude the deleted ones" is a question every future caller would
        # have to answer correctly, and the cost of one getting it wrong is a
        # file the user deleted showing up in Work.
        clauses: List[str] = ["trashed_at IS NULL"]
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

        where = f" WHERE {' AND '.join(clauses)}"
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
        clauses: List[str] = ["trashed_at IS NULL"]
        params: List[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)

        where = f" WHERE {' AND '.join(clauses)}"
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
                "WHERE project_id != '' AND trashed_at IS NULL "
                "GROUP BY project_id ORDER BY project_id"
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
                "SELECT COUNT(*) AS n FROM artifacts "
                "WHERE project_id = ? AND trashed_at IS NULL",
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
    from core.paths import in_data_dir

    return in_data_dir(DEFAULT_DB_NAME, "ZARAM_ARTIFACTS_DB")
