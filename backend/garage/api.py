"""Read-only HTTP API for the AI Garage (v0.6.0).

Exposes the Garage's discovery results as read-only endpoints. Every handler
delegates to :class:`~garage.manager.GarageManager` — there is no
discovery logic here, and no download / mutation surface (out of scope).

The Garage Runtime is attached by the application bootstrap via
:func:`set_garage_runtime`; until then the endpoints respond 503 so the
rest of the app is unaffected during early boot.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException

from .manager import GarageManager
from .runtime import GarageRuntime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/garage", tags=["garage"])

_GARAGE_RUNTIME: Optional[GarageRuntime] = None


def set_garage_runtime(runtime: GarageRuntime) -> None:
    """Attach the live Garage Runtime (called from the app lifespan)."""
    global _GARAGE_RUNTIME
    _GARAGE_RUNTIME = runtime


def _manager() -> GarageManager:
    if _GARAGE_RUNTIME is None:
        raise HTTPException(status_code=503, detail="AI Garage not initialized")
    return _GARAGE_RUNTIME.manager


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


@router.get("/providers")
async def list_providers() -> List[dict]:
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
