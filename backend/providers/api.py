"""HTTP API for the provider layer.

Mostly read-only: every listing handler delegates to
:class:`~providers.manager.ProviderManager` and there is no discovery logic
here. The one mutation surface is the cloud connection — which provider Zaram
may call and with whose key — and it lives in :mod:`providers.cloud_config`
rather than in this file, so the rules about what may be connected are stated
once and tested without a web server.

The Provider Runtime is attached by the application bootstrap via
:func:`set_providers_runtime`; until then the endpoints respond 503 so the
rest of the app is unaffected during early boot.

**This router went unmounted for its whole life.** It was written, tested and
never included in the FastAPI app, so every path below answered 404 on the
running product while its tests passed — they build their own app and mount the
router themselves. That is the failure this repo keeps recording in a new
place each time: a feature's tests can all pass while the feature cannot
happen. ``backend/tests/test_routes_are_mounted.py`` now asserts against the
real application object, which is the only version of the claim that means
anything.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from . import catalogue, cloud_config
from .cloud_config import CloudConfigError
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


# --------------------------------------------------------------- catalogue


@router.get("/catalogue")
async def provider_catalogue() -> dict:
    """The dated manifest of providers a person can pick from.

    Reads no files and opens no sockets, so it works before discovery has run
    and on a machine with no network at all — which is the point of shipping it
    as a manifest rather than fetching it (rule 7g).

    Not behind ``_manager()``: this is static data, and making a picker
    unavailable because the provider layer is still booting would be a spinner
    over a constant.
    """
    return catalogue.to_payload()


# ---------------------------------------------------------- cloud connection


class CloudConnectRequest(BaseModel):
    """What Settings sends to connect a cloud provider.

    ``provider_id`` is a catalogue entry; ``base_url`` overrides or replaces it
    for a service configured by hand. Both are optional individually and one is
    required — the refusal for neither is written in
    :func:`providers.cloud_config._resolve_endpoint`, in plain language.
    """

    provider_id: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


def _require_browser_origin(client: Optional[str]) -> None:
    """Force a CORS preflight on the routes that change what Zaram may call.

    The local API has no authentication, which is fine for reads on loopback
    and is not fine for a route that decides which third party receives the
    user's prompts. A form post from any web page the user happens to have open
    would otherwise reach this endpoint: CORS does not stop a *simple* request
    being sent, only its response being read, and setting an endpoint is a write
    whose response the attacker does not need.

    Requiring a header that is not on the CORS safelist makes the request
    non-simple, so the browser must preflight it, and the preflight is checked
    against the origin allow-list in ``main.py``. One header, and the hole
    closes.
    """
    if not client:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only callable from Zaram's own interface.",
        )


@router.get("/cloud")
async def cloud_status() -> dict:
    """Every connected cloud provider. Never a key — see `cloud_config`."""
    return cloud_config.status()


@router.post("/cloud")
async def cloud_connect(
    request: CloudConnectRequest,
    x_zaram_client: Optional[str] = Header(default=None),
) -> dict:
    """Point Zaram's cloud path at a provider, effective without a restart.

    Makes no network call, so a 200 here means "configured", never "reachable"
    and never "the key is valid". Saying otherwise would require testing the
    key, and rule 7g puts that behind the user's consent — it happens on the
    first message, where the egress gate can log and confirm it.
    """
    _require_browser_origin(x_zaram_client)
    try:
        return await cloud_config.connect(
            provider_id=request.provider_id,
            base_url=request.base_url,
            api_key=request.api_key,
        )
    except CloudConfigError as exc:
        # 400 with the catalogue's own sentence. The alternative — a generic
        # failure — would leave the user unable to tell "wrong key" from
        # "Zaram cannot speak to this provider at all", which are different
        # problems with different fixes.
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/cloud")
async def cloud_disconnect(
    provider_id: str = "",
    x_zaram_client: Optional[str] = Header(default=None),
) -> dict:
    """Forget one connection. Local answering and every other connection are unaffected.

    ``provider_id`` is required in practice and defaulted here so that a call
    without it fails as a 400 naming the missing argument rather than as a 422
    of framework validation text — the same reason the refusals in
    ``cloud_config`` are sentences.
    """
    _require_browser_origin(x_zaram_client)
    if not provider_id:
        raise HTTPException(
            status_code=400,
            detail="Say which provider to disconnect.",
        )
    return cloud_config.disconnect(provider_id)
