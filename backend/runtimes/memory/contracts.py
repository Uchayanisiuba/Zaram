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
    # The memory runtime's shutdown() assigned these and they did not exist, so
    # every kernel shutdown raised AttributeError here. It was invisible because
    # the speech runtime raised first and shutdown never got this far.
    STOPPING = "stopping"
    STOPPED = "stopped"


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
    #: Id of the fact that replaced this one, or None while it still stands.
    #:
    #: Rule 4 says the user can *correct* a fact and the affected answers must
    #: change. Correction was previously only expressible as deletion, which
    #: throws away the more interesting half of the record: that Zaram had it
    #: wrong, and that the user said so. A superseded fact stays in the store,
    #: is excluded from recall, and remains visible in the interface struck
    #: through. A system that shows you where it was wrong is one you can
    #: believe when it says it is right.
    superseded_by: str | None = None
    superseded_at: float | None = None
    #: Pinned facts are never decayed and are preferred during recall.
    pinned: bool = False

    @property
    def is_superseded(self) -> bool:
        return self.superseded_by is not None


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
    """One retrieved memory, with **two** numbers that are not interchangeable.

    `relevance` answers "does this bear on the question" and is the similarity
    retrieval produced. `score` answers "show this one first" and blends in
    importance, recency, how often the fact has been used, and whether it
    belongs to this session.

    They were one field. `MemoryRanker.rank()` overwrote `score` with the blend
    — in which similarity carries a weight of 0.35 — and `ExecutionEngine` then
    compared the result to `MIN_RECALL_SCORE`, a threshold measured and
    documented as a *cosine* floor. So a completely unrelated fact could clear
    it on recency and session membership alone, which is exactly what a reply
    citing five unrelated memories for a statement the user had just made
    turned out to be.

    Ordering and permission are different questions. CLAUDE.md already says so
    for tools — "retrieval produces a shortlist; the model chooses; a retrieval
    score authorises nothing" — and citation is the same shape: rank on
    whatever is useful, but decide *whether to cite* on relevance alone.
    """

    record: MemoryRecord
    #: Ranking score. Ordering only. Never compare this to a relevance floor.
    score: float
    #: Similarity as retrieval produced it, before any ranking blend. This is
    #: what a citation threshold is applied to.
    relevance: float | None = None
    match_reason: str = ""
    rank: int = 0

    def __post_init__(self) -> None:
        # A result built without one keeps them equal, so every existing caller
        # behaves as before until the ranker separates them.
        if self.relevance is None:
            self.relevance = self.score


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
    #: Count one *recall*. Reading a record is not recalling it — the Memory
    #: surface listing a fact must not make it look load-bearing. Part of the
    #: contract because the two implementations disagreed about it silently:
    #: one incremented inside `get`, the other did nothing, and the one that
    #: did nothing is the one the product runs.
    async def record_access(self, record_id: str) -> None: ...
    async def delete(self, record_id: str) -> bool: ...
    async def query(self, query: MemoryQuery) -> list[MemoryRecord]: ...
    async def all_records(self) -> list[MemoryRecord]: ...
    async def stats(self) -> MemoryStats: ...
    async def health_check(self) -> dict[str, Any]: ...


class MemoryIndex(Protocol):
    async def add(self, record: MemoryRecord) -> None: ...
    async def remove(self, record_id: str) -> None: ...
    async def search(self, query: MemoryQuery) -> list[tuple[str, float]]: ...
    async def rebuild(self, records: list[MemoryRecord] | None = None) -> None: ...
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