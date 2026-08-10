"""Project records on SQLite.

Deliberately small. A project is a name, a type and a creation time — the
things that cannot be derived from anything else. Everything a project appears
to contain (artifacts, facts, later a plan) lives in its own store and points
back here by id, because a project that owned copies of them would be a fourth
place for the same truth.

**Deleting is the operation with teeth**, and it is why this file has more
comment than code. A project holds facts scoped to it and files assigned to it.
Rule 4 says the user can delete any stored fact and the answers change; it does
not say a container may take its contents with it silently. So deletion states
what happens to the contents and the caller has to choose — see
:meth:`ProjectRecords.delete`.
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

logger = logging.getLogger(__name__)

DEFAULT_DB_NAME = "projects.db"


class ProjectType(str, Enum):
    """What kind of work this is, which is what activates a pack.

    `CLAUDE.md`: "Projects have a type, chosen once at creation, and that choice
    activates the pack." Chosen at creation because that is the only moment the
    user actually knows — and because rule 7e forbids asking a question the
    system could answer from behaviour, which this one cannot be.

    `general` exists so the question is answerable by someone who does not want
    to decide yet. A required choice at creation would be a wall in front of the
    first project anyone makes.
    """

    GENERAL = "general"
    BUSINESS = "business"
    CODING = "coding"
    THREE_D = "3d"
    MCP = "mcp"


class UnknownProject(KeyError):
    """No project with that id."""


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    type: ProjectType
    created_at: float
    #: Free text the user wrote about the project. Not parsed, not fed to
    #: recall — it is a label for a human, and inventing structure in it would
    #: be modelling their business for them.
    note: str = ""

    @property
    def scope(self) -> str:
        """The scope string facts in this project carry: ``project:<id>``.

        Spelled here as well as in `runtimes.memory.contracts.project_scope` is
        exactly the duplication rule 7i warns about, so it is *not* spelled
        here — this delegates. The property exists so callers have one obvious
        way to get from a project to its scope.
        """
        from runtimes.memory.contracts import project_scope

        return project_scope(self.id)


def slugify(name: str) -> str:
    """A stable, readable id from a name.

    Readable because it appears in `project:<id>` on every fact and in the
    egress log, and `project:a3f9c2` tells a user reading their own logs
    nothing. Stable because renaming must *not* change it — the id is what
    facts and artifacts point at, and a rename that re-scoped every fact would
    be a migration disguised as an edit.
    """
    # Transliterate before stripping, or accented letters vanish instead of
    # folding: "Ünïcodé Studio" became "n-cod-studio", and a French, German or
    # Yorùbá business name would come out as debris. NFKD splits a letter from
    # its accent so the letter survives the ASCII filter and the accent does not.
    decomposed = unicodedata.normalize("NFKD", name.strip())
    folded = decomposed.encode("ascii", "ignore").decode("ascii")

    slug = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    # Not empty, and not so long it is unreadable in a log line. A name written
    # entirely in a non-Latin script folds to nothing, which is a real case and
    # not an error — it gets a generated id rather than a refusal.
    return slug[:48] or f"project-{uuid.uuid4().hex[:8]}"


class ProjectRecords:
    """Projects on SQLite. Create, list, rename, retype, delete."""

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
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id         TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    type       TEXT NOT NULL DEFAULT 'general',
                    created_at REAL NOT NULL,
                    note       TEXT NOT NULL DEFAULT ''
                )
                """
            )

    # ------------------------------------------------------------------ read

    def list(self) -> List[Project]:
        """Every project, oldest first.

        Creation order rather than alphabetical: it is the order the user built
        them in, which is closer to how they think about them than the alphabet
        is, and it keeps a newly created project at the end where it was just
        added rather than jumping into the middle of the list.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM projects ORDER BY created_at"
            ).fetchall()
        return [_from_row(row) for row in rows]

    def get(self, project_id: str) -> Project:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if row is None:
            raise UnknownProject(project_id)
        return _from_row(row)

    def exists(self, project_id: str) -> bool:
        with self._connect() as conn:
            return (
                conn.execute(
                    "SELECT 1 FROM projects WHERE id = ?", (project_id,)
                ).fetchone()
                is not None
            )

    # ----------------------------------------------------------------- write

    def create(
        self,
        name: str,
        *,
        type: ProjectType = ProjectType.GENERAL,
        note: str = "",
        project_id: str = "",
    ) -> Project:
        """Make a project. Returns the stored record, id included.

        A colliding slug gets a numeric suffix rather than an error. Two
        projects called "Harbour Lane" is a thing a person legitimately does —
        a rebuild, a second season — and refusing the second one would make them
        invent a name to satisfy a database.
        """
        clean = name.strip()
        if not clean:
            raise ValueError("A project needs a name.")

        base = project_id.strip() or slugify(clean)
        with self._lock, self._connect() as conn:
            candidate, n = base, 2
            while conn.execute(
                "SELECT 1 FROM projects WHERE id = ?", (candidate,)
            ).fetchone():
                candidate, n = f"{base}-{n}", n + 1

            project = Project(
                id=candidate,
                name=clean,
                type=ProjectType(type),
                created_at=time.time(),
                note=note.strip(),
            )
            conn.execute(
                "INSERT INTO projects (id, name, type, created_at, note) "
                "VALUES (?, ?, ?, ?, ?)",
                (project.id, project.name, project.type.value, project.created_at, project.note),
            )
        logger.info("Created project %s (%s)", project.id, project.type.value)
        return project

    def rename(self, project_id: str, name: str) -> Project:
        """Change the display name. **The id never moves.**

        Facts carry `project:<id>` and artifacts carry `project_id`. Re-slugging
        on rename would orphan every one of them, which is a migration wearing
        the costume of an edit — so the readable id is fixed at creation and a
        rename is exactly what it says.
        """
        clean = name.strip()
        if not clean:
            raise ValueError("A project needs a name.")
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "UPDATE projects SET name = ? WHERE id = ?", (clean, project_id)
            ).rowcount
        if not changed:
            raise UnknownProject(project_id)
        return self.get(project_id)

    def set_type(self, project_id: str, type: ProjectType) -> Project:
        """Change the type, which changes which pack is active.

        `CLAUDE.md` says the type is chosen "once at creation". This exists
        because the alternative to changing it is deleting the project and
        remaking it, which would take the facts and files with it — a far worse
        outcome than letting someone correct a choice they made in ten seconds
        before they knew what the project was.
        """
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "UPDATE projects SET type = ? WHERE id = ?",
                (ProjectType(type).value, project_id),
            ).rowcount
        if not changed:
            raise UnknownProject(project_id)
        return self.get(project_id)

    def set_note(self, project_id: str, note: str) -> Project:
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "UPDATE projects SET note = ? WHERE id = ?", (note.strip(), project_id)
            ).rowcount
        if not changed:
            raise UnknownProject(project_id)
        return self.get(project_id)

    def delete(self, project_id: str) -> None:
        """Remove the project record itself, and **only** that.

        This does not touch facts or artifacts, and the omission is the design.
        A project holds things that outlive it: rule 4 gives the user power over
        their own facts, and a container quietly exercising that power on their
        behalf is how someone loses a client's rates by tidying up a sidebar.

        Deciding what happens to the contents belongs one layer up, where the
        counts are known and the user can be shown them — see the delete
        endpoint, which requires the caller to say. This method is the last step
        of whichever choice was made, never the whole of it.
        """
        with self._lock, self._connect() as conn:
            changed = conn.execute(
                "DELETE FROM projects WHERE id = ?", (project_id,)
            ).rowcount
        if not changed:
            raise UnknownProject(project_id)
        logger.info("Deleted project record %s", project_id)


def _from_row(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        # Tolerant of a type this build does not know: a project made by a newer
        # version must still open, degraded to general, rather than raise and
        # take the whole list with it.
        type=_type_or_general(row["type"]),
        created_at=row["created_at"],
        note=row["note"],
    )


def _type_or_general(value: str) -> ProjectType:
    try:
        return ProjectType(value)
    except ValueError:
        logger.warning("Unknown project type %r, treating as general", value)
        return ProjectType.GENERAL


def default_db_path() -> str:
    return os.getenv(
        "ZARAM_PROJECTS_DB",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), DEFAULT_DB_NAME),
    )
