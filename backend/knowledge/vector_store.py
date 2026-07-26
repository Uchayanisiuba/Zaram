# backend/knowledge/vector_store.py
from __future__ import annotations

import json
import math
import os
import threading
from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeChunk, VectorStore


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class LocalVectorStore(VectorStore):
    """In-memory local vector store with persistent index support."""

    index_path: str = ""
    _chunks: dict[str, KnowledgeChunk] = field(default_factory=dict)
    _vectors: dict[str, list[float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, chunks: list[KnowledgeChunk]) -> None:
        with self._lock:
            for chunk in chunks:
                if chunk.embedding:
                    self._chunks[chunk.id] = chunk
                    self._vectors[chunk.id] = list(chunk.embedding)

    def search(self, query_vector: list[float], top_k: int = 10) -> list[tuple[KnowledgeChunk, float]]:
        with self._lock:
            scored = [
                (self._chunks[cid], _cosine_similarity(query_vector, vec))
                for cid, vec in self._vectors.items()
            ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def delete(self, chunk_id: str) -> None:
        with self._lock:
            self._chunks.pop(chunk_id, None)
            self._vectors.pop(chunk_id, None)

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._vectors.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._chunks)

    def persist(self, path: str) -> None:
        with self._lock:
            data = {
                "chunks": [
                    {
                        "id": c.id,
                        "text": c.text,
                        "embedding": c.embedding,
                        "token_count": c.token_count,
                        "chunk_index": c.chunk_index,
                        "metadata": c.metadata,
                    }
                    for c in self._chunks.values()
                ]
            }
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        with self._lock:
            for item in data.get("chunks", []):
                chunk = KnowledgeChunk(
                    id=item["id"],
                    text=item.get("text", ""),
                    embedding=item.get("embedding"),
                    token_count=item.get("token_count", 0),
                    chunk_index=item.get("chunk_index", 0),
                    metadata=item.get("metadata", {}),
                )
                self._chunks[chunk.id] = chunk
                if chunk.embedding:
                    self._vectors[chunk.id] = list(chunk.embedding)
