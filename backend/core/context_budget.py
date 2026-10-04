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
from functools import lru_cache
from typing import Any, Optional

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

#: How full a working context may get before the task hands itself over.
#:
#: **Half the window, and the handoff is silent.** A long task fills its context
#: with what it has read; left alone it either overflows or stops and asks the
#: user for permission to carry on. Both are worse than compacting: at half full
#: there is still room for the model to think, the prompt being re-sent stays
#: small — and a smaller prompt is a cheaper one on a metered provider, which is
#: how this protects the bill without ever putting a dialog in front of anybody.
#:
#: Measured against the **whole window**, not against the input budget, because
#: what is being bounded here is the size of the request actually being sent:
#: system prompt, recalled facts, question and every result carried forward.
#:
#: A judgement, labelled as one, and the number a session should form a view on
#: by watching a real task rather than by reasoning about it.
HANDOFF_SHARE = 0.5

#: How much of the window a handoff may carry into the next one.
#:
#: Deliberately well under `HANDOFF_SHARE`, and the gap is the point: carrying
#: right up to the handoff threshold would trip it again on the next call, and
#: the task would spend its life handing over instead of working. A quarter
#: leaves the same room to work that the first window had.
CARRY_SHARE = 0.25


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


#: Local inference servers Zaram will ask, beyond Ollama.
#:
#: Loopback only, and guarded as such below -- a context length is not worth a
#: hole in rule 3.
LOCAL_SERVER_URLS = (
    "http://127.0.0.1:1234",  # TabbyAPI / ExLlamaV3, the maintainer's
    "http://127.0.0.1:8080",  # llama.cpp's `llama-server` default
)


def _tabby_window(payload: object) -> tuple[Optional[str], Optional[int]]:
    """TabbyAPI's `/v1/model`: the served name and its loaded window.

    **Not an OpenAI route**, despite the prefix. The OpenAI API has `/v1/models`
    and it carries no context length at all, so nothing about this generalises
    by standard -- it is one server's shape, and naming it after the standard
    would mean a different server silently reporting nothing.
    """
    if not isinstance(payload, dict):
        return None, None
    parameters = payload.get("parameters")
    if not isinstance(parameters, dict):
        return None, None
    window = parameters.get("max_seq_len")
    return str(payload.get("id") or "").strip(), window if isinstance(window, int) else None


def _llama_cpp_window(payload: object) -> tuple[Optional[str], Optional[int]]:
    """llama.cpp's `/props`: the loaded model's path and its window.

    A second shape rather than a second product decision. Zaram ships no
    inference server and never will -- rule 1 -- so which one a user runs is
    theirs to choose, and the cost of that choice must not be that Zaram stops
    being able to size a request. `llama-server` is the likeliest alternative to
    both of the maintainer's, being what Ollama wraps.

    The name comes from `model_path`, since `/props` carries no id. Compared on
    the basename, because a path is where a file is and a model name is what it
    is called.
    """
    if not isinstance(payload, dict):
        return None, None
    settings = payload.get("default_generation_settings")
    window = settings.get("n_ctx") if isinstance(settings, dict) else None
    path = str(payload.get("model_path") or "").strip()
    name = path.replace(chr(92), "/").rsplit("/", 1)[-1] if path else ""
    if name:
        name = name.rsplit(".", 1)[0]
    return name, window if isinstance(window, int) else None


#: Route to reader. Asked in order; the first that answers about *this* model wins.
_SERVER_SHAPES = (
    ("/v1/model", _tabby_window),
    ("/props", _llama_cpp_window),
)


