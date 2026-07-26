# backend/knowledge/reindexing.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeChunk, KnowledgeObject


@dataclass
class ReindexTask:
    task_id: str
    task_type: str
    created_at: float = field(default_factory=time.time)
    status: str = "pending"
    processed: int = 0
    total: int = 0
    error: str | None = None


class BackgroundReindexer:
    """Background maintenance worker for knowledge reindexing."""

    def __init__(self, runtime: Any):
        self._runtime = runtime
        self._queue: list[ReindexTask] = []
        self._lock: threading.Lock = threading.Lock()
        self._running = False
        self._worker_thread: threading.Thread | None = None
        self._interval_seconds: int = 3600

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._worker_thread = threading.Thread(target=self._run, daemon=True)
            self._worker_thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)

    def enqueue(self, task_type: str, items: list[Any]) -> ReindexTask:
        task = ReindexTask(
            task_id=f"reindex-{int(time.time()*1000)}",
            task_type=task_type,
            total=len(items),
        )
        with self._lock:
            self._queue.append(task)
        return task

    def _run(self) -> None:
        while True:
            with self._lock:
                if not self._running:
                    break
                if not self._queue:
                    time.sleep(self._interval_seconds)
                    continue
                task = self._queue.pop(0)
            try:
                task.status = "running"
                self._process_task(task)
                task.status = "completed"
            except Exception as e:
                task.status = "failed"
                task.error = str(e)

    def _process_task(self, task: ReindexTask) -> None:
        if task.task_type == "refresh_embeddings":
            self._refresh_embeddings(task)
        elif task.task_type == "rebuild_relationships":
            self._rebuild_relationships(task)
        elif task.task_type == "merge_duplicates":
            self._merge_duplicates(task)
        elif task.task_type == "refresh_authority":
            self._refresh_authority(task)
        elif task.task_type == "update_confidence":
            self._update_confidence(task)
        elif task.task_type == "garbage_collect":
            self._garbage_collect(task)

    def _refresh_embeddings(self, task: ReindexTask) -> None:
        from .incremental_embedding import IncrementalEmbeddingEngine
        engine = IncrementalEmbeddingEngine()
        engine.embedding = self._runtime._embedding
        for obj in getattr(self._runtime, "_objects", []):
            engine.embed_object(obj, force=True)
            task.processed += 1

    def _rebuild_relationships(self, task: ReindexTask) -> None:
        from .relationships import RelationshipBuilder
        builder = RelationshipBuilder()
        for obj in getattr(self._runtime, "_objects", []):
            builder.build_from_object(obj)
            task.processed += 1

    def _merge_duplicates(self, task: ReindexTask) -> None:
        response = self._runtime.search("", max_results=1000)
        from .fusion import KnowledgeFusionEngine
        engine = KnowledgeFusionEngine()
        engine.fuse(response.results)
        task.processed = len(response.results)

    def _refresh_authority(self, task: ReindexTask) -> None:
        registry = getattr(self._runtime, "_authority", None)
        if not registry:
            return
        for provider in getattr(self._runtime, "_providers", []):
            registry.register(provider.id, provider.priority() / 100.0)
            task.processed += 1

    def _update_confidence(self, task: ReindexTask) -> None:
        for obj in getattr(self._runtime, "_objects", []):
            if obj.confidence:
                obj.confidence = self._runtime._confidence.compute(
                    result=__import__("knowledge.protocol", fromlist=["KnowledgeResult"]).KnowledgeResult(title=obj.content[:80], confidence=obj.confidence.confidence),
                    sources=obj.confidence.sourceCount,
                    agreement=obj.confidence.agreementScore,
                    freshness=obj.freshness.compute_score() if obj.freshness else 1.0,
                    ranking=obj.confidence.rankingScore,
                )
            task.processed += 1

    def _garbage_collect(self, task: ReindexTask) -> None:
        from .garbage_collection import KnowledgeGarbageCollector
        collector = KnowledgeGarbageCollector(self._runtime)
        result = collector.collect()
        task.processed = result.get("removed_count", 0)
