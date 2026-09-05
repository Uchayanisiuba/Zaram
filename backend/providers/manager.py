"""Orchestration manager for the provider layer (v0.6.0).

:class:`ProviderManager` is the single control point the API and runtime talk
to. It owns the model catalog and the caches of voices / runtimes /
personalities / hardware, drives discovery through the scanner, and exposes
pure, offline, read-only accessors. It never imports a concrete engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.event_bus import EventBus

from .contracts import (
    CapabilityLocality,
    HardwareProfile,
    ModelCategory,
    ModelInfo,
    ProviderKind,
    RuntimeInfo,
    VoiceInfo,
)
from .health import ProviderHealth, ProviderHealthAggregator
from .model_catalog import ModelCatalog
from .registry import ProviderRegistry
from .scanner import ProviderScanner

logger = logging.getLogger(__name__)

#: What a model's KV cache costs, as a fraction of its own weights.
#:
#: Weights are not the whole cost — the cache grows with context length — so a
#: model sized to exactly the free VRAM fits at load and thrashes a few
#: thousand tokens into a conversation. That failure arrives late and looks
#: like the product being slow, which is why an allowance exists at all.
#:
#: **It is charged against the model, not against the card, and that is the
#: correction.** It used to be a flat 20% of VRAM held back from the budget,
#: which is a tax unrelated to the model being tested: identical for a 3 GB
#: model and a 30 GB one, and 4.8 GB on a 24 GB card no matter what is being
#: loaded. Measured 31 August 2026 on the 12 GB card it excluded *every* chat
#: model installed — `qwen3:14b` missed the budget by 0.13 GB while running
#: perfectly well beside the embedder — and an empty candidate set is what
#: produced "No model was selected for this request".
#:
#: The number stays a judgement, but it is now a judgement in the right units
#: and checked against one real measurement: `qwen3-14b-8k` is 9.28 GB on disk
#: and **10.32 GB resident at `num_ctx 8192`**, a cache of 11% of its weights.
#: 20% keeps roughly the margin that reading is worth, and errs large, which is
#: the direction that costs a swap rather than a wrong answer.
#:
#: The remaining honest fix is to read the model's own `num_ctx` — `/api/ps`
#: reports it — and size the cache from the architecture rather than from the
#: weights. That is a measurement; this is still a proxy.
_KV_CACHE_ALLOWANCE_FRACTION = 0.20


def _same_model(a: str, b: str) -> bool:
    """Whether two model names refer to the same model.

    Three spellings of one thing are in play, which is two more than anyone
    would guess from a single call site:

    - the **catalog id**, provider-prefixed: `ollama:gemma3:latest`
    - the **provider-native name**, which `/api/ps` and `/api/tags` report and
      which the chat path passes to Ollama: `gemma3:latest`
    - the **bare name**, which a config file or a per-task assignment may use,
      and which Ollama itself treats as `:latest`: `gemma3`

    Comparing any two of those directly fails. Getting it wrong is not a
    crash — it is a residency check that silently never matches, so the
    embedder gets charged against the chat budget and the orb announces a swap
    before every single message. Discovered against the real catalog; the
    first version of this compared ids only and the fakes in the tests happened
    to be keyed the same way as `/api/ps`, so nothing failed.
    """
    def norm(name: str) -> str:
        name = (name or "").strip().lower()
        for prefix in ("ollama:", "lmstudio:", "lm_studio:", "openrouter:"):
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        return name[: -len(":latest")] if name.endswith(":latest") else name

    return norm(a) == norm(b)


def _matches_resident(model_id: str, resident: Dict[str, Optional[int]]) -> bool:
    return any(_same_model(model_id, name) for name in resident)


@dataclass(frozen=True)
class SwapPlan:
    """What loading a model will cost, decided before it is loaded.

    `kind` is one of:

    - `resident` — already loaded, nothing to say
    - `load` — a cold start with room to spare
    - `swap` — something resident must be evicted to make room
    - `oversized` — larger than the whole budget, so evicting everything would
      not help; it will load with layers spilled to system RAM

    Four rather than a boolean because the remedies differ. A cold start passes
    on its own; a recurring swap is a model-assignment problem the user can fix
    in Settings; an oversized model is a hardware fact no setting will change.
    """

    kind: str
    model: str
    #: Models that would be unloaded to make room. Empty unless `kind` is `swap`.
    evicts: List[str]
    bytes_needed: int

    @property
    def requires_swap(self) -> bool:
        return self.kind == "swap"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "model": self.model,
            "evicts": list(self.evicts),
            "bytes_needed": self.bytes_needed,
        }


class ProviderManager:
    """Discovers and serves Zaram's AI resources."""

    def __init__(
        self,
        registry: Optional[ProviderRegistry] = None,
        scanner: Optional[ProviderScanner] = None,
        *,
        event_bus: Optional[EventBus] = None,
        aggregator: Optional[ProviderHealthAggregator] = None,
    ) -> None:
        self.registry = registry or ProviderRegistry()
        self.scanner = scanner or ProviderScanner(self.registry)
        self._event_bus = event_bus
        self._aggregator = aggregator or ProviderHealthAggregator()

        self.catalog = ModelCatalog()
        self._voices: List[VoiceInfo] = []
        self._runtimes: List[RuntimeInfo] = []
        self._personalities: List[Dict[str, Any]] = []
        self._hardware: HardwareProfile = HardwareProfile()
        self._scanned = False

    # --- discovery lifecycle ---
    async def refresh(self, *, timeout: float = 2.0) -> None:
        """Re-run discovery across every configured source and cache the results."""
        models = await self.scanner.scan_models(timeout=timeout)
        self.catalog.clear()
        self.catalog.upsert_all(models)

        self._voices = await self.scanner.scan_voices()
        self._runtimes = self.scanner.scan_runtimes()
        self._personalities = self.scanner.scan_personalities()
        self._hardware = self.scanner.profile_hardware()

        self._scanned = True
        self._publish_scanned()
        logger.info(
            "Provider scan complete: %d models, %d voices, %d runtimes, %d personalities",
            self.catalog.count(),
            len(self._voices),
            len(self._runtimes),
            len(self._personalities),
        )

    async def ensure_scanned(self) -> None:
        """Lazily perform one scan if none has happened yet."""
        if not self._scanned:
            await self.refresh()

    # --- model read API ---
    def list_models(
        self,
        *,
        category: Optional[ModelCategory] = None,
        capability: Optional[str] = None,
        locality: Optional[CapabilityLocality] = None,
        available_only: bool = False,
        provider: Optional[str] = None,
    ) -> List[ModelInfo]:
        return self.catalog.filter(
            category=category,
            capability=capability,
            locality=locality,
            available_only=available_only,
            provider=provider,
        )

    def get_model(self, model_id: str) -> Optional[ModelInfo]:
        return self.catalog.get(model_id)

    def embedding_footprint_bytes(self) -> int:
        """What the embedding model claims, since it is resident continuously.

        Recall runs on every exchange, so the embedder is not an occasional
        tenant of VRAM — it is a permanent one. A chat model chosen as though it
        had the whole card to itself will evict it on the first message and get
        evicted back on the next recall, which is the swap this budget exists to
        prevent.

        Read from the catalog rather than from configuration: whichever
        embedding model discovery actually found is the one that will be
        resident, and the provider layer must not hardcode its name.
        """
        embedders = self.list_models(
            category=ModelCategory.EMBEDDING, available_only=True
        )
        return max((m.size_bytes or 0 for m in embedders), default=0)

    def resident_budget_bytes(self) -> Optional[int]:
        """VRAM a chat model may claim alongside the embedder, or ``None``.

        ``None`` means residency cannot be planned — no accelerator, or one
        whose capacity we cannot read (Metal, DirectML). It is not a budget of
        zero, and callers must not treat it as one: on those machines the fit
        test is skipped rather than failed, because inventing a number here is
        the false-zero bug that ``HardwareProfile.vram_known`` exists to stop.

        **The KV allowance is no longer deducted here.** It belongs to the
        model being tested, not to the card — see
        `_KV_CACHE_ALLOWANCE_FRACTION` and `resident_cost_bytes`. Deducting it
        from the budget *and* comparing against weights that exclude the cache
        was one charge in two places, and it excluded every model on a machine
        that ran one of them fine.
        """
        hardware = self.hardware_profile()
        if not hardware.vram_known:
            return None

        vram = hardware.vram_bytes or 0
        return max(vram - self.embedding_footprint_bytes(), 0)

    def resident_cost_bytes(self, model: ModelInfo) -> Optional[int]:
        """What ``model`` actually claims on the card, weights plus its cache.

        ``None`` when the model does not report a size, which is every model on
        an OpenAI-compatible server — no such route carries a memory figure.
        Callers must read that as "cannot tell", never as zero.

        This is the quantity every residency comparison wants, and using
        ``size_bytes`` instead is what made the gate wrong: an on-disk figure
        is the weights alone, so a model was measured against a budget that had
        already been docked for a cache the figure did not include.
        """
        if model.size_bytes is None:
            return None
        return int(model.size_bytes * (1 + _KV_CACHE_ALLOWANCE_FRACTION))

    def swap_preflight(self, model_id: str) -> Optional["SwapPlan"]:
        """Will answering with ``model_id`` force a model out of VRAM?

        Asked **before** generation starts, not discovered during it. CLAUDE.md
        requires that a route which forces a swap be visible in the orb's
        state, and a spinner that appears once the machine has already stalled
        is not visibility — the user has by then spent the seconds and drawn
        their own conclusion about why the product is slow.

        Three outcomes, and the middle one is the reason this is not a boolean:

        - **resident** — the model is already loaded. Nothing to say.
        - **load** — not loaded, but it fits alongside what is. A cold start,
          which is `warming`: a wait with no eviction behind it.
        - **swap** — not loaded, and loading it exceeds the budget, so
          something currently resident has to go. This is the one the rule is
          about, and it is also the one that will happen *again* on the next
          message that routes back.

        Returns ``None`` when the question cannot be answered — no accelerator,
        unreadable VRAM, an unreachable Ollama, or a model whose size we do not
        know. Never guesses. Announcing a swap that does not happen would train
        the user to ignore the indicator, which costs more than staying quiet.

        Returns ``None`` in one further case, and it is new: the model does not
        fit, and nothing Zaram's own servers would unload is what is in the
        way. That happens when a *second* local server holds the card, or when
        a program Zaram knows nothing about does. There is no honest sentence
        for it in this vocabulary — it is not ``oversized``, because the model
        is not too big for the machine, and it is not a ``swap``, because
        nothing is displaced — so it says nothing rather than saying the
        nearest wrong thing.
        """
        model = self._resolve_model(model_id)
        if model is None:
            return None

        resident = self._resident_models()
        if resident is None:
            return None

        # **Asked before size, and that ordering is the fix.** Whether a model
        # is already on the card is answerable from the residency map alone; it
        # does not need a budget and it does not need the model's size.
        #
        # The checks used to run the other way round, so a model reporting no
        # size returned `None` here — "cannot determine" — before residency was
        # ever consulted. No OpenAI-compatible server reports a size, so for
        # every TabbyAPI model that was *always*, and no `model_load` event was
        # emitted at all. The interface then fell back to its timer, which
        # guesses that silence means a cold model, and the orb read **Warming
        # up** on every single message including ones answered in under a
        # second by weights that had not moved.
        #
        # Measured in the running app, 31 August 2026, with
        # `Qwen3.8-27B-exl3-2.20bpw` pinned: second message, model resident,
        # "Warming up · Starting the local model. The first reply of a session
        # takes longer."
        #
        # Ollama tags are matched loosely because a request may name `gemma3`
        # while `/api/ps` reports `gemma3:latest`. Treating those as different
        # models would announce a swap before every single reply.
        if _matches_resident(model_id, resident):
            return SwapPlan(kind="resident", model=model_id, evicts=[], bytes_needed=0)

        # Weights plus the model's own cache, which is what loading it will
        # actually claim. `bytes_needed` reaches the interface, so it has to be
        # the number the card will see rather than the number on disk.
        cost = self.resident_cost_bytes(model)
        if cost is None:
            return None

        budget = self.resident_budget_bytes()
        if budget is None:
            return None

        # A model that does not fit even with the card cleared is not swapping
        # anything — there is nothing to evict that would make room. Ollama
        # loads it anyway and spills layers to system RAM, which is slow for a
        # different reason and has a different remedy.
        #
        # Reporting that as a swap would produce an indicator naming nothing
        # displaced, which cannot explain itself: "switching model, evicting —"
        # is worse than saying nothing. Found by a test asserting the embedder
        # was excluded, which it was; the leftover `swap` with an empty
        # `evicts` was the real defect underneath.
        #
        # Asked before headroom, and that ordering is load-bearing now that
        # headroom can be unknown: whether a model is too big for the whole
        # card is decidable from capacity alone, so an unsizeable tenant must
        # not be allowed to suppress the one verdict it has no bearing on.
        if cost > budget:
            return SwapPlan(
                kind="oversized", model=model_id, evicts=[],
                bytes_needed=cost,
            )

        headroom = self._headroom_bytes(resident)
        if headroom is None:
            return None

        if cost <= headroom:
            return SwapPlan(kind="load", model=model_id, evicts=[], bytes_needed=cost)

        evicts = self._evictable_by(model, resident)
        if not evicts:
            # It does not fit, and nothing this model's own server would unload
            # is what is occupying the card. Another local server or another
            # program is, and neither will step aside. Naming an eviction that
            # will not happen is the failure the `oversized` branch above was
            # written to avoid, so this stays quiet instead.
            return None

        return SwapPlan(
            kind="swap",
            model=model_id,
            evicts=evicts,
            bytes_needed=cost,
        )

    def _resolve_model(self, model_id: str) -> Optional[ModelInfo]:
        """Find a catalogued model, tolerating a missing `:latest`.

        The catalog is keyed by the name Ollama reports (`gemma3:latest`) while
        a request, a config file or a per-task assignment may say `gemma3`.
        Ollama treats those as the same model and so must this — an exact-match
        lookup returns None for a model that is plainly installed, and a
        pre-flight that cannot find the model reports "cannot determine" for
        the most ordinary case there is.
        """
        exact = self.get_model(model_id)
        if exact is not None:
            return exact
        for candidate in self.catalog.all():
            # Both spellings, because the catalog id carries a provider prefix
            # the caller does not use and `display_name` is the provider-native
            # name that both the chat path and `/api/ps` speak.
            if _same_model(model_id, candidate.id) or _same_model(
                model_id, candidate.display_name
            ):
                return candidate
        return None

    def _resident_models(self) -> Optional[Dict[str, Optional[int]]]:
        """Live residency across **every** local server, or None for unknown.

        Merged, not first-wins. This used to return the first adapter that gave
        a non-``None`` answer, which on a one-server machine is
        indistinguishable from correct and on a two-server machine is a
        ten-gigabyte lie. Measured 28 August 2026 on the 12 GB card: Ollama
        answered an empty map first while TabbyAPI held 9.5 GB, so
        `swap_preflight` planned against an empty card and would have graded a
        cold start onto 2.6 GB of actual headroom as "fits".

        **A provider that cannot answer makes the whole answer unknown.**
        Merging whatever happens to be reachable would report a partial picture
        as a complete one, which is the same defect at a smaller scale — and
        the error runs in the dangerous direction, because an unseen tenant
        always makes the card look emptier than it is. Silence is a supported
        outcome downstream; a confident undercount is not.

        A local provider with no residency probe at all is likewise unknown
        rather than nothing: that absence *is* the hole this method was fixed
        to close, and treating it as an empty answer would reintroduce it by a
        quieter route. Cloud providers are skipped — they hold no VRAM on this
        machine — and a provider that does not say which kind it is is treated
        as local, because that is the assumption that fails safe.

        Values are ``Optional[int]``: bytes where the server reports them,
        ``None`` for "resident, size unknown". TabbyAPI is the second shape,
        since no OpenAI-compatible route carries a memory figure. Callers must
        not read that ``None`` as a zero.
        """
        merged: Dict[str, Optional[int]] = {}
        for adapter in self.registry.list_model_providers():
            if getattr(adapter, "kind", None) is ProviderKind.CLOUD_API:
                continue
            probe = getattr(adapter, "resident_models", None)
            if probe is None:
                logger.debug(
                    "Residency unknown: local provider %s cannot report what it holds",
                    getattr(adapter, "provider_id", "?"),
                )
                return None
            try:
                result = probe()
            except Exception as exc:
                logger.debug(
                    "Residency unknown: provider %s probe raised: %s",
                    getattr(adapter, "provider_id", "?"), exc,
                )
                return None
            if result is None:
                return None
            merged.update(result)
        return merged

    def _vram_used_bytes(self) -> Optional[int]:
        """The driver's own reading of what is on the card, or None.

        Asked of the hardware profiler rather than of the model providers,
        because it is the one source that sees tenants Zaram did not put there.
        Guarded with ``getattr`` so a profiler that predates the probe — every
        fake in the suite — degrades to "cannot tell" rather than raising on
        the reply path.
        """
        profiler = self.registry.get_hardware_profiler()
        probe = getattr(profiler, "vram_used_bytes", None)
        if probe is None:
            return None
        try:
            return probe()
        except Exception as exc:
            logger.debug("VRAM occupancy probe failed: %s", exc)
            return None

    def _headroom_bytes(self, resident: Dict[str, Optional[int]]) -> Optional[int]:
        """Bytes a new model may claim right now without displacing anything.

        Two sources for the same quantity, preferred in this order — and they
        are *alternatives*, never blended. Each is measured against its own
        baseline, because mixing the baselines is how a number gets charged
        twice.

        **The sum**, when every resident chat model reports a size. Counted
        against ``resident_budget_bytes``, which has already deducted the
        embedder. Preferred because it is attributable: it
        counts Zaram's own tenants and nothing else, so the answer does not
        move when an unrelated program takes a slice of the card.

        **The driver**, when it does not. A server that names the model it
        holds without sizing it — TabbyAPI, and any other OpenAI-compatible
        server — leaves the sum unanswerable, and an unanswerable sum is how
        9.5 GB came to be invisible. This one is counted against raw capacity,
        because the measured figure already contains the embedder if the
        embedder is loaded. Deducting it from the budget as well would charge
        it twice, and charging it twice with the on-disk size standing in for
        its resident footprint would over-deduct in the direction that invents
        swaps.

        **Neither path deducts a KV reserve any more, and both used to.** The
        sum path counts residency figures read from ``/api/ps`` as
        ``size_vram`` — a model's cache is already inside that number — and the
        driver path counts what the card actually reports as used, which
        contains every byte of every cache on it. Holding back a further 20% of
        capacity charged those caches a second time, and the caller compares
        this against `resident_cost_bytes`, which carries the *incoming*
        model's allowance. Once here, once there.

        When the embedder is *not* resident, room is left for it explicitly:
        recall runs on every exchange, so it is not an optional tenant.
        """
        budget = self.resident_budget_bytes()
        if budget is None:
            return None

        chat = {
            name: size
            for name, size in resident.items()
            if not self._is_embedding_model(name)
        }
        if all(size is not None for size in chat.values()):
            return max(budget - sum(size or 0 for size in chat.values()), 0)

        used = self._vram_used_bytes()
        if used is None:
            return None

        profile = self.hardware_profile()
        total = profile.vram_bytes or 0
        headroom = total - used
        if not any(self._is_embedding_model(name) for name in resident):
            headroom -= self.embedding_footprint_bytes()
        return max(headroom, 0)

    def _evictable_by(
        self, model: ModelInfo, resident: Dict[str, Optional[int]]
    ) -> List[str]:
        """Resident models that loading ``model`` would actually displace.

        A server evicts its own tenants and nobody else's. Ollama unloads an
        Ollama model to make room for an Ollama model; it has no way to touch
        what a second server on the same card is holding, and does not try — it
        loads anyway and spills layers to system RAM. Naming a cross-server
        model here would be an indicator claiming a displacement that never
        happens, which is the swap-with-nothing-evicted failure wearing a
        different disguise.

        The provider is read from the catalog rather than from the probe,
        because the residency map is keyed by provider-native names and the
        provider is a catalog fact. A resident model the catalog does not know
        is not named: we cannot say whose it is, and a guess here becomes a
        sentence on screen about a model being unloaded.
        """
        evictable: List[str] = []
        for name in resident:
            if self._is_embedding_model(name):
                continue
            other = self._resolve_model(name)
            if other is not None and other.provider == model.provider:
                evictable.append(name)
        return sorted(evictable)

    def _is_embedding_model(self, name: str) -> bool:
        """Whether a resident model is the embedder rather than a chat model.

        Resolved through the catalog rather than by matching on the string
        "embed", so a differently-named embedder is still recognised — the
        provider layer must not hardcode which model does the embedding.
        """
        embedders = self.list_models(category=ModelCategory.EMBEDDING)
        return any(
            _same_model(name, m.id) or _same_model(name, m.display_name)
            for m in embedders
        )

    def model_fits_resident(self, model: ModelInfo) -> Optional[bool]:
        """Whether ``model`` can be co-resident with the embedder.

        Three answers, and the third matters: ``True``, ``False``, and ``None``
        for "cannot be determined" — either the budget is unknown or the model
        does not report a size. ``None`` is never promoted to ``True``.

        Compared as *cost* against *capacity less the embedder*: both sides of
        this inequality changed on 31 August 2026, in opposite directions, and
        the pair has to move together. See `resident_cost_bytes`.
        """
        budget = self.resident_budget_bytes()
        cost = self.resident_cost_bytes(model)
        if budget is None or cost is None:
            return None
        return cost <= budget

    def select_default_model(
        self, *, category: ModelCategory = ModelCategory.LLM
    ) -> Optional[ModelInfo]:
        """The model Zaram may route to without the user having chosen one.

        Returns ``None`` rather than a fallback when nothing qualifies. A
        caller with no model is a caller that says so; a caller handed a model
        the user never consented to is a Rule 5 violation that looks like a
        working feature.

        Three criteria, in this order, because that is the order in which
        getting it wrong hurts:

        1. **Does it fit alongside the embedding model.** A model that forces a
           swap is not the default while anything else is available — the cost
           lands on every single exchange, and it is the kind of slowness users
           attribute to the product rather than to a setting.

           **It is a strong preference, not a hard gate, and the difference is
           what "No model was selected" cost.** A hard gate on a machine where
           nothing fits leaves no default at all, so Zaram declines to answer a
           question it can answer slowly. See `select_model_for_task`.
        2. **Is it general-purpose.** A coding fine-tune answering general
           questions is a category error that shows up as oddly-shaped answers
           rather than as an obvious failure, so it is harder to diagnose than
           it looks.
        3. **Size**, last, as a rough stand-in for capability. It is the axis
           that matters least and the only one that is easy to measure, which is
           precisely why it used to be the only one considered.

        Size-first selection is what picked a 9 GB coding model on a 12 GB card
        for general chat: largest wins, and both of the criteria that should
        have vetoed it were absent.

        This is `select_model_for_task` with nothing known about the task,
        which is a real case and not a degenerate one: the answer to "what
        should Zaram use when it knows nothing about the question" is what
        Settings displays and what the models runtime loads at boot.
        """
        return self.select_model_for_task(category=category)

    def select_model_for_task(
        self,
        *,
        requires_vision: bool = False,
        requires_image_output: bool = False,
        specialisation: Optional[str] = None,
        category: ModelCategory = ModelCategory.LLM,
    ) -> Optional[ModelInfo]:
        """The same selection, with this request's own requirements applied.

        Three arguments, and **they are deliberately different kinds of
        thing**:

        - ``requires_vision`` is a **gate**. A model that cannot accept an
          image is not a worse answer to "what is in this screenshot", it is
          not an answer at all — so it is removed before ranking rather than
          scored down inside it.
        - ``requires_image_output`` is the **other** gate, and it is a
          different question from the first one. Reading a picture and drawing
          one are not degrees of the same ability, and `CLAUDE.md` names
          collapsing them as the error that gets a text model asked to draw.
          Added 3 September 2026: the flag it reads,
          `ModelInfo.emits_image`, is derived from the output modalities
          OpenRouter discovery already recorded and threw nothing away to
          build.
        - ``specialisation`` is a **preference**. "A coding model is better at
          this" is a judgement, and the general model stays a real answer when
          no specialist is installed.

        Merging the two is this codebase's most expensive recurring bug in
        its modality form. The `orchestrator` package contained a working
        version of the mistake — `scoring.py` recorded a *missing required
        capability* as a warning and ranked the candidate anyway — and it was
        deleted on 28 August 2026 rather than left as a temptation with a
        comment on it. That shape is how a text-only model comes to be asked to
        read a picture and answers with confident prose about an image it never
        saw: rule 9's failure in a new medium.

        Returns ``None`` when the gate empties the field, and callers must not
        substitute: no vision-capable model installed means Zaram cannot answer
        that question, not that it should answer it blind.

        **Residency does not get to answer a capability question, and it used
        to.** `_auto_candidates` drops anything that positively does not fit
        VRAM *before* this gate runs, so on a machine whose only vision-capable
        model is oversized the field emptied for the wrong reason and the user
        was told:

            "No model on this machine can read images. Zaram will not answer
             about a picture it cannot see."

        Measured 28 August 2026: `gemma4:26b-a4b` catalogued
        ``supports_vision: True``, ``fits_resident: False`` — 18.2 GB against a
        12 GB card. It can see perfectly well. It is *slow*, which is a
        different sentence, and `CLAUDE.md` settles which one wins: **"VRAM
        limits route a task; they do not reject a vertical."**

        So when the field empties, the residency filter is relaxed and only
        then is the answer `None`. That ordering is the whole point —
        capability first, speed second — and it keeps the two questions apart
        rather than merging them into one refusal that names the wrong reason.
        Consent filters are untouched by the retry.

        **The relaxation used to run only for vision, and that was backwards.**
        Residency emptying the field on its own is the *more* common case and
        the one with no capability question in it at all: measured 31 August
        2026, every chat model on the 12 GB card reported ``fits_resident:
        false``, so auto-routing had nothing to rank and the user was told "No
        model was selected for this request" on a machine with three chat
        models installed — one of which was running fine. A slow answer was
        available the whole time. `CLAUDE.md` settles it in the same sentence
        that settled the vision case: **"VRAM limits route a task; they do not
        reject a vertical… warn, never block."** A refusal is what a *consent*
        filter is for.

        Nothing is relaxed silently. Ranking still puts a model that fits ahead
        of one that does not, so this changes the answer only when the honest
        alternative was no answer, and `rejected_default_candidates` still
        names residency as the reason a model was passed over.

        The caller still has to say the reply will be slow; `swap_preflight`
        already reports ``oversized`` and the chat stream already carries a
        `model_load` event for it. Warn, never block.
        """
        preference = self._routing_preference()

        def field(*, require_resident_fit: bool) -> List[ModelInfo]:
            models = self._auto_candidates(
                category, preference, require_resident_fit=require_resident_fit
            )

            # A model that draws may be catalogued under either category, and
            # asking for a picture must not depend on which.
            # `_apply_modality` leaves a model that emits **both** text and
            # images an `LLM` — correctly, since it can still hold the
            # conversation — while one that emits images and no text becomes a
            # `ModelCategory.IMAGE`. Filtering on the caller's category alone
            # would therefore drop exactly one of those two, and which one
            # depends on an argument default rather than on anything about the
            # request. So the field is widened before the gate runs, and the
            # gate is what decides.
            if requires_image_output and category is not ModelCategory.IMAGE:
                models = models + [
                    m
                    for m in self._auto_candidates(
                        ModelCategory.IMAGE,
                        preference,
                        require_resident_fit=require_resident_fit,
                    )
                    if m not in models
                ]

            # The gates. Before the ranking, never inside it.
            if requires_vision:
                models = [m for m in models if m.supports_vision]
            if requires_image_output:
                models = [m for m in models if m.emits_image]
            return models

        candidates = field(require_resident_fit=True)
        if not candidates:
            # Capability first, speed second. A model that does not fit is a
            # slow answer; no model at all is a refusal, and refusing when
            # something on the machine can do the job is the worse of the two.
            # Consent is re-applied, never skipped.
            candidates = field(require_resident_fit=False)

        if not candidates:
            return None

        # `prefer_cloud` moves locality and does nothing else. It cannot
        # promote a model whose terms are unknown, because
        # `selectable_by_default` already excluded those and that is a consent
        # gate, not a ranking one. The Settings screen makes exactly this claim
        # to the user — "a bias, not a permission" — and this is what makes it
        # true.
        cloud_first = preference == "prefer_cloud"

        return sorted(
            candidates,
            key=lambda m: self._rank_key(
                m, cloud_first=cloud_first, specialisation=specialisation
            ),
        )[0]

    def _auto_candidates(
        self,
        category: ModelCategory,
        preference: str,
        *,
        require_resident_fit: bool = True,
    ) -> List[ModelInfo]:
        """Models Zaram may pick on its own, before the task is considered.

        Consent and residency. Every filter here answers "may this model be
        used at all", which is why it is shared by every caller rather than
        recomputed per task — a task-specific filter that quietly dropped one
        of these would be a consent gate with an exception in it.

        **`require_resident_fit` is the one exception, and consent is not part
        of it.** Residency is a *speed* judgement; consent is a permission.
        Relaxing the first never relaxes the second — `selectable_by_default`
        and `prefer_local` apply either way — so the escape hatch cannot become
        a route around rule 5. See `select_model_for_task` for when it is used
        and why refusing was worse.
        """
        candidates = [
            m
            for m in self.list_models(category=category, available_only=True)
            if m.selectable_by_default
        ]

        # `None` (unknown fit) survives — an unmeasurable machine must not be
        # left with no default at all — but ranks below a model we positively
        # know fits, so "we could not check" never outranks "it fits".
        if require_resident_fit:
            candidates = [
                m for m in candidates if self.model_fits_resident(m) is not False
            ]

        # `prefer_local` is the one that constrains rather than reorders.
        # "Prefer" is doing real work here: a ranking nudge would be
        # indistinguishable from `auto`, since `auto` already ranks local
        # first — and two settings with identical behaviour are a dead control
        # wearing a third label. This one means Zaram will not pick a cloud
        # model on its own at all. Choosing one by hand still works; this
        # governs what happens when nobody chose.
        if preference == "prefer_local":
            # Not `or candidates`. Falling back to a cloud model here would make
            # the strictest setting the one that silently sends data off-device
            # on a machine with no local model — the exact inversion rule 5
            # exists to prevent. No model is the honest answer, and callers
            # already handle it: returning None is "say so", never
            # "substitute something".
            candidates = [
                m for m in candidates if m.locality is CapabilityLocality.LOCAL
            ]

        return candidates

    def _rank_key(
        self,
        model: ModelInfo,
        *,
        cloud_first: bool,
        specialisation: Optional[str],
    ) -> tuple:
        """Order among models that are all permitted and all capable.

        Fit stays first, ahead of the task match, and that ordering is load
        bearing: a specialist that forces an eviction costs seconds on this
        exchange *and* on the next one that swaps back, which is a worse
        answer than a general model that is already resident.
        `test_fit_outranks_general_purpose` asserts the untasked half of it.
        """
        fits = self.model_fits_resident(model)
        is_local = model.locality is CapabilityLocality.LOCAL
        return (
            0 if fits is True else 1,
            self._specialisation_rank(model, specialisation),
            (1 if is_local else 0) if cloud_first else (0 if is_local else 1),
            -(model.size_bytes or 0),
            model.id,  # deterministic across equal candidates
        )

    @staticmethod
    def _specialisation_rank(model: ModelInfo, wanted: Optional[str]) -> int:
        """0 is best. Three tiers, and the third is why this is not a boolean.

        With no task in hand a general model wins — the existing behaviour, and
        the reason a coding fine-tune stopped answering general questions. With
        a task in hand the specialist for *that* task wins, the general model
        is second, and a specialist for a *different* task is last: a maths
        fine-tune is a worse answer to a coding question than a general model
        is, and a two-way split has no way to say so.
        """
        if wanted is None:
            return 0 if model.is_general_purpose else 1
        if model.specialisation == wanted:
            return 0
        return 1 if model.is_general_purpose else 2

    def _routing_preference(self) -> str:
        """The user's *Prefer local · Auto · Prefer cloud* choice, or ``auto``.

        Read here rather than passed in, because every caller of
        `select_default_model` wants the user's preference applied and none of
        them should have to remember to fetch it — the version of this that
        took it as an argument would be wrong at whichever call site was added
        last.

        Any failure yields ``auto``, which is the behaviour this method had
        before the preference existed. A settings file must never be able to
        change which model answers by being unreadable.
        """
        try:
            from core.user_settings import get_user_settings

            return get_user_settings().routing_preference.value
        except Exception:
            return "auto"

    def rejected_default_candidates(
        self, *, category: ModelCategory = ModelCategory.LLM
    ) -> List[tuple[ModelInfo, str]]:
        """Available models excluded from auto-selection, each with the reason.

        "Show routing decisions in plain language" needs the models that were
        *not* picked as much as the one that was, and needs to distinguish the
        reasons: a user told "no default model" deserves to know whether that
        was their data policy or their VRAM, since only one of those is
        something they can act on.

        **The chosen model is never in this list, and that guard is new.** Only
        consent can refuse now; residency merely passes a model over, so on a
        machine where nothing fits the model that does not fit is also the
        model that answers. Listing it as rejected would put two contradictory
        sentences on one row of the picker.
        """
        chosen = self.select_default_model(category=category)
        chosen_id = chosen.id if chosen is not None else None

        rejected: List[tuple[ModelInfo, str]] = []
        for model in self.list_models(category=category, available_only=True):
            if model.id == chosen_id:
                continue
            if not model.selectable_by_default:
                reason = (
                    "data policy is unknown"
                    if not model.data_policy_known
                    else "provider logs and trains on prompts"
                )
                rejected.append((model, reason))
            elif self.model_fits_resident(model) is False:
                rejected.append(
                    (model, "does not fit alongside the embedding model")
                )
        return rejected

    # --- provider read API ---
    def list_providers(self) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        for provider in self.registry.list_model_providers():
            pid = getattr(provider, "provider_id", "?")
            models = self.catalog.filter(provider=pid)
            available = any(m.available for m in models)
            try:
                base = provider.to_dict()
            except Exception:
                base = {
                    "id": pid,
                    "kind": getattr(provider, "kind", ProviderKind.LOCAL_LLM).value,
                }
            base["model_count"] = len(models)
            base["available"] = available
            base["health_status"] = "healthy" if available else "unavailable"
            specs.append(base)
        return specs

    # --- voices / runtimes / personalities / hardware ---
    def list_voices(self) -> List[VoiceInfo]:
        return list(self._voices)

    def list_runtimes(self) -> List[RuntimeInfo]:
        return list(self._runtimes)

    def list_personalities(self) -> List[Dict[str, Any]]:
        return list(self._personalities)

    def hardware_profile(self) -> HardwareProfile:
        return self._hardware

    # --- comprehensive health report ---
    def health_report(self) -> Dict[str, Any]:
        provider_specs = self.list_providers()
        health = self._aggregator.aggregate(
            runtime_status="ready" if self._scanned else "uninitialized",
            provider_specs=provider_specs,
            scanner_health={"providers": {}},
            model_count=self.catalog.count(),
            available_models=self.catalog.available_count(),
            voice_count=len(self._voices),
            runtime_count=len(self._runtimes),
            personality_count=len(self._personalities),
            categories=list(self.catalog.by_category().keys()),
            hardware=self._hardware.to_dict(),
        )
        return health.to_dict()

    # --- events ---
    def _publish_scanned(self) -> None:
        if self._event_bus is None:
            return
        try:
            from core.event_bus import ZaramEvent

            self._event_bus.publish(
                ZaramEvent(
                    source_runtime="providers",
                    event_type="providers.scanned",
                    data={
                        "models": self.catalog.count(),
                        "voices": len(self._voices),
                        "runtimes": len(self._runtimes),
                        "personalities": len(self._personalities),
                    },
                )
            )
        except Exception:  # pragma: no cover - defensive
            return