def configured_context_length(
    model: Optional[str], *, base_url: str = "http://127.0.0.1:11434", timeout: float = 1.0
) -> Optional[int]:
    """The window a model is **configured** to load with, or ``None``.

    **This is the half `loaded_context_length` cannot answer, and the gap was
    costing the product its memory.** `/api/ps` lists what is resident *now*,
    so it goes quiet the moment Ollama evicts a model -- which it does after a
    few minutes idle. Between two turns of a conversation the user spends
    reading an answer, the model is gone, the budget falls back to 4,096, and
    the share of it the conversation may spend collapses to 768 tokens. A reply
    containing a code block is bigger than that, so `fit` keeps nothing and the
    follow-up is answered by a model that was shown none of what it follows.
    Measured 10 September 2026: every installed chat model read 4,096 while
    idle, and 16,384 or 32,768 the moment it was resident.

    **`parameters`, never `model_info`.** The module docstring's whole argument
    is that a model's declared maximum is the wrong number -- `qwen3-14b-16k`
    reports `qwen3.context_length: 40960` there while loading with 16,384. What
    is read here is the `num_ctx` in the model's own parameters, which is the
    figure Ollama will actually serve it with. That is a measurement of a
    setting rather than of a running process, and it is still not a guess.

    ``None`` when there is no explicit `num_ctx`, and that is the right answer
    rather than a gap: a model created without one gets Ollama's default, which
    is the fallback constant this returns to. Measured on the same machine --
    `qwen3-coder:30b` and `bge-m3` carry no `num_ctx`, the three models built
    with one report it.

    Never raises, for the same reason as its neighbour.
    """
    if not model:
        return None
    if not _is_loopback(base_url):
        logger.warning("configured context refused for a non-loopback host: %r", base_url)
        return None
    try:
        response = requests.post(
            f"{base_url}/api/show", json={"model": model}, timeout=timeout
        )
        response.raise_for_status()
        parameters = response.json().get("parameters")
    except Exception as exc:
        logger.debug("configured context unreadable for %r: %s", model, exc)
        return None
    if not isinstance(parameters, str):
        return None

    # Ollama renders the parameters as the Modelfile's own lines, so this is a
    # text field rather than a mapping. Anchored per line so a parameter whose
    # *name* ends in `num_ctx` cannot answer for it.
    import re

    match = re.search(r"^num_ctx\s+(\d+)", parameters, re.MULTILINE)
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


@lru_cache(maxsize=1)
def _provider_ids() -> frozenset[str]:
    """Every catalogued provider id, lowercased.

    Imported here rather than at module scope, like every other cross-package
    reach in this file: a budget calculation must not fail to import because
    the provider catalogue cannot. An empty set is the safe answer if it
    cannot be read — no prefix resolves, which is the behaviour this had
    before, rather than a guess about which prefixes are real.
    """
    try:
        from providers.catalogue import PROVIDERS

        ids = {str(entry.id).strip().lower() for entry in PROVIDERS if entry.id}
    except Exception:  # noqa: BLE001 - see the docstring
        logger.debug("provider catalogue unreadable; no prefix will resolve", exc_info=True)
        return frozenset()
    # Local servers the catalogue does not list as connectable providers but
    # which the provider layer still qualifies names with.
    return frozenset(ids | {"ollama", "tabby", "tabbyapi", "llama_cpp", "llamacpp"})


def _same_model(served: str, wanted: str) -> bool:
    """Whether the name a server reports is the model that was asked for.

    The provider layer records models as ``<provider_id>:<name>`` and these
    servers report the bare one, so an exact comparison failed every qualified
    name and fell back to 4,096 — measured 29 September 2026 as a sixteen-fold
    under-budget on a model whose server reports 65,536.

    **A named provider, never a split at the first colon.** Ollama's names
    *are* ``name:tag``, so cutting there would compare ``qwen2.5:14b`` as
    ``14b``. A bare suffix test is not enough either, and a test here caught
    it: ``"qwen2.5:14b".endswith(":14b")`` is true, so a server reporting a
    model called ``14b`` would have answered for it — the confident wrong
    budget this module warns is worse than the conservative one.

    So the prefix must be a **catalogued provider id**. ``lm_studio:Qwen…``
    resolves because `lm_studio` is one; ``qwen2.5:14b`` does not, because
    `qwen2.5` is a model. The list is the provider catalogue's own, so adding
    a provider needs nothing here.
    """
    served = served.strip().lower()
    if not served:
        return False
    if wanted == served:
        return True
    prefix, sep, rest = wanted.partition(":")
    return bool(sep) and rest == served and prefix in _provider_ids()


