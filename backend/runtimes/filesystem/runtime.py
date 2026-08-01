from __future__ import annotations

import asyncio
import time
import hashlib
from pathlib import Path
from typing import Any

from .contracts import (
    FileRecord,
    FileSearchResult,
    FilesystemRuntime,
    FilesystemStatus,
    FileType,
    SearchStrategy,
    RuntimeMetadata,
    Capability,
    CapabilityLocality,
)
from .store import InMemoryFilesystemStore, create_filesystem_store, FilesystemStore
from .index import HybridFilesystemIndex, create_filesystem_index, FilesystemIndex
from .retrieval import FilesystemRetrieverImpl, FilesystemRetriever
from .connectors.local import LocalFilesystemConnector, FilesystemConnector


class FilesystemRuntimeImpl(FilesystemRuntime):
    """Main Filesystem Runtime - handles file search, open, metadata, and indexing."""

    def __init__(
        self,
        root_path: str = ".",
        store_type: str = "memory",
        index_type: str = "hybrid",
        persist_path: str | None = None,
    ):
        self._runtime_id = "filesystem"
        self._state = FilesystemStatus.INITIALIZING
        self._start_time = time.time()
        self._initialized = False

        self._root_path = Path(root_path).resolve()
        self._connector: FilesystemConnector = LocalFilesystemConnector(str(self._root_path))
        self._store: FilesystemStore = create_filesystem_store(store_type, persist_path=persist_path)
        self._index: FilesystemIndex = create_filesystem_index(index_type)
        self._retriever: FilesystemRetriever = FilesystemRetrieverImpl(self._store, self._index)

        self._stats = {
            "indexed_files": 0,
            "searches": 0,
            "opens": 0,
            "errors": 0,
            "total_latency_ms": 0.0,
        }

    async def initialize(self) -> None:
        self._state = FilesystemStatus.INITIALIZING
        await self._store.health_check()
        await self._index.health_check()
        await self._connector.health_check()
        await self._index_full()
        self._state = FilesystemStatus.READY
        self._initialized = True
        print(f"[FilesystemRuntime] Initialized with root={self._root_path}")

    async def shutdown(self) -> None:
        self._state = FilesystemStatus.STOPPING
        self._state = FilesystemStatus.STOPPED

    def get_runtime_id(self) -> str:
        return self._runtime_id

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id=self._runtime_id,
            version="1.0.0",
            priority="high",
            capabilities=[
                Capability(id="filesystem.search", runtime_id=self._runtime_id, category="filesystem"),
                Capability(id="filesystem.open", runtime_id=self._runtime_id, category="filesystem"),
                Capability(id="filesystem.metadata", runtime_id=self._runtime_id, category="filesystem"),
                Capability(id="filesystem.index", runtime_id=self._runtime_id, category="filesystem"),
                Capability(id="filesystem.reindex", runtime_id=self._runtime_id, category="filesystem"),
            ],
        )

    def get_state(self) -> FilesystemStatus:
        return self._state

    def health_check(self) -> dict[str, Any]:
        store_health = asyncio.run(self._store.health_check()) if hasattr(self._store, 'health_check') else {"status": "unknown"}
        index_health = asyncio.run(self._index.health_check()) if hasattr(self._index, 'health_check') else {"status": "unknown"}
        connector_health = self._connector.health_check()

        return {
            "runtime_id": self._runtime_id,
            "state": self._state.value,
            "uptime_seconds": time.time() - self._start_time,
            "root_path": str(self._root_path),
            "store": store_health,
            "index": index_health,
            "connector": connector_health,
            "stats": self._stats,
        }

    async def _index_full(self) -> None:
        files = await self._connector.list_files("", recursive=True)
        for file_path in files:
            await self.index_file(file_path)

    async def index_file(
        self,
        path: str,
        content: str | None = None,
        file_type: FileType | None = None,
        project_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        start = time.time()
        try:
            full_path = self._root_path / path
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            meta = await self._connector.get_metadata(path)
            if content is None:
                content = await self._connector.read_file(path)
                if isinstance(content, bytes):
                    content = content.decode("utf-8", errors="replace")

            if file_type is None:
                from .connectors.local import LocalFilesystemConnector
                file_type = LocalFilesystemConnector("")._get_file_type(full_path)

            checksum = hashlib.sha256(content.encode() if isinstance(content, str) else content).hexdigest()[:16]

            record = FileRecord(
                path=path,
                name=full_path.name,
                file_type=file_type,
                content=content,
                metadata=metadata or {},
                size_bytes=meta.size_bytes,
                mime_type=meta.mime_type,
                created_at=meta.created_at,
                modified_at=meta.modified_at,
                indexed_at=time.time(),
                tags=tags or [],
                project_id=project_id,
                checksum=checksum,
            )

            await self._store.put(record)
            await self._index.add(record)
            self._stats["indexed_files"] += 1
            return record.id

        except Exception as e:
            self._stats["errors"] += 1
            print(f"[FilesystemRuntime] Index failed for {path}: {e}")
            raise
        finally:
            self._stats["total_latency_ms"] += (time.time() - start) * 1000

    async def search(
        self,
        query: str,
        file_types: list[FileType] | None = None,
        project_id: str | None = None,
        max_results: int = 20,
    ) -> list[FileSearchResult]:
        start = time.time()
        try:
            fs_query = FilesystemQuery(
                query=query,
                file_types=file_types or [],
                max_results=max_results,
                strategy=SearchStrategy.HYBRID,
                project_id=project_id,
            )
            results = await self._retriever.retrieve(fs_query)
            self._stats["searches"] += 1
            return results
        except Exception as e:
            self._stats["errors"] += 1
            print(f"[FilesystemRuntime] Search failed: {e}")
            raise
        finally:
            self._stats["total_latency_ms"] += (time.time() - start) * 1000

    async def open_file(self, record_id: str) -> FileRecord | None:
        start = time.time()
        try:
            record = await self._store.get(record_id)
            if record:
                self._stats["opens"] += 1
            return record
        finally:
            self._stats["total_latency_ms"] += (time.time() - start) * 1000

    async def get_metadata(self, record_id: str) -> FileRecord | None:
        return await self._store.get(record_id)

    async def reindex(self, project_id: str | None = None) -> dict[str, Any]:
        start = time.time()
        await self._index.rebuild()
        files = await self._connector.list_files("", recursive=True)
        for file_path in files:
            try:
                await self.index_file(file_path, project_id=project_id)
            except Exception as e:
                print(f"[FilesystemRuntime] Reindex failed for {file_path}: {e}")
        return {
            "reindexed": self._stats["indexed_files"],
            "duration_ms": (time.time() - start) * 1000,
        }

    async def remove_file(self, record_id: str) -> bool:
        await self._index.remove(record_id)
        return await self._store.delete(record_id)

    async def get_stats(self) -> dict[str, Any]:
        store_stats = await self._store.health_check()
        index_stats = await self._index.health_check()
        return {
            "runtime_id": self._runtime_id,
            "state": self._state.value,
            "store": store_stats,
            "index": index_stats,
            "stats": self._stats,
        }


def create_filesystem_runtime(**kwargs) -> FilesystemRuntimeImpl:
    return FilesystemRuntimeImpl(**kwargs)