# backend/runtimes/memory/embeddings.py
from __future__ import annotations

import hashlib
import math
from typing import Any


class EmbeddingService:
    """Generates embeddings for text content.

    Supports multiple backends:
    - 'ollama': Uses Ollama's embedding API (requires running Ollama)
    - 'hash': Deterministic hash-based embeddings (fallback, no dependencies)
    """

    def __init__(self, backend: str = "hash", dim: int = 384, ollama_url: str = "http://localhost:11434", ollama_model: str = "nomic-embed-text"):
        self._backend = backend
        self._dim = dim
        self._ollama_url = ollama_url
        self._ollama_model = ollama_model
        self._cache: dict[str, list[float]] = {}

    def get_dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        if not text or not text.strip():
            return [0.0] * self._dim

        cache_key = text
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self._backend == "ollama":
            embedding = self._embed_ollama(text)
        else:
            embedding = self._embed_hash(text)

        self._cache[cache_key] = embedding
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [self.embed(t) for t in texts]

    def _embed_hash(self, text: str) -> list[float]:
        """Deterministic hash-based embedding.

        Produces a fixed-size vector from the text using multiple hash functions.
        This is a fallback when no embedding model is available.
        """
        normalized = text.lower().strip()
        vec = [0.0] * self._dim

        for i in range(self._dim):
            h = hashlib.md5(f"{i}:{normalized}".encode()).digest()
            val = int.from_bytes(h[:4], "big") / (2**32)
            vec[i] = val * 2 - 1

        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def _embed_ollama(self, text: str) -> list[float]:
        """Generate embedding using Ollama's embedding API."""
        import json
        import urllib.request

        payload = json.dumps({
            "model": self._ollama_model,
            "prompt": text,
        }).encode()

        req = urllib.request.Request(
            f"{self._ollama_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            embedding = data.get("embedding", [])
            if len(embedding) != self._dim:
                embedding = self._pad_or_truncate(embedding, self._dim)
            return embedding

    def _pad_or_truncate(self, vec: list[float], target_dim: int) -> list[float]:
        if len(vec) >= target_dim:
            return vec[:target_dim]
        return vec + [0.0] * (target_dim - len(vec))

    def clear_cache(self) -> None:
        self._cache.clear()

    def health_check(self) -> dict[str, Any]:
        if self._backend == "ollama":
            try:
                self._embed_ollama("test")
                return {"status": "healthy", "backend": self._backend, "dim": self._dim}
            except Exception as e:
                return {"status": "degraded", "backend": self._backend, "error": str(e)}
        return {"status": "healthy", "backend": self._backend, "dim": self._dim}


def create_embedding_service(backend: str = "hash", dim: int = 384, **kwargs) -> EmbeddingService:
    """Factory for creating embedding services."""
    return EmbeddingService(backend=backend, dim=dim, **kwargs)
