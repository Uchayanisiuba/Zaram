# backend/knowledge/embedding.py
from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from .protocol import EmbeddingProvider


@dataclass
class HashEmbeddingProvider(EmbeddingProvider):
    _cache: dict[str, list[float]] = field(default_factory=dict, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _dimension: int = 384

    def __init__(self, dimension: int = 384, **kwargs: Any) -> None:
        self._cache = {}
        self._lock = threading.Lock()
        self._dimension = dimension

    @property
    def id(self) -> str:
        return "hash"

    def dimension(self) -> int:
        return self._dimension

    def _hash_vector(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec: list[float] = []
        dim = self._dimension
        for i in range(dim):
            byte_val = h[i % len(h)]
            vec.append((byte_val / 255.0) * 2 - 1)
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            key = text.strip().lower()
            with self._lock:
                if key in self._cache:
                    results.append(self._cache[key])
                    continue
            vec = self._hash_vector(text)
            with self._lock:
                self._cache[key] = vec
            results.append(vec)
        return results

    def is_available(self) -> bool:
        return True


@dataclass
class EmbeddingRuntime:
    """Provider-agnostic embedding runtime with dynamic registration."""

    providers: dict[str, EmbeddingProvider] = field(default_factory=dict)
    _default: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def register(self, provider: EmbeddingProvider) -> None:
        with self._lock:
            self.providers[provider.id] = provider
            if self._default is None:
                self._default = provider.id

    def unregister(self, provider_id: str) -> None:
        with self._lock:
            self.providers.pop(provider_id, None)
            if self._default == provider_id:
                self._default = next(iter(self.providers)) if self.providers else None

    def get_provider(self, provider_id: str) -> EmbeddingProvider | None:
        return self.providers.get(provider_id)

    def default_provider(self) -> EmbeddingProvider | None:
        return self.providers.get(self._default) if self._default else None

    def embed(self, texts: list[str], provider_id: str | None = None) -> list[list[float]]:
        provider = self.get_provider(provider_id) if provider_id else self.default_provider()
        if not provider:
            raise RuntimeError("No embedding provider available")
        return provider.embed(texts)

    def list_providers(self) -> list[dict[str, Any]]:
        return [
            {
                "id": p.id,
                "dimension": p.dimension(),
                "available": p.is_available(),
                "default": p.id == self._default,
            }
            for p in self.providers.values()
        ]

    def health(self) -> dict[str, Any]:
        default = self.default_provider()
        return {
            "default_provider": self._default,
            "providers": len(self.providers),
            "available": default.is_available() if default else False,
        }
