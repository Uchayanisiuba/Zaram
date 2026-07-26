from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
import time
import uuid

from core.contracts import RuntimeMetadata, Capability, CapabilityLocality


class MemoryType(str, Enum):
    CONVERSATION = "conversation"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    WORKING = "working"


class MemoryStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    INITIALIZING = "initializing"
    READY = "ready"
    DISABLED = "disabled"


class RetrievalStrategy(str, Enum):
    VECTOR_SIMILARITY = "vector_similarity"
    KEYWORD_MATCH = "keyword_match"
    HYBRID = "hybrid"
    TEMPORAL = "temporal"
    SEMANTIC = "semantic"


@dataclass(frozen=True)
class MemoryRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    memory_type: MemoryType = MemoryType.CONVERSATION
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    session_id: str | None = None
    user_id: str | None = None
    importance: float = 0.5
    source: str = "user"


@dataclass(frozen=True)
class MemoryQuery:
    query: str
    memory_types: list[MemoryType] = field(default_factory=lambda: [MemoryType.CONVERSATION, MemoryType.EPISODIC, MemoryType.SEMANTIC])
    max_results: int = 10
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    filters: dict[str, Any] = field(default_factory=dict)
    min_importance: float = 0.0
    session_id: str | None = None
    user_id: str | None = None
    time_range: tuple[float, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryResult:
    record: MemoryRecord
    score: float
    match_reason: str = ""
    rank: int = 0


@dataclass
class MemoryStats:
    total_records: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    total_embeddings: int = 0
    storage_size_bytes: int = 0
    last_indexed: float = 0.0


class MemoryStore(Protocol):
    async def put(self, record: MemoryRecord) -> str: ...
    async def get(self, record_id: str) -> MemoryRecord | None: ...
    async def delete(self, record_id: str) -> bool: ...
    async def query(self, query: MemoryQuery) -> list[MemoryRecord]: ...
    async def stats(self) -> MemoryStats: ...
    async def health_check(self) -> dict[str, Any]: ...


class MemoryIndex(Protocol):
    async def add(self, record: MemoryRecord) -> None: ...
    async def remove(self, record_id: str) -> None: ...
    async def search(self, query: MemoryQuery) -> list[tuple[str, float]]: ...
    async def rebuild(self) -> None: ...
    async def health_check(self) -> dict[str, Any]: ...


class MemoryRetriever(Protocol):
    async def retrieve(self, query: MemoryQuery) -> list[MemoryResult]: ...
    async def health_check(self) -> dict[str, Any]: ...


class MemoryRanker(Protocol):
    async def rank(self, results: list[MemoryResult], query: MemoryQuery) -> list[MemoryResult]: ...
    async def health_check(self) -> dict[str, Any]: ...


class MemoryRuntime(Protocol):
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def get_runtime_id(self) -> str: ...
    def get_metadata(self) -> RuntimeMetadata: ...
    def get_state(self) -> MemoryStatus: ...
    def health_check(self) -> dict[str, Any]: ...
    async def store(self, content: str, memory_type: MemoryType, metadata: dict[str, Any] | None = None, session_id: str | None = None, user_id: str | None = None, tags: list[str] | None = None, importance: float = 0.5) -> str: ...
    async def retrieve(self, query: str, memory_types: list[MemoryType] | None = None, max_results: int = 10, strategy: RetrievalStrategy = RetrievalStrategy.HYBRID, session_id: str | None = None, user_id: str | None = None, filters: dict[str, Any] | None = None) -> list[MemoryResult]: ...
    async def remember(self, content: str, memory_type: MemoryType = MemoryType.SEMANTIC, metadata: dict[str, Any] | None = None, session_id: str | None = None, user_id: str | None = None, tags: list[str] | None = None, importance: float = 0.5) -> str: ...
    async def reinforce(self, record_id: str, delta: float = 0.1) -> bool: ...
    async def get_conversation_history(self, session_id: str, limit: int = 50) -> list[MemoryRecord]: ...
    async def get_episodic_memories(self, user_id: str, limit: int = 20) -> list[MemoryRecord]: ...
    async def get_semantic_memories(self, query: str, limit: int = 10) -> list[MemoryResult]: ...
    async def update_importance(self, record_id: str, importance: float) -> bool: ...
    async def forget(self, record_id: str) -> bool: ...
    async def consolidate(self) -> dict[str, Any]: ...
    async def apply_decay(self, decay_threshold: float = 0.1) -> dict[str, Any]: ...