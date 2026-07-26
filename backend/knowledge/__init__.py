from __future__ import annotations

from .runtime import KnowledgeRuntime
from .protocol import (
    KnowledgeProvider, KnowledgeResult, SearchResponse, ProviderStatus, ResultType,
    KnowledgeRequest, KnowledgeChunk, KnowledgeContext, KnowledgeObject,
    Citation, FreshnessScore, ConfidenceScore, RankedResult, KnowledgeFusion,
    TelemetrySnapshot, EmbeddingProvider, VectorStore,
    KnowledgeType, EntityType, RelationshipType, Entity, EntityAlias, Relationship, Edge,
    TemporalVersion, AuthorityScore,
)
from .cache import KnowledgeCache
from .chunking import SemanticChunker, ChunkingConfig
from .embedding import EmbeddingRuntime, HashEmbeddingProvider
from .vector_store import LocalVectorStore
from .retrieval import SemanticRetrieval, RetrievalResult
from .ranking import RankingEngine
from .freshness import FreshnessEngine
from .citations import CitationEngine
from .confidence import ConfidenceEngine
from .fusion import KnowledgeFusionEngine
from .telemetry import KnowledgeTelemetry
from .graph import KnowledgeGraph
from .entity_extraction import EntityExtractor, EntityExtractionResult
from .relationships import RelationshipBuilder
from .temporal import TemporalEngine
from .knowledge_types import KnowledgeTypeClassifier
from .authority import AuthorityRegistry
from .incremental_embedding import IncrementalEmbeddingEngine
from .reindexing import BackgroundReindexer, ReindexTask
from .continuous_learning import ContinuousLearningPipeline
from .garbage_collection import KnowledgeGarbageCollector, GarbageCollectionResult
from .cross_document import CrossDocumentLinker
from .conflict_resolution import ConflictResolution
from .stats import KnowledgeStatistics

__all__ = [
    "KnowledgeRuntime",
    "KnowledgeProvider",
    "KnowledgeResult",
    "SearchResponse",
    "ProviderStatus",
    "ResultType",
    "KnowledgeRequest",
    "KnowledgeChunk",
    "KnowledgeContext",
    "KnowledgeObject",
    "Citation",
    "FreshnessScore",
    "ConfidenceScore",
    "RankedResult",
    "KnowledgeFusion",
    "TelemetrySnapshot",
    "EmbeddingProvider",
    "VectorStore",
    "KnowledgeType",
    "EntityType",
    "RelationshipType",
    "Entity",
    "EntityAlias",
    "Relationship",
    "Edge",
    "TemporalVersion",
    "AuthorityScore",
    "KnowledgeCache",
    "SemanticChunker",
    "ChunkingConfig",
    "EmbeddingRuntime",
    "HashEmbeddingProvider",
    "LocalVectorStore",
    "SemanticRetrieval",
    "RetrievalResult",
    "RankingEngine",
    "FreshnessEngine",
    "CitationEngine",
    "ConfidenceEngine",
    "KnowledgeFusionEngine",
    "KnowledgeTelemetry",
    "KnowledgeGraph",
    "EntityExtractor",
    "EntityExtractionResult",
    "RelationshipBuilder",
    "TemporalEngine",
    "KnowledgeTypeClassifier",
    "AuthorityRegistry",
    "IncrementalEmbeddingEngine",
    "BackgroundReindexer",
    "ReindexTask",
    "ContinuousLearningPipeline",
    "KnowledgeGarbageCollector",
    "GarbageCollectionResult",
    "CrossDocumentLinker",
    "ConflictResolution",
    "KnowledgeStatistics",
]
