from __future__ import annotations

import json
import os
import time
from typing import Any
from collections import defaultdict

from .contracts import FilesystemStore, FilesystemQuery, FileRecord, FileType


class InMemoryFilesystemStore(FilesystemStore):
    """In-memory file store with optional persistence."""

    def __init__(self, persist_path: str | None = None):
        self._records: dict[str, FileRecord] = {}
        self._by_project: dict[str, list[str]] = defaultdict(list)
        self._by_type: dict[FileType, list[str]] = defaultdict(list)
        self._persist_path = persist_path
        self._load()

    def _load(self) -> None:
        if self._persist_path and os.path.exists(self._persist_path):
            try:
                with open(self._persist_path, "r") as f:
                    data = json.load(f)
                for item in data:
                    record = FileRecord(**item)
                    self._records[record.id] = record
                    if record.project_id:
                        self._by_project[record.project_id].append(record.id)
                    self._by_type[record.file_type].append(record.id)
            except Exception as e:
                print(f"[FilesystemStore] Failed to load: {e}")

    def _save(self) -> None:
        if not self._persist_path:
            return
        try:
            data = [r.__dict__ for r in self._records.values()]
            with open(self._persist_path, "w") as f:
                json.dump(data, f, default=str)
        except Exception as e:
            print(f"[FilesystemStore] Failed to save: {e}")

    async def put(self, record: FileRecord) -> str:
        self._records[record.id] = record
        if record.project_id:
            self._by_project[record.project_id].append(record.id)
        self._by_type[record.file_type].append(record.id)
        self._save()
        return record.id

    async def get(self, record_id: str) -> FileRecord | None:
        return self._records.get(record_id)

    async def delete(self, record_id: str) -> bool:
        if record_id in self._records:
            record = self._records.pop(record_id)
            if record.project_id and record_id in self._by_project[record.project_id]:
                self._by_project[record.project_id].remove(record_id)
            if record_id in self._by_type[record.file_type]:
                self._by_type[record.file_type].remove(record_id)
            self._save()
            return True
        return False

    async def query(self, query: FilesystemQuery) -> list[FileRecord]:
        candidates = set(self._records.keys())

        if query.file_types:
            type_ids = set()
            for ft in query.file_types:
                type_ids.update(self._by_type.get(ft, []))
            candidates &= type_ids

        if query.project_id:
            candidates &= set(self._by_project.get(query.project_id, []))

        results = []
        for rid in candidates:
            record = self._records.get(rid)
            if not record:
                continue
            if query.tags and not any(t in record.tags for t in query.tags):
                continue
            if query.path_prefix and not record.path.startswith(query.path_prefix):
                continue
            if query.modified_after and record.modified_at < query.modified_after:
                continue
            if query.modified_before and record.modified_at > query.modified_before:
                continue
            match = True
            for k, v in query.metadata_filters.items():
                if record.metadata.get(k) != v:
                    match = False
                    break
            if not match:
                continue
            results.append(record)

        results.sort(key=lambda r: r.modified_at, reverse=True)
        return results[: query.max_results]

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "records": len(self._records),
            "projects": len(self._by_project),
            "persist_path": self._persist_path,
        }


class SQLiteFilesystemStore(FilesystemStore):
    """SQLite-backed filesystem store."""

    def __init__(self, db_path: str = "filesystem.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    mime_type TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    modified_at REAL NOT NULL,
                    indexed_at REAL NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    project_id TEXT,
                    checksum TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_project ON files(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON files(file_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_path ON files(path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_modified ON files(modified_at)")

    async def put(self, record: FileRecord) -> str:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO files
                (id, path, name, file_type, content, metadata, size_bytes, mime_type,
                 created_at, modified_at, indexed_at, tags, project_id, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record.id,
                    record.path,
                    record.name,
                    record.file_type.value,
                    record.content,
                    json.dumps(record.metadata),
                    record.size_bytes,
                    record.mime_type,
                    record.created_at,
                    record.modified_at,
                    record.indexed_at,
                    json.dumps(record.tags),
                    record.project_id,
                    record.checksum,
                ),
            )
        return record.id

    async def get(self, record_id: str) -> FileRecord | None:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM files WHERE id = ?", (record_id,)).fetchone()
            if not row:
                return None
            return self._row_to_record(row)

    async def delete(self, record_id: str) -> bool:
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM files WHERE id = ?", (record_id,))
            return cursor.rowcount > 0

    async def query(self, query: FilesystemQuery) -> list[FileRecord]:
        import sqlite3

        where_clauses = []
        params = []

        if query.file_types:
            placeholders = ",".join("?" * len(query.file_types))
            where_clauses.append(f"file_type IN ({placeholders})")
            params.extend(ft.value for ft in query.file_types)

        if query.project_id:
            where_clauses.append("project_id = ?")
            params.append(query.project_id)

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM files {where_sql} ORDER BY modified_at DESC LIMIT ?",
                (*params, query.max_results),
            ).fetchall()
            return [self._row_to_record(r) for r in rows]

    async def health_check(self) -> dict[str, Any]:
        import sqlite3

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1")
            return {"status": "healthy", "db_path": self.db_path}
        except Exception as e:
            return {"status": "unavailable", "error": str(e)}

    def _row_to_record(self, row: "sqlite3.Row") -> FileRecord:
        return FileRecord(
            id=row["id"],
            path=row["path"],
            name=row["name"],
            file_type=FileType(row["file_type"]),
            content=row["content"],
            metadata=json.loads(row["metadata"] or "{}"),
            size_bytes=row["size_bytes"],
            mime_type=row["mime_type"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            indexed_at=row["indexed_at"],
            tags=json.loads(row["tags"] or "[]"),
            project_id=row["project_id"],
            checksum=row["checksum"],
        )


def create_filesystem_store(store_type: str = "memory", **kwargs) -> FilesystemStore:
    if store_type == "sqlite":
        return SQLiteFilesystemStore(kwargs.get("db_path", "filesystem.db"))
    return InMemoryFilesystemStore(kwargs.get("persist_path"))