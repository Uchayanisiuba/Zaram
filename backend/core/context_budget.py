"""How much room a request actually has, measured rather than assumed.

**The declared maximum is the wrong number, and using it overflows the context
on almost every real document.** Ollama serves a default `num_ctx` regardless of
what a model advertises: measured on this machine, `gemma4:12b` reports a
262,144-token maximum through `/api/show` and loads with **4,096** in
`/api/ps`; `bge-m3` advertises more and loads with 8,192. Sizing a prompt
against the declared figure is sizing it against a number no request will ever
have.

`attachments/compose.py` has carried a constant with that reasoning in its own
comment since it was written — *"Reading the loaded model's real `num_ctx` from
`/api/ps` would make this a measurement; until then it errs small"*. This module
is that measurement.

Three rules, and they are the same three this codebase keeps relearning:

**Unknown is a third answer.** `loaded_context_length` returns ``None`` when it
cannot read one, never a guess and never a zero. It is the discipline
`vram_bytes` keeps by refusing to report ``0`` for an unreadable card, and that
`locality_of` keeps by refusing to say "local" for a model it cannot place. A
caller handed ``None`` falls back to a conservative constant it chose
deliberately; a caller handed a wrong number sizes a contract against it.

**Estimation errs toward fewer characters fitting.** English averages nearer
four characters per token; three is used so the estimate overstates the cost.
The opposite error silently drops the end of a document, and the end of a
contract is where the termination clause lives.

**A budget is not a measurement of what was sent.** This plans; the egress log
records. Nothing here may be read as evidence about what left the machine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

#: Characters per token, conservative on purpose. See the module docstring.
CHARS_PER_TOKEN = 3

#: What to assume when the real context cannot be read.
#:
#: Ollama's own default, which is what an unconfigured model loads with. Erring
#: here costs an excerpt where the whole document would have fitted; erring the
#: other way costs a truncation nobody sees.
FALLBACK_CONTEXT_TOKENS = 4096

#: Share of the context held back for the reply itself.
#:
#: A budget that spends the whole window on input leaves the model room to say
#: nothing. A judgement, not a measurement, and labelled as one — the same
#: honesty `_KV_CACHE_RESERVE_FRACTION` keeps in the provider layer.
REPLY_RESERVE_FRACTION = 0.25

#: Share of the *input* budget that attached documents may spend.
#:
#: The rest covers the identity preamble, recalled facts and the question. A
#: judgement rather than a measurement, and calibrated against the constant it
#: replaces: at Ollama's 4,096 default this yields 1,843 tokens against the
#: 1,800 `compose.py` used, so nothing about the current behaviour changes and
#: a larger loaded context now buys a larger share.
DOCUMENT_SHARE = 0.6


#: Hosts this module may ask. Loopback only, and enforced rather than assumed.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


def _is_loopback(base_url: str) -> bool:
    """Whether ``base_url`` names this machine.

    Parsed rather than matched on a prefix: ``http://127.0.0.1.evil.test`` and
    ``http://user@127.0.0.1@evil.test`` both begin with something that looks
    like loopback and neither is. The host is what `urlparse` says the host is.
    """
    from urllib.parse import urlparse

    try:
        host = (urlparse(base_url).hostname or "").strip().lower()
    except Exception:
        return False
    return host in _LOOPBACK_HOSTS


def estimate_tokens(text: str) -> int:
    """Roughly how many tokens ``text`` will cost, rounded up.

    Deliberately not a tokenizer. A real one is per-model, is a dependency for
    each provider family, and would be exact about a number that is then
    compared against a context length which is itself approximate. Rounding up
    a character count costs a few hundred tokens of headroom and no
    dependencies.
    """
    if not text:
        return 0
    return -(-len(text) // CHARS_PER_TOKEN)


def loaded_context_length(
    model: Optional[str], *, base_url: str = "http://127.0.0.1:11434", timeout: float = 1.0
) -> Optional[int]:
    """The context a model is **actually loaded with**, or ``None``.

    Read from `/api/ps`, which reports the window the running instance was
    given — not `/api/show`, which reports what the weights could support. The
    gap between those is the whole reason this function exists.

    ``None`` means the question could not be answered: Ollama unreachable, the
    model not resident, or a reply this does not understand. It is never
    promoted to a number. A model that is not loaded has no loaded context, and
    inventing one for it would be the false-zero bug wearing different clothes.

    Never raises. A budget that cannot be measured must cost a conservative
    estimate, never the request.
    """
    if not model:
        return None
    if not _is_loopback(base_url):
        # **Refused rather than logged.** `test_egress_chokepoint.py` exempts
        # this module on the grounds that its destination "cannot leave the
        # machine", and that exemption has to be true rather than intended --
        # `base_url` is a parameter, so without this it is a promise a caller
        # can break. A context length is not worth a hole in rule 3.
        logger.warning("context length refused for a non-loopback host: %r", base_url)
        return None
    try:
        response = requests.get(f"{base_url}/api/ps", timeout=timeout)
        response.raise_for_status()
        loaded = response.json().get("models")
    except Exception as exc:
        logger.debug("context length unreadable for %r: %s", model, exc)
        return None
    if not isinstance(loaded, list):
        return None

    # Ollama answers with the name it resolved, which may carry a `:latest` the
    # request did not. Same normalisation the residency check makes, and for
    # the same reason -- and the tag is part of the name, so `gemma4:12b` must
    # not match `gemma4:26b`.
    def norm(name: str) -> str:
        name = (name or "").strip().lower()
        if name.startswith("ollama:"):
            name = name[len("ollama:") :]
        return name[: -len(":latest")] if name.endswith(":latest") else name

    wanted = norm(model)
    for entry in loaded:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or entry.get("model") or "")
        if not name or norm(name) != wanted:
            continue
        length = entry.get("context_length")
        # A context of zero is not a context. Treated as unreadable rather than
        # as a budget of nothing, which would make every document "too large".
        if isinstance(length, int) and length > 0:
            return length
        return None
    return None


@dataclass(frozen=True)
class ContextBudget:
    """Room for one request, and whether the figure was measured or assumed.

    ``measured`` is carried rather than inferred from the numbers, because the
    two cases can produce the same total and a caller that wants to say *"read
    in full"* versus *"read what fitted"* is entitled to know which it is
    looking at. It is also what stops a fallback constant being quoted back to
    a user as though it were a fact about their machine.
    """

    #: The model's real loaded window, or the fallback when unknown.
    total_tokens: int
    #: Whether `total_tokens` came from `/api/ps` or from the fallback.
    measured: bool
    #: Held back for the reply.
    reply_reserve_tokens: int

    @property
    def input_tokens(self) -> int:
        """What the prompt may spend, all of it: system, recall, question, files."""
        return max(0, self.total_tokens - self.reply_reserve_tokens)

    @property
    def input_chars(self) -> int:
        """The same budget in characters, which is what the composer counts in."""
        return self.input_tokens * CHARS_PER_TOKEN

    @property
    def document_tokens(self) -> int:
        """The share attached documents may spend.

        **Not the whole input budget**, which is the mistake this property
        exists to prevent. The input budget also has to cover the identity
        preamble, the facts recall injects, and the question itself — none of
        which are free, and all of which matter more than a fourth excerpt.
        Handing the whole figure to the composer lets one long document crowd
        out the memory that makes the answer worth having.

        `DOCUMENT_SHARE` generalises a judgement that was already here rather
        than replacing it. `compose.py` used a flat 1,800 tokens, chosen as
        *"roughly half"* of Ollama's 4,096 default with the rest left for
        everything else. At that context this returns 1,843 — the same call,
        now expressed as a proportion, so a model loaded with 16,384 gets a
        proportionally larger share instead of the same small constant.
        """
        return int(self.input_tokens * DOCUMENT_SHARE)

    @property
    def document_chars(self) -> int:
        """The same share in characters, which is what the composer counts in."""
        return self.document_tokens * CHARS_PER_TOKEN

    def remaining_after(self, *texts: str) -> int:
        """Tokens left once ``texts`` are spent. Never negative.

        Clamped at zero because a negative budget is not a smaller budget — it
        is a request that will not fit, and a caller doing arithmetic on the
        difference should be deciding what to drop rather than subtracting
        further.
        """
        spent = sum(estimate_tokens(t) for t in texts)
        return max(0, self.input_tokens - spent)

    def fits(self, *texts: str) -> bool:
        return sum(estimate_tokens(t) for t in texts) <= self.input_tokens


def budget_for(
    model: Optional[str], *, base_url: str = "http://127.0.0.1:11434"
) -> ContextBudget:
    """The budget for a request answered by ``model``.

    Measured where it can be, assumed where it cannot, and the result says
    which. This is the one function callers should reach for; the parts above
    are exposed for tests and for callers that genuinely want the raw figure.
    """
    measured = loaded_context_length(model, base_url=base_url)
    total = measured if measured is not None else FALLBACK_CONTEXT_TOKENS
    return ContextBudget(
        total_tokens=total,
        measured=measured is not None,
        reply_reserve_tokens=int(total * REPLY_RESERVE_FRACTION),
    )
