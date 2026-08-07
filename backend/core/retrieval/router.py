"""The decision rule for routing: one winner, or an honest shrug.

`SemanticIndex.search` ranks. This turns a ranking into a decision, and the two
are separate because tool selection wants the ranking and nothing else — see the
module docstring in `index.py`.

Two gates, and the second is the one that matters
-------------------------------------------------
**A floor.** Below it, nothing was close enough to anything, and the request is
an ordinary conversation.

**A margin.** The gap between first and second place. Cosine scores against
short exemplars run high and close together, so a top score of 0.71 means very
little on its own — but 0.71 against a runner-up of 0.44 means something, and
0.71 against 0.70 means the two are indistinguishable. Routing on the top score
alone produces confident wrong answers on exactly the ambiguous phrasings that
most need care, and a wrong route is worse than no route: it sends the request
to a capability that will answer the wrong question convincingly.

When the margin is too narrow, this returns `conversation` and says why. An
ordinary answer to an ambiguous request is recoverable; a document generated
from a question is not.

Degradation is visible, not silent
----------------------------------
The embedding service falls back to a hash backend when Ollama is unreachable.
Hash vectors collide on keyword overlap and carry no semantics, so routing on
them is not "slightly worse" — it is arbitrary. When the index reports it is not
running semantically, this refuses to route and hands back to the keyword
classifier, which is at least predictable. CLAUDE.md: never render invented
values; a confident route computed from noise is one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .exemplars import INTENT_NAMESPACE, intent_candidates
from .index import SemanticIndex

logger = logging.getLogger(__name__)

#: Nothing below this is close enough to anything to act on.
DEFAULT_FLOOR = 0.45

#: First place must beat second by this much. Tuned against the exemplar set:
#: unrelated intents separate by well over 0.1, and genuinely ambiguous prompts
#: land inside it — which is the case this exists to catch.
DEFAULT_MARGIN = 0.06

#: What an unroutable request becomes.
FALLBACK_INTENT = "conversation"


@dataclass
class RouteDecision:
    """Where a prompt is going, and the reason in words a user could read.

    CLAUDE.md requires routing to be legible: "routed to qwen2.5-coder — coding
    task". `reason` is that sentence, and `exemplar` is the evidence behind it —
    the phrasing the prompt actually landed nearest to. Both are here so the
    surface never has to invent an explanation for a decision it did not make.
    """

    intent: str
    confidence: float
    reason: str
    #: The exemplar the prompt matched. Empty when routing did not run.
    exemplar: str = ""
    #: Runner-up and its score, when there was one. The margin is the whole
    #: confidence story, so hiding it would make a close call unauditable.
    runner_up: Optional[str] = None
    runner_up_score: float = 0.0
    #: True when this came from embeddings rather than the keyword fallback.
    semantic: bool = True
    scores: Dict[str, float] = field(default_factory=dict)


class SemanticIntentRouter:
    """Routes prompts by similarity to task exemplars."""

    def __init__(
        self,
        index: SemanticIndex,
        *,
        floor: float = DEFAULT_FLOOR,
        margin: float = DEFAULT_MARGIN,
        exemplars: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        self._index = index
        self._floor = floor
        self._margin = margin
        self._index.register_all(intent_candidates(exemplars))

    @property
    def index(self) -> SemanticIndex:
        return self._index

    def is_semantic(self) -> bool:
        """Whether real embeddings are behind this. See the module docstring."""
        return bool(self._index.health().get("semantic", False))

    def route(self, prompt: str) -> Optional[RouteDecision]:
        """Decide an intent, or return None meaning "use the keyword router".

        None rather than a low-confidence guess: the caller has a working
        keyword classifier, and handing back to it is strictly better than
        forwarding a coin flip that looks like a decision.
        """
        if not prompt or not prompt.strip():
            return None

        if not self.is_semantic():
            logger.warning(
                "Routing fell back to keywords: the embedder is not running "
                "semantically, so similarity scores would be arbitrary."
            )
            return None

        matches = self._index.search(prompt, namespace=INTENT_NAMESPACE, k=3)
        if not matches:
            return None

        best = matches[0]
        second = matches[1] if len(matches) > 1 else None
        scores = {m.id: round(m.score, 4) for m in matches}

        if best.score < self._floor:
            return RouteDecision(
                intent=FALLBACK_INTENT,
                confidence=best.score,
                reason=(
                    f"nothing matched closely enough (best was {best.id} at "
                    f"{best.score:.2f}), so this is an ordinary question"
                ),
                exemplar=best.exemplar,
                runner_up=second.id if second else None,
                runner_up_score=second.score if second else 0.0,
                scores=scores,
            )

        if second is not None and (best.score - second.score) < self._margin:
            # Two intents are indistinguishable. Answering normally is
            # recoverable; generating a document from a question is not.
            return RouteDecision(
                intent=FALLBACK_INTENT,
                confidence=best.score - second.score,
                reason=(
                    f"{best.id} and {second.id} were too close to call "
                    f"({best.score:.2f} against {second.score:.2f}), so this is "
                    "being treated as an ordinary question"
                ),
                exemplar=best.exemplar,
                runner_up=second.id,
                runner_up_score=second.score,
                scores=scores,
            )

        return RouteDecision(
            intent=best.id,
            confidence=best.score,
            reason=f'routed to {best.id} — closest to "{best.exemplar}"',
            exemplar=best.exemplar,
            runner_up=second.id if second else None,
            runner_up_score=second.score if second else 0.0,
            scores=scores,
        )


def shortlist(
    index: SemanticIndex, query: str, *, namespace: str, k: int = 5
) -> List[Any]:
    """Top-k for a model to choose from. The other decision rule.

    No floor and no margin, deliberately. Tool selection is not a decision —
    excluding the right tool is the only failure that matters, and a marginal
    extra candidate costs a model almost nothing to ignore. This is what will
    turn an MCP server's two hundred tools into the five worth showing.

    Kept beside the router so the asymmetry is visible in one file: same index,
    same similarity, different question.
    """
    return index.search(query, namespace=namespace, k=k)
