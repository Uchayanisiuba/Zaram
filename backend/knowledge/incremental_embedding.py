# backend/knowledge/incremental_embedding.py
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeChunk, KnowledgeObject
from .embedding import EmbeddingRuntime


@dataclass
class IncrementalEmbeddingEngine:
    """Detect changed chunks and embed only modified chunks."""

    embedding: EmbeddingRuntime = field(default_factory=EmbeddingRuntime)
    _hash_cache: dict[str, str] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def register_provider(self, provider: Any) -> None:
        self.embedding.register(provider)

    def embed_object(self, obj: KnowledgeObject, force: bool = False) -> list[KnowledgeChunk]:
        changed_chunks: list[KnowledgeChunk] = []
        for chunk in obj.chunks:
            chunk_hash = self._compute_hash(chunk.text)
            with self._lock:
                cached_hash = self._hash_cache.get(chunk.id)
            if force or cached_hash != chunk_hash:
                changed_chunks.append(chunk)
                with self._lock:
                    self._hash_cache[chunk.id] = chunk_hash
        if changed_chunks:
            texts = [c.text for c in changed_chunks]
            vectors = self.embedding.embed(texts)
            for chunk, vector in zip(changed_chunks, vectors):
                chunk.embedding = vector
        return changed_chunks

    def embed_chunks(self, chunks: list[KnowledgeChunk], force: bool = False) -> list[KnowledgeChunk]:
        changed: list[KnowledgeChunk] = []
        for chunk in chunks:
            chunk_hash = self._compute_hash(chunk.text)
            with self._lock:
                cached_hash = self._hash_cache.get(chunk.id)
            if force or cached_hash != chunk_hash:
                changed.append(chunk)
                with self._lock:
                    self._hash_cache[chunk.id] = chunk_hash
        if changed:
            texts = [c.text for c in changed]
            vectors = self.embedding.embed(texts)
            for chunk, vector in zip(changed, vectors):
                chunk.embedding = vector
        return changed

    def _compute_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def clear_cache(self) -> None:
        with self._lock:
            self._hash_cache.clear()
