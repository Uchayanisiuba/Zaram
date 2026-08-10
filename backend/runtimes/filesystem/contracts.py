from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
import time


class FileType(str, Enum):
    PROJECT = "project"
    MARKDOWN = "markdown"
    PDF = "pdf"
    IMAGE = "image"
    ASSET = "asset"
    NOTE = "note"
    CODE = "code"
    DOCUMENT = "document"
    OTHER = "other"


class SearchStrategy(str, Enum):
    FULLTEXT = "fulltext"
    METADATA = "metadata"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class FileRecord:
    id: str
    path: str
    name: str
    file_type: FileType
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    size_bytes: int = 0
    mime_type: str = ""
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    indexed_at: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    project_id: str | None = None
    checksum: str = ""


@dataclass
class FilesystemQuery:
    query: str = ""
    file_types: list[FileType] | None = None
    project_id: str | None = None
    path_prefix: str | None = None
    tags: list[str] | None = None
    metadata_filters: dict[str, Any] = field(default_factory=dict)
    modified_after: float | None = None
    modified_before: float | None = None
    max_results: int = 20
    strategy: SearchStrategy = SearchStrategy.HYBRID


@dataclass
class FileSearchResult:
    record: FileRecord
    score: float
    match_type: str = ""
    rank: int = 0


@dataclass
class FilesystemStats:
    total_files: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_project: dict[str, int] = field(default_factory=dict)
    total_size_bytes: int = 0
    indexed_files: int = 0


class FilesystemStore(Protocol):
    async def put(self, record: FileRecord) -> str: ...
    async def get(self, record_id: str) -> FileRecord | None: ...
    async def delete(self, record_id: str) -> bool: ...
    async def query(self, query: FilesystemQuery) -> list[FileRecord]: ...
    async def health_check(self) -> dict[str, Any]: ...


class FilesystemIndex(Protocol):
    async def add(self, record: FileRecord) -> None: ...
    async def remove(self, record_id: str) -> None: ...
    async def search(self, query: FilesystemQuery) -> list[tuple[str, float]]: ...
    async def rebuild(self) -> None: ...
    async def health_check(self) -> dict[str, Any]: ...


class FilesystemRetriever(Protocol):
    async def retrieve(self, query: FilesystemQuery) -> list[FileSearchResult]: ...
    async def health_check(self) -> dict[str, Any]: ...


class FilesystemRuntime(Protocol):
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def get_runtime_id(self) -> str: ...
    def get_metadata(self) -> dict[str, Any]: ...
    def get_state(self) -> str: ...
    def health_check(self) -> dict[str, Any]: ...
    async def index_file(
        self,
        path: str,
        content: str,
        file_type: FileType,
        project_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> str: ...
    async def search(
        self,
        query: str,
        file_types: list[FileType] | None = None,
        project_id: str | None = None,
        max_results: int = 20,
    ) -> list[FileSearchResult]: ...
    async def open_file(self, record_id: str) -> FileRecord | None: ...
    async def get_metadata(self, record_id: str) -> FileRecord | None: ...
    async def reindex(self, project_id: str | None = None) -> dict[str, Any]: ...
    async def remove_file(self, record_id: str) -> bool: ...
    async def get_stats(self) -> FilesystemStats: ...