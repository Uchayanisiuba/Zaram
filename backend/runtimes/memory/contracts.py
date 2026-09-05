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


class Origin(str, Enum):
    """Where a fact came from. Rule 7b: every fact carries its origin.

    The point is not bookkeeping. Recall must be able to say *"from a proposal
    Zaram generated in April"* rather than *"from your client brief"*, because
    those read very differently to someone deciding whether to trust an answer
    — and because deprioritising Zaram's own restatements where a user source
    says the same thing is what makes indexing generated artifacts safe at all.
    """

    #: A passage from a file the user wrote or received.
    USER_DOCUMENT = "user_document"
    #: Something the user said in conversation.
    CONVERSATION = "conversation"
    #: Text Zaram produced — a generated document, a summary, a draft.
    GENERATED = "generated"


#: Facts about the *user*: preferences, working style, how they like things
#: written. Never shared — this is the multiplayer boundary, and it is a
#: constant rather than a string literal because a typo in a scope check is a
#: privacy failure that no test would notice.
GLOBAL_SCOPE = "global"

#: Prefix for facts about *the work*: decisions, constraints, client feedback.
PROJECT_SCOPE_PREFIX = "project:"


def project_scope(project_id: str) -> str:
    """The scope string for a project. One spelling, in one place."""
    project_id = (project_id or "").strip()
    if not project_id:
        return GLOBAL_SCOPE
    return f"{PROJECT_SCOPE_PREFIX}{project_id}"


def scope_project_id(scope: str) -> str | None:
    """The project a scope refers to, or None for global."""
    if scope and scope.startswith(PROJECT_SCOPE_PREFIX):
        return scope[len(PROJECT_SCOPE_PREFIX):] or None
    return None


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
    #: When the fact *became* true, and when it stopped — as distinct from
    #: when Zaram was told either of those things.
    #:
    #: `superseded_at` is **recorded time**: the moment the user corrected it.
    #: `valid_until` is **valid time**: the moment the world changed. They are
    #: routinely months apart, and conflating them loses the question people
    #: actually ask. A client raises your rate in June and you tell Zaram in
    #: August; with only `superseded_at`, "what was my rate in July" cannot be
    #: answered, because the store knows when it was told and not when it was
    #: true.
    #:
    #: That is not a reporting nicety — it decides whether a July invoice was
    #: right. An accounting question asked about the past must be answered with
    #: what was true then, not with what is true now.
    #:
    #: Both default to None, and None is meaningful rather than missing:
    #: `valid_from` unknown means "assume it has always been true as far as
    #: Zaram knows", which for a fact captured in conversation is honest —
    #: nobody stated a start date. `valid_until` of None means it still stands.
    #: Neither is defaulted to `created_at`, because a capture time presented
    #: as a validity date is a value nobody entered.
    valid_from: float | None = None
    valid_until: float | None = None
    #: Pinned facts are never decayed and are preferred during recall.
    pinned: bool = False
    #: ``global`` or ``project:<id>`` — rule 7i.
    #:
    #: One field on one store, not two stores. Facts move between scopes,
    #: recall needs both at once, and the correction loop has to stay uniform;
    #: splitting them would make every one of those a special case.
    #:
    #: Defaults to global rather than to a project because a fact captured with
    #: no project in play genuinely is not about one, and inventing a project
    #: for it would be a value nobody entered. The engine passes the current
    #: project when there is one.
    scope: str = GLOBAL_SCOPE
    #: Rule 7b. See :class:`Origin`.
    origin: Origin = Origin.CONVERSATION
    #: Distinct projects this fact has been recalled in, for rule 7i's
    #: promotion evidence. A count cannot answer "recalled across three
    #: *different* projects", so the identities are kept rather than a number.
    recalled_in: list[str] = field(default_factory=list)

    @property
    def is_superseded(self) -> bool:
        return self.superseded_by is not None

    @property
    def is_global(self) -> bool:
        return self.scope == GLOBAL_SCOPE

    @property
    def project_id(self) -> str | None:
        return scope_project_id(self.scope)


@dataclass(frozen=True)
class MemoryQuery:
    query: str
    memory_types: list[MemoryType] = field(default_factory=lambda: [MemoryType.CONVERSATION, MemoryType.EPISODIC, MemoryType.SEMANTIC])
    max_results: int = 10
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    filters: dict[str, Any] = field(default_factory=dict)
    min_importance: float = 0.0
    #: Restrict to this scope plus `global`. ``None`` means every scope, which
    #: only the Memory surface wants — it shows the user everything they have.
    scope: str | None = None
    #: Restrict to these fact ids, for a question asked inside a knowledge
    #: domain. ``None`` is unrestricted; an **empty set is not** — it means a
    #: domain that can answer from nothing yet, and collapsing the two would
    #: silently widen a scope the user chose. Resolved by
    #: `knowledge/domain_recall.py`, which is where the reasoning lives.
    only_ids: frozenset[str] | None = None
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