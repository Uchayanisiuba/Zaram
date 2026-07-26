# backend/knowledge/cross_document.py
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any
from .protocol import Entity, KnowledgeChunk, KnowledgeObject, Relationship, RelationshipType


@dataclass
class CrossDocumentLinker:
    """Automatically connect related documents."""

    _links: dict[str, set[str]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def link_objects(self, objects: list[KnowledgeObject]) -> list[Relationship]:
        relationships: list[Relationship] = []
        for i, obj_a in enumerate(objects):
            for j, obj_b in enumerate(objects):
                if i == j:
                    continue
                rels = self._link_pair(obj_a, obj_b)
                relationships.extend(rels)
        return relationships

    def _link_pair(self, a: KnowledgeObject, b: KnowledgeObject) -> list[Relationship]:
        relationships: list[Relationship] = []
        shared_entities = self._shared_entities(a, b)
        for entity in shared_entities:
            relationships.append(Relationship(
                source_id=a.id,
                target_id=b.id,
                relationship_type=RelationshipType.REFERENCES,
                confidence=0.7,
                metadata={"shared_entity_id": entity.id, "shared_entity_name": entity.name},
            ))
        shared_concepts = self._shared_concepts(a, b)
        for concept in shared_concepts:
            relationships.append(Relationship(
                source_id=a.id,
                target_id=b.id,
                relationship_type=RelationshipType.RELATED_TO,
                confidence=0.5,
                metadata={"shared_concept": concept},
            ))
        return relationships

    def _shared_entities(self, a: KnowledgeObject, b: KnowledgeObject) -> list[Entity]:
        a_entities = {e.name.lower(): e for e in getattr(a, "entities", [])}
        b_entities = {e.name.lower(): e for e in getattr(b, "entities", [])}
        shared = []
        for name, entity in a_entities.items():
            if name in b_entities:
                shared.append(entity)
        return shared

    def _shared_concepts(self, a: KnowledgeObject, b: KnowledgeObject) -> list[str]:
        a_words = set(a.content.lower().split())
        b_words = set(b.content.lower().split())
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "shall", "to", "of", "in", "for", "on", "with", "at", "by", "from", "as", "into", "through", "during", "before", "after", "above", "below", "between", "out", "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "each", "every", "both", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "just", "because", "but", "and", "or", "if", "while", "about", "against", "up", "down", "it", "its", "this", "that", "these", "those", "i", "me", "my", "we", "our", "you", "your", "he", "him", "his", "she", "her", "they", "them", "their"}
        concepts = (a_words - stop_words) & (b_words - stop_words)
        return list(concepts)[:10]

    def get_links(self, object_id: str) -> set[str]:
        with self._lock:
            return self._links.get(object_id, set()).copy()

    def record_link(self, source_id: str, target_id: str) -> None:
        with self._lock:
            self._links.setdefault(source_id, set()).add(target_id)
            self._links.setdefault(target_id, set()).add(source_id)
