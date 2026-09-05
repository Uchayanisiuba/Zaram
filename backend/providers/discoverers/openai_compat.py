"""OpenAI-compatible discovery adapter for the provider layer (v0.6.0).

Many local AI servers (LM Studio, Ollama's OpenAI mode, LocalAI, ...) and
cloud endpoints expose the OpenAI ``/v1/models`` contract. This single
adapter covers all of them; the only difference is the base URL. LM Studio
is therefore just this adapter pointed at its default local port.

Like every provider discoverer, this module is the *only* place that knows the
OpenAI wire format, and it never hardcodes a model name.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.error
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from ..contracts import (
    CapabilityLocality,
    DataPolicy,
    HealthStatus,
    ModelCategory,
    ModelInfo,
    ProviderKind,
    ProviderSummary,
    specialisation_from_name,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:1234"
LM_STUDIO_BASE_URL = "http://127.0.0.1:1234"
OPENAI_BASE_URL = "https://api.openai.com"

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]", "0.0.0.0"}


def _policy_for(base_url: str) -> Optional[DataPolicy]:
    """Infer a data policy from the URL, or decline to.

    This adapter is the one that genuinely cuts both ways — the same class is
    LM Studio on loopback and api.openai.com behind a bearer token — so the
    policy is read from the destination rather than from whichever caller
    remembered to pass it. Same reasoning as ``_get`` deferring to the egress
    gate a few lines down.

    Loopback is the only case that can be inferred, and only because it is
    structural: a request to 127.0.0.1 cannot leave. Everything else returns
    ``None``. That is not a gap to fill in later with a sensible guess — the
    terms under which a remote provider handles prompts are not derivable from
    its hostname, and a wrong guess here is a privacy claim the user acts on.
    Whoever registers a cloud provider passes ``data_policy`` explicitly.
    """
    host = urlparse(base_url).hostname
    if host and host.lower() in _LOOPBACK_HOSTS:
        return DataPolicy.NEVER_LEAVES_DEVICE
    return None


def _strip_version(base_url: str) -> str:
    """The API root without a trailing `/v1`, however the user wrote it."""
    trimmed = (base_url or "").strip().rstrip("/")
    return trimmed[: -len("/v1")] if trimmed.endswith("/v1") else trimmed


#: A server saying, with a status code, that it is holding nothing.
#:
#: TabbyAPI's answer to `/v1/model` when no model is loaded is 503 with
#: ``{"detail": "No models are currently loaded."}``. Matched on the sentence
#: as well as the status, because 503 on its own also means "busy, try later" —
#: and a busy server is exactly the one most likely to be holding the card.
#: Reading that as an empty card is the error that runs in the dangerous
#: direction. See `OpenAICompatibleAdapter.resident_models`.
_NOTHING_LOADED = re.compile(r"no models? (?:are |is )?(?:currently )?loaded", re.I)


def _says_nothing_is_loaded(exc: "urllib.error.HTTPError") -> bool:
    """Whether an error response is the server reporting an empty card.

    Reads the body at most once — an `HTTPError` is a one-shot stream, so a
    second reader would get nothing — and answers False on anything it cannot
    read, which leaves residency unknown rather than guessing empty.
    """
    if exc.code != 503:
        return False
    try:
        body = exc.read().decode("utf-8", "replace")
    except Exception:
        return False
    return bool(_NOTHING_LOADED.search(body))


class OpenAICompatibleAdapter:
    """Discovers models from any OpenAI-compatible ``/v1/models`` endpoint."""

    def __init__(
        self,
        provider_id: str = "openai_compatible",
        *,
        base_url: str = DEFAULT_BASE_URL,
        kind: ProviderKind = ProviderKind.LOCAL_AI_SERVER,
        api_key: Optional[str] = None,
        data_policy: Optional[DataPolicy] = None,
    ) -> None:
        self.provider_id = provider_id
        self.kind = kind
        # `/v1` is stripped here and re-added by each path below, so a base URL
        # given either way reaches the same place. The engine already accepts
        # both — its docstring says so, because both are what providers print
        # in their own dashboards — and the two halves of the cloud path
        # disagreeing about one env var is how `ZARAM_OPENAI_ENDPOINT` ending
        # in `/v1` produced a working chat and a discovery that asked for
        # `/v1/v1/models`. Discovery then returned nothing, no cloud model was
        # known, and routing sent every message local without saying why.
        self.base_url = _strip_version(base_url)
        self._api_key = api_key
        self._data_policy = data_policy if data_policy is not None else _policy_for(base_url)

    # --- ModelProviderAdapter surface ---
    async def discover_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        try:
            payload = await asyncio.to_thread(self._get, "/v1/models", timeout=timeout) or {}
        except Exception as exc:
            logger.warning(
                "%s discovery failed (provider unavailable): %s",
                self.provider_id,
                exc,
                extra={"provider": self.provider_id},
            )
            return []

        models: List[ModelInfo] = []
        for entry in payload.get("data", []) or []:
            model_id = entry.get("id")
            if not model_id:
                continue
            models.append(self._to_model(model_id, entry))
        return models

    async def health(self) -> Dict[str, Any]:
        try:
            await asyncio.to_thread(self._get, "/v1/models", timeout=2.0)
            return {"available": True, "provider": self.provider_id, "endpoint": self.base_url}
        except Exception as exc:
            return {"available": False, "provider": self.provider_id, "error": str(exc)}

    def resident_models(
        self, *, timeout: float = 1.0
    ) -> Optional[Dict[str, Optional[int]]]:
        """What this server holds in VRAM right now, or ``None`` for unknown.

        A second local AI server is the reason this exists.
        `ProviderManager._resident_models` used to return the first adapter
        that answered, so on a machine running Ollama *and* something else the
        second one was invisible. Measured 28 August 2026 on the 12 GB card:
        Ollama answered `{}` first while TabbyAPI held 9.5 GB, and every fit
        decision downstream was taken as though the card were empty.

        **The size is not knowable here, and it is reported as unknown rather
        than as zero.** `/v1/model` returns the loaded model's id, its context
        and cache settings and its chat template — no memory figure, because
        the OpenAI contract has no field for one. A `0` would be a measurement
        meaning "holds nothing", which is the false zero `vram_bytes` already
        cost this codebase once; the caller reaches for a real measurement
        instead.

        Three outcomes, and the middle one is why this is not one `except`
        around everything:

        - a **cloud** provider holds no VRAM on this machine, so it answers
          ``{}`` without a request. Asking would also put a network call on
          the reply path for an answer that is known in advance.
        - a **refused connection** on a local port is a fact rather than a
          failure: nothing is listening, so that server is holding nothing.
          ``{}``. This matters because the LM Studio adapter is registered
          whether or not anything is running behind it, and treating an absent
          server as unknowable would silence the swap indicator on every
          Ollama-only machine.
        - anything else — a timeout, an HTTP error, unparseable JSON — is
          "could not find out", which is ``None``. A server that is up but
          slow to answer may well be the one holding the card, and being busy
          is exactly when that is most likely.
        """
        if self.kind is ProviderKind.CLOUD_API:
            return {}
        try:
            payload = self._get("/v1/model", timeout=timeout)
        except urllib.error.HTTPError as exc:
            # **An error status is two different answers, and reading it as one
            # is what put "Warming up" under every reply.**
            #
            # TabbyAPI, up with nothing loaded, answers `/v1/model` with
            # **503 and `{"detail": "No models are currently loaded."}`** —
            # measured against the running server on 127.0.0.1:1234, 3
            # September 2026. That is a well-formed statement that the card is
            # empty: the same fact the `not model_id` branch below already
            # handles, arriving with a status code instead of a null field.
            #
            # Treated as "cannot read", it made residency unknown for the whole
            # machine — `ProviderManager._resident_models` merges every local
            # provider and one unknown makes the merge unknown — so
            # `swap_preflight` returned None, no `model_load` event was sent,
            # and the interface's 2.5-second timer guessed a cold model on
            # every single message. The `resident` event that exists to cancel
            # that guess was never emitted at all. The LM Studio adapter is
            # registered at that address on every machine, so an idle
            # OpenAI-compatible server anywhere on the box was enough.
            #
            # Anything else stays unknown, and that asymmetry is deliberate:
            # the error of reporting an empty card is the dangerous one — an
            # unseen tenant makes a cold start look like it fits.
            if _says_nothing_is_loaded(exc):
                return {}
            logger.debug("%s residency probe rejected: %s", self.provider_id, exc)
            return None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ConnectionRefusedError):
                return {}
            logger.debug("%s residency probe failed: %s", self.provider_id, exc)
            return None
        except Exception as exc:
            logger.debug("%s residency probe failed: %s", self.provider_id, exc)
            return None

        if not isinstance(payload, dict):
            return None
        model_id = payload.get("id")
        if not model_id:
            # A well-formed answer naming no model: the server is up with
            # nothing loaded. That is a fact, not the absence of one.
            return {}
        return {str(model_id): None}

    def to_dict(self) -> Dict[str, Any]:
        return ProviderSummary(
            id=self.provider_id,
            kind=self.kind,
            endpoint=self.base_url,
            health_status=HealthStatus.UNKNOWN,
        ).to_dict()

    # --- internals ---
    def _get(self, path: str, *, timeout: float) -> Optional[Dict[str, Any]]:
        # Synchronous, and called from a thread by both callers above. That is
        # not tidiness — it is the M10 freeze, which cost a session to find.
        #
        # A host whose policy is *ask* blocks inside the gate on a
        # `threading.Event` until a browser answers the confirmation. Run that
        # on the event loop and the backend stops serving, `/egress/pending`
        # can never be fetched, the dialog can never appear, and the only
        # reachable outcome is a timeout. Discovery against a cloud provider is
        # exactly that shape, and it became reachable the moment the per-host
        # policy was something a user could set to *ask* from Settings.
        #
        # Through the gate. This discoverer is the one that genuinely cuts both
        # ways: pointed at LM Studio it is loopback and passes through unlogged,
        # pointed at api.openai.com it is egress carrying a bearer token. The
        # gate decides from the URL, so neither case depends on the caller
        # remembering which it is.
        from core.egress import get_gate

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return json.loads(
            get_gate().request(
                f"{self.base_url}{path}",
                timeout=timeout,
                headers=headers,
                source="providers.openai_compat",
            )
        )

    def _to_model(self, model_id: str, entry: Dict[str, Any]) -> ModelInfo:
        # OpenAI's /v1/models exposes only an id + ownership; deeper metadata
        # (size, context, quantization, capabilities) is not part of the spec,
        # so we record what we know and leave the rest unknown.
        owned_by = entry.get("owned_by", "unknown")
        # The short name is what `specialisation_from_name` reads, and it is the
        # wrong thing to *show*. An aggregator's ids are `vendor/model` —
        # `anthropic/claude-sonnet-4.5` — and dropping the vendor gives a list
        # where two different models can appear under one label, on the screen
        # whose whole job is choosing between them. It is also the name the
        # provider itself uses, so it is what a user recognises from anywhere
        # else they have seen it.
        #
        # Safe to widen: the cloud wire name comes from `resolve_for_model`,
        # which partitions the catalogue id and never reads this field.
        name = model_id.split("/")[-1]
        return ModelInfo(
            id=f"{self.provider_id}:{model_id}",
            display_name=model_id,
            provider=self.provider_id,
            provider_kind=self.kind,
            category=ModelCategory.LLM,
            version=entry.get("version", ""),
            supports_tools=True,  # OpenAI-compatible servers generally support tools
            locality=(
                CapabilityLocality.CLOUD
                if self.kind is ProviderKind.CLOUD_API
                else CapabilityLocality.LOCAL
            ),
            available=True,
            health_status=HealthStatus.HEALTHY,
            endpoint=self.base_url,
            data_policy=self._data_policy,
            specialisation=specialisation_from_name(name),
            metadata={"owned_by": owned_by, "raw_id": model_id},
        )


class LMStudioAdapter(OpenAICompatibleAdapter):
    """Whatever OpenAI-compatible server is on 127.0.0.1:1234, if anything.

    **The class name and the `lm_studio` provider id are historical, and
    neither is a claim about which program is answering.** Nothing in the
    `/v1/models` contract identifies the server, and this port is served by LM
    Studio, TabbyAPI, LocalAI, vLLM, llama.cpp and Jan alike. The catalogue
    entry carries the reasoning and the user-facing string, which names the
    port instead of guessing the product; see `providers/catalogue.py`.

    Nothing here may infer a product name from a response either. `owned_by`
    is set by the server operator and is not an identity.
    """

    def __init__(self, base_url: str = LM_STUDIO_BASE_URL) -> None:
        super().__init__(
            provider_id="lm_studio",
            base_url=base_url,
            kind=ProviderKind.LOCAL_AI_SERVER,
        )
