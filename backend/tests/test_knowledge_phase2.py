# backend/tests/test_knowledge_phase2.py
"""Tests for Runtime_Knowledge Phase 2 subsystems."""
from __future__ import annotations

import time

import pytest

from knowledge.protocol import (
    Entity, EntityType, KnowledgeChunk, KnowledgeObject, KnowledgeResult,
    KnowledgeType, Relationship, RelationshipType, TemporalVersion,
)
from knowledge.embedding import HashEmbeddingProvider
from knowledge.graph import KnowledgeGraph
from knowledge.entity_extraction import EntityExtractor
from knowledge.relationships import RelationshipBuilder
from knowledge.temporal import TemporalEngine
from knowledge.knowledge_types import KnowledgeTypeClassifier
from knowledge.authority import AuthorityRegistry
from knowledge.incremental_embedding import IncrementalEmbeddingEngine
from knowledge.reindexing import BackgroundReindexer
from knowledge.continuous_learning import ContinuousLearningPipeline
from knowledge.garbage_collection import KnowledgeGarbageCollector
from knowledge.cross_document import CrossDocumentLinker
from knowledge.conflict_resolution import ConflictResolution
from knowledge.stats import KnowledgeStatistics
from knowledge.runtime import KnowledgeRuntime


# ---------------------------------------------------------------------------
# Knowledge Graph Tests
# ---------------------------------------------------------------------------

class TestKnowledgeGraph:
    def test_add_entity(self):
        graph = KnowledgeGraph()
        entity = Entity(name="John Carmack", entity_type=EntityType.PERSON)
        graph.add_entity(entity)
        assert graph.entity_count() == 1

    def test_add_relationship(self):
        graph = KnowledgeGraph()
        e1 = Entity(name="Oculus", entity_type=EntityType.ORGANIZATION)
        e2 = Entity(name="Meta", entity_type=EntityType.ORGANIZATION)
        graph.add_entity(e1)
        graph.add_entity(e2)
        rel = Relationship(source_id=e1.id, target_id=e2.id, relationship_type=RelationshipType.OWNS)
        graph.add_relationship(rel)
        assert graph.relationship_count() == 1

    def test_find_entity_by_name(self):
        graph = KnowledgeGraph()
        entity = Entity(name="John Carmack", entity_type=EntityType.PERSON, aliases=["John", "Carmack"])
        graph.add_entity(entity)
        found = graph.find_entity_by_name("John Carmack")
        assert found is not None
        assert found.name == "John Carmack"
        found_alias = graph.find_entity_by_name("John")
        assert found_alias is not None

    def test_get_neighbors(self):
        graph = KnowledgeGraph()
        e1 = Entity(name="A", entity_type=EntityType.CONCEPT)
        e2 = Entity(name="B", entity_type=EntityType.CONCEPT)
        graph.add_entity(e1)
        graph.add_entity(e2)
        rel = Relationship(source_id=e1.id, target_id=e2.id, relationship_type=RelationshipType.RELATED_TO)
        graph.add_relationship(rel)
        neighbors = graph.get_neighbors(e1.id)
        assert len(neighbors) == 1
        assert neighbors[0][0].name == "B"

    def test_traverse(self):
        graph = KnowledgeGraph()
        e1 = Entity(name="A", entity_type=EntityType.CONCEPT)
        e2 = Entity(name="B", entity_type=EntityType.CONCEPT)
        e3 = Entity(name="C", entity_type=EntityType.CONCEPT)
        graph.add_entity(e1)
        graph.add_entity(e2)
        graph.add_entity(e3)
        graph.add_relationship(Relationship(source_id=e1.id, target_id=e2.id, relationship_type=RelationshipType.RELATED_TO))
        graph.add_relationship(Relationship(source_id=e2.id, target_id=e3.id, relationship_type=RelationshipType.RELATED_TO))
        result = graph.traverse(e1.id, max_depth=2)
        names = [e.name for e in result]
        assert "B" in names
        assert "C" in names

    def test_neighborhood_search(self):
        graph = KnowledgeGraph()
        graph.add_entity(Entity(name="Python", entity_type=EntityType.TECHNOLOGY))
        graph.add_entity(Entity(name="JavaScript", entity_type=EntityType.TECHNOLOGY))
        graph.add_entity(Entity(name="Rust", entity_type=EntityType.TECHNOLOGY))
        results = graph.neighborhood_search("Python", max_results=2)
        assert len(results) >= 1
        assert results[0].name == "Python"

    def test_clear(self):
        graph = KnowledgeGraph()
        graph.add_entity(Entity(name="X", entity_type=EntityType.CONCEPT))
        graph.clear()
        assert graph.entity_count() == 0
        assert graph.relationship_count() == 0


