from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any
from collections import defaultdict
from contextlib import closing

logger = logging.getLogger(__name__)

from .contracts import (
    GLOBAL_SCOPE,
    MemoryRecord,
    MemoryQuery,
    MemoryStats,
    MemoryStore,
    MemoryType,
    Origin,
    RetrievalStrategy,
)


def _origin_or_default(value: Any) -> Origin:
    """Read an origin off a row, tolerating a Spine written before M8.

    An unrecognised value becomes `CONVERSATION` rather than raising: a fact
    whose origin cannot be read is still the user's fact, and refusing to load
    the Spine over a label would lose everything to protect a footnote.
    """
    if not value:
        return Origin.CONVERSATION
    try:
        return Origin(value)
    except ValueError:
        logger.warning("Spine: unknown origin %r, reading as conversation", value)
        return Origin.CONVERSATION


class InMemoryMemoryStore(MemoryStore):
    """In-memory implementation of MemoryStore with optional persistence."""

    def __init__(self, persist_path: str | None = None):
        self._records: dict[str, MemoryRecord] = {}
        self._by_session: dict[str, list[str]] = defaultdict(list)
        self._by_user: dict[str, list[str]] = defaultdict(list)
        self._by_type: dict[MemoryType, list[str]] = defaultdict(list)
        self._persist_path = persist_path
        self._load()

    def _load(self) -> None:
        if self._persist_path and os.path.exists(self._persist_path):
            try:
                with open(self._persist_path, "r") as f:
                    data = json.load(f)
                for item in data:
                    record = MemoryRecord(**item)
                    self._records[record.id] = record
                    if record.session_id:
                        self._by_session[record.session_id].append(record.id)
                    if record.user_id:
                        self._by_user[record.user_id].append(record.id)
                    self._by_type[record.memory_type].append(record.id)
            except Exception as e:
                print(f"[MemoryStore] Failed to load from {self._persist_path}: {e}")

    def _save(self) -> None:
        if not self._persist_path:
            return
        try:
            data = [r.__dict__ for r in self._records.values()]
            with open(self._persist_path, "w") as f:
                json.dump(data, f, default=str)
        except Exception as e:
            print(f"[MemoryStore] Failed to save to {self._persist_path}: {e}")

    async def put(self, record: MemoryRecord) -> str:
        self._records[record.id] = record
        if record.session_id:
            self._by_session[record.session_id].append(record.id)
        if record.user_id:
            self._by_user[record.user_id].append(record.id)
        self._by_type[record.memory_type].append(record.id)
        self._save()
        return record.id

    async def get(self, record_id: str) -> MemoryRecord | None:
        """Read one record. Reading is not recalling — see `record_access`."""
        return self._records.get(record_id)

    async def record_access(self, record_id: str, scope: str | None = None) -> None:
        """Count one *recall* of this fact, and where it happened.

        Separate from `get` on purpose. Rule 7e makes this number load-bearing:
        facts enter provisionally, become durable through use, and decay if
        never recalled, and `decay.py` forgets anything with `access_count == 0`
        after 30 days. A count that also went up when the Memory surface merely
        listed a fact would make browsing look like use.

        It used to be a side effect of `get` here and *nowhere at all* in
        `SQLiteMemoryStore`, which is the store the product actually runs. So
        every fact read "Recalled 0 times" forever, promotion-through-use could
        never happen, and every fact was permanently a decay candidate.

        `scope` records *which* project recalled it. Rule 7i promotes a fact to
        global when it has been useful across three different projects, and a
        bare count cannot answer "three *different*" — so the identities are
        kept rather than a number.
        """
        record = self._records.get(record_id)
        if record is None:
            return
        seen = list(record.recalled_in or [])
        if scope and scope != GLOBAL_SCOPE and scope not in seen:
            seen.append(scope)
        self._records[record_id] = MemoryRecord(
            **{
                **record.__dict__,
                "access_count": record.access_count + 1,
                "last_accessed": time.time(),
                "recalled_in": seen,
            }
        )
        self._save()

    async def delete(self, record_id: str) -> bool:
        if record_id in self._records:
            record = self._records.pop(record_id)
            if record.session_id and record_id in self._by_session[record.session_id]:
                self._by_session[record.session_id].remove(record_id)
            if record.user_id and record_id in self._by_user[record.user_id]:
                self._by_user[record.user_id].remove(record_id)
            if record_id in self._by_type[record.memory_type]:
                self._by_type[record.memory_type].remove(record_id)
            self._save()
            return True
        return False

    async def query(self, query: MemoryQuery) -> list[MemoryRecord]:
        candidates = []

        if query.session_id:
            candidate_ids = self._by_session.get(query.session_id, [])
        elif query.user_id:
            candidate_ids = self._by_user.get(query.user_id, [])
        else:
            candidate_ids = []
            for mt in query.memory_types:
                candidate_ids.extend(self._by_type.get(mt, []))

        # Kept identical to the SQLite store's behaviour on purpose. Two stores
        # that disagree about whether a corrected fact can be recalled would
        # make Rule 4 depend on which backend happened to be configured.
        include_superseded = bool(query.filters.get("include_superseded"))
        filters = {k: v for k, v in query.filters.items() if k != "include_superseded"}

        for rid in candidate_ids:
            record = self._records.get(rid)
            if not record:
                continue
            if record.is_superseded and not include_superseded:
                continue
            if query.min_importance and record.importance < query.min_importance:
                continue
            if filters:
                match = True
                for k, v in filters.items():
                    if record.metadata.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            if query.time_range:
                if not (query.time_range[0] <= record.created_at <= query.time_range[1]):
                    continue
            # Same scope rule as the SQLite store. Two stores disagreeing about
            # which project's facts are visible would make a privacy boundary
            # depend on which backend happened to be configured.
            if query.scope and record.scope not in (query.scope, GLOBAL_SCOPE):
                continue
            candidates.append(record)

        # Pinned first: the user said these matter, which outranks recency.
        candidates.sort(key=lambda r: (not r.pinned, -r.created_at))
        return candidates

    async def all_records(self, include_superseded: bool = False) -> list[MemoryRecord]:
        """Every live record. Used to rebuild the index on boot.

        Superseded facts are excluded by default so a restart does not silently
        undo every correction the user has made.
        """
        return [
            r for r in self._records.values() if include_superseded or not r.is_superseded
        ]

    async def stats(self) -> MemoryStats:
        by_type = defaultdict(int)
        total_embeddings = 0
        for r in self._records.values():
            by_type[r.memory_type.value] += 1
            if r.embedding:
                total_embeddings += 1
        return MemoryStats(
            total_records=len(self._records),
            by_type=dict(by_type),
            total_embeddings=total_embeddings,
            storage_size_bytes=sum(len(r.content) for r in self._records.values()),
            last_indexed=time.time(),
        )

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "records": len(self._records),
            "persist_path": self._persist_path,
        }