def local_server_context_length(
    model: Optional[str],
    *,
    urls: tuple[str, ...] = LOCAL_SERVER_URLS,
    timeout: float = 1.0,
) -> Optional[int]:
    """The window a non-Ollama local server loaded with, or ``None``.

    **This is the half that was missing, and it was a 32x error.** Measured
    7 September 2026: `loaded_context_length` can only ask Ollama's `/api/ps`,
    so a TabbyAPI model answered ``None`` and `budget_for` fell back to 4,096 --
    on a model whose own route reports **65,536**. A task there handed itself
    over at 2,048 tokens, a thirty-second of the window it actually had.

    **The dangerous part is not reading a second server, it is reading it for
    the wrong model.** These routes describe whatever that server happens to
    hold, regardless of what was asked for, so a lookup that skipped the name
    check would hand every Ollama model TabbyAPI's window -- a confident wrong
    budget, which is worse than the conservative one it replaces, because a
    request sized against it does not fit. Every shape returns a name and it
    must match.

    Asked after Ollama, never before: Ollama is the common case, and this is two
    HTTP calls to ports that are usually closed.
    """
    if not model:
        return None
    wanted = model.strip().lower()

    for base_url in urls:
        if not _is_loopback(base_url):
            logger.warning("context length refused for a non-loopback host: %r", base_url)
            continue
        for route, read in _SERVER_SHAPES:
            try:
                response = requests.get(f"{base_url}{route}", timeout=timeout)
                response.raise_for_status()
                served, window = read(response.json())
            except Exception as exc:
                logger.debug("context unreadable at %s%s: %s", base_url, route, exc)
                continue
            # Zero is not a window: unreadable rather than a budget of nothing,
            # which would make every document too large.
            if not served or not window or window <= 0:
                continue
            if _same_model(served, wanted):
                return window
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

    #: The model's real window, or the fallback when unknown.
    total_tokens: int
    #: Whether `total_tokens` was read from the model rather than assumed.
    measured: bool
    #: Held back for the reply.
    reply_reserve_tokens: int
    #: Which reading answered, for the log.
    #:
    #: Carried because "measured" turned out to hide the thing that mattered.
    #: A budget read from `/api/ps` and one read from the fallback are easy to
    #: tell apart; a budget that *used* to be measured and is now assumed
    #: because Ollama evicted the model is the same boolean on Tuesday and
    #: Thursday, and that is the failure this field exists to make legible in a
    #: log line rather than in an investigation.
    source: str = "assumed"

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

    @property
    def handoff_tokens(self) -> int:
        """How large a request may get before the task compacts and carries on.

        Compared against the *whole* request — system prompt, recalled facts,
        question and every result carried forward — because that is the thing
        being sent, and the thing a metered provider charges for. See
        `HANDOFF_SHARE`.
        """
        return int(self.total_tokens * HANDOFF_SHARE)

    @property
    def carry_tokens(self) -> int:
        """How much of what was found may travel into the next window.

        Under `handoff_tokens` on purpose: carrying right up to the threshold
        would trip it again on the next call, and the task would spend its life
        handing over instead of working.
        """
        return int(self.total_tokens * CARRY_SHARE)

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


def cloud_context_length(model: Optional[str], catalog: Any) -> Optional[int]:
    """The window of a *cloud* model, or ``None`` for a local one or an
    unknown one.

    Asked of the provider catalogue, which is the only thing that knows where
    a model runs. Two readings: what the provider's listing declared
    (`ModelInfo.context_length`, recorded by the discoverer), then the dated
    floor in `providers.windows`. A local model answers ``None`` here so the
    loopback readings in `budget_for` keep sizing it — Ollama's declared
    maximum is the wrong number, and this must not become a route to it.
    """
    if not model or catalog is None:
        return None
    info = _catalogued(model, catalog)
    if info is None or not _is_cloud(info):
        return None
    declared = getattr(info, "context_length", None)
    if isinstance(declared, int) and declared > 0:
        return declared
    from providers.windows import known_window

    return known_window(getattr(info, "id", None) or model)


def is_cloud_model(model: Optional[str], catalog: Any) -> bool:
    """Whether the catalogue places ``model`` off this machine. ``False`` when
    it cannot say — the loopback readings then run, and find nothing."""
    if not model or catalog is None:
        return False
    info = _catalogued(model, catalog)
    return info is not None and _is_cloud(info)


def _catalogued(model: str, catalog: Any):
    get = getattr(catalog, "get_model", None)
    info = get(model) if callable(get) else None
    if info is None:
        resolve = getattr(catalog, "_resolve_model", None)
        info = resolve(model) if callable(resolve) else None
    return info


def _is_cloud(info: Any) -> bool:
    locality = getattr(info, "locality", None)
    value = getattr(locality, "value", locality)
    return str(value).lower() in {"cloud", "hybrid"}