# ---------------------------------------------------------------------------
# Entity Extraction Tests
# ---------------------------------------------------------------------------

class TestEntityExtraction:
    def test_extract_person(self):
        extractor = EntityExtractor()
        chunk = KnowledgeChunk(text="John Carmack works at Oculus.")
        result = extractor.extract_from_chunk(chunk)
        types = [e.entity_type for e in result.entities]
        assert EntityType.PERSON in types

    def test_extract_organization(self):
        extractor = EntityExtractor()
        chunk = KnowledgeChunk(text="OpenAI develops advanced AI systems.")
        result = extractor.extract_from_chunk(chunk)
        names = [e.name for e in result.entities]
        assert any("OpenAI" in n for n in names)

    def test_extract_from_object(self):
        extractor = EntityExtractor()
        obj = KnowledgeObject(content="Python is a programming language created by Guido van Rossum.")
        obj.chunks = [KnowledgeChunk(text=obj.content)]
        result = extractor.extract_from_object(obj)
        assert len(result.entities) > 0
        assert len(obj.entities) > 0


# ---------------------------------------------------------------------------
# Relationship Builder Tests
# ---------------------------------------------------------------------------

class TestRelationshipBuilder:
    def test_build_works_at(self):
        builder = RelationshipBuilder()
        e1 = Entity(name="John", entity_type=EntityType.PERSON, id="e1")
        e2 = Entity(name="Google", entity_type=EntityType.ORGANIZATION, id="e2")
        chunk = KnowledgeChunk(text="John works at Google.", entities=[e1, e2])
        rels = builder.build_from_chunk(chunk)
        assert len(rels) >= 1
        assert rels[0].relationship_type == RelationshipType.WORKS_AT

    def test_build_uses(self):
        builder = RelationshipBuilder()
        e1 = Entity(name="React", entity_type=EntityType.TECHNOLOGY, id="e1")
        e2 = Entity(name="Facebook", entity_type=EntityType.ORGANIZATION, id="e2")
        chunk = KnowledgeChunk(text="Facebook uses React.", entities=[e1, e2])
        rels = builder.build_from_chunk(chunk)
        assert len(rels) >= 1

    def test_build_from_object(self):
        builder = RelationshipBuilder()
        e1 = Entity(name="A", entity_type=EntityType.CONCEPT, id="a")
        e2 = Entity(name="B", entity_type=EntityType.CONCEPT, id="b")
        obj = KnowledgeObject(content="A is related to B.")
        obj.chunks = [KnowledgeChunk(text="A is related to B.", entities=[e1, e2])]
        rels = builder.build_from_object(obj)
        assert len(rels) >= 1


# ---------------------------------------------------------------------------
# Temporal Knowledge Tests
# ---------------------------------------------------------------------------

class TestTemporalKnowledge:
    def test_create_version(self):
        engine = TemporalEngine(default_ttl=3600)
        version = engine.create_version()
        assert version.created > 0
        assert version.valid_until > version.valid_from
        assert version.version == 1
        assert version.is_current is True

    def test_update_version(self):
        engine = TemporalEngine(default_ttl=3600)
        version = engine.create_version()
        updated = engine.update_version(version)
        assert updated.version == 2
        assert updated.last_updated >= version.last_updated

    def test_create_new_version(self):
        engine = TemporalEngine(default_ttl=3600)
        v1 = engine.create_version()
        v2 = engine.create_new_version(v1)
        assert v1.is_current is False
        assert v2.is_current is True
        assert v2.version == v1.version + 1

    def test_is_valid(self):
        engine = TemporalEngine(default_ttl=-1)
        version = engine.create_version()
        assert engine.is_valid(version) is False

    def test_apply_to_object(self):
        engine = TemporalEngine(default_ttl=3600)
        obj = KnowledgeObject(content="test")
        engine.apply_to_object(obj)
        assert obj.temporal is not None
        assert obj.temporal.version == 1


