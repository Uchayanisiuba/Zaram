"""Semantic retrieval — routing today, MCP tool selection next.

One index, one similarity computation, two decision rules. See `index.py` for
why those are separated and `router.py` for the two rules themselves.
"""

from .exemplars import INTENT_EXEMPLARS, INTENT_NAMESPACE, intent_candidates
from .index import (
    Candidate,
    DimensionMismatch,
    Embedder,
    Match,
    SemanticIndex,
)
from .router import (
    DEFAULT_FLOOR,
    DEFAULT_MARGIN,
    FALLBACK_INTENT,
    RouteDecision,
    SemanticIntentRouter,
    shortlist,
)

__all__ = [
    "Candidate",
    "DEFAULT_FLOOR",
    "DEFAULT_MARGIN",
    "DimensionMismatch",
    "Embedder",
    "FALLBACK_INTENT",
    "INTENT_EXEMPLARS",
    "INTENT_NAMESPACE",
    "Match",
    "RouteDecision",
    "SemanticIndex",
    "SemanticIntentRouter",
    "intent_candidates",
    "shortlist",
]