def budget_for(
    model: Optional[str],
    *,
    base_url: str = "http://127.0.0.1:11434",
    catalog: Any = None,
) -> ContextBudget:
    """The budget for a request answered by ``model``.

    Measured where it can be, assumed where it cannot, and the result says
    which. This is the one function callers should reach for; the parts above
    are exposed for tests and for callers that genuinely want the raw figure.

    ``catalog`` is the provider manager, when the caller has one. It is what
    tells a cloud model apart from a local one, and for a cloud model it is
    the *only* reading — see `cloud_context_length`. Without it every model
    is sized as though it ran here, which for a cloud model means the
    fallback: the failure this argument was added to end.
    """
    # **A cloud model is sized by what its provider says, never by Ollama's
    # default.** Measured 14 September 2026 on `nvidia_nim:z-ai/glm-5.3-flash`:
    # the three loopback readings below cannot see a model that runs
    # elsewhere, so it fell through to 4,096 and a 128K model was shown one
    # exchange of the conversation. The loopback probes are skipped for it
    # too — they would only find nothing, on a request that is about to wait
    # on the network anyway.
    if is_cloud_model(model, catalog):
        from providers.windows import CLOUD_FALLBACK_CONTEXT_TOKENS

        known = cloud_context_length(model, catalog)
        if known is not None:
            return ContextBudget(
                total_tokens=known,
                measured=True,
                reply_reserve_tokens=int(known * REPLY_RESERVE_FRACTION),
                source="declared",
            )
        return ContextBudget(
            total_tokens=CLOUD_FALLBACK_CONTEXT_TOKENS,
            measured=False,
            reply_reserve_tokens=int(CLOUD_FALLBACK_CONTEXT_TOKENS * REPLY_RESERVE_FRACTION),
            source="assumed-cloud",
        )
    # **Four readings, most specific first, and the second one is why this
    # function stopped lying between turns.**
    #
    # `/api/ps` is the best answer when it can be had: it is what the running
    # instance was actually given. But it only speaks for a *resident* model,
    # and Ollama evicts after a few minutes idle -- so across the pause a user
    # spends reading a reply, the same model answers 16,384 and then 4,096. The
    # conversation share of the second is 768 tokens, which is smaller than one
    # code answer, so the follow-up was shown nothing at all. That is what
    # "Zaram does not keep the thread of a conversation" turned out to be the
    # second time it was reported.
    #
    # `/api/show` answers for an idle model because it reads the configuration
    # rather than a process. It is a weaker claim and still not a guess, and
    # `source` says which was used.
    total = loaded_context_length(model, base_url=base_url)
    source = "loaded"
    if total is None:
        total = configured_context_length(model, base_url=base_url)
        source = "configured"
    if total is None:
        total = local_server_context_length(model)
        source = "server"
    measured = total
    if total is None:
        total, source = FALLBACK_CONTEXT_TOKENS, "assumed"
    # **Not cached, deliberately.** Two callers now ask per reply — the chat
    # route to size attached documents, the engine to size how much of the
    # conversation the model is shown — and a memo keyed on the model name was
    # written and removed the same hour. It bought a couple of milliseconds of
    # loopback against a request that spends seconds generating, and it cost
    # module-level mutable state that made one test's answer depend on whether
    # another had run first. That is the wrong trade on a number whose whole
    # value is being current: it changes on a model load, and a load is the
    # exact moment a stale answer would be quoted.
    return ContextBudget(
        total_tokens=total,
        measured=measured is not None,
        reply_reserve_tokens=int(total * REPLY_RESERVE_FRACTION),
        source=source,
    )




def declared_context_length(
    model: Optional[str],
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 2.0,
) -> Optional[int]:
    """The ceiling the model's own file declares, or ``None``.

    **The number this module's docstring warns against using, exposed on
    purpose and under a name that says which one it is.** Sizing a prompt
    against it overflows the context, which is why `loaded_context_length`
    and `configured_context_length` both refuse to read it. But *"how much
    could this model hold if asked"* is a different question from *"how
    much will this request have"*, and it is the right number for exactly
    one job: the ceiling on a control that lets somebody raise `num_ctx`.

    LM Studio does the same thing, and the maintainer asked for it by
    name — the slider stops at what the file says, because the model's
    creator wrote that number into it.

    Read from `model_info`, matched on any key ending `.context_length`
    rather than on `<architecture>.context_length`: the prefix is the
    architecture, so hardcoding it would need a list of every
    architecture Ollama supports and would silently answer ``None`` for
    the next one. Measured 4 October 2026: `gemma4:12b` reports
    `gemma4.context_length: 262144` while loading with 4,096.

    Never raises, and ``None`` is a real answer — the same three-valued
    discipline the rest of this module keeps.
    """
    if not model:
        return None
    if not _is_loopback(base_url):
        logger.warning("declared context refused for a non-loopback host: %r", base_url)
        return None
    try:
        response = requests.post(
            f"{base_url}/api/show", json={"model": model}, timeout=timeout
        )
        response.raise_for_status()
        info = response.json().get("model_info")
    except Exception as exc:
        logger.debug("declared context unreadable for %r: %s", model, exc)
        return None
    if not isinstance(info, dict):
        return None
    for key, value in info.items():
        if isinstance(key, str) and key.endswith(".context_length"):
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if number > 0:
                return number
    return None


