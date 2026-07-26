# backend/knowledge/protocol.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import time
import uuid


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class ResultType(str, Enum):
    MEMORY = "memory"
    VECTOR = "vector"
    WEB = "web"
    RSS = "rss"
    GITHUB = "github"
    PROJECT = "project"
    DOCUMENT = "document"
    IMAGE = "image"
    CODE = "code"
    PLACEHOLDER = "placeholder"


@dataclass(frozen=True)
class KnowledgeResult:
    """Uniform result object returned by every provider."""
    title: str
    url: str = ""
    snippet: str = ""
    provider: str = ""
    published: str | None = None
    confidence: float = 0.8
    score: float = 0.0
    type: ResultType = ResultType.WEB
    metadata: dict[str, Any] = field(default_factory=dict)
    retrieved_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "provider": self.provider,
            "published": self.published,
            "confidence": self.confidence,
            "score": self.score,
            "type": self.type.value if hasattr(self.type, "value") else str(self.type),
            "metadata": self.metadata,
            "retrieved_at": self.retrieved_at,
        }


@dataclass(frozen=True)
class SearchResponse:
    """Unified search response from the Knowledge Runtime."""
    query: str
    results: list[KnowledgeResult]
    providers_consulted: list[str]
    provider_status: dict[str, str]
    latency_ms: float = 0.0
    cached: bool = False
    status: ProviderStatus = ProviderStatus.HEALTHY


@dataclass(frozen=True)
class Citation:
    """Citation metadata for a knowledge chunk."""
    origin: str = ""
    provider: str = ""
    url: str = ""
    document: str = ""
    section: str = ""
    title: str = ""
    author: str = ""
    timestamp: float = field(default_factory=time.time)
    published: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FreshnessScore:
    """Freshness tracking for a knowledge object."""
    created: float = field(default_factory=time.time)
    indexed: float = field(default_factory=time.time)
    lastUpdated: float = field(default_factory=time.time)
    expires: float = 0.0
    freshnessScore: float = 1.0

    def compute_score(self, now: float | None = None) -> float:
        now = now or time.time()
        if self.expires > 0 and now >= self.expires:
            return 0.0
        age = now - self.created
        if age <= 0:
            return 1.0
        half_life = 7 * 24 * 3600
        return max(0.0, 2 ** (-age / half_life))


@dataclass(frozen=True)
class ConfidenceScore:
    """Confidence scoring for a knowledge result."""
    confidence: float = 0.5
    sourceCount: int = 1
    agreementScore: float = 1.0
    freshnessScore: float = 1.0
    rankingScore: float = 0.0

    def compute(self) -> float:
        weights = {
            "confidence": 0.35,
            "agreement": 0.25,
            "freshness": 0.20,
            "ranking": 0.20,
        }
        return max(0.0, min(1.0, (
            weights["confidence"] * self.confidence
            + weights["agreement"] * self.agreementScore
            + weights["freshness"] * self.freshnessScore
            + weights["ranking"] * self.rankingScore
        )))


@dataclass(frozen=True)
class KnowledgeChunk:
    """A normalized chunk of knowledge text with metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    embedding: list[float] | None = None
    citation: Citation | None = None
    freshness: FreshnessScore | None = None
    confidence: ConfidenceScore | None = None
    token_count: int = 0
    chunk_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeContext:
    """Context window optimization data."""
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    total_tokens: int = 0
    max_tokens: int = 4096
    overlap_tokens: int = 0
    strategy: str = "top_k"


@dataclass
class KnowledgeObject:
    """A complete knowledge object with chunking, embedding, and metadata."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    citation: Citation | None = None
    freshness: FreshnessScore | None = None
    confidence: ConfidenceScore | None = None
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeRequest:
    """Request object for knowledge operations."""
    query: str = ""
    operation: str = "search"
    max_results: int = 6
    context: KnowledgeContext | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    user_id: str | None = None
    providers: list[str] | None = None
    strategy: str = "hybrid"


@dataclass(frozen=True)
class RankedResult:
    """A knowledge result with ranking metadata."""
    result: KnowledgeResult
    rank_score: float = 0.0
    similarity: float = 0.0
    recency: float = 0.0
    authority: float = 0.0
    freshness_score: float = 0.0
    citation_score: float = 0.0
    confidence_score: float = 0.0
    chunks: list[KnowledgeChunk] = field(default_factory=list)


@dataclass
class KnowledgeFusion:
    """Fused knowledge from multiple providers."""
    primary: KnowledgeResult
    duplicates: list[KnowledgeResult] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    agreement_score: float = 1.0
    fused_confidence: float = 0.0
    sources: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TelemetrySnapshot:
    """Telemetry data for the knowledge pipeline."""
    embedding_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    ranking_latency_ms: float = 0.0
    cache_hits: int = 0
    index_size: int = 0
    duplicate_ratio: float = 0.0
    avg_confidence: float = 0.0
    pipeline_stage: str = "idle"


class EmbeddingProvider(ABC):
    """Provider-agnostic embedding interface."""

    @property
    @abstractmethod
    def id(self) -> str:
        ...

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts into vectors."""
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        ...

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.id,
            "status": ProviderStatus.HEALTHY.value if self.is_available() else ProviderStatus.UNAVAILABLE.value,
            "dimension": self.dimension(),
        }


class VectorStore(ABC):
    """Abstract vector store interface."""

    @abstractmethod
    def add(self, chunks: list[KnowledgeChunk]) -> None:
        """Add chunks to the index."""
        ...

    @abstractmethod
    def search(self, query_vector: list[float], top_k: int = 10) -> list[tuple[KnowledgeChunk, float]]:
        """Search for similar chunks."""
        ...

    @abstractmethod
    def delete(self, chunk_id: str) -> None:
        """Remove a chunk from the index."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear all indexed data."""
        ...

    @abstractmethod
    def size(self) -> int:
        """Return the number of indexed chunks."""
        ...

    @abstractmethod
    def persist(self, path: str) -> None:
        """Persist the index to disk."""
        ...

    @abstractmethod
    def load(self, path: str) -> None:
        """Load the index from disk."""
        ...


class KnowledgeProvider(ABC):
    """Base interface for all knowledge providers."""

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique provider identifier."""
        ...

    @abstractmethod
    def search(self, query: str, max_results: int = 6) -> list[KnowledgeResult]:
        """Search for knowledge relevant to the query."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether this provider is currently available."""
        ...

    def priority(self) -> int:
        """Provider priority for result ranking (higher = more trusted)."""
        return 50

    def health(self) -> dict[str, Any]:
        return {
            "provider": self.id,
            "status": ProviderStatus.HEALTHY.value if self.is_available() else ProviderStatus.UNAVAILABLE.value,
            "priority": self.priority(),
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": getattr(self, "result_type", ResultType.WEB).value,
            "cache_ttl": getattr(self, "cache_ttl", 900),
        }
