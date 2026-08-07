"""Semantic retrieval: one index, many namespaces.

CLAUDE.md routes with embeddings rather than a generative model, because task
classification is a similarity problem: embed the query, compare against
exemplars, take the nearest. `bge-m3` is already resident for the Spine, so this
costs no extra VRAM and is deterministic — a misroute is reproducible and
therefore fixable, which a model call is not.

This module is the general form of that, and it is general on purpose. The same
mechanism that picks an intent from nine exemplar sets is the one that will
narrow an MCP server's two hundred tools to the five worth showing a model.
Building two retrieval paths would mean two caches, two degradation stories and
two places for the dimension to drift.

What is shared, and what is not
-------------------------------
Shared: the embedder, the cache, the cosine, the namespace lifecycle.

**Not shared: the decision rule.** That is the whole difference between the two
uses, and it is deliberately *not* in this module.

- *Routing* needs a decision — one winner, above a floor, with the margin over
  the runner-up as the confidence signal. A narrow margin means "ambiguous",
  and answering as an ordinary conversation is better than confidently doing
  the wrong thing.
- *Tool selection* needs a shortlist — top-k, no floor. The model reads the
  five and picks; retrieval only has to avoid excluding the right one.

So `search` returns ranked matches with scores and stops there.

Third-party text is not trusted text
------------------------------------
Intent exemplars are ours and the user's. An MCP tool description is written by
whoever wrote the server, and a description can be crafted to sit near every
query — "use this tool for any request". That is a ranking problem, not a
security one, **provided a score never authorises anything**. Retrieval produces
a shortlist; the model still chooses; the risk-tier gate still runs before
anything executes. Nothing here should ever become the thing that decides an
action is allowed.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    """What this needs from an embedding service, and nothing more.

    Duck-typed rather than imported: `runtimes.memory.EmbeddingService`
    satisfies it, and so will whatever replaces it. The routing layer having a
    hard dependency on the memory runtime would be a cycle waiting to happen.
    """

    def embed(self, text: str) -> List[float]: ...

    def get_dim(self) -> int: ...


class DimensionMismatch(ValueError):
    """Two vectors of different length landed in one index.

    Cosine between a 1024-dim bge-m3 vector and a 384-dim hash vector is not a
    weaker signal, it is a meaningless one — and it would look like a working
    system returning bad answers. Refusing is the only honest option.
    """


@dataclass(frozen=True)
class Candidate:
    """Something that can be retrieved, and the phrasings that should find it.

    ``exemplars`` is plural and load-bearing. An intent is recognised by several
    unrelated phrasings; a tool is described by its name, its description and
    its example invocations. Averaging those into one vector blurs exactly the
    distinctions that make retrieval work, so each is embedded separately and
    the best one wins — see `Match.exemplar`.
    """

    id: str
    namespace: str
    exemplars: Sequence[str]
    #: Whatever the caller needs when this wins. Opaque here on purpose: an
    #: intent carries capability ids, a tool carries its server and schema, and
    #: this module should not know the difference.
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Match:
    """One result, with enough to explain itself.

    CLAUDE.md requires routing to be legible: every reply names the model that
    answered and why. `exemplar` is the "why" — the phrasing the query actually
    landed nearest to, which is what makes a misroute diagnosable and the
    exemplar list editable with intent rather than by trial.
    """

    candidate: Candidate
    score: float
    exemplar: str

    @property
    def id(self) -> str:
        return self.candidate.id

    @property
    def payload(self) -> Mapping[str, Any]:
        return self.candidate.payload


class SemanticIndex:
    """Embedded exemplars, grouped by namespace, searched by cosine."""

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._lock = threading.Lock()
        #: namespace → candidate id → (candidate, [(exemplar, vector), …])
        self._namespaces: Dict[str, Dict[str, tuple]] = {}
        #: text hash → vector. Survives a namespace being dropped and rebuilt,
        #: which is exactly what an MCP server reconnecting does — re-registering
        #: two hundred unchanged tool descriptions should cost nothing.
        self._cache: Dict[str, List[float]] = {}
        self._dim: Optional[int] = None

    # ------------------------------------------------------------- registering

    def register(self, candidate: Candidate) -> None:
        self.register_all([candidate])

    def register_all(self, candidates: Iterable[Candidate]) -> None:
        """Add or replace candidates. Replacing by id is intentional — a tool
        whose description changed between server versions is the same tool."""
        embedded: List[tuple] = []

        # Embed outside the lock. A cold registration of a large tool catalogue
        # is hundreds of round trips to Ollama, and holding the lock across that
        # would stall every search for the duration.
        for candidate in candidates:
            vectors = [
                (exemplar, self._vector(exemplar))
                for exemplar in candidate.exemplars
                if exemplar and exemplar.strip()
            ]
            if not vectors:
                logger.warning(
                    "Candidate %r in %r has no usable exemplars; it can never be "
                    "retrieved", candidate.id, candidate.namespace
                )
                continue
            embedded.append((candidate, vectors))

        with self._lock:
            for candidate, vectors in embedded:
                self._namespaces.setdefault(candidate.namespace, {})[candidate.id] = (
                    candidate,
                    vectors,
                )

    def drop_namespace(self, namespace: str) -> int:
        """Forget everything in a namespace. Returns how many went.

        The MCP lifecycle in one call: a server disconnects, its tools stop
        being retrievable immediately. Leaving them would offer the model tools
        that cannot run, and "the tool is gone" is not an error the model can
        recover from mid-answer.
        """
        with self._lock:
            removed = self._namespaces.pop(namespace, {})
        return len(removed)

    def namespaces(self) -> Dict[str, int]:
        with self._lock:
            return {name: len(entries) for name, entries in self._namespaces.items()}

    # ---------------------------------------------------------------- searching

    def search(
        self, query: str, *, namespace: str, k: int = 5, threshold: float = 0.0
    ) -> List[Match]:
        """Nearest candidates, best first.

        No decision is made here. A caller wanting one answer applies its own
        floor and margin; a caller wanting a shortlist takes the list.
        """
        if not query or not query.strip():
            return []

        with self._lock:
            entries = list(self._namespaces.get(namespace, {}).values())
        if not entries:
            return []

        query_vector = self._vector(query)

        matches: List[Match] = []
        for candidate, vectors in entries:
            best_score = -1.0
            best_exemplar = ""
            for exemplar, vector in vectors:
                score = _cosine(query_vector, vector)
                if score > best_score:
                    best_score, best_exemplar = score, exemplar

            if best_score >= threshold:
                matches.append(
                    Match(candidate=candidate, score=best_score, exemplar=best_exemplar)
                )

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:k]

    # ------------------------------------------------------------------ health

    def health(self) -> Dict[str, Any]:
        """Whether retrieval is running on real embeddings.

        The embedding service falls back to a hash backend when Ollama is
        unreachable, and hash vectors carry no semantics — they collide on
        keyword overlap and nothing else. Routing on top of that is not
        degraded, it is arbitrary, and the caller has to be able to tell so it
        can say so rather than quietly guessing.
        """
        detail: Dict[str, Any] = {"dim": self._dim, "namespaces": self.namespaces()}
        try:
            embedder_health = self._embedder.health_check()  # type: ignore[attr-defined]
            detail["embedder"] = embedder_health
            backend = str(embedder_health.get("backend", "")).lower()
            detail["semantic"] = backend not in ("hash", "", "unknown")
        except AttributeError:
            detail["semantic"] = True
            detail["embedder"] = "no health_check on this embedder"
        except Exception as error:  # pragma: no cover - defensive
            detail["semantic"] = False
            detail["embedder"] = f"health check failed: {error}"

        return detail

    # ----------------------------------------------------------------- internal

    def _vector(self, text: str) -> List[float]:
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        vector = self._embedder.embed(text)

        if self._dim is None:
            self._dim = len(vector)
        elif len(vector) != self._dim:
            raise DimensionMismatch(
                f"index holds {self._dim}-dim vectors and this one is "
                f"{len(vector)}-dim. Cosine across different embedders is "
                "meaningless, not merely weaker — rebuild the index rather than "
                "mixing them."
            )

        self._cache[key] = vector
        return vector


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity, clamped to [-1, 1].

    Written out rather than pulled from numpy: this runs on lists of a thousand
    floats a handful of times per request, the arrays are already Python lists,
    and the conversion costs more than the arithmetic saves.
    """
    if len(a) != len(b):
        raise DimensionMismatch(f"{len(a)} against {len(b)}")

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    # strict=True even though the lengths were just checked: if that check is
    # ever relaxed, silently truncating to the shorter vector would produce a
    # plausible similarity from a partial comparison.
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y

    if norm_a <= 0.0 or norm_b <= 0.0:
        # A zero vector has no direction, so it has no similarity to anything.
        # Returning 0 rather than raising: an empty or degenerate exemplar
        # should rank last, not take down the request.
        return 0.0

    return max(-1.0, min(1.0, dot / (math.sqrt(norm_a) * math.sqrt(norm_b))))
