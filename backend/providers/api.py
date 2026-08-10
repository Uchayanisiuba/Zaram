"""Read-only HTTP API for the provider layer (v0.6.0).

Exposes the provider layer's discovery results as read-only endpoints. Every handler
delegates to :class:`~providers.manager.ProviderManager` — there is no
discovery logic here, and no download / mutation surface (out of scope).

The Provider Runtime is attached by the application bootstrap via
:func:`set_providers_runtime`; until then the endpoints respond 503 so the
rest of the app is unaffected during early boot.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException

from .manager import ProviderManager
from .runtime import ProvidersRuntime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["providers"])

_PROVIDERS_RUNTIME: Optional[ProvidersRuntime] = None


def set_providers_runtime(runtime: ProvidersRuntime) -> None:
    """Attach the live Provider Runtime (called from the app lifespan)."""
    global _PROVIDERS_RUNTIME
    _PROVIDERS_RUNTIME = runtime


def _manager() -> ProviderManager:
    if _PROVIDERS_RUNTIME is None:
        raise HTTPException(status_code=503, detail="provider layer not initialized")
    return _PROVIDERS_RUNTIME.manager


@router.get("/models")
async def list_models() -> List[dict]:
    manager = _manager()
    await manager.ensure_scanned()
    return [m.to_dict() for m in manager.list_models()]


@router.get("/models/{model_id}")
async def get_model(model_id: str) -> dict:
    manager = _manager()
    await manager.ensure_scanned()
    model = manager.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model.to_dict()


@router.get("/sources")
async def list_providers() -> List[dict]:
    """The provider *sources* (Ollama, an OpenAI-compatible server), not models.

    Named ``/sources`` rather than ``/providers`` only because the router prefix
    is already ``/providers`` and ``/providers/providers`` reads as a mistake.
    """
    manager = _manager()
    await manager.ensure_scanned()
    return manager.list_providers()


@router.get("/voices")
async def list_voices() -> List[dict]:
    manager = _manager()
    await manager.ensure_scanned()
    return [v.to_dict() for v in manager.list_voices()]


@router.get("/runtimes")
async def list_runtimes() -> List[dict]:
    manager = _manager()
    await manager.ensure_scanned()
    return [r.to_dict() for r in manager.list_runtimes()]


@router.get("/personalities")
async def list_personalities() -> List[dict]:
    manager = _manager()
    await manager.ensure_scanned()
    return manager.list_personalities()


@router.get("/hardware")
async def hardware_profile() -> dict:
    manager = _manager()
    await manager.ensure_scanned()
    return manager.hardware_profile().to_dict()


@router.get("/health")
async def health_report() -> dict:
    manager = _manager()
    await manager.ensure_scanned()
    return manager.health_report()