# How many bytes one cached token costs, per element of the cache. Ollama
# serves an f16 KV cache unless told otherwise, which is two bytes for the
# key and two for the value.
_KV_ELEMENT_BYTES = 2


def _geometry(info: dict) -> Optional[tuple[int, int]]:
    """``(total_kv_heads_across_layers, key_plus_value_length)`` or ``None``.

    Read from the same `model_info` block `declared_context_length` reads,
    and matched on key *suffix* for the same reason: the prefix is the
    architecture.

    **Returns ``None`` rather than a figure whenever the geometry is
    ambiguous, and the ambiguous case is real.** `gemma4:12b` reports
    `key_length_swa` and `value_length_swa` beside the full-length pair
    and a per-layer `head_count_kv` of `[8,8,8,8,8,1,...]`: most of its
    layers attend over a sliding window and cache a fraction of the
    context, and nothing in `model_info` says which layers those are.
    Measured 4 October 2026, the naive sum overstates gemma4's cost by
    roughly ten times - so a confident number here would cap a 262,144
    ceiling at a few thousand tokens and call it a measurement.

    That is rule 9 applied to arithmetic. A caller handed ``None`` falls
    back deliberately; a caller handed a wrong number cannot.
    """

    def ends(suffix: str):
        for key, value in info.items():
            if isinstance(key, str) and key.endswith(suffix):
                return value
        return None

    # Sliding-window attention: the full-length pair is not what most
    # layers cache, and the apportionment is not stated. Refuse.
    if ends(".attention.key_length_swa") is not None:
        return None

    heads = ends(".attention.head_count_kv")
    key_len = ends(".attention.key_length")
    value_len = ends(".attention.value_length")
    blocks = ends(".block_count")

    try:
        if isinstance(heads, (list, tuple)):
            # Per-layer, which is the honest sum: one entry per block, and
            # multiplying a single figure by `block_count` would be wrong
            # for any model that varies it.
            total_heads = sum(int(h) for h in heads)
        else:
            total_heads = int(heads) * int(blocks)
        width = int(key_len) + int(value_len)
    except (TypeError, ValueError):
        return None

    if total_heads <= 0 or width <= 0:
        return None
    return total_heads, width


def kv_bytes_per_token(
    model: Optional[str],
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 2.0,
) -> Optional[int]:
    """What one token of context costs this model in graphics memory.

    The number that makes a context window a *decision* rather than a
    figure somebody types. Measured on the maintainer's machine, 4 October
    2026: `qwen3-14b-16k` costs **160 KiB per token**, so its own declared
    ceiling of 40,960 is 6.7 GB of cache on top of ~9 GB of weights, and
    131,072 would be **21.5 GB** - on a 12 GB card.

    That is why *"default high and clamp to the model's limit"* does not
    work: the model's limit is almost never the binding constraint, the
    card is, and clamping to the declared ceiling still produces a window
    that will not load. It does not fail cleanly either - it spills into
    system RAM and every reply becomes slow, which reads as the model
    being bad rather than as a setting being wrong.

    ``None`` when the geometry cannot be read or is ambiguous. Never
    raises, for the reason every reader in this module keeps.
    """
    if not model:
        return None
    if not _is_loopback(base_url):
        logger.warning("kv cost refused for a non-loopback host: %r", base_url)
        return None
    try:
        response = requests.post(
            f"{base_url}/api/show", json={"model": model}, timeout=timeout
        )
        response.raise_for_status()
        info = response.json().get("model_info")
    except Exception as exc:
        logger.debug("kv geometry unreadable for %r: %s", model, exc)
        return None
    if not isinstance(info, dict):
        return None
    shape = _geometry(info)
    if shape is None:
        return None
    total_heads, width = shape
    return total_heads * width * _KV_ELEMENT_BYTES


