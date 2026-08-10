# backend/runtime/discovery/contracts.py
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class FreshnessLevel(str, Enum):
    UNKNOWN = "unknown"
    STATIC = "static"
    RECENT = "recent"
    LIVE = "live"


class DiscoveryIntent(str, Enum):
    ENCYCLOPEDIA = "encyclopedia"
    PROGRAMMING = "programming"
    NEWS = "news"
    GENERAL = "general"
    RSS = "rss"
    DYNAMIC = "dynamic"
    ACADEMIC = "academic"
    SOCIAL = "social"


class RetrievalMode(str, Enum):
    SINGLE = "single"
    PARALLEL = "parallel"
    FALLBACK = "fallback"
    PRIORITY = "priority"
    STREAMING = "streaming"


class ProviderStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class AuthorityLevel(str, Enum):
    GOVERNMENT = "government"
    ACADEMIC = "academic"
    OFFICIAL_DOCS = "official_docs"
    WIKIPEDIA = "wikipedia"
    GITHUB = "github"
    COMMUNITY = "community"
    BLOG = "blog"
    UNKNOWN = "unknown"


class ExecutionStrategy(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


class Capability(str, Enum):
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    NEWS = "news"
    CODE = "code"
    REPOSITORIES = "repositories"
    WEB = "web"
    REFERENCE = "reference"
    ACADEMIC = "academic"
    COMMUNITY = "community"


class SearchDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class DiscoveryMetadata:
    provider: str
    url: str
    title: str
    author: str | None = None
    published: str | None = None
    language: str = "en"
    confidence: float = 0.8
    freshness: FreshnessLevel = FreshnessLevel.UNKNOWN
    license: str | None = None
    last_modified: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscoveryResult:
    content: str
    summary: str
    metadata: DiscoveryMetadata
    sources: list[DiscoveryMetadata] = field(default_factory=list)
    confidence: float = 0.8
    freshness: FreshnessLevel = FreshnessLevel.UNKNOWN
    provider: str = ""
    retrieval_time: float = 0.0


@dataclass(frozen=True)
class DiscoveryRequest:
    query: str
    intent: DiscoveryIntent | None = None
    mode: RetrievalMode = RetrievalMode.PARALLEL
    providers: list[str] | None = None
    max_results: int = 10
    language: str = "en"
    ttl: int = 900
    context: dict[str, Any] | None = None
    strategy: ExecutionStrategy = ExecutionStrategy.BALANCED
    freshness_requirement: FreshnessLevel = FreshnessLevel.UNKNOWN
    authority_requirement: AuthorityLevel = AuthorityLevel.UNKNOWN
    latency_budget_ms: float = 0.0
    require_verification: bool = False
    stream_callback: Callable[[DiscoveryResult], None] | None = None


@dataclass
class DiscoveryContext:
    request: DiscoveryRequest
    started_at: float = field(default_factory=time.time)
    provider_results: dict[str, list[DiscoveryResult]] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    telemetry: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class DiscoveryProvider(Protocol):
    def get_provider_id(self) -> str: ...
    def get_provider_type(self) -> str: ...
    async def discover(
        self, request: DiscoveryRequest, context: DiscoveryContext
    ) -> list[DiscoveryResult]: ...
    def is_available(self) -> bool: ...
    def health_check(self) -> dict[str, Any]: ...
    def priority(self) -> int: ...
    def cache_ttl(self) -> int: ...
    def get_capabilities(self) -> list[Capability]: ...
    def get_authority_level(self) -> AuthorityLevel: ...
    def estimated_cost(self) -> float: ...
    def estimated_latency_ms(self) -> float: ...
    def estimated_confidence(self) -> float: ...


@dataclass(frozen=True)
class ProviderCapability:
    provider_id: str
    capabilities: list[Capability]
    authority: AuthorityLevel
    cost: float = 0.0
    avg_latency_ms: float = 0.0
    success_rate: float = 1.0
    availability: float = 1.0


@dataclass(frozen=True)
class QueryAnalysis:
    intent: DiscoveryIntent
    topic: str
    domain: str
    freshness_requirement: FreshnessLevel
    authority_requirement: AuthorityLevel
    latency_budget_ms: float
    search_difficulty: SearchDifficulty
    expected_capabilities: list[Capability]
    raw_query: str
    confidence: float = 0.8


@dataclass(frozen=True)
class QueryRewrite:
    original_query: str
    rewritten_query: str
    provider_id: str
    capability: Capability
    confidence: float = 0.8


@dataclass(frozen=True)
class ProviderScore:
    provider_id: str
    score: float
    authority: AuthorityLevel
    latency_ms: float
    cost: float
    success_rate: float
    confidence: float
    availability: float


@dataclass(frozen=True)
class ExecutionStep:
    provider_id: str
    capability: Capability
    timeout_ms: float
    retries: int
    cache_policy: bool
    query_rewrite: QueryRewrite | None = None
    streaming: bool = False


@dataclass(frozen=True)
class DiscoveryPlan:
    query: str
    analysis: QueryAnalysis
    steps: list[ExecutionStep]
    strategy: ExecutionStrategy
    fallback_chain: list[str] = field(default_factory=list)
    authority_ranking: list[str] = field(default_factory=list)
    estimated_total_latency_ms: float = 0.0
    estimated_total_cost: float = 0.0
    require_verification: bool = False


@dataclass(frozen=True)
class VerificationResult:
    agreement_score: float
    conflict_score: float
    duplicate_count: int
    missing_information: list[str]
    conflict_report: list[dict[str, Any]]
    overall_confidence: float
    verified: bool


@dataclass(frozen=True)
class StreamingDiscoveryResult:
    result: DiscoveryResult
    is_final: bool
    provider_id: str
    sequence: int


@dataclass(frozen=True)
class DiscoveryDashboard:
    registered_providers: int
    healthy_providers: int
    avg_latency_ms: float
    success_rate: float
    failure_rate: float
    cache_hit_ratio: float
    verification_rate: float
    planner_decisions: dict[str, int]
    current_searches: int
    background_searches: int
    authority_distribution: dict[str, int]
    execution_strategy_distribution: dict[str, int]