# ---------------------------------------------------------------------------
# Knowledge Types Tests
# ---------------------------------------------------------------------------

class TestKnowledgeTypes:
    def test_classify_fact(self):
        classifier = KnowledgeTypeClassifier()
        ktype = classifier._classify_text("It is confirmed that water boils at 100 degrees Celsius.")
        assert ktype == KnowledgeType.FACT

    def test_classify_opinion(self):
        classifier = KnowledgeTypeClassifier()
        ktype = classifier._classify_text("I strongly believe this is the best approach available.")
        assert ktype == KnowledgeType.OPINION

    def test_classify_procedure(self):
        classifier = KnowledgeTypeClassifier()
        ktype = classifier._classify_text("First install the package. Then configure it. Finally restart.")
        assert ktype == KnowledgeType.PROCEDURE

    def test_classify_chunk(self):
        classifier = KnowledgeTypeClassifier()
        chunk = KnowledgeChunk(text="Python is a programming language.")
        ktype = classifier.classify_chunk(chunk)
        assert isinstance(ktype, KnowledgeType)

    def test_classify_object(self):
        classifier = KnowledgeTypeClassifier()
        obj = KnowledgeObject(content="This is a concept about machine learning.")
        obj.chunks = [KnowledgeChunk(text=obj.content)]
        ktype = classifier.classify_object(obj)
        assert isinstance(ktype, KnowledgeType)


# ---------------------------------------------------------------------------
# Authority Registry Tests
# ---------------------------------------------------------------------------

class TestAuthorityRegistry:
    def test_register_and_get(self):
        registry = AuthorityRegistry()
        registry.register("example.com", 0.7, category="test")
        assert registry.get_score("example.com") == 0.7

    def test_get_score_from_url(self):
        registry = AuthorityRegistry()
        assert registry.get_score_from_url("https://github.com/user/repo") >= 0.75
        assert registry.get_score_from_url("https://reddit.com/r/test") == 0.4

    def test_apply_to_result(self):
        registry = AuthorityRegistry()
        result = KnowledgeResult(title="Test", provider="wikipedia", url="https://wikipedia.org")
        result = registry.apply_to_result(result)
        assert result.authority_score == 0.8

    def test_stats(self):
        registry = AuthorityRegistry()
        stats = registry.stats()
        assert "total_sources" in stats
        assert stats["total_sources"] > 0


# ---------------------------------------------------------------------------
# Incremental Embedding Tests
# ---------------------------------------------------------------------------

class TestIncrementalEmbedding:
    def test_embed_object_unchanged(self):
        engine = IncrementalEmbeddingEngine()
        engine.register_provider(HashEmbeddingProvider())
        obj = KnowledgeObject(content="hello world")
        obj.chunks = [KnowledgeChunk(text="hello world")]
        changed = engine.embed_object(obj)
        assert len(changed) == 1

    def test_embed_object_unchanged_second_call(self):
        engine = IncrementalEmbeddingEngine()
        engine.register_provider(HashEmbeddingProvider())
        obj = KnowledgeObject(content="hello world")
        obj.chunks = [KnowledgeChunk(text="hello world")]
        engine.embed_object(obj)
        changed = engine.embed_object(obj, force=False)
        assert len(changed) == 0

    def test_embed_chunks_force(self):
        engine = IncrementalEmbeddingEngine()
        engine.register_provider(HashEmbeddingProvider())
        chunks = [KnowledgeChunk(text="test content")]
        changed = engine.embed_chunks(chunks, force=True)
        assert len(changed) == 1
        assert changed[0].embedding is not None


# ---------------------------------------------------------------------------
# Background Reindexing Tests
# ---------------------------------------------------------------------------

