"""Runtime source adapter for the AI Garage (v0.6.0).

The Garage learns which Zaram runtimes are installed by reading the Kernel
RuntimeRegistry through its public surface (``list_capabilities`` and
``get_system_health``). It never imports a concrete runtime.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..contracts import RuntimeInfo

logger = logging.getLogger(__name__)


class RegistryRuntimeSource:
    """Adapts a Kernel ``RuntimeRegistry`` (or any compatible object)."""

    def __init__(
        self,
        registry: Any,
        *,
        version_lookup: Any = None,
    ) -> None:
        self._registry = registry
        # Optional callable(runtime_id) -> version str for richer metadata.
        self._version_lookup = version_lookup

    def snapshot_runtimes(self) -> List[RuntimeInfo]:
        try:
            capabilities = self._registry.list_capabilities()
        except Exception as exc:
            logger.warning("Runtime discovery failed: %s", exc)
            return []

        try:
            health = self._registry.get_system_health() or {}
        except Exception:
            health = {}

        by_runtime: Dict[str, List[str]] = {}
        version_by_runtime: Dict[str, str] = {}
        for cap in capabilities:
            rid = getattr(cap, "runtime_id", None) or "unknown"
            by_runtime.setdefault(rid, []).append(getattr(cap, "id", ""))
            if getattr(cap, "version", None):
                version_by_runtime.setdefault(rid, cap.version)

        infos: List[RuntimeInfo] = []
        for rid, caps in by_runtime.items():
            state = str(health.get(rid, "unknown"))
            version = version_by_runtime.get(rid, "")
            if self._version_lookup is not None and not version:
                try:
                    version = self._version_lookup(rid) or ""
                except Exception:
                    version = ""
            infos.append(
                RuntimeInfo(
                    runtime_id=rid,
                    version=version,
                    state=state,
                    healthy=(state == "ready"),
                    capabilities=list(caps),
                )
            )
        return infos
