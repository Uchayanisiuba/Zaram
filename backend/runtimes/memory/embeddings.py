# backend/runtimes/memory/embeddings.py
from __future__ import annotations

import hashlib
import math
from typing import Any

#: How long Ollama holds the embedding model after a call. Matches
#: `OllamaEngine.KEEP_ALIVE`; see `_embed_ollama` for why it is not imported.
_KEEP_ALIVE = "30m"

#: Where Ollama answers. One constant so the probe below and the service that
#: does the real work cannot disagree about it — a probe that measured a
#: different Ollama from the one being used would report a dimension for a
#: model nothing is going to call.
DEFAULT_OLLAMA_URL = "http://localhost:11434"


class EmbeddingService:
    """Generates embeddings for text content.

    Supports multiple backends:
    - 'ollama': Uses Ollama's embedding API (requires running Ollama)
    - 'hash': Deterministic hash-based embeddings (fallback, no dependencies)
    """

    def __init__(
        self,
        backend: str = "hash",
        dim: int = 384,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        ollama_model: str = "nomic-embed-text",
        on_gpu: bool = True,
    ):
        self._backend = backend
        self._dim = dim
        self._ollama_url = ollama_url
        self._ollama_model = ollama_model
        #: Whether Ollama may put the embedder's weights on the card. See
        #: `_embed_ollama` and `embed_on_gpu` for the measurement behind it.
        self._on_gpu = on_gpu
        self._cache: dict[str, list[float]] = {}
        self._degraded = False
        #: Said once, not on every call. See `_embed_ollama`.
        self._dim_corrected = False

    @property
    def on_gpu(self) -> bool:
        return self._on_gpu

    def get_dim(self) -> int:
        return self._dim

    def signature(self) -> str:
        """Which embedder this is, as one string stored beside every vector.

        Backend, model and dimension, because all three change what the
        numbers mean: `ollama:bge-m3:1024`, `hash:384`. A vector is only
        comparable with another carrying the same signature — see
        `MemoryRecord.embedded_by`.

        The hash backend names no model on purpose. It is not a model; it is
        the fallback that keeps storage and keyword recall working when Ollama
        is not there, and giving it a model name would suggest its vectors are
        worth comparing against a real one's.
        """
        if self._backend == "ollama":
            return f"ollama:{self._ollama_model}:{self._dim}"
        return f"{self._backend}:{self._dim}"

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        if not text or not text.strip():
            return [0.0] * self._dim

        cache_key = text
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self._backend == "ollama":
            try:
                embedding = self._embed_ollama(text)
            except Exception as e:
                # Ollama unreachable or the model is not pulled. Fall back to
                # hashing so storage and keyword recall keep working, and say so
                # once rather than on every call.
                if not self._degraded:
                    self._degraded = True
                    print(
                        f"[EmbeddingService] Ollama embeddings unavailable "
                        f"({type(e).__name__}: {e}). Falling back to hash embeddings — "
                        f"semantic recall will be weak. Run: ollama pull {self._ollama_model}"
                    )
                embedding = self._embed_hash(text)
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

        # The embedder is a *permanent* tenant, not an occasional one — recall
        # runs on every exchange — so it gets the same treatment the chat model
        # already gets in `OllamaEngine`. Without this it inherited Ollama's
        # five-minute default and was unloaded between questions, which is the
        # same defect `warm_local_model` was written to fix, on the other model.
        #
        # Not imported from `runtimes.models`: this module is the memory
        # runtime and must not depend on the model runtime. Two constants, one
        # value, and a mismatch costs nothing worse than an idle model.
        payload_dict: dict[str, Any] = {
            "model": self._ollama_model,
            "prompt": text,
            "keep_alive": _KEEP_ALIVE,
        }
        # **On a card that cannot hold both, the embedder is what evicts the
        # chat model — measured 12 September 2026.** On a 12 GB card holding a
        # 10.4 GB chat model, one embedding call loaded bge-m3 (0.66 GB) and
        # Ollama evicted the chat model to make room; the next reply loaded
        # the chat model back and evicted the embedder. Every exchange moved
        # ~10 GB through PCIe twice, and the whole desktop stalled while it
        # did. `num_gpu: 0` keeps the embedder's weights in system RAM: a
        # single query embedding on CPU costs ~100 ms, and 0.66 GB of VRAM is
        # the margin that decides whether a 14B fits beside it.
        if not self._on_gpu:
            payload_dict["options"] = {"num_gpu": 0}
        payload = json.dumps(payload_dict).encode()

        req = urllib.request.Request(
            f"{self._ollama_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            embedding = data.get("embedding", [])

        if embedding and len(embedding) != self._dim:
            # **The model is right and the configuration is wrong.** This used
            # to zero-pad or truncate to the configured length, which is the
            # `Win32_VideoController.AdapterRAM` failure in another module: a
            # confident wrong number where the honest move is to take the
            # measurement. A padded vector is not a worse embedding, it is not
            # an embedding — half of it is zeros nobody computed, and it is
            # then compared by cosine against real ones.
            #
            # The dimension is adopted rather than raised over, because it is
            # safe to: `signature()` carries the dimension, so vectors made
            # before and after this correction are never compared with each
            # other.
            if not self._dim_corrected:
                self._dim_corrected = True
                print(
                    f"[EmbeddingService] {self._ollama_model} returns "
                    f"{len(embedding)} dimensions, not the configured {self._dim}. "
                    f"Taking the model's number."
                )
            self._dim = len(embedding)
        return embedding

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


def probe_dim(
    *,
    backend: str,
    model: str,
    fallback: int,
    url: str = DEFAULT_OLLAMA_URL,
    on_gpu: bool = False,
) -> int:
    """How many numbers this embedder actually returns.

    Asked once, at boot, rather than configured — because a configured
    dimension is a value nobody measured, and the one thing every other
    measurement in this product is written to avoid. `ZARAM_EMBED_DIM` used to
    default to 1024 "because bge-m3", which is right until somebody chooses a
    768-dimension model in Settings and nothing anywhere notices.

    Falls back to ``fallback`` rather than raising: an unreachable Ollama
    already degrades to hash embeddings, and a boot that stops because a probe
    failed would be a worse product than one that starts with a stale number
    it will correct on the first real call.
    """
    if backend != "ollama":
        return fallback
    try:
        service = EmbeddingService(
            backend="ollama", dim=fallback, ollama_url=url,
            ollama_model=model, on_gpu=on_gpu,
        )
        vector = service._embed_ollama("dimension probe")
        return len(vector) or fallback
    except Exception as error:  # noqa: BLE001 - a probe never blocks boot
        print(f"[EmbeddingService] Could not measure {model}'s dimensions ({error}).")
        return fallback


#: Below this much VRAM the embedder runs on the CPU.
#:
#: Measured rather than chosen: a 14B at Q4_K_M with a 16k window holds
#: 10.4 GB, the desktop under it holds 2.2-3.0 GB, and bge-m3 holds 0.66 GB.
#: That sum clears 12 GB and does not clear 16 GB, so 16 GB is the smallest
#: common card size on which the embedder and a mid-size chat model can share
#: the card without one evicting the other. Above it the GPU makes folder
#: ingestion several times faster and costs nothing that matters; below it the
#: same 0.66 GB is the difference between a resident chat model and a 10 GB
#: swap on every question.
EMBED_ON_GPU_MIN_VRAM_BYTES = 16 * 1024**3


def embed_on_gpu(vram_bytes: int | None, preference: str | None = None) -> bool:
    """Whether the embedder's weights may go on the card.

    ``preference`` is the `ZARAM_EMBED_DEVICE` override -- ``"gpu"``, ``"cpu"``,
    or anything else for automatic. Automatic decides from the card's size and
    answers **CPU when the size is unknown**: an unmeasurable card is the case
    where a confident wrong answer costs the most, and CPU embedding is slower
    rather than broken.
    """
    choice = (preference or "").strip().lower()
    if choice == "gpu":
        return True
    if choice == "cpu":
        return False
    return vram_bytes is not None and vram_bytes >= EMBED_ON_GPU_MIN_VRAM_BYTES