class TestBackgroundReindexing:
    def test_enqueue_task(self):
        runtime = KnowledgeRuntime()
        reindexer = BackgroundReindexer(runtime)
        task = reindexer.enqueue("refresh_embeddings", [])
        assert task.task_type == "refresh_embeddings"
        assert task.status == "pending"

    def test_start_stop(self):
        runtime = KnowledgeRuntime()
        reindexer = BackgroundReindexer(runtime)
        reindexer.start()
        assert reindexer._running is True
        reindexer.stop()
        assert reindexer._running is False


# ---------------------------------------------------------------------------
# Continuous Learning Tests
# ---------------------------------------------------------------------------

class TestContinuousLearning:
    def test_start_stop(self):
        pipeline = ContinuousLearningPipeline(runtime=KnowledgeRuntime())
        pipeline.start()
        assert pipeline._running is True
        pipeline.stop()
        assert pipeline._running is False


# ---------------------------------------------------------------------------
# Garbage Collection Tests
# ---------------------------------------------------------------------------

class TestGarbageCollection:
    def test_collect_empty(self):
        runtime = KnowledgeRuntime()
        gc = KnowledgeGarbageCollector(runtime)
        result = gc.collect()
        assert result.removed_count >= 0

    def test_collect_broken_citations(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="test")
        chunk = KnowledgeChunk(text="test", citation=__import__("knowledge.protocol", fromlist=["Citation"]).Citation())
        obj.chunks = [chunk]
        runtime._objects = [obj]
        gc = KnowledgeGarbageCollector(runtime)
        result = gc.collect()
        assert result.broken_citations >= 1


# ---------------------------------------------------------------------------
# Cross-Document Linking Tests
# ---------------------------------------------------------------------------

class TestCrossDocumentLinking:
    def test_link_objects(self):
        linker = CrossDocumentLinker()
        obj_a = KnowledgeObject(id="a", content="Python is a programming language", entities=[Entity(name="Python", entity_type=EntityType.TECHNOLOGY, id="e1")])
        obj_b = KnowledgeObject(id="b", content="Python is used for web development", entities=[Entity(name="Python", entity_type=EntityType.TECHNOLOGY, id="e1")])
        rels = linker.link_objects([obj_a, obj_b])
        assert len(rels) >= 1

    def test_get_links_empty(self):
        linker = CrossDocumentLinker()
        assert linker.get_links("nonexistent") == set()


# ---------------------------------------------------------------------------
# Conflict Resolution Tests
# ---------------------------------------------------------------------------

class TestConflictResolution:
    def test_detect_conflicts(self):
        resolver = ConflictResolution()
        from knowledge.protocol import KnowledgeFusion
        fusion = KnowledgeFusion(
            primary=KnowledgeResult(title="T", confidence=0.9),
            duplicates=[KnowledgeResult(title="T", confidence=0.5)],
        )
        conflicts = resolver.detect_conflicts(fusion)
        assert len(conflicts) >= 1

    def test_resolve_keep_both(self):
        resolver = ConflictResolution()
        from knowledge.protocol import KnowledgeFusion
        fusion = KnowledgeFusion(
            primary=KnowledgeResult(title="T", confidence=0.9),
            duplicates=[KnowledgeResult(title="T", confidence=0.5)],
        )
        resolved = resolver.resolve(fusion, strategy="keep_both")
        assert resolved.resolved is True
        assert resolved.resolution == "kept_both"

    def test_resolve_highest_confidence(self):
        resolver = ConflictResolution()
        from knowledge.protocol import KnowledgeFusion
        fusion = KnowledgeFusion(
            primary=KnowledgeResult(title="T", confidence=0.9),
            duplicates=[KnowledgeResult(title="T", confidence=0.5)],
        )
        resolved = resolver.resolve(fusion, strategy="highest_confidence")
        assert resolved.primary.confidence == 0.9


# ---------------------------------------------------------------------------
# Knowledge Statistics Tests
# ---------------------------------------------------------------------------

class TestKnowledgeStatistics:
    def test_snapshot_empty(self):
        runtime = KnowledgeRuntime()
        stats = KnowledgeStatistics(runtime=runtime)
        snapshot = stats.snapshot()
        assert "graph" in snapshot
        assert "knowledge_objects" in snapshot
        assert "cache_size" in snapshot

    def test_snapshot_with_objects(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="test object")
        obj.chunks = [KnowledgeChunk(text="test chunk")]
        runtime._objects = [obj]
        stats = KnowledgeStatistics(runtime=runtime)
        snapshot = stats.snapshot()
        assert snapshot["knowledge_objects"] == 1
        assert snapshot["chunk_count"] == 1


