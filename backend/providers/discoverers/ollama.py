"""Ollama discovery adapter for the provider layer (v0.6.0).

This is the *only* module in the provider layer that knows about Ollama. It queries
the Ollama REST API and translates responses into provider-independent
:class:`~providers.contracts.ModelInfo` records. No model name is hardcoded;
everything is learned from ``/api/tags`` and ``/api/show``.

All network access is failure-safe and timeout-bounded so the provider layer never
blocks or crashes when Ollama is not installed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterator, List, Optional

import requests

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

DEFAULT_BASE_URL = "http://127.0.0.1:11434"



#: `num_ctx` as Ollama renders it in `/api/show`.
#:
#: The parameters come back as the Modelfile's own lines rather than as a
#: mapping, so this is text. Anchored per line so a parameter whose *name* ends
#: in `num_ctx` cannot answer for it.
_NUM_CTX = re.compile(r"^num_ctx\s+(\d+)", re.MULTILINE)


def _served_context(parameters: Any) -> Optional[int]:
    """The window this model is configured to load with, or ``None``."""
    if not isinstance(parameters, str):
        return None
    match = _NUM_CTX.search(parameters)
    if not match:
        return None
    value = int(match.group(1))
    return value if value > 0 else None


class OllamaAdapter:
    """Discovers models served by a local Ollama instance."""

    provider_id = "ollama"
    kind = ProviderKind.LOCAL_LLM

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    # --- ModelProviderAdapter surface ---
    async def discover_models(self, *, timeout: float = 2.0) -> List[ModelInfo]:
        try:
            tags = self._get("/api/tags", timeout=timeout) or {}
        except Exception as exc:
            logger.warning(
                "Ollama discovery failed (provider unavailable): %s", exc,
                extra={"provider": self.provider_id},
            )
            return []

        models: List[ModelInfo] = []
        for entry in tags.get("models", []) or []:
            name = entry.get("name") or entry.get("model")
            if not name:
                continue
            models.append(self._to_model(name, entry, timeout=timeout))
        return models

    async def health(self) -> Dict[str, Any]:
        try:
            self._get("/api/tags", timeout=2.0)
            return {"available": True, "provider": self.provider_id, "endpoint": self.base_url}
        except Exception as exc:
            return {"available": False, "provider": self.provider_id, "error": str(exc)}

    def resident_models(self, *, timeout: float = 1.0) -> Optional[Dict[str, int]]:
        """What is loaded in VRAM *right now*, name to bytes.

        `/api/tags` lists what is installed; this asks what is actually
        resident. They are different questions and only the second can answer
        "will this request force a swap".

        Returns ``None`` when Ollama cannot be reached or does not answer —
        never an empty dict. "Nothing is loaded" and "we could not find out" are
        different facts, and a caller that confuses them will announce a swap on
        every message the moment Ollama is briefly busy. Same discipline as
        `vram_bytes`: unknown is a value, not a zero.

        The timeout is deliberately short. This runs before every generation, so
        it is on the critical path of a reply; a slow answer here is worse than
        no answer, because the fallback (say nothing) is correct and cheap.
        """
        try:
            payload = self._get("/api/ps", timeout=timeout)
        except Exception as exc:
            logger.debug("Ollama residency probe failed: %s", exc)
            return None
        if not isinstance(payload, dict):
            return None

        resident: Dict[str, int] = {}
        for entry in payload.get("models", []) or []:
            name = entry.get("name") or entry.get("model")
            if not name:
                continue
            # `size_vram` is what the model occupies on the card. `size` is the
            # total including any CPU-offloaded layers, which is not what a
            # residency decision is about.
            resident[name] = int(entry.get("size_vram") or 0)
        return resident

    def to_dict(self) -> Dict[str, Any]:
        return ProviderSummary(
            id=self.provider_id,
            kind=self.kind,
            endpoint=self.base_url,
            health_status=HealthStatus.UNKNOWN,
        ).to_dict()

    # --- internals ---
    def _get(self, path: str, *, timeout: float) -> Optional[Dict[str, Any]]:
        response = requests.get(f"{self.base_url}{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()

    def _to_model(
        self, name: str, tag: Dict[str, Any], *, timeout: float
    ) -> ModelInfo:
        details = tag.get("details", {}) or {}
        capabilities: set[str] = set()
        context_length: Optional[int] = None
        size = tag.get("size")

        # Enrich with /api/show when reachable (best-effort).
        try:
            show = self._post("/api/show", {"model": name}, timeout=timeout) or {}
            caps = show.get("capabilities") or []
            capabilities.update(str(c).lower() for c in caps)
            model_info = show.get("model_info", {}) or {}
            # **The window it will actually serve, not the one the weights
            # allow, and the two differ by more than a factor of two.**
            #
            # This read `model_info["context_length"]`, which is the
            # architecture maximum: `qwen3-14b-16k` reports **40,960** there
            # and loads with **16,384**; a model with no `num_ctx` at all
            # reports 262,144 and is served Ollama's 4,096 default.
            # `core/context_budget.py` exists because sizing a prompt against
            # that number overflows the context on almost every real request,
            # and its docstring says so at length -- while this discoverer
            # recorded exactly the number it warns about, from the same
            # `/api/show` reply that carries the right one.
            #
            # It was read by nothing, which is why it never showed up as a
            # wrong answer. That is not a reason to leave it: a wrong value in
            # a field named `context_length` is a trap primed for whoever uses
            # it next, and the ranking below is now that caller.
            #
            # `None` when there is no explicit `num_ctx`. Ollama's default is
            # what such a model gets, and `budget_for` already falls back to it
            # deliberately -- but the default is configurable, so asserting it
            # here would be a guess about the server dressed as a measurement.
            # Unknown is a third answer.
            context_length = _served_context(show.get("parameters"))
            q = (
                show.get("details", {}).get("quantization_level")
                or model_info.get("quantization_level")
            )
            if q:
                details = {**details, "quantization_level": q}
        except Exception as exc:
            logger.debug(
                "Ollama /api/show failed for %s: %s", name, exc,
                extra={"provider": self.provider_id},
            )

        is_embedding = "embedding" in capabilities
        category = ModelCategory.EMBEDDING if is_embedding else ModelCategory.LLM

        quantization = details.get("quantization_level")
        parameter_size = details.get("parameter_size")

        return ModelInfo(
            id=f"{self.provider_id}:{name}",
            display_name=name,
            provider=self.provider_id,
            provider_kind=self.kind,
            category=category,
            size_bytes=size if isinstance(size, int) else None,
            context_length=context_length,
            quantization=quantization if isinstance(quantization, str) else None,
            capabilities=capabilities,
            supports_vision="vision" in capabilities,
            supports_embedding="embedding" in capabilities,
            supports_tools="tools" in capabilities,
            recommended_use=(
                "semantic search / vector embeddings"
                if is_embedding
                else                 "local chat, reasoning and tool use"
            ),
            memory_requirement_bytes=size if isinstance(size, int) else None,
            locality=CapabilityLocality.LOCAL,
            available=True,
            health_status=HealthStatus.HEALTHY,
            endpoint=self.base_url,
            # Ollama runs on the user's own machine. This is the one case where
            # the guarantee is structural rather than contractual: there is no
            # provider to trust, because inference never leaves the device.
            data_policy=DataPolicy.NEVER_LEAVES_DEVICE,
            specialisation=specialisation_from_name(name),
            metadata={
                "parameter_size": parameter_size,
                "family": details.get("family"),
                "format": details.get("format"),
            },
        )

    def pull_model(
        self, name: str, *, timeout: float = 30.0
    ) -> Iterator[Dict[str, Any]]:
        """Ask Ollama to fetch ``name``, yielding its progress lines as they land.

        `/api/pull` answers with NDJSON: a line per state change, each one
        carrying `status`, and the ones that matter carrying `total` and
        `completed` in bytes. They are yielded raw — naming the stages in a
        person's words is a decision about what to *say*, which belongs where
        the sentence is written and not in the adapter that reads the wire.

        **The transfer is Ollama's, not Zaram's.** This request goes to
        127.0.0.1 and carries a model name; the gigabytes come from the
        registry to Ollama, over a socket this process does not own and cannot
        gate. That is exactly why the caller writes the egress entry *before*
        starting: a download recorded only on success is a log that misses
        every interrupted one.

        ``timeout`` is the read timeout between lines, not for the pull. A
        multi-gigabyte fetch takes minutes and a deadline on the whole thing
        would cancel a download that was working perfectly.
        """
        with requests.post(
            f"{self.base_url}/api/pull",
            json={"model": name, "stream": True},
            stream=True,
            timeout=timeout,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    # One unreadable line is not a failed download. The stream
                    # carries its own outcome — `success`, or an `error` field
                    # — and dropping a line loses a progress tick at worst.
                    logger.debug("unreadable line from /api/pull: %r", line)
                    continue
                if isinstance(event, dict):
                    yield event

    def _post(
        self, path: str, payload: Dict[str, Any], *, timeout: float
    ) -> Optional[Dict[str, Any]]:
        response = requests.post(f"{self.base_url}{path}", json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
