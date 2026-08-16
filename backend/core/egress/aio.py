"""The async half of the gate.

``EgressGate.request`` covers synchronous call sites. The internet runtime is
async and holds long-lived ``aiohttp`` sessions, so it needs something with a
session's shape rather than a one-shot call.

The important property is that the check is **not optional**. An earlier version
of this migration had async call sites resolve the URL, get a verdict, and then
send it themselves — which works, and which someone will eventually get wrong by
resolving one URL and sending another, or by adding a second request and
forgetting the first line. :class:`GatedSession` removes the opportunity: it
takes the same arguments as ``aiohttp.ClientSession.get`` and consults the gate
inside, so there is no ordering for a caller to get wrong.

This module and ``gate.py`` are the only two places in the backend permitted to
open an outbound connection. ``test_egress_chokepoint.py`` enforces that by
reading the source.
"""

from __future__ import annotations

from typing import Any

from .runtime import get_gate


class GatedSession:
    """An ``aiohttp`` session that cannot make an unchecked request.

    Lazily constructs the underlying session, so importing this module does not
    require an event loop and the internet runtime can be built at import time
    as it is today.
    """

    def __init__(self, *, headers: dict[str, str] | None = None, source: str = "unknown",
                 grant: Any = None):
        self._headers = headers
        self._source = source
        # A capability, not a label. See `SearchReadGrant` in `gate.py`: it
        # names the exact URLs this session may read past default-deny, so a
        # session cannot widen its own permissions by describing itself
        # differently. None, as here by default, means ordinary policy only.
        self._grant = grant
        self._session: Any = None

    async def _ensure(self) -> Any:
        if self._session is None:
            import aiohttp

            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    def _request(self, method: str, url: str, params: dict[str, Any] | None,
                 body: str | None):
        """Check first. Returns the resolved URL, or raises ``EgressDenied``."""
        return get_gate().resolve(
            url, params=params, method=method, body=body, source=self._source,
            grant=self._grant,
        )

    def get(self, url: str, *, params: dict[str, Any] | None = None, **kwargs: Any):
        """Same shape as ``aiohttp``'s ``get``, with the gate in front.

        ``params`` is folded into the URL before the check so that what is
        logged is byte-for-byte what leaves.
        """
        resolved = self._request("GET", url, params, None)
        return _Ctx(self, resolved, kwargs)

    def post(self, url: str, *, params: dict[str, Any] | None = None,
             data: Any = None, json: Any = None, **kwargs: Any):
        body = None
        if json is not None:
            import json as _json

            body = _json.dumps(json)
        elif isinstance(data, (str, bytes)):
            body = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
        resolved = self._request("POST", url, params, body)
        return _Ctx(self, resolved, {**kwargs, "data": data, "json": json})

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> GatedSession:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()


class _Ctx:
    """Defers the actual send until ``async with``, matching aiohttp's usage.

    The gate has already been consulted by the time one of these exists — the
    check happens in ``get``/``post``, not here, so a caller that builds a
    request and never awaits it has still been governed.
    """

    def __init__(self, owner: GatedSession, url: str, kwargs: dict[str, Any]):
        self._owner = owner
        self._url = url
        self._kwargs = {k: v for k, v in kwargs.items() if v is not None}
        self._cm: Any = None

    async def __aenter__(self) -> Any:
        session = await self._owner._ensure()
        method = self._kwargs.pop("_method", "get")
        self._cm = getattr(session, method)(self._url, **self._kwargs)
        return await self._cm.__aenter__()

    async def __aexit__(self, *exc: Any) -> Any:
        if self._cm is not None:
            return await self._cm.__aexit__(*exc)
        return None


def gated_session(*, headers: dict[str, str] | None = None,
                  source: str = "unknown", grant: Any = None) -> GatedSession:
    """Build a session that checks every request. Use instead of aiohttp.

    `grant` is an optional `SearchReadGrant` naming exact URLs this session may
    read past default-deny. Omit it — as every existing call site does — and
    the session is bound by the per-host policy alone.
    """
    return GatedSession(headers=headers, source=source, grant=grant)
