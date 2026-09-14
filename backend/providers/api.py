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

import json
import logging
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from . import catalogue, cloud_config, pairing
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


def _payload(manager: ProviderManager, model) -> dict:
    """A model as the interface needs it: the record, plus whether it fits.

    **The fit verdict cannot live on `ModelInfo.to_dict()`**, and that is why
    it is added here rather than there. Fitting is a question about *this
    machine* — the card's capacity, minus the embedder, minus the KV-cache
    reserve — and a `ModelInfo` is a record of what a provider offers. Putting
    a machine-dependent answer on a provider record would make the same model
    serialise differently on two computers, which is the kind of quiet
    coupling that is discovered a year later.

    So `ProviderManager` answers it, at the one place a model is handed to the
    interface.

    Three values, never two. ``None`` means the question could not be
    answered — no accelerator, unreadable VRAM (Metal and DirectML report
    nothing), or a model that does not state its size — and it must render as
    *"cannot tell"* rather than as a quiet yes. `model_fits_resident` never
    promotes ``None`` to ``True`` and neither may the UI: a false reassurance
    here is worse than silence, because the user acts on it.

    `resident_budget_bytes` rides along on every row, redundantly. One number
    repeated is cheaper than a second round trip, and the picker needs it to
    say something actionable — *"21.6 GB, and this machine has 11.7 GB for a
    chat model"* is a sentence a person can act on; *"does not fit"* is not.

    **`resident_cost_bytes` is the number that sentence must use, and that is
    why it is here.** The picker compared `size_bytes` — on-disk weights —
    against the budget, which was correct only while the two sides were the
    same quantity. Since the KV allowance moved onto the model they are not: a
    model can be graded as not fitting while its *weights* are comfortably
    under the budget, and the row would then read "10.0 GB, and this machine
    has about 11.7 GB" beside a verdict of too large. The interface must not
    contradict itself on the one indicator whose job is to be trusted.
    """
    payload = model.to_dict()
    payload["fits_resident"] = manager.model_fits_resident(model)
    payload["resident_budget_bytes"] = manager.resident_budget_bytes()
    payload["resident_cost_bytes"] = manager.resident_cost_bytes(model)
    return payload


@router.get("/models")
async def list_models() -> List[dict]:
    manager = _manager()
    await manager.ensure_scanned()
    return [_payload(manager, m) for m in manager.list_models()]


@router.post("/rescan")
async def rescan() -> List[dict]:
    """Run discovery again and return what is there now.

    **Discovery ran once per process and never again.** `ensure_scanned` sets a
    flag on its first call, so every listing after that reads a catalogue
    frozen at boot — and a local inference server started *after* Zaram was
    invisible until Zaram itself was restarted. Measured 30 August 2026:
    TabbyAPI serving `Qwen3.8-27B-exl3-2.20bpw` on 127.0.0.1:1234, confirmed
    answering, while `/providers/models` returned only the two Ollama models
    found at boot. The user had installed nothing wrong and had no way to tell
    the difference between "Zaram cannot see my model" and "my model is gone".

    `CLAUDE.md` already specified this and named it: *"Re-runnable from
    Settings as **re-scan**, not as a replayed wizard: it re-detects and shows
    a diff, changing nothing without confirmation."* This is the re-detect
    half. It changes no setting — a model the user had pinned stays pinned,
    including one that has since disappeared, because silently unpinning a
    choice somebody made is worse than showing it as missing.

    **A POST rather than a scan on every GET.** Discovery asks every connected
    cloud provider what it offers, so it is egress and it is logged; putting it
    behind a listing that the interface polls would send a request to every
    provider on a timer that nobody asked for. Rule 7g's posture applied to
    the smaller case: refreshing from the network is an explicit action.
    """
    manager = _manager()
    await manager.refresh()
    return [_payload(manager, m) for m in manager.list_models()]


@router.get("/models/{model_id}")
async def get_model(model_id: str) -> dict:
    manager = _manager()
    await manager.ensure_scanned()
    model = manager.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return _payload(manager, model)


