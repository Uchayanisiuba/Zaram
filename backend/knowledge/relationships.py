# backend/knowledge/relationships.py
from __future__ import annotations

import re
import threading
from typing import Any
from .protocol import (
    Entity, EntityType, KnowledgeChunk, KnowledgeObject,
    Relationship, RelationshipType,
)


_RULES: list[tuple[RelationshipType, list[str]]] = [
    (RelationshipType.WORKS_AT, ["works at", "works for", "employed by", "employee of"]),
    (RelationshipType.OWNS, ["owns", "owned by", "acquisition", "acquired"]),
    (RelationshipType.CREATED, ["created", "founded", "developed", "built", "invented"]),
    (RelationshipType.PART_OF, ["part of", "subsidiary of", "division of", "unit of"]),
    (RelationshipType.USES, ["uses", "using", "built with", "powered by", "runs on"]),
    (RelationshipType.DEPENDS_ON, ["depends on", "requires", "needs", "relies on"]),
    (RelationshipType.MENTIONS, ["mentions", "referenced in", "cited in"]),
    (RelationshipType.REFERENCES, ["references", "see also", "related to", "linked to"]),
    (RelationshipType.RELATED_TO, ["related", "similar to", "associated with", "connected to"]),
    (RelationshipType.LOCATED_IN, ["located in", "based in", "headquartered in", "from"]),
    (RelationshipType.MEMBER_OF, ["member of", "part of team", "joins", "joined"]),
]


class RelationshipBuilder:
    """Automatically infer relationships between entities."""

    def __init__(self):
        self._entity_pairs: set[tuple[str, str]] = set()
        self._lock = threading.Lock()

    def build_from_chunk(self, chunk: KnowledgeChunk) -> list[Relationship]:
        entities = chunk.entities or []
        relationships: list[Relationship] = []
        text_lower = chunk.text.lower()
        for i, source in enumerate(entities):
            for j, target in enumerate(entities):
                if i == j:
                    continue
                rel_type, confidence = self._infer_relationship(text_lower, source, target)
                if rel_type:
                    pair = tuple(sorted([source.id, target.id]))
                    with self._lock:
                        if pair in self._entity_pairs:
                            continue
                        self._entity_pairs.add(pair)
                    relationships.append(Relationship(
                        source_id=source.id,
                        target_id=target.id,
                        relationship_type=rel_type,
                        confidence=confidence,
                        metadata={"chunk_id": chunk.id},
                    ))
        return relationships

    def build_from_object(self, obj: KnowledgeObject) -> list[Relationship]:
        relationships: list[Relationship] = []
        for chunk in obj.chunks:
            relationships.extend(self.build_from_chunk(chunk))
        obj.relationships = relationships
        return relationships

    def _infer_relationship(self, text: str, source: Entity, target: Entity) -> tuple[RelationshipType | None, float]:
        source_name = source.name.lower()
        target_name = target.name.lower()
        text_lower = text.lower()
        for rel_type, indicators in _RULES:
            for indicator in indicators:
                pattern = rf"{re.escape(source_name)}\s+{re.escape(indicator)}\s+{re.escape(target_name)}"
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return rel_type, 0.9
                pattern_rev = rf"{re.escape(target_name)}\s+{re.escape(indicator)}\s+{re.escape(source_name)}"
                if re.search(pattern_rev, text_lower, re.IGNORECASE):
                    return rel_type, 0.8
        if source.entity_type == EntityType.PERSON and target.entity_type == EntityType.ORGANIZATION:
            return RelationshipType.WORKS_AT, 0.4
        if source.entity_type == EntityType.ORGANIZATION and target.entity_type == EntityType.PRODUCT:
            return RelationshipType.OWNS, 0.3
        if source.entity_type == EntityType.TECHNOLOGY and target.entity_type == EntityType.ORGANIZATION:
            return RelationshipType.USES, 0.3
        return RelationshipType.RELATED_TO, 0.2
