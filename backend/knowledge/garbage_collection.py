# backend/knowledge/garbage_collection.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeChunk, KnowledgeObject


@dataclass
class GarbageCollectionResult:
    removed_count: int = 0
    expired_entries: int = 0
    broken_citations: int = 0
    orphaned_entities: int = 0
    duplicate_chunks: int = 0
    unused_embeddings: int = 0
    unused_graph_nodes: int = 0


class KnowledgeGarbageCollector:
    """Cleanup expired, broken, and orphaned knowledge."""

    def __init__(self, runtime: Any):
        self._runtime = runtime

    def collect(self) -> GarbageCollectionResult:
        result = GarbageCollectionResult()
        self._collect_expired(result)
        self._collect_broken_citations(result)
        self._collect_duplicate_chunks(result)
        self._collect_orphaned_entities(result)
        self._collect_unused_graph_nodes(result)
        return result

    def _collect_expired(self, result: GarbageCollectionResult) -> None:
        objects = getattr(self._runtime, "_objects", [])
        now = time.time()
        valid_objects: list[KnowledgeObject] = []
        for obj in objects:
            if obj.temporal and not self._runtime._temporal.is_valid(obj.temporal, now):
                result.expired_entries += 1
                continue
            if obj.freshness and obj.freshness.expires > 0 and now >= obj.freshness.expires:
                result.expired_entries += 1
                continue
            valid_objects.append(obj)
        setattr(self._runtime, "_objects", valid_objects)

    def _collect_broken_citations(self, result: GarbageCollectionResult) -> None:
        objects = getattr(self._runtime, "_objects", [])
        for obj in objects:
            for chunk in obj.chunks:
                if chunk.citation:
                    if not chunk.citation.url and not chunk.citation.title:
                        chunk.citation = None
                        result.broken_citations += 1

    def _collect_duplicate_chunks(self, result: GarbageCollectionResult) -> None:
        objects = getattr(self._runtime, "_objects", [])
        for obj in objects:
            seen: set[str] = set()
            unique: list[KnowledgeChunk] = []
            for chunk in obj.chunks:
                key = chunk.text.strip().lower()
                if key in seen:
                    result.duplicate_chunks += 1
                    continue
                seen.add(key)
                unique.append(chunk)
            obj.chunks = unique

    def _collect_orphaned_entities(self, result: GarbageCollectionResult) -> None:
        graph = getattr(self._runtime, "_graph", None)
        if not graph:
            return
        objects = getattr(self._runtime, "_objects", [])
        used_entity_ids: set[str] = set()
        for obj in objects:
            for entity in getattr(obj, "entities", []):
                used_entity_ids.add(entity.id)
            for chunk in obj.chunks:
                for entity in chunk.entities:
                    used_entity_ids.add(entity.id)
        for entity_id in list(graph._entities.keys()):
            if entity_id not in used_entity_ids:
                graph._entities.pop(entity_id, None)
                result.orphaned_entities += 1

    def _collect_unused_graph_nodes(self, result: GarbageCollectionResult) -> None:
        graph = getattr(self._runtime, "_graph", None)
        if not graph:
            return
        connected = set()
        for edge_id, edge in list(graph._edges.items()):
            if edge.weight <= 0.01:
                graph._edges.pop(edge_id, None)
                result.unused_graph_nodes += 1
            else:
                connected.add(edge.source)
                connected.add(edge.target)
        for entity_id in list(graph._entities.keys()):
            if entity_id not in connected:
                graph._entities.pop(entity_id, None)
                result.unused_graph_nodes += 1