@router.post("/pull")
async def pull_recommended_model():
    """Fetch the model the first-run screen offered, streaming its progress.

    **Which model is decided here, not sent.** `/readiness` computed the offer
    from the manifest and the measured budget; this recomputes it the same way,
    so the thing downloaded is the thing the user was quoted a price for. A
    name in a request body would be a second source of truth for the same
    question, and the first time they disagreed the user would be charged
    gigabytes for a model nobody offered.

    NDJSON, on the same pattern as `/ingest` and `/chat`, because the frontend
    already parses it. The egress entry is written by `stream_pull` before the
    first byte moves — see that module for why it is recorded rather than
    gated.

    The budget is read from the manager only if discovery has already run.
    Forcing a scan here would send a request to every connected provider as a
    side effect of pressing *download*, which is the shape of the thing rule 7g
    refuses.
    """
    from core.egress import get_gate

    from .discoverers.ollama import OllamaAdapter
    from .pull import PullUnavailable, stream_pull

    budget_bytes = None
    if _PROVIDERS_RUNTIME is not None:
        try:
            budget_bytes = _PROVIDERS_RUNTIME.manager.resident_budget_bytes()
        except Exception:
            logger.debug("pull: could not measure the resident budget", exc_info=True)

    try:
        log = get_gate().log
    except Exception:
        # A pull with no log is not a pull. Rule 3 is not conditional on the
        # gate having been installed, and a download that could not be recorded
        # must not happen quietly instead.
        logger.warning("pull refused: the egress log is not available")
        raise HTTPException(status_code=503, detail="the egress log is not ready")

    def _stream():
        try:
            for event in stream_pull(
                budget_bytes=budget_bytes, adapter=OllamaAdapter(), log=log
            ):
                yield json.dumps(event) + "\n"
        except PullUnavailable as exc:
            # The body has already started, so this cannot become a status
            # code. It arrives as the stream's own terminal event, which is
            # what the screen renders either way.
            yield json.dumps({"error": str(exc)}) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


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


# ---------------------------------------------------------------- the card

#: The models runtime, for the one sentence it owns about the card: why the
#: preload did not happen. Set by `main.py` after boot, beside
#: `set_providers_runtime`; ``None`` until then, which reads as no sentence.
_models_runtime: Any = None


def set_models_runtime(runtime: Any) -> None:
    global _models_runtime
    _models_runtime = runtime


def _resident_payload(manager: ProviderManager) -> dict:
    """What is on the card now, in the shape Settings draws.

    `resident` is ``None`` when residency cannot be established — a local
    server that cannot say what it holds makes the whole answer unknown, and
    the interface must show *unknown* rather than an empty list that reads as
    "nothing loaded". `free_vram_bytes` is the driver's answer for the card as
    a whole, beside every other process; ``None`` where there is no NVIDIA
    driver to ask.

    `preload_skipped_because` is the models runtime's own sentence for why it
    did not warm a model at boot — the preference, another server, or the
    space that was free at the time. Empty when it did, or was never asked.
    """
    from .discoverers.hardware import vram_free_bytes

    resident = manager.resident_now()
    rows = None
    if resident is not None:
        rows = [{"name": name, "bytes": size} for name, size in sorted(resident.items())]

    skipped = getattr(_models_runtime, "preload_skipped_because", "") or ""

    return {
        "resident": rows,
        "free_vram_bytes": vram_free_bytes(),
        "preload_skipped_because": skipped,
    }


@router.get("/resident")
async def resident_models() -> dict:
    """What is holding the card, and how much of it is free right now."""
    manager = _manager()
    await manager.ensure_scanned()
    return _resident_payload(manager)


@router.post("/release")
async def release_resident() -> dict:
    """Give the card back.

    The user's "I am about to open Unreal" action. Unloads every model every
    local server can unload, reports the ones it cannot, and answers with the
    same payload `GET /resident` does so the screen redraws from one shape.
    Loopback only, never egress; a person pressed it, so it needs no confirm
    beyond the button.
    """
    manager = _manager()
    await manager.ensure_scanned()
    outcome = manager.release_resident()
    return {**_resident_payload(manager), "outcome": outcome}


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


