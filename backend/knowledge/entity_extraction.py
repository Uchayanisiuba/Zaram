# backend/knowledge/entity_extraction.py
from __future__ import annotations

import re
import threading
from typing import Any
from .protocol import Entity, EntityAlias, EntityType, KnowledgeChunk, KnowledgeObject


_PATTERNS: dict[EntityType, list[str]] = {
    EntityType.PERSON: [
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b",
    ],
    EntityType.ORGANIZATION: [
        r"\b(?:[A-Z][a-z]*\s*)+(?:Inc|Corp|LLC|Ltd|Company|Corporation|Foundation|Institute|University|Group)\b",
        r"\b[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*\b",
    ],
    EntityType.PLACE: [
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:City|State|Country|Province|Region|Valley|Mountain|River|Lake)\b",
    ],
    EntityType.PRODUCT: [
        r"\b[A-Z][a-zA-Z0-9]*(?:\s+[a-zA-Z0-9]+)*\s+(?:Pro|Max|Mini|Plus|Ultra|Edition|Version)\b",
    ],
    EntityType.TECHNOLOGY: [
        r"\b(?:Python|JavaScript|TypeScript|Rust|Go|React|Vue|Angular|Docker|Kubernetes|TensorFlow|PyTorch|PostgreSQL|Redis|MongoDB|GraphQL|REST|API|SDK|CLI)\b",
    ],
    EntityType.EVENT: [
        r"\b(?:WWDC|CES|Google I/O|Build|F8|SIGGRAPH|GDC|KubeCon|PyCon|RustConf|React Conf)\b",
    ],
    EntityType.DATE: [
        r"\b(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?)\b",
    ],
    EntityType.DOCUMENT: [
        r"\b(?:README|CHANGELOG|LICENSE|CONTRIBUTING|Makefile|Dockerfile|package\.json|requirements\.txt|pyproject\.toml)\b",
    ],
    EntityType.CONCEPT: [
        r"\b(?:Machine Learning|Deep Learning|Neural Network|Transformer|Attention|Embedding|Vector|Semantic|Graph|API|REST|GraphQL)\b",
    ],
}


class EntityExtractor:
    """Automatic entity extraction from knowledge text."""

    def __init__(self):
        self._compiled: dict[EntityType, list[re.Pattern]] = {}
        for etype, patterns in _PATTERNS.items():
            self._compiled[etype] = [re.compile(p) for p in patterns]

    def extract_from_chunk(self, chunk: KnowledgeChunk) -> EntityExtractionResult:
        entities: list[Entity] = []
        aliases: list[EntityAlias] = []
        seen_names: set[str] = set()
        for etype, patterns in self._compiled.items():
            for pattern in patterns:
                for match in pattern.finditer(chunk.text):
                    name = match.group(0).strip()
                    if not name or name.lower() in seen_names:
                        continue
                    seen_names.add(name.lower())
                    entity = Entity(name=name, entity_type=etype)
                    entities.append(entity)
                    aliases.append(EntityAlias(alias=name, entity_id=entity.id))
        return EntityExtractionResult(entities=entities, aliases=aliases)

    def extract_from_object(self, obj: KnowledgeObject) -> EntityExtractionResult:
        all_entities: list[Entity] = []
        all_aliases: list[EntityAlias] = []
        seen_names: set[str] = set()
        for chunk in obj.chunks:
            result = self.extract_from_chunk(chunk)
            for entity in result.entities:
                if entity.name.lower() not in seen_names:
                    all_entities.append(entity)
                    seen_names.add(entity.name.lower())
            all_aliases.extend(result.aliases)
        obj.entities = all_entities
        return EntityExtractionResult(entities=all_entities, aliases=all_aliases)


class EntityExtractionResult:
    def __init__(self, entities: list[Entity] | None = None, aliases: list[EntityAlias] | None = None):
        self.entities = entities or []
        self.aliases = aliases or []
