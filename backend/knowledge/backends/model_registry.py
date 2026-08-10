# backend/knowledge/backends/model_registry.py
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelInfo:
    id: str
    name: str
    size: str | None = None
    modified_at: str | None = None
    digest: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ModelRegistry:
    """Background updater for Ollama model registry.

    Polls the Ollama /api/tags endpoint every 24 hours to refresh
    the list of available models without downloading anything.
    """

    def __init__(self, base_url: str = "http://localhost:11434", refresh_interval_hours: int = 24):
        self._base_url = base_url.rstrip("/")
        self._refresh_interval = refresh_interval_hours * 3600
        self._models: dict[str, ModelInfo] = {}
        self._last_refresh = 0.0
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def start(self) -> None:
        """Start the background refresh loop."""
        self._schedule_next()

    def stop(self) -> None:
        """Stop the background refresh loop."""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def get_models(self) -> list[ModelInfo]:
        """Get current model registry, refreshing if stale."""
        with self._lock:
            if time.time() - self._last_refresh > self._refresh_interval:
                self._refresh()
            return list(self._models.values())

    def get_model(self, model_id: str) -> ModelInfo | None:
        return self._models.get(model_id)

    def _schedule_next(self) -> None:
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(self._refresh_interval, self._refresh)
        self._timer.daemon = True
        self._timer.start()

    def _refresh(self) -> None:
        # Through the gate. Normally this is Ollama on loopback, which the gate
        # classifies as local and passes straight through unlogged — but the
        # base URL is configurable, and if it is ever pointed off the machine
        # that must be governed and recorded like anything else. Routing it
        # here means the caller does not have to know which case it is in.
        try:
            from core.egress import get_gate

            data = __import__("json").loads(
                get_gate().request(
                    f"{self._base_url}/api/tags", timeout=10, source="model_registry"
                )
            )
        except Exception:
            return

        models: dict[str, ModelInfo] = {}
        for m in (data.get("models") or []):
            model_id = m.get("name", "")
            if not model_id:
                continue
            models[model_id] = ModelInfo(
                id=model_id,
                name=m.get("name", model_id),
                size=str(m.get("size")) if m.get("size") else None,
                modified_at=m.get("modified_at"),
                digest=m.get("digest"),
                details=m.get("details", {}),
            )

        with self._lock:
            self._models = models
            self._last_refresh = time.time()
        self._schedule_next()
