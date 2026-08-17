"""Knowledge domains — a named retrieval scope over the user's own sources.

**A domain is not a folder.** `CLAUDE.md` is explicit: if it only groups files
it is a filter, and it has to change answers. So the store here exists to
answer one question at recall time — *which facts belong to this domain* — and
everything else it does is in service of that.

Four properties, each load-bearing and each guarded by a test:

**A retrieval scope.** `fact_ids_for` is the point of the whole module. A
domain that could not narrow recall would be a label.

**Many-to-many, never a tree.** A contract is Clients *and* Legal. The link
table is what makes that possible, and a parent column is what would quietly
make it impossible — so there is no parent column, and there never should be.
A hierarchy is also rule 7h smuggled back in: it asks the user to decide, in
advance, the one place a document lives.

**Every domain carries a one-line description.** Not decoration. Routing reads
it to know when to reach for a domain, and the reply uses it to say *"answered
from your Investing domain"*. A domain with no description cannot be routed to
by anything except its name.

**A domain is the shareable unit** — the thing that will sync, that a team will
share, and that a pack eventually is. That is why it has an id, a name and a
description of its own rather than being a query saved somewhere.

One thing this module deliberately does not do
----------------------------------------------
It does not hold facts, and it does not copy them. *One memory, many domains* —
domains scope retrieval and never fragment the Spine into per-domain silos,
which is the trap custom GPTs fell into and the reason nothing compounds there.
A domain is a set of sources; the facts stay where they are.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DB_NAME = "domains.db"

#: A description is required, and this is how short it may be. Routing reads it
#: to decide when a domain is worth reaching for, so "x" buys nothing — but a
#: hard floor that rejected a real short answer would be worse than a soft one.
MIN_DESCRIPTION = 3

#: One line, not a document. The reply says "answered from your Investing
#: domain — the funds and positions you track", and a paragraph there is a
#: paragraph in the middle of an answer.
MAX_DESCRIPTION = 200
MAX_NAME = 80


class DomainError(ValueError):
    """A domain could not be created or changed, with a reason for a person."""


class KnowledgeDomains:
    """Domains, and which sources belong to them."""

    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._create()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _create(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS domains (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL UNIQUE,
                    -- Required, and required to say something. Routing reads
                    -- this to decide when to reach for the domain, and the
                    -- reply quotes it back when it does.
                    description TEXT NOT NULL,
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL
                );

                -- Many-to-many, and that is the whole design. A contract is
                -- Clients *and* Legal. There is no parent column here and
                -- adding one would turn a scope into a hierarchy, which is the
                -- one shape `CLAUDE.md` rules out.
                CREATE TABLE IF NOT EXISTS domain_sources (
                    domain_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    linked_at REAL NOT NULL,
                    PRIMARY KEY (domain_id, source_id),
                    FOREIGN KEY (domain_id) REFERENCES domains(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_domain_sources_source
                    ON domain_sources(source_id);
                """
            )

    # -- writing ------------------------------------------------------------ #

    @staticmethod
    def _clean(name: str, description: str) -> tuple[str, str]:
        """Validate once, for create and rename alike.

        Refuses rather than silently trimming to nothing: a domain called `"  "`
        would list as a blank row the user cannot select, and a domain with no
        description cannot be routed to.
        """
        name = (name or "").strip()
        description = (description or "").strip()

        if not name:
            raise DomainError("A domain needs a name.")
        if len(name) > MAX_NAME:
            raise DomainError(f"That name is longer than {MAX_NAME} characters.")
        if len(description) < MIN_DESCRIPTION:
            raise DomainError(
                "A domain needs a line saying what is in it — that is how Zaram "
                "knows when to reach for it, and how a reply can say where an "
                "answer came from."
            )
        if len(description) > MAX_DESCRIPTION:
            raise DomainError(
                f"Keep the description under {MAX_DESCRIPTION} characters — it is "
                "shown inside answers."
            )
        return name, description

    def create(self, name: str, description: str) -> dict[str, Any]:
        name, description = self._clean(name, description)
        now = time.time()
        domain_id = f"dom-{uuid.uuid4().hex[:12]}"
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO domains (id, name, description, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (domain_id, name, description, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise DomainError(f"There is already a domain called {name}.") from exc
        return {
            "id": domain_id,
            "name": name,
            "description": description,
            "created_at": now,
            "updated_at": now,
            "source_ids": [],
        }

    def rename(self, domain_id: str, name: str, description: str) -> bool:
        name, description = self._clean(name, description)
        with self._lock, self._connect() as connection:
            try:
                cursor = connection.execute(
                    "UPDATE domains SET name = ?, description = ?, updated_at = ? WHERE id = ?",
                    (name, description, time.time(), domain_id),
                )
            except sqlite3.IntegrityError as exc:
                raise DomainError(f"There is already a domain called {name}.") from exc
            return cursor.rowcount > 0

    def link(self, domain_id: str, source_id: str) -> bool:
        """Put a source in a domain. Idempotent — linking twice is not an error.

        A source may be in any number of domains at once; that is the point.
        """
        with self._lock, self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM domains WHERE id = ?", (domain_id,)
            ).fetchone()
            if not exists:
                return False
            connection.execute(
                "INSERT OR IGNORE INTO domain_sources (domain_id, source_id, linked_at)"
                " VALUES (?, ?, ?)",
                (domain_id, source_id, time.time()),
            )
            return True

    def unlink(self, domain_id: str, source_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM domain_sources WHERE domain_id = ? AND source_id = ?",
                (domain_id, source_id),
            )
            return cursor.rowcount > 0

    def remove(self, domain_id: str) -> bool:
        """Delete a domain. **Its sources and their facts are untouched.**

        A domain is a way of looking at what is already there, so removing one
        removes a lens and nothing else. This is the opposite of withdrawing a
        source, which does take facts with it — and the difference is worth
        being sure of, because the two live on the same screen.
        """
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
            connection.execute("DELETE FROM domain_sources WHERE domain_id = ?", (domain_id,))
            return cursor.rowcount > 0

    def forget_source(self, source_id: str) -> int:
        """Drop a withdrawn source from every domain that held it.

        Called when a source is removed. Without it a domain keeps pointing at
        a source that no longer exists, and the count beside its name counts
        something that is gone.
        """
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM domain_sources WHERE source_id = ?", (source_id,)
            )
            return cursor.rowcount

    # -- reading ------------------------------------------------------------ #

    def all(self) -> list[dict[str, Any]]:
        """Every domain with the sources in it. What Knowledge lists."""
        with self._lock, self._connect() as connection:
            rows = connection.execute("SELECT * FROM domains ORDER BY name").fetchall()
            links = connection.execute(
                "SELECT domain_id, source_id FROM domain_sources"
            ).fetchall()

        by_domain: dict[str, list[str]] = {}
        for link in links:
            by_domain.setdefault(link["domain_id"], []).append(link["source_id"])

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "source_ids": by_domain.get(row["id"], []),
            }
            for row in rows
        ]

    def get(self, domain_id: str) -> dict[str, Any] | None:
        for domain in self.all():
            if domain["id"] == domain_id:
                return domain
        return None

    def source_ids(self, domain_id: str) -> list[str]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT source_id FROM domain_sources WHERE domain_id = ?", (domain_id,)
            ).fetchall()
        return [row["source_id"] for row in rows]


def default_db_path() -> str:
    from core.paths import in_data_dir

    return in_data_dir(DEFAULT_DB_NAME, "ZARAM_DOMAINS_DB")
