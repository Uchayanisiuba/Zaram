from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any
from collections import defaultdict

from .contracts import (
    MemoryRecord,
    MemoryQuery,
    MemoryStats,
    MemoryStore,
    MemoryType,
    RetrievalStrategy,
)


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
        record = self._records.get(record_id)
        if record:
            updated = MemoryRecord(
                **{
                    **record.__dict__,
                    "access_count": record.access_count + 1,
                    "last_accessed": time.time(),
                }
            )
            self._records[record_id] = updated
            return updated
        return None

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

        for rid in candidate_ids:
            record = self._records.get(rid)
            if not record:
                continue
            if query.min_importance and record.importance < query.min_importance:
                continue
            if query.filters:
                match = True
                for k, v in query.filters.items():
                    if record.metadata.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            if query.time_range:
                if not (query.time_range[0] <= record.created_at <= query.time_range[1]):
                    continue
            candidates.append(record)

        return candidates

    async def all_records(self) -> list[MemoryRecord]:
        """Every record in the store. Used to rebuild the index on boot."""
        return list(self._records.values())

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

        with sqlite3.connect(self.db_path) as conn:
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

    async def put(self, record: MemoryRecord) -> str:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories
                (id, content, memory_type, metadata, embedding, created_at, updated_at,
                 access_count, last_accessed, tags, session_id, user_id, importance, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
        return record.id

    async def get(self, record_id: str) -> MemoryRecord | None:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (record_id,)).fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    async def delete(self, record_id: str) -> bool:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
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

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM memories {where_sql} ORDER BY created_at DESC LIMIT ?",
                (*params, query.max_results),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    async def all_records(self) -> list[MemoryRecord]:
        """Every record in the store. Used to rebuild the index on boot."""
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM memories").fetchall()
            return [self._row_to_record(r) for r in rows]

    async def stats(self) -> MemoryStats:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
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
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1")
            return {"status": "healthy", "db_path": self.db_path}
        except Exception as e:
            return {"status": "unavailable", "error": str(e)}

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
        )


def create_memory_store(store_type: str = "memory", **kwargs) -> MemoryStore:
    """Factory for creating memory stores."""
    if store_type == "sqlite":
        return SQLiteMemoryStore(kwargs.get("db_path", "memory.db"))
    return InMemoryMemoryStore(kwargs.get("persist_path"))