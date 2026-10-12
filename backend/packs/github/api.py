"""The routes the Settings screen uses to connect GitHub.

The window never sees the token. It asks for a code, shows it, opens GitHub, and
polls; the backend holds the device code, stores the token sealed, and answers
"connected as <login>". Nothing here returns a credential, and nothing here pushes
or opens anything -- the model's tools do that, one confirmation at a time.

**Pressing Connect is the decision about github.com and api.github.com**
(rule 7j: connecting a destination deliberately *is* the per-item consent). It sets
those two hosts to allowed for ordinary requests, unless the person has blocked one
on purpose, in which case it says so instead of overriding them. It does **not**
allow pushing a repository: that is its own data class and asks once, by name, the
first time (`DataClass.REPO` in `core/egress/policy.py`).
"""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import app, vault
from .client import GitHub, GitHubError

#: Device codes in flight, by an opaque id the window holds. The code itself never
#: leaves this process. Bounded and short-lived: a flow is fifteen minutes.
_FLOWS: Dict[str, Dict[str, Any]] = {}
_MAX_FLOWS = 8


class PollRequest(BaseModel):
    flow: str


def _allow_hosts() -> Optional[str]:
    """Allow the two hosts for ordinary requests, or say why that is not possible."""
    from core.egress import Mode, get_gate

    policy = get_gate().policy
    if policy.kill_switch():
        return "The kill switch is on, so nothing can be sent. Turn it off in Activity first."
    for host in app.HOSTS:
        if policy.has_rule(host) and policy.decide(host).mode is Mode.DENY:
            return f"{host} is blocked in Activity. Allow it there first; Zaram will not override a block you set."
    for host in app.HOSTS:
        if not policy.has_rule(host):
            policy.set(host, Mode.ALLOW)
    return None


def _forget_old(now: float) -> None:
    for key in [k for k, v in _FLOWS.items() if v["expires"] <= now]:
        _FLOWS.pop(key, None)
    while len(_FLOWS) > _MAX_FLOWS:
        _FLOWS.pop(next(iter(_FLOWS)))


def _status() -> Dict[str, Any]:
    stored = vault.load()
    return {
        "configured": app.configured(),
        "connected": bool(stored and not stored.expired),
        "expired": bool(stored and stored.expired),
        "login": stored.login if stored else "",
        "expires_at": stored.expires_at if stored else None,
        "sealed": vault.sealed_on_disk(),
        "install_url": app.install_url(),
        "manage_url": app.manage_url(),
    }


def build_router(client: Optional[GitHub] = None) -> APIRouter:
    router = APIRouter(prefix="/github", tags=["github"])
    github = client or GitHub()

    @router.get("/status")
    async def status():
        return _status()

    @router.post("/connect")
    async def connect():
        if not app.configured():
            raise HTTPException(status_code=503, detail="The GitHub app is not registered on this build.")
        blocked = _allow_hosts()
        if blocked:
            raise HTTPException(status_code=409, detail=blocked)
        try:
            code = await asyncio.to_thread(github.start_device_flow)
        except GitHubError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        now = time.time()
        _forget_old(now)
        flow = secrets.token_urlsafe(16)
        _FLOWS[flow] = {
            "device_code": code.device_code,
            "interval": code.interval,
            "expires": now + code.expires_in,
        }
        return {
            "flow": flow,
            "user_code": code.user_code,
            "verification_uri": code.verification_uri,
            "interval": code.interval,
            "expires_in": code.expires_in,
        }

    @router.post("/connect/poll")
    async def poll(body: PollRequest):
        record = _FLOWS.get(body.flow)
        if record is None or record["expires"] <= time.time():
            _FLOWS.pop(body.flow, None)
            return {"state": "expired", "detail": "That sign-in timed out. Press Connect to start again."}
        try:
            result = await asyncio.to_thread(github.poll_device_flow, record["device_code"])
        except GitHubError as error:
            return {"state": "error", "detail": str(error)}
        state = result["state"]
        if state == "slow_down":
            record["interval"] = record["interval"] + 5
            return {"state": "pending", "interval": record["interval"]}
        if state != "done":
            if state in ("expired", "denied", "error"):
                _FLOWS.pop(body.flow, None)
            return {"state": state, "detail": result.get("detail", ""), "interval": record["interval"]}
        try:
            who = await asyncio.to_thread(github.whoami, result["token"])
        except GitHubError as error:
            return {"state": "error", "detail": str(error)}
        vault.save(
            vault.Connection(
                login=who["login"],
                user_id=who["id"],
                token=result["token"],
                connected_at=time.time(),
                expires_at=result.get("expires_at"),
            )
        )
        _FLOWS.pop(body.flow, None)
        return {"state": "done", **_status()}

    @router.get("/repositories")
    async def repositories():
        stored = vault.load()
        if stored is None or stored.expired:
            raise HTTPException(status_code=409, detail="GitHub is not connected.")
        try:
            listing = await asyncio.to_thread(github.repositories, stored.token)
        except GitHubError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return {"repositories": listing, "install_url": app.install_url()}

    @router.delete("/connect")
    async def disconnect():
        vault.clear()
        _FLOWS.clear()
        return {
            **_status(),
            # Said plainly: forgetting the token here does not revoke it on GitHub.
            "note": f"Zaram has forgotten the sign-in. To withdraw its access on GitHub too, remove it at {app.manage_url()}.",
        }

    return router


router = build_router()
