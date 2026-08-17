"""Where ingest outcomes live, so Knowledge can show them and the user can act.

The service already returns an outcome per file. Without this they exist for
the length of one HTTP request and then stop existing, which makes the whole
"failures must be loud" rule a matter of whether somebody happened to be
watching the response stream. A file that gave nothing back has to still be
sayable tomorrow.

Two tables, and the split is the same one `artifacts/` makes. A **source** is a
folder the user pointed at — it persists, it is what Knowledge lists, and it
carries the per-source privacy policy that rule 5 requires. An **outcome** is
what happened to one file on one run; re-ingesting replaces the outcomes for
that source rather than accumulating them, because a list showing yesterday's
failure beside today's success is worse than either.

What this store will not do
---------------------------
There is no general `update`. Mutation is one named method per field the user
actually controls — `acknowledge_notice`, `set_policy` — for the reason written
out in `artifacts/records.py`: a signature that takes arbitrary attributes is
how a record silently becomes wrong.

Deleting a *source* is real and is offered, because it is the user withdrawing
a folder. Rule 4 says a stored fact can be removed and the answers change, so
removing a source has to take its facts with it; the fact ids are kept on the
outcome for exactly that.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

from .contracts import IngestOutcome, IngestStatus

logger = logging.getLogger(__name__)

DEFAULT_DB_NAME = "ingest.db"


class IngestRecords:
    """Ingest sources and per-file outcomes on SQLite."""

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
        return connection

    def _create(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id           TEXT PRIMARY KEY,
                    root         TEXT NOT NULL UNIQUE,
                    added_at     REAL NOT NULL,
                    scanned_at   REAL NOT NULL,
                    seconds      REAL NOT NULL DEFAULT 0,
                    -- Rule 5: nothing leaves without an explicit per-item
                    -- policy. Default deny is the only safe default here, and
                    -- it is a column rather than a global setting because the
                    -- rule is per-source.
                    policy       TEXT NOT NULL DEFAULT 'local_only',
                    -- Whether the user has been told about this run's problems
                    -- in conversation. One notice, not one per reply.
                    notified     INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS outcomes (
                    id          TEXT PRIMARY KEY,
                    source_id   TEXT NOT NULL,
                    path        TEXT NOT NULL,
                    name        TEXT NOT NULL,
                    status      TEXT NOT NULL,
                    parser      TEXT NOT NULL DEFAULT '',
                    chars       INTEGER NOT NULL DEFAULT 0,
                    pages       INTEGER NOT NULL DEFAULT 0,
                    fact_ids    TEXT NOT NULL DEFAULT '[]',
                    reason      TEXT NOT NULL DEFAULT '',
                    remedy      TEXT NOT NULL DEFAULT '',
                    seconds     REAL NOT NULL DEFAULT 0,
                    recorded_at REAL NOT NULL,
                    FOREIGN KEY (source_id) REFERENCES sources(id)
                );

                CREATE INDEX IF NOT EXISTS idx_outcomes_source
                    ON outcomes(source_id);
                CREATE INDEX IF NOT EXISTS idx_outcomes_status
                    ON outcomes(source_id, status);
                """
            )

    # -- sources ----------------------------------------------------------- #

    def upsert_source(self, root: str, seconds: float = 0.0) -> str:
        """Record that this folder was scanned. Returns the source id.

        Re-scanning an existing folder keeps its id and its policy — the user
        set that deliberately and a re-scan is not a reason to forget it — and
        clears `notified`, because a new run has new problems to mention.
        """
        root = os.path.abspath(root)
        now = time.time()
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM sources WHERE root = ?", (root,)
            ).fetchone()
            if row:
                connection.execute(
                    "UPDATE sources SET scanned_at = ?, seconds = ?, notified = 0 WHERE id = ?",
                    (now, seconds, row["id"]),
                )
                return str(row["id"])
            source_id = f"src-{uuid.uuid4().hex[:12]}"
            connection.execute(
                "INSERT INTO sources (id, root, added_at, scanned_at, seconds) "
                "VALUES (?, ?, ?, ?, ?)",
                (source_id, root, now, now, seconds),
            )
            return source_id

    _INSERT_OUTCOME = (
        "INSERT INTO outcomes (id, source_id, path, name, status, parser, chars,"
        " pages, fact_ids, reason, remedy, seconds, recorded_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    @staticmethod
    def _row(source_id: str, outcome: IngestOutcome, now: float) -> tuple[Any, ...]:
        return (
            f"out-{uuid.uuid4().hex[:12]}",
            source_id,
            outcome.path,
            outcome.name,
            outcome.status.value,
            outcome.parser,
            outcome.chars,
            outcome.pages,
            json.dumps(list(outcome.fact_ids)),
            outcome.reason,
            outcome.remedy,
            outcome.seconds,
            now,
        )

    def record_outcomes(self, source_id: str, outcomes: list[IngestOutcome]) -> None:
        """Replace this source's outcomes with the ones from the latest run.

        Replace rather than append: a list showing yesterday's failure beside
        today's success for the same file cannot be read, and the user's
        question is always "what is wrong *now*".

        **Only correct when the run saw the whole source.** A folder scan does;
        a drop of two files into the shared uploads directory does not, and
        calling this for one would delete the other forty files' rows — losing
        their `fact_ids` and with them the only route rule 4 has to take those
        facts back out of the Spine. `merge_outcomes` is that case.
        """
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM outcomes WHERE source_id = ?", (source_id,))
            connection.executemany(
                self._INSERT_OUTCOME,
                [self._row(source_id, outcome, now) for outcome in outcomes],
            )

    def merge_outcomes(self, source_id: str, outcomes: list[IngestOutcome]) -> None:
        """Record these files' outcomes, leaving the source's others alone.

        For a run that saw only part of a source — a drop, a paste, an upload.
        Per *path* rather than wholesale, so re-reading one file still replaces
        its own row and the "what is wrong now" property holds per file; every
        other row survives, along with the fact ids that make its facts
        removable.
        """
        now = time.time()
        with self._lock, self._connect() as connection:
            for outcome in outcomes:
                connection.execute(
                    "DELETE FROM outcomes WHERE source_id = ? AND path = ?",
                    (source_id, outcome.path),
                )
                connection.execute(self._INSERT_OUTCOME, self._row(source_id, outcome, now))

    def sources(self) -> list[dict[str, Any]]:
        """Every folder, with its counts. What Knowledge lists."""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sources ORDER BY scanned_at DESC"
            ).fetchall()
            out = []
            for row in rows:
                counts = {
                    r["status"]: r["n"]
                    for r in connection.execute(
                        "SELECT status, COUNT(*) AS n FROM outcomes"
                        " WHERE source_id = ? GROUP BY status",
                        (row["id"],),
                    ).fetchall()
                }
                out.append(
                    {
                        "id": row["id"],
                        "root": row["root"],
                        "name": os.path.basename(row["root"]) or row["root"],
                        "added_at": row["added_at"],
                        "scanned_at": row["scanned_at"],
                        "seconds": row["seconds"],
                        "policy": row["policy"],
                        "notified": bool(row["notified"]),
                        "counts": counts,
                        "total": sum(counts.values()),
                        "problems": sum(
                            counts.get(s.value, 0)
                            for s in IngestStatus
                            if s.is_visible_problem
                        ),
                    }
                )
            return out

    def outcomes(
        self, source_id: str | None = None, *, problems_only: bool = False
    ) -> list[dict[str, Any]]:
        clauses, params = [], []
        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)
        if problems_only:
            marks = ",".join("?" for s in IngestStatus if s.is_visible_problem)
            clauses.append(f"status IN ({marks})")
            params.extend(s.value for s in IngestStatus if s.is_visible_problem)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                # Problems first, then largest, so the list opens on what needs
                # attention rather than on whatever sorted first alphabetically.
                f"SELECT * FROM outcomes{where} ORDER BY status ASC, chars DESC",
                params,
            ).fetchall()
        return [self._row_to_outcome(row) for row in rows]

    @staticmethod
    def _row_to_outcome(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "source_id": row["source_id"],
            "path": row["path"],
            "name": row["name"],
            "status": row["status"],
            "parser": row["parser"],
            "chars": row["chars"],
            "pages": row["pages"],
            "fact_ids": json.loads(row["fact_ids"]),
            "reason": row["reason"],
            "remedy": row["remedy"],
            "seconds": row["seconds"],
        }

    def get_outcome(self, outcome_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM outcomes WHERE id = ?", (outcome_id,)
            ).fetchone()
        return self._row_to_outcome(row) if row else None

    def replace_outcome(self, outcome_id: str, outcome: IngestOutcome) -> bool:
        """Update one file's outcome after a retry.

        Named for the one thing it does. A retry is the only reason a single
        outcome changes without a whole re-scan, and it is offered on every
        visible problem — a failure the user cannot act on is just bad news.
        """
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE outcomes SET status = ?, parser = ?, chars = ?, pages = ?,"
                " fact_ids = ?, reason = ?, remedy = ?, seconds = ?, recorded_at = ?"
                " WHERE id = ?",
                (
                    outcome.status.value,
                    outcome.parser,
                    outcome.chars,
                    outcome.pages,
                    json.dumps(list(outcome.fact_ids)),
                    outcome.reason,
                    outcome.remedy,
                    outcome.seconds,
                    time.time(),
                    outcome_id,
                ),
            )
            return cursor.rowcount > 0

    # -- the conversation notice ------------------------------------------- #

    def pending_notice(self) -> dict[str, Any] | None:
        """The problems the user has not been told about in conversation yet.

        Knowledge showing a failure only helps someone who opens Knowledge. The
        milestone says a file that gave nothing back is *mentioned in the
        conversation the first time it matters*, because the moment it matters
        is when they ask a question the missing document would have answered —
        and that is when they are looking at the conversation, not at a list.

        Returns None once acknowledged. One notice per scan, never per reply:
        a warning that repeats is one the user learns to skip.
        """
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sources WHERE notified = 0 ORDER BY scanned_at DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            problem_statuses = [s.value for s in IngestStatus if s.is_visible_problem]
            marks = ",".join("?" for _ in problem_statuses)
            problems = connection.execute(
                f"SELECT * FROM outcomes WHERE source_id = ? AND status IN ({marks})"
                " ORDER BY status ASC",
                [row["id"], *problem_statuses],
            ).fetchall()
        if not problems:
            # A clean scan is not news. Mark it seen so it never surfaces.
            self.acknowledge_notice(str(row["id"]))
            return None
        return {
            "source_id": row["id"],
            "root": row["root"],
            "name": os.path.basename(row["root"]) or row["root"],
            "problems": [self._row_to_outcome(p) for p in problems],
        }

    def acknowledge_notice(self, source_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE sources SET notified = 1 WHERE id = ?", (source_id,)
            )
            return cursor.rowcount > 0

    # -- policy and removal ------------------------------------------------- #

    def set_policy(self, source_id: str, policy: str) -> bool:
        """Rule 5: per-source, default deny. The only values are the two."""
        if policy not in {"local_only", "cloud_allowed"}:
            raise ValueError(f"unknown policy {policy!r}")
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE sources SET policy = ? WHERE id = ?", (policy, source_id)
            )
            return cursor.rowcount > 0

    def source_root(self, source_id: str) -> str | None:
        """The absolute path this source stands for, or None if unknown.

        Needed because *where* a source is decides what withdrawing it may
        delete: files under the uploads directory are copies Zaram made, and a
        scanned folder holds the user's own originals. The caller makes that
        judgement — this only reports the place.
        """
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT root FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
        return str(row["root"]) if row else None

    def remove_source(self, source_id: str) -> list[str]:
        """Forget a folder. Returns the fact ids its files produced.

        The caller deletes those from the Spine. This store does not reach into
        memory itself — rule 4 belongs to whoever owns the facts, and a store
        that quietly deleted from another store is how a correction loop gets
        two owners.
        """
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT fact_ids FROM outcomes WHERE source_id = ?", (source_id,)
            ).fetchall()
            fact_ids = [fid for row in rows for fid in json.loads(row["fact_ids"])]
            connection.execute("DELETE FROM outcomes WHERE source_id = ?", (source_id,))
            connection.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        return fact_ids
