# backend/knowledge/graph.py
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any
from .protocol import (
    Entity, EntityAlias, Edge, KnowledgeChunk, KnowledgeObject,
    Relationship, RelationshipType, EntityType,
)


@dataclass
class KnowledgeGraph:
    """Graph layer above vector retrieval."""

    _entities: dict[str, Entity] = field(default_factory=dict)
    _edges: dict[str, Edge] = field(default_factory=dict)
    _adjacency: dict[str, set[str]] = field(default_factory=dict)
    _reverse_adjacency: dict[str, set[str]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add_entity(self, entity: Entity) -> None:
        with self._lock:
            self._entities[entity.id] = entity
            for alias in entity.aliases:
                self._adjacency.setdefault(alias.lower(), set()).add(entity.id)
                self._reverse_adjacency.setdefault(entity.id, set()).add(alias.lower())

    def add_relationship(self, rel: Relationship) -> None:
        with self._lock:
            edge = Edge(
                source=rel.source_id,
                target=rel.target_id,
                relationship_type=rel.relationship_type,
                weight=rel.confidence,
                metadata={"relationship_id": rel.id},
            )
            self._edges[rel.id] = edge
            self._adjacency.setdefault(rel.source_id, set()).add(rel.target_id)
            self._reverse_adjacency.setdefault(rel.target_id, set()).add(rel.source_id)

    def add_edge(self, edge: Edge) -> None:
        self.add_relationship(Relationship(
            id=edge.metadata.get("relationship_id", ""),
            source_id=edge.source,
            target_id=edge.target,
            relationship_type=edge.relationship_type,
            confidence=edge.weight,
        ))

    def get_entity(self, entity_id: str) -> Entity | None:
        with self._lock:
            return self._entities.get(entity_id)

    def find_entity_by_name(self, name: str, exact_match: bool = False) -> Entity | None:
        with self._lock:
            if exact_match:
                entity = self._entities.get(name)
                if entity:
                    return entity
            # Fall back to alias resolution
            name_lower = name.lower()
            entity_ids = self._adjacency.get(name_lower, set())
            if entity_ids:
                return self._entities.get(next(iter(entity_ids)))
            for entity in self._entities.values():
                if entity.name.lower() == name_lower:
                    return entity
                if name_lower in [a.lower() for a in entity.aliases]:
                    return entity
        return None

    def get_neighbors(self, entity_id: str, relationship_type: RelationshipType | None = None) -> list[tuple[Entity, RelationshipType]]:
        with self._lock:
            neighbors: list[tuple[Entity, RelationshipType]] = []
            targets = self._adjacency.get(entity_id, set())
            for target_id in targets:
                for edge in self._edges.values():
                    if edge.source == entity_id and edge.target == target_id:
                        if relationship_type is None or edge.relationship_type == relationship_type:
                            entity = self._entities.get(target_id)
                            if entity:
                                neighbors.append((entity, edge.relationship_type))
                        break
            return neighbors

    def get_predecessors(self, entity_id: str) -> list[tuple[Entity, RelationshipType]]:
        with self._lock:
            predecessors: list[tuple[Entity, RelationshipType]] = []
            sources = self._reverse_adjacency.get(entity_id, set())
            for source_id in sources:
                for edge in self._edges.values():
                    if edge.source == source_id and edge.target == entity_id:
                        entity = self._entities.get(source_id)
                        if entity:
                            predecessors.append((entity, edge.relationship_type))
                        break
            return predecessors

    def traverse(self, start: str, relationship_type: RelationshipType | None = None, max_depth: int = 3) -> list[Entity]:
        visited = set()
        result: list[Entity] = []
        stack = [(start, 0)]
        while stack:
            current, depth = stack.pop()
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            entity = self._entities.get(current)
            if entity and depth > 0:
                result.append(entity)
            for neighbor, _ in self.get_neighbors(current, relationship_type):
                stack.append((neighbor.id, depth + 1))
        return result

    def neighborhood_search(self, query: str, max_results: int = 10) -> list[Entity]:
        with self._lock:
            query_lower = query.lower()
            scored: list[tuple[float, Entity]] = []
            for entity in self._entities.values():
                score = 0.0
                if entity.name.lower() == query_lower:
                    score += 2.0
                elif query_lower in entity.name.lower():
                    score += 1.0
                for alias in entity.aliases:
                    if alias.lower() == query_lower:
                        score += 1.5
                    elif query_lower in alias.lower():
                        score += 0.5
                if score > 0:
                    scored.append((score, entity))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [e for _, e in scored[:max_results]]

    def entity_count(self) -> int:
        with self._lock:
            return len(self._entities)

    def relationship_count(self) -> int:
        with self._lock:
            return len(self._edges)

    def clear(self) -> None:
        with self._lock:
            self._entities.clear()
            self._edges.clear()
            self._adjacency.clear()
            self._reverse_adjacency.clear()

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entity_count": len(self._entities),
                "relationship_count": len(self._edges),
            }