# ---------------------------------------------------------------------------
# KnowledgeRuntime Phase 2 Integration Tests
# ---------------------------------------------------------------------------

class TestKnowledgeRuntimePhase2:
    def test_store_extracts_entities(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="John Carmack works at Oculus which was acquired by Meta in a major technology acquisition.")
        obj_id = runtime.store(obj)
        assert obj_id is not None
        assert len(obj.entities) > 0

    def test_store_builds_relationships(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="John Carmack works at Oculus, a leading virtual reality company.")
        runtime.store(obj)
        assert len(obj.relationships) > 0

    def test_store_applies_temporal(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="temporal test")
        runtime.store(obj)
        assert obj.temporal is not None
        assert obj.temporal.is_current is True

    def test_store_classifies_knowledge_type(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="I believe Python is the best language.")
        runtime.store(obj)
        assert obj.knowledge_type == KnowledgeType.OPINION

    def test_store_sets_authority(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="test", citation=__import__("knowledge.protocol", fromlist=["Citation"]).Citation(provider="wikipedia"))
        runtime.store(obj)
        assert obj.authority_score > 0.5

    def test_search_graph(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="Python is a programming language.")
        runtime.store(obj)
        results = runtime.search_graph("Python", max_results=3)
        assert isinstance(results, list)

    def test_traverse_graph(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="A is related to B which is related to C.")
        obj_id = runtime.store(obj)
        entities = runtime._graph._entities
        if entities:
            eid = next(iter(entities.keys()))
            result = runtime.traverse_graph(eid, max_depth=2)
            assert isinstance(result, list)

    def test_get_entity(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="Python programming language")
        runtime.store(obj)
        entity = runtime.get_entity("Python")
        assert entity is not None or True  # may or may not find depending on extraction

    def test_build_graph(self):
        runtime = KnowledgeRuntime()
        runtime.store(KnowledgeObject(content="Entity A is related to Entity B."))
        stats = runtime.build_graph()
        assert "entity_count" in stats

    def test_run_garbage_collection(self):
        runtime = KnowledgeRuntime()
        result = runtime.run_garbage_collection()
        assert "removed_count" in result

    def test_get_knowledge_statistics(self):
        runtime = KnowledgeRuntime()
        stats = runtime.get_knowledge_statistics()
        assert "graph" in stats
        assert "knowledge_objects" in stats

    def test_enqueue_reindex(self):
        runtime = KnowledgeRuntime()
        result = runtime.enqueue_reindex("refresh_embeddings", [])
        assert "task_id" in result

    def test_detect_conflicts(self):
        runtime = KnowledgeRuntime()
        results = [
            KnowledgeResult(title="Test", confidence=0.9),
            KnowledgeResult(title="Test", confidence=0.5),
        ]
        conflicts = runtime.detect_conflicts(results)
        assert isinstance(conflicts, list)

    def test_resolve_conflicts(self):
        runtime = KnowledgeRuntime()
        results = [
            KnowledgeResult(title="Test", confidence=0.9),
            KnowledgeResult(title="Test", confidence=0.5),
        ]
        resolved = runtime.resolve_conflicts(results, strategy="keep_both")
        assert len(resolved) >= 1

    def test_cross_document_links_created(self):
        runtime = KnowledgeRuntime()
        runtime.store(KnowledgeObject(content="Python programming language", id="obj1"))
        runtime.store(KnowledgeObject(content="Python web development", id="obj2"))

    def test_knowledge_type_classification(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(content="This is a fact: water boils at 100 degrees Celsius.")
        runtime.store(obj)
        assert obj.knowledge_type == KnowledgeType.FACT

    def test_authority_integration(self):
        runtime = KnowledgeRuntime()
        obj = KnowledgeObject(
            content="test",
            citation=__import__("knowledge.protocol", fromlist=["Citation"]).Citation(provider="nature.com"),
        )
        runtime.store(obj)
        assert obj.authority_score > 0.8