@router.get("/cloud/{provider_id}/pairing")
async def cloud_pairing(provider_id: str) -> dict:
    """What one tap would assign, for a connected provider, from what its
    key can actually see. See `pairing`.

    Discovery runs here if it has not, which is a request to the provider
    the person already connected — the same consent as any model listing.
    """
    if provider_id not in cloud_config.connections():
        raise HTTPException(status_code=404, detail=f"{provider_id} is not connected.")
    manager = _manager()
    await manager.ensure_scanned()
    seen = [m.id for m in manager.list_models(provider=provider_id)]
    picks = pairing.recommend(provider_id, seen)
    entry = catalogue.get(provider_id)
    return {
        "provider_id": provider_id,
        "display_name": entry.display_name if entry else provider_id,
        "generated": pairing.GENERATED,
        "seen": len(seen),
        "picks": picks,
    }


class PairingApply(BaseModel):
    #: The picks as returned by GET, so what is written is what was shown.
    picks: Dict[str, Dict[str, str]]


@router.post("/cloud/{provider_id}/pairing")
async def cloud_pairing_apply(provider_id: str, body: PairingApply) -> dict:
    """Write the picks into the same fields the Advanced picker writes.

    Only models the key can see are accepted, checked again here rather
    than trusted from the request — the list shown may be a minute old.
    """
    from core.user_settings import get_user_settings

    if provider_id not in cloud_config.connections():
        raise HTTPException(status_code=404, detail=f"{provider_id} is not connected.")
    manager = _manager()
    await manager.ensure_scanned()
    seen = {m.id for m in manager.list_models(provider=provider_id)}
    picks = {
        slot: pick
        for slot, pick in body.picks.items()
        if slot in pairing.SLOTS and isinstance(pick, dict) and pick.get("model") in seen
    }
    if not picks:
        raise HTTPException(status_code=400, detail="None of those models is one this key can see.")
    return {"assigned": pairing.apply(get_user_settings(), picks), "picks": picks}


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
        status = await cloud_config.connect(
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
    _consent_to_the_host_just_connected(status, request.provider_id, request.base_url)
    return status


def _consent_to_the_host_just_connected(
    status: dict, provider_id: Optional[str], base_url: Optional[str]
) -> None:
    """Rule 7j, as written: *"connecting a cloud provider — choosing it,
    pasting a key for it, pressing Connect — is rule 5's explicit per-item
    decision about that provider's host."*

    Until 14 September 2026 nothing did this. A key pasted on first run
    stored fine, and the first question was refused by the per-host policy —
    correctly, by default-deny — with the remedy an amber line in Settings
    that the first-run screen never shows. The maintainer's report was the
    one the rule predicts: *"I copy the key and it doesn't work."*

    Only for the connection just made, only the ``prompt`` class (an image
    is its own consent, asked once on its own), and only where the person
    has said nothing about the host yet — a host they deliberately denied
    stays denied, because a key is not a louder opinion than a rule. A
    loopback server needs no rule and gets none.
    """
    from core.egress import DataClass, Mode, get_gate

    wanted = provider_id or (urlparse((base_url or "").strip()).hostname or "custom")
    connection = next(
        (c for c in status.get("connections", []) if c.get("provider_id") == wanted), None
    )
    host = (urlparse(str(connection.get("base_url", ""))).hostname or "").lower() if connection else ""
    if not host or host in {"127.0.0.1", "localhost", "::1"}:
        return
    try:
        policy = get_gate().policy
        if policy.has_rule(host, DataClass.PROMPT):
            return
        policy.set(host, Mode.ALLOW, DataClass.PROMPT)
        logger.info("connected %s: %s may now receive prompts (rule 7j)", wanted, host)
    except Exception as exc:  # noqa: BLE001 - the key is stored; the rule is the courtesy
        logger.warning("could not record consent for %s: %s", host, exc)


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
