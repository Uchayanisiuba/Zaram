"""Whether a turn needs the Spine at all.

**The bug this exists for.** Typing `Hi` retrieved three of the user's
documents — day rates, an invoice — and injected them into the system prompt,
then rendered "0 sources · nothing left this device · 3 recalled, not cited"
under a two-word greeting. Recall ran unconditionally in ``ExecutionEngine.run``
and the relevance floor was expected to clean up afterwards.

**Why the floor cannot do this job.** Measured against bge-m3 on 10 August 2026
(``backend/tests/test_conversational_turns_do_not_recall.py``, ``-m measure``):

    social turns, best corpus similarity      0.396 - 0.493
    referential turns, best corpus similarity 0.463 - 0.800

They *overlap*. "good morning" scores 0.493 against the user's files while
"what did I quote them" scores 0.463 — so any floor that rejects the greeting
also rejects the vague referential question, which is precisely the case rule 9
says must keep working. No threshold on that number can separate these
populations, and raising ``MIN_RECALL_SCORE`` would trade a cosmetic bug for a
recall failure.

**So the gate asks a different question.** Not "how similar is this turn to the
user's documents" but "is this turn more like small talk or more like a request
about the user's work" — nearest exemplar, which is the approach ``CLAUDE.md``
already specifies for routing, applied one decision earlier. On that comparison
the populations separate cleanly:

    social turns          social exemplar wins by +0.220 to +0.449
    everything else       social exemplar wins by at most +0.025

An order of magnitude of empty space, so the threshold inside it is not
delicate.

**Three properties that are deliberate, not incidental.**

*It fails open.* Every path that cannot produce a trustworthy margin — no
embedder, a degraded embedder, an exception, an empty query — returns "recall".
Suppressing recall on a real question is a silent wrong answer; running recall
on a greeting costs some milliseconds and a line of UI. The failure modes are
not symmetric and the code is not either.

*It never sees the Spine.* The gate reads the turn and two fixed exemplar lists.
It cannot be influenced by what happens to be stored, which keeps it from
drifting as the user's corpus grows, and it means a retrieval score never
decides whether retrieval is permitted — the separation ``CLAUDE.md`` insists on
between ranking, selection and permission.

*It only gates recall.* It does not choose a model, suppress a reply, or decide
whether anything may leave the device. A turn the gate calls social is answered
exactly as before, just without the user's files in its prompt.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Callable, Sequence

_log = logging.getLogger(__name__)

#: Small talk. Short and generic on purpose — an exemplar mentioning invoices
#: would pull every money question toward the social side and suppress recall on
#: exactly the turns that need it most.
SOCIAL_EXEMPLARS: tuple[str, ...] = (
    "hello there",
    "hi, good to see you",
    "thanks very much",
    "how are you doing today",
    "good morning",
    "ok, sounds good",
    "goodbye for now",
)

#: Turns that need the Spine. About *the user's own things* without naming any
#: of them: an exemplar carrying this user's clients would stop working for the
#: next user, and these have to generalise past whoever is being tested against.
TASK_EXEMPLARS: tuple[str, ...] = (
    "what did I agree with the client",
    "how much do I charge for this",
    "when is that due",
    "what were the terms we settled on",
    "find the file about that project",
    "what did I say in the last email",
    "write that up as a document",
)

#: How far a turn must sit toward the social exemplars before recall is skipped.
#:
#: Measured, and sitting in a gap rather than on an edge: true social turns win
#: by at least 0.220, everything else by at most 0.025. 0.12 is the middle of
#: that band. A bare argmax was rejected because it has no headroom — "who won
#: the 2026 world cup" lands social by +0.025, harmless there but with nothing
#: to spare, and the direction of any future error should be *toward* recalling.
#:
#: Overridable for a different embedding model, exactly as MIN_RECALL_SCORE is:
#: this number is a property of bge-m3's similarity distribution and does not
#: transfer.
SOCIAL_MARGIN = float(os.getenv("ZARAM_SOCIAL_MARGIN", "0.12"))

#: Turns longer than this are never gated, whatever the exemplars say.
#:
#: A long turn carries enough content to be about something, and the cost of
#: being wrong grows with it — a paragraph wrongly called small talk loses real
#: recall. The exemplars are all short, so a long input is also the case they
#: describe least well. Measured turns in the referential set run to 34
#: characters; 120 leaves room without approaching a paragraph.
MAX_SOCIAL_CHARS = int(os.getenv("ZARAM_MAX_SOCIAL_CHARS", "120"))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class RecallGate:
    """Decides whether a turn should reach the Spine.

    Exemplars are embedded once on first use and kept, so the steady-state cost
    is one embedding of the user's turn — 10-30ms against a bge-m3 that is
    already resident for the Spine itself, and no extra VRAM.
    """

    def __init__(
        self,
        embed: Callable[[str], Sequence[float]] | None,
        *,
        social_exemplars: Sequence[str] = SOCIAL_EXEMPLARS,
        task_exemplars: Sequence[str] = TASK_EXEMPLARS,
        margin: float = SOCIAL_MARGIN,
        max_social_chars: int = MAX_SOCIAL_CHARS,
        is_degraded: Callable[[], bool] | None = None,
    ) -> None:
        self._embed = embed
        self._social_exemplars = tuple(social_exemplars)
        self._task_exemplars = tuple(task_exemplars)
        self._margin = margin
        self._max_social_chars = max_social_chars
        self._is_degraded = is_degraded
        self._social_vectors: list[Sequence[float]] | None = None
        self._task_vectors: list[Sequence[float]] | None = None

    # -- internals ---------------------------------------------------------

    def _vectors(self) -> tuple[list[Sequence[float]], list[Sequence[float]]] | None:
        if self._social_vectors is not None and self._task_vectors is not None:
            return self._social_vectors, self._task_vectors
        if self._embed is None:
            return None
        self._social_vectors = [self._embed(t) for t in self._social_exemplars]
        self._task_vectors = [self._embed(t) for t in self._task_exemplars]
        return self._social_vectors, self._task_vectors

    # -- the decision ------------------------------------------------------

    def social_margin(self, text: str) -> float | None:
        """How far toward small talk this turn sits, or ``None`` if unknowable.

        ``None`` is not zero and the distinction is the whole safety property:
        zero would mean "measured, and balanced", while None means "no
        trustworthy measurement exists" — and only one of those may suppress
        recall.
        """
        if self._embed is None:
            return None
        try:
            vectors = self._vectors()
            if vectors is None:
                return None
            social_vectors, task_vectors = vectors

            # Checked *after* embedding, because the degraded flag is only set
            # once a call has failed. Hash-fallback embeddings would produce a
            # confident margin from the wrong model.
            if self._is_degraded is not None and self._is_degraded():
                return None

            vector = self._embed(text)
            if not any(vector):
                return None

            social = max(_cosine(vector, v) for v in social_vectors)
            task = max(_cosine(vector, v) for v in task_vectors)
            return social - task
        except Exception as exc:
            _log.debug("recall gate could not measure %r: %s", text[:40], exc)
            return None

    def should_recall(self, text: str) -> bool:
        """``True`` when this turn should reach the Spine.

        Every uncertain path returns ``True``. The gate is an optimisation with
        a UI benefit, never a correctness mechanism, and it must not be able to
        cost the user an answer.
        """
        stripped = (text or "").strip()
        if not stripped:
            # Nothing to recall against, and nothing to lose by saying so.
            return False
        if len(stripped) > self._max_social_chars:
            return True

        margin = self.social_margin(stripped)
        if margin is None:
            return True
        return margin < self._margin


def gate_from_memory_runtime(runtime: Any) -> RecallGate:
    """Build a gate from whatever embedder the memory runtime already has.

    Reaches for the running service rather than constructing a second one, so
    the gate cannot silently disagree with recall about what an embedding is —
    and so it inherits the degraded flag rather than re-deriving it.

    Returns a gate with no embedder, which recalls everything, if the runtime
    does not expose one. A gate that cannot measure is not an error; it is the
    behaviour that shipped before this file existed.
    """
    # `_embedder` is what `MemoryRuntime` actually calls it, and it is first
    # because it is the real one — the others are tolerated spellings, not
    # guesses ranked by hope. The first version of this list omitted `_embedder`
    # entirely: the gate silently built itself with no embedder, failed open on
    # every turn, and `Hi` went on recalling three documents while fourteen unit
    # tests passed against a fake exposing `_embedding_service`. A fixture that
    # invents the attribute it is testing for will agree with any bug.
    # `test_it_finds_the_real_memory_runtime_s_embedder` now pins the real name.
    for attribute in ("_embedder", "_embedding_service", "embedding_service"):
        service = getattr(runtime, attribute, None)
        if service is not None and hasattr(service, "embed"):
            break
    else:
        service = None

    if service is None:
        # Loud, because an inert gate is indistinguishable from a working one
        # from the outside: it fails open, so everything keeps working and
        # nothing says the check stopped happening.
        _log.warning(
            "Recall gate has no embedder (%s exposes none of %s); every turn "
            "will recall, including greetings.",
            type(runtime).__name__,
            "_embedder/_embedding_service/embedding_service",
        )
        return RecallGate(embed=None)

    return RecallGate(
        embed=service.embed,
        is_degraded=lambda: bool(getattr(service, "_degraded", False)),
    )