# Windows the *control* offers, largest first. These are choices a person
# makes, so they are the round numbers a model card quotes.
#
# **Resolution does not round onto this ladder**, which is what it did
# first and the reason that was wrong: a card with room for 31,000 tokens
# resolved to 16,384 and left 48% of the memory unspent. The maintainer
# ruled that out in one line — *"the solution should give the user at
# least 50 to 90% of what the LLM and PC can handle in terms of tokens"* —
# and a power-of-two ladder's worst case is exactly 51%.
CONTEXT_STEPS = (131_072, 65_536, 32_768, 16_384, 8_192, 4_096, 2_048)

#: Resolved windows are rounded down to a multiple of this. Fine enough to
#: spend ~99% of the memory and coarse enough that the figure reads as a
#: setting rather than as a measurement with a remainder.
CONTEXT_GRANULARITY = 1_024

#: The smallest window worth resolving to. A model given less is not
#: usable for the jobs a local model does well, and this is also the
#: answer when nothing fits at all.
MIN_CONTEXT_TOKENS = 2_048

#: Held back from the cache, over and above the weights and the embedder.
#:
#: **Not a percentage**, because what it is reserved for does not scale
#: with the cache: llama.cpp allocates a compute buffer sized by the
#: model's dimensions and batch size, and the driver and the desktop take
#: their own. A fraction would under-reserve on a small card and waste
#: memory on a large one.
#:
#: The failure it exists to prevent is the one the maintainer quoted from
#: LM Studio's own behaviour: a cache that overruns the card is not
#: refused, it is **offloaded to system RAM**, and generation speed
#: collapses mid-conversation. That reads as the model being bad, so the
#: margin is deliberately on the safe side of the arithmetic.
COMPUTE_RESERVE_BYTES = 384_000_000