class SQLiteMemoryStore(MemoryStore):
    """SQLite-backed memory store for persistence."""

    def __init__(self, db_path: str = "memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        import sqlite3

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    embedding TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    last_accessed REAL NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    session_id TEXT,
                    user_id TEXT,
                    importance REAL NOT NULL DEFAULT 0.5,
                    source TEXT NOT NULL DEFAULT 'user'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON memories(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user ON memories(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON memories(memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)")

            # Supersession, added after the first Spines were already on disk.
            # ALTER TABLE ADD COLUMN rather than a recreate, so an existing
            # Spine keeps every fact it holds — this is the user's data, and a
            # migration that drops it to simplify our code is not a trade we get
            # to make. Guarded per column so the migration is idempotent.
            existing = {r[1] for r in conn.execute("PRAGMA table_info(memories)")}
            for column, ddl in (
                ("superseded_by", "ALTER TABLE memories ADD COLUMN superseded_by TEXT"),
                ("superseded_at", "ALTER TABLE memories ADD COLUMN superseded_at REAL"),
                ("pinned", "ALTER TABLE memories ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0"),
                # M8, and the reason it lands before the alpha rather than
                # after: retrofitting scope onto facts that lack it means
                # guessing for everything already stored. `global` is the only
                # honest default for a pre-M8 fact — it was captured with no
                # project in play, so assigning one would invent a value nobody
                # entered. Scope and origin migrate together because they are
                # columns on the same rows and doing them separately is two
                # migrations over the user's data for no gain.
                ("scope", f"ALTER TABLE memories ADD COLUMN scope TEXT NOT NULL DEFAULT '{GLOBAL_SCOPE}'"),
                ("origin", f"ALTER TABLE memories ADD COLUMN origin TEXT NOT NULL DEFAULT '{Origin.CONVERSATION.value}'"),
                ("recalled_in", "ALTER TABLE memories ADD COLUMN recalled_in TEXT NOT NULL DEFAULT '[]'"),
            ):
                if column not in existing:
                    conn.execute(ddl)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_superseded ON memories(superseded_by)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scope ON memories(scope)")

    async def put(self, record: MemoryRecord) -> str:
        import sqlite3

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories
                (id, content, memory_type, metadata, embedding, created_at, updated_at,
                 access_count, last_accessed, tags, session_id, user_id, importance, source,
                 superseded_by, superseded_at, pinned, scope, origin, recalled_in)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record.id,
                    record.content,
                    record.memory_type.value,
                    json.dumps(record.metadata),
                    json.dumps(record.embedding) if record.embedding else None,
                    record.created_at,
                    record.updated_at,
                    record.access_count,
                    record.last_accessed,
                    json.dumps(record.tags),
                    record.session_id,
                    record.user_id,
                    record.importance,
                    record.source,
                    record.superseded_by,
                    record.superseded_at,
                    1 if record.pinned else 0,
                    record.scope,
                    record.origin.value if hasattr(record.origin, "value") else str(record.origin),
                    json.dumps(list(record.recalled_in or [])),
                ),
            )
        return record.id

    async def get(self, record_id: str) -> MemoryRecord | None:
        import sqlite3

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (record_id,)).fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    async def record_access(self, record_id: str, scope: str | None = None) -> None:
        """Count one recall, and where it happened. This store had none at all.

        `InMemoryMemoryStore` incremented as a side effect of `get`; this one
        did nothing, and this is the store the product runs. Every fact
        therefore read "Recalled 0 times" in the Memory surface no matter how
        often it was cited, and `decay.py` — which forgets anything never
        accessed after 30 days — saw a Spine in which nothing had ever been
        used.

        `recalled_in` is read-modify-write rather than a SQL append because it
        is a JSON set and SQLite has no set type. The window is small and the
        worst case is a lost duplicate, not a lost fact.
        """
        import sqlite3

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT recalled_in FROM memories WHERE id = ?", (record_id,)
            ).fetchone()
            if row is None:
                return
            seen = json.loads(row["recalled_in"] or "[]")
            if scope and scope != GLOBAL_SCOPE and scope not in seen:
                seen.append(scope)
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1,"
                " last_accessed = ?, recalled_in = ? WHERE id = ?",
                (time.time(), json.dumps(seen), record_id),
            )

    async def delete(self, record_id: str) -> bool:
        import sqlite3

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (record_id,))
            return cursor.rowcount > 0

    async def query(self, query: MemoryQuery) -> list[MemoryRecord]:
        import sqlite3

        where_clauses = []
        params = []

        if query.memory_types:
            placeholders = ",".join("?" * len(query.memory_types))
            where_clauses.append(f"memory_type IN ({placeholders})")
            params.extend(mt.value for mt in query.memory_types)

        if query.session_id:
            where_clauses.append("session_id = ?")
            params.append(query.session_id)

        if query.user_id:
            where_clauses.append("user_id = ?")
            params.append(query.user_id)

        if query.min_importance > 0:
            where_clauses.append("importance >= ?")
            params.append(query.min_importance)

        if query.time_range:
            where_clauses.append("created_at BETWEEN ? AND ?")
            params.extend(query.time_range)

        # Superseded facts never come back from a query. This is the half of
        # Rule 4 that makes correction mean anything: if the old fact could
        # still be recalled, the user would correct it and watch the answer stay
        # the same. `include_superseded` in filters opts back in, which only the
        # Memory surface does — to show the struck-through record.
        if not query.filters.get("include_superseded"):
            where_clauses.append("superseded_by IS NULL")

        # Rule 7i: recall needs both scopes at once. A question asked inside a
        # project draws on that project's facts *and* on what is true about the
        # user generally — "the Harbour Lane rate is 425,000" and "never send a
        # document without a summary" both bear on writing a proposal. Other
        # projects' facts are excluded, which is what makes scope a boundary
        # rather than a label.
        if query.scope:
            where_clauses.append("(scope = ? OR scope = ?)")
            params.extend([query.scope, GLOBAL_SCOPE])

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.row_factory = sqlite3.Row
            # Pinned first: the user said these matter, which outranks recency.
            rows = conn.execute(
                f"SELECT * FROM memories {where_sql} "
                f"ORDER BY pinned DESC, created_at DESC LIMIT ?",
                (*params, query.max_results),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    async def all_records(self, include_superseded: bool = False) -> list[MemoryRecord]:
        """Every live record. Used to rebuild the index on boot.

        Superseded facts are excluded by default so they do not re-enter the
        vector index at startup, which would silently undo every correction the
        user has made the next time the process restarts.
        """
        import sqlite3

        sql = "SELECT * FROM memories"
        if not include_superseded:
            sql += " WHERE superseded_by IS NULL"
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql).fetchall()
            return [self._row_to_record(r) for r in rows]

    async def stats(self) -> MemoryStats:
        import sqlite3

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) as c FROM memories").fetchone()["c"]
            by_type = {}
            for row in conn.execute("SELECT memory_type, COUNT(*) as c FROM memories GROUP BY memory_type"):
                by_type[row["memory_type"]] = row["c"]
            embeddings = conn.execute("SELECT COUNT(*) as c FROM memories WHERE embedding IS NOT NULL").fetchone()["c"]
            size = conn.execute("SELECT SUM(LENGTH(content)) as s FROM memories").fetchone()["s"] or 0
            return MemoryStats(
                total_records=total,
                by_type=by_type,
                total_embeddings=embeddings,
                storage_size_bytes=size,
                last_indexed=time.time(),
            )

    async def health_check(self) -> dict[str, Any]:
        import sqlite3

        try:
            with closing(sqlite3.connect(self.db_path)) as conn, conn:
                conn.execute("SELECT 1")
            return {"status": "healthy", "db_path": self.db_path}
        except Exception as e:
            return {"status": "unavailable", "error": str(e)}

    def close(self) -> None:
        """Fold the write-ahead log back into the database file.

        Called on shutdown so the Spine is left as one consistent file rather
        than a file plus a WAL that the next process has to recover. SQLite
        recovers from an orphaned WAL correctly, so this is not about
        correctness — it is about not treating "crashed on exit, recovered on
        boot" as the normal path, because that is the state in which a real
        corruption would go unnoticed.

        Best-effort by design: a checkpoint failure must never be the reason
        shutdown does not finish.
        """
        import sqlite3

        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Spine WAL checkpoint failed on shutdown: %s", exc)

    def _row_to_record(self, row: "sqlite3.Row") -> MemoryRecord:
        import json

        return MemoryRecord(
            id=row["id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            metadata=json.loads(row["metadata"] or "{}"),
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            tags=json.loads(row["tags"] or "[]"),
            session_id=row["session_id"],
            user_id=row["user_id"],
            importance=row["importance"],
            source=row["source"],
            # `in row.keys()` rather than a bare lookup: a Spine written before
            # the supersession migration has rows without these columns, and
            # sqlite3.Row raises on a missing key rather than returning None.
            superseded_by=row["superseded_by"] if "superseded_by" in row.keys() else None,
            superseded_at=row["superseded_at"] if "superseded_at" in row.keys() else None,
            pinned=bool(row["pinned"]) if "pinned" in row.keys() else False,
            # A fact written before M8 is `global`, because it was captured
            # with no project in play. Guessing a project for it would invent a
            # value the user never entered — which is the whole reason scope
            # lands before the alpha rather than after.
            scope=row["scope"] if "scope" in row.keys() and row["scope"] else GLOBAL_SCOPE,
            origin=_origin_or_default(row["origin"] if "origin" in row.keys() else None),
            recalled_in=json.loads(
                row["recalled_in"] if "recalled_in" in row.keys() and row["recalled_in"] else "[]"
            ),
        )


def create_memory_store(store_type: str = "memory", **kwargs) -> MemoryStore:
    """Factory for creating memory stores."""
    if store_type == "sqlite":
        return SQLiteMemoryStore(kwargs.get("db_path", "memory.db"))
    return InMemoryMemoryStore(kwargs.get("persist_path"))