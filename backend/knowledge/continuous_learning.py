# backend/knowledge/continuous_learning.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeChunk, KnowledgeObject


@dataclass
class ContinuousLearningPipeline:
    """Continuous learning pipeline for knowledge evolution."""

    runtime: Any = None
    _running: bool = False
    _thread: threading.Thread | None = None
    _interval_seconds: int = 1800
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                time.sleep(self._interval_seconds)
                if not self._running:
                    break
            try:
                self._evolve()
            except Exception:
                pass

    def _evolve(self) -> None:
        if not self.runtime:
            return
        objects = getattr(self.runtime, "_objects", [])
        if not objects:
            return
        self._reorganize(objects)
        self._rebuild_graph(objects)
        self._update_confidence(objects)
        self._refresh_indexes(objects)

    def _reorganize(self, objects: list[KnowledgeObject]) -> None:
        for obj in objects:
            if hasattr(obj, "chunks") and obj.chunks:
                texts = [c.text for c in obj.chunks]
                seen: set[str] = set()
                unique: list[KnowledgeChunk] = []
                for chunk in obj.chunks:
                    key = chunk.text.strip().lower()
                    if key not in seen:
                        seen.add(key)
                        unique.append(chunk)
                obj.chunks = unique

    def _rebuild_graph(self, objects: list[KnowledgeObject]) -> None:
        graph = getattr(self.runtime, "_graph", None)
        if not graph:
            return
        from .entity_extraction import EntityExtractor
        from .relationships import RelationshipBuilder
        extractor = EntityExtractor()
        builder = RelationshipBuilder()
        for obj in objects:
            extraction = extractor.extract_from_object(obj)
            for entity in extraction.entities:
                graph.add_entity(entity)
            relationships = builder.build_from_object(obj)
            for rel in relationships:
                graph.add_relationship(rel)

    def _update_confidence(self, objects: list[KnowledgeObject]) -> None:
        for obj in objects:
            if obj.confidence and obj.freshness:
                obj.confidence = self.runtime._confidence.compute(
                    result=__import__("knowledge.protocol", fromlist=["KnowledgeResult"]).KnowledgeResult(title=obj.content[:80], confidence=obj.confidence.confidence),
                    sources=obj.confidence.sourceCount,
                    agreement=obj.confidence.agreementScore,
                    freshness=obj.freshness.compute_score(),
                    ranking=obj.confidence.rankingScore,
                )

    def _refresh_indexes(self, objects: list[KnowledgeObject]) -> None:
        vector_store = getattr(self.runtime, "_vector_store", None)
        incremental = getattr(self.runtime, "_incremental_embedding", None)
        if not vector_store or not incremental:
            return
        for obj in objects:
            changed = incremental.embed_object(obj, force=False)
            if changed:
                vector_store.add(changed)