def affordable_context_length(
    bytes_per_token: Optional[int], free_bytes: Optional[int]
) -> Optional[int]:
    """The largest window whose cache fits in ``free_bytes``, or ``None``.

    Pure, so the arithmetic is checked without a server.

    **Rounded down to `CONTEXT_GRANULARITY`, not onto a ladder.** The first
    version answered with a power of two, which is defensible for a
    control somebody is reading and wasteful as a decision: between two
    steps it discards up to half the memory, and the maintainer's
    requirement is 50–90% of what the machine can hold rather than
    50% of it at worst. A 1,024-token granularity spends ~99% and still
    reads as a setting.

    ``None`` in either argument gives ``None`` out — an unmeasured machine
    and an unreadable model are both *unknown*, and neither of them is
    "nothing fits". The same three-valued discipline `vram_bytes` keeps by
    refusing to answer ``0``.

    **Unknown and nothing-fits are different answers.** Both inputs read
    and no window affordable is a conclusion: the weights overrun the
    card, and `MIN_CONTEXT_TOKENS` is the reply. ``None`` is reserved for
    not knowing, and sends the caller to the model author's own figure
    instead.
    """
    if not bytes_per_token or bytes_per_token <= 0:
        return None
    if free_bytes is None:
        return None

    usable = free_bytes - COMPUTE_RESERVE_BYTES
    if usable <= 0:
        return MIN_CONTEXT_TOKENS

    tokens = int(usable // bytes_per_token)
    tokens -= tokens % CONTEXT_GRANULARITY
    return max(tokens, MIN_CONTEXT_TOKENS)


@dataclass(frozen=True)
class ContextChoice:
    """A resolved window and why it is that number.

    ``tokens`` of ``0`` means *send no `num_ctx` and let the server use its
    own default* - the honest answer when nothing could be worked out, and
    distinct from a small window that was chosen.

    ``reason`` is shown to the person. Routing legibility applied to the
    one setting whose wrong value makes a good model look bad.
    """

    tokens: int
    reason: str


_SERVER_DEFAULT = "Whatever the server does, usually 4,096 tokens"


def resolve_context_window(
    *,
    declared: Optional[int],
    configured: Optional[int],
    bytes_per_token: Optional[int],
    free_bytes: Optional[int],
    override: Optional[int] = None,
    policy: str = "fit",
    fixed: Optional[int] = None,
) -> ContextChoice:
    """How much context to ask for, decided per model rather than per user.

    **The elegant alternative to a number the user re-picks on every model
    switch**, asked for 4 October 2026: *"I don't want users to need to
    switch token limits every time they switch or download a new model."*
    The stored setting stops being a figure and becomes an intent; the
    figure is worked out here, for this model, against this card.

    Order, and each step answers a different question:

    1. **An override for this model wins.** A number somebody set
       deliberately is remembered against the model it was set for, never
       globally - that is what stops one choice being wrong for every
       other model.
    2. ``policy == "server"`` leaves Ollama alone, which is what the whole
       setting did before this existed.
    3. ``policy == "fixed"`` honours one number for everything, for
       somebody who genuinely wants that.
    4. Otherwise **fit**: the largest step that fits beside the weights,
       never past what the model says it can hold.

    Every branch is capped by ``declared``. Asking for more context than
    the model's own file admits to is wrong however it was arrived at, and
    the cap is silent because there is nothing for the person to decide.

    When the cost per token cannot be worked out - `gemma4`'s
    sliding-window layers are the measured case - fit falls back to the
    window the model's **own file** asks for. That is its author's
    judgement about its own geometry, which beats Zaram's guess and beats
    4,096.
    """
    ceiling = declared if declared and declared > 0 else None

    def capped(tokens: int) -> int:
        return min(tokens, ceiling) if ceiling else tokens

    if override and override > 0:
        tokens = capped(override)
        if ceiling and override > ceiling:
            return ContextChoice(tokens, f"{_k(tokens)}, the most this model can hold")
        return ContextChoice(tokens, f"{_k(tokens)}, set for this model")

    if policy == "server":
        return ContextChoice(0, _SERVER_DEFAULT)

    if policy == "fixed":
        # **Capped like every other branch, and that is why this goes
        # through here rather than being read straight out of Settings.**
        # The first version let the engine return the stored figure
        # directly, which asked `qwen3-14b-16k` for 131,072 against a
        # declared ceiling of 40,960 — a number the model cannot hold,
        # arrived at by the one route that skipped the cap. A rule applied
        # in three places is a rule broken in one of them.
        if fixed and fixed > 0:
            tokens = capped(fixed)
            if ceiling and fixed > ceiling:
                return ContextChoice(
                    tokens, f"{_k(tokens)}, the most this model can hold"
                )
            return ContextChoice(tokens, f"{_k(tokens)}, set for every model")
        # `0` means nobody has typed a number yet, so there is nothing to
        # honour and the server default is the truth.
        return ContextChoice(0, _SERVER_DEFAULT)

    fits = affordable_context_length(bytes_per_token, free_bytes)
    if fits is not None:
        tokens = capped(fits)
        if ceiling and fits > ceiling:
            return ContextChoice(tokens, f"{_k(tokens)}, the most this model can hold")
        return ContextChoice(
            tokens, f"{_k(tokens)}, the most this card affords beside the weights"
        )

    if configured and configured > 0:
        tokens = capped(configured)
        return ContextChoice(tokens, f"{_k(tokens)}, what the model's own file asks for")

    return ContextChoice(0, _SERVER_DEFAULT)


def _k(tokens: int) -> str:
    """``32k``, or ``15k`` — the unit a model's own documentation uses, so
    this figure and the one on its model card compare at a glance.

    Resolved windows are multiples of 1,024 rather than powers of two, so
    this says `15k` where it used to say `15,360`. The exact number is
    never hidden from somebody who wants it: the reason line beside it
    names the source, and the override ladder is explicit.
    """
    if tokens >= 1_024 and tokens % 1_024 == 0:
        return f"{tokens // 1_024}k tokens"
    return f"{tokens:,} tokens"


def room_for_a_cache(model: str) -> Optional[int]:
    """Room for this model's cache once its weights are in, or ``None``.

    **Measured against the card's total, deliberately, and not against
    what is free this minute.** `vram_free_bytes` exists and is the better
    reading for a preload — its own docstring says so and gives the
    measurement — but it is the wrong one here, and trying it first is how
    that was found. Probed on the maintainer's machine 4 October 2026 with
    TabbyAPI resident: **1.2 GB free of 12.3**, which resolves a 14B's
    window to the smallest step on the ladder. Unload Tabby and the same
    model deserves 8k.

    A context window that silently shrinks because something else is open,
    and stays shrunk, is not a setting — it is a reading, and the person
    would experience it as Zaram getting worse for no reason they can
    see. So the basis is a property of *(this machine, this model)*: the
    card's capacity, less what Zaram keeps resident, less the weights.

    The cost of choosing this way is accepted and named: when another
    process does hold the card, the resolved window is larger than will
    fit and Ollama spills. That is already true of the weights themselves,
    it is the condition the orb's swap state exists to show, and it is not
    something a context setting can fix by being pessimistic forever.

    ``None`` is a real answer and the common one off NVIDIA — Apple and
    DirectML report no VRAM at all, because Apple shares one pool with the
    CPU and quoting system RAM would overstate what a model can claim. The
    resolver then falls back to the window the model's own file asks for,
    which is its author's judgement about its own geometry rather than
    Zaram's guess.
    """
    try:
        from providers.discoverers.hardware import HardwareProfiler

        total = HardwareProfiler().profile().vram_bytes
    except Exception:
        return None
    if not total or total <= 0:
        return None

    weights = _weights_bytes(model)
    if weights is None:
        return None

    # What Zaram holds beside a chat model. The embedder measures 0.66 GB
    # resident on the maintainer's card (CLAUDE.md's residency table); 0.7
    # rounds against the user rather than for them, which is the direction
    # to round when the cost of being wrong is the card spilling.
    embedder = 700_000_000

    # **Not clamped to zero**, and that is the point. A negative result
    # means the weights alone exceed the card, which is a *measurement*
    # and not an absence of one — the honest reply to it is the cheapest
    # cache on the ladder, and clamping to 0 would have made it
    # indistinguishable from the unknown case that falls back to 128k.
    return total - embedder - weights


def _weights_bytes(model: str) -> Optional[int]:
    """This model's size on disk, as Ollama reports it, or ``None``."""
    try:
        import requests

        reply = requests.get("http://127.0.0.1:11434/api/tags", timeout=2.0)
        reply.raise_for_status()
        for entry in reply.json().get("models") or []:
            if isinstance(entry, dict) and entry.get("name") == model:
                size = entry.get("size")
                return int(size) if isinstance(size, (int, float)) and size > 0 else None
    except Exception:
        return None
    return None


@dataclass(frozen=True)
class ModelWindow:
    """What is known about one model's context, whoever is serving it.

    **Added 4 October 2026, immediately after the model-neutrality rule
    went into `CLAUDE.md`, because the code written an hour earlier broke
    it.** Every reader feeding `resolve_context_window` spoke Ollama's
    `/api/show` and nothing else, so the control was asked about the model
    that would actually answer on the maintainer's machine —
    `Qwen3.8-27B-exl3-2.20bpw`, served by TabbyAPI — and every field came
    back `None`. It resolved to *"whatever the server does, usually
    4,096"* for a model holding **65,536**: the same 32x error
    `local_server_context_length` was written to fix, reintroduced by a
    feature that only knew one runtime.

    ``settable`` is the honest half. Zaram sets a window by sending
    `num_ctx` on an Ollama request; there is no equivalent on an
    OpenAI-compatible route, where the window is fixed when that server
    loads the model. So for those the figure is **reported, not
    controlled**, and a control that offered to change it would be a
    switch that settles nothing — which this codebase already refuses to
    ship for permission scopes and should refuse here for the same reason.
    """

    declared: Optional[int]
    configured: Optional[int]
    bytes_per_token: Optional[int]
    settable: bool
    #: Which runtime answered, for a reason line that can say so.
    served_by: str


def read_model_window(
    model: Optional[str],
    base_url: str = "http://127.0.0.1:11434",
    timeout: float = 2.0,
) -> ModelWindow:
    """Everything the resolver needs, from whichever runtime has the model.

    **Ollama first, then the other local servers**, which is the order
    `local_server_context_length` already argues for: Ollama is the common
    case, and the rest are two HTTP calls to ports usually closed.

    A second server's route reports the window it loaded with, which *is*
    that model's ceiling until it is restarted — so the same number serves
    as both ``declared`` and ``configured``, and nothing is invented to
    fill the other field. The cache cannot be priced there at all, because
    no OpenAI-compatible route publishes the attention geometry; that is
    ``None``, and `fit` then uses the server's own figure, which is the
    right answer rather than a fallback.
    """
    if not model:
        return ModelWindow(None, None, None, True, "")

    declared = declared_context_length(model, base_url, timeout)
    if declared is not None:
        return ModelWindow(
            declared=declared,
            configured=configured_context_length(model, base_url=base_url, timeout=timeout),
            bytes_per_token=kv_bytes_per_token(model, base_url, timeout),
            settable=True,
            served_by="ollama",
        )

    served = local_server_context_length(model)
    if served is not None:
        return ModelWindow(
            declared=served,
            configured=served,
            bytes_per_token=None,
            settable=False,
            served_by="local server",
        )

    # Unknown, and `settable` stays true: an Ollama model whose `/api/show`
    # did not answer is still one Zaram can send `num_ctx` to, and saying
    # otherwise would hide the control from the case it was built for.
    return ModelWindow(None, None, None, True, "")
