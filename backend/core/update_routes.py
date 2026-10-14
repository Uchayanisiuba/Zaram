"""The update routes: what Settings and the banner read, and what the shell asks.

Thin on purpose -- `core/updates.py` holds the rules. Two things live here
because they are about the request rather than the update: answering yes is what
allows the update hosts (rule 7j), and a check that nobody asked for does not
happen while the person has said no or has not been asked.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import updates


class SettingsBody(BaseModel):
    checks: bool


class CheckBody(BaseModel):
    #: The person pressed *Check for updates*: an act, so it is not held back by
    #: the setting or by the last answer being recent.
    force: bool = False


def build_router(service: Optional[updates.Updates] = None) -> APIRouter:
    router = APIRouter(prefix="/updates", tags=["updates"])

    def current() -> updates.Updates:
        return service or updates.shared()

    @router.get("/status")
    async def status() -> Dict[str, Any]:
        return await asyncio.to_thread(current().status)

    @router.put("/settings")
    async def settings(body: SettingsBody) -> Dict[str, Any]:
        svc = current()
        svc.set_checks(body.checks)
        answer = await asyncio.to_thread(svc.status)
        if body.checks:
            blocked = updates.allow_hosts()
            if blocked:
                answer["note"] = blocked
        return answer

    @router.post("/check")
    async def check(body: CheckBody) -> Dict[str, Any]:
        svc = current()
        if not body.force and svc.checks() is not True:
            return await asyncio.to_thread(svc.status)
        blocked = updates.allow_hosts()
        if blocked:
            raise HTTPException(status_code=409, detail=blocked)
        return await asyncio.to_thread(lambda: svc.check(force=body.force))

    @router.post("/download")
    async def download() -> Dict[str, Any]:
        svc = current()
        blocked = updates.allow_hosts()
        if blocked:
            raise HTTPException(status_code=409, detail=blocked)
        try:
            return await asyncio.to_thread(svc.download)
        except updates.UpdateError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/installer")
    async def installer() -> Dict[str, Any]:
        """The verified installer waiting to be run -- asked for by the desktop shell."""
        found = await asyncio.to_thread(current().pending)
        if found is None:
            raise HTTPException(status_code=404, detail="There is no downloaded update ready to install.")
        return found

    return router


router = build_router()
