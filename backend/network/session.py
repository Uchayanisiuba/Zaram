"""Zaram Governed Network Session.

This module provides the single point of egress for all aiohttp-based outbound
connections. No module may create a raw `aiohttp.ClientSession` — all HTTP
traffic must pass through `ZaramGovernedSession`, which enforces the EgressGate
before any bytes leave the machine.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import ClientRequest, ClientResponse

from core.egress import EgressGate, EgressDenied, DataClass, SearchReadGrant


class ZaramSecurityViolation(Exception):
    """Raised when an outbound request violates Zaram's egress policy.

    This is a terminal exception — the request was not sent, and the violation
    is logged to the egress log. Callers should not retry.
    """

    def __init__(
        self,
        message: str,
        host: str,
        url: str,
        entry_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.host = host
        self.url = url
        self.entry_id = entry_id


class _GovernedRequestContext:
    """Internal context for a single governed request."""

    def __init__(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
        source: str = "web_search",
        data_class: DataClass = DataClass.PROMPT,
        grant: Optional[SearchReadGrant] = None,
    ):
        self.method = method.upper()
        self.url = url
        self.headers = headers or {}
        self.body = body
        self.source = source
        self.data_class = data_class
        self.grant = grant
        self.start_time = time.time()


class _GovernedCall:
    """A governed request that can be awaited or used with ``async with``.

    aiohttp's own request object is both, and every caller in the web search pack
    writes ``async with session.post(...) as resp``. The shortcuts were ``async def``,
    which made that a ``TypeError``: a coroutine is not a context manager.
    """

    def __init__(self, start):
        self._start = start
        self._response = None

    def __await__(self):
        return self._start().__await__()

    async def __aenter__(self):
        self._response = await self._start()
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        if self._response is not None:
            self._response.release()


class ZaramGovernedSession:
    """Governed aiohttp session wrapper.

    This is the ONLY permitted way to make outbound aiohttp requests in Zaram.
    It wraps a raw `aiohttp.ClientSession` but intercepts every request,
    routing it through the `EgressGate` before any network I/O occurs.

    Usage:
        session = ZaramGovernedSession(egress_gate, source="my_provider")
        async with session.post("https://api.example.com/search", json=payload) as resp:
            data = await resp.json()
    """

    def __init__(
        self,
        egress_gate: EgressGate,
        *,
        source: str = "web_search",
        default_headers: Optional[Dict[str, str]] = None,
        timeout: Optional[aiohttp.ClientTimeout] = None,
        connector: Optional[aiohttp.BaseConnector] = None,
    ):
        """
        Args:
            egress_gate: The EgressGate instance to enforce policy.
            source: Logical source identifier for egress logging (e.g., "tavily", "brave").
            default_headers: Headers to include on every request.
            timeout: aiohttp ClientTimeout for the underlying session.
            connector: aiohttp connector for connection pooling.
        """
        self._gate = egress_gate
        self._source = source
        self._default_headers = default_headers or {}
        self._timeout = timeout or aiohttp.ClientTimeout(total=30)
        self._connector = connector
        self._session: Optional[aiohttp.ClientSession] = None
        self._closed = False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the underlying aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                connector=self._connector,
                headers=self._default_headers,
            )
        return self._session

    async def _enforce_gate(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
        source: Optional[str] = None,
        data_class: DataClass = DataClass.PROMPT,
        grant: Optional[SearchReadGrant] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, Optional[str]]:
        """Enforce egress gate before sending request.

        Returns:
            Tuple of (approved_url, approved_body_text) — the exact URL and body
            that were checked and approved by the gate.

        Raises:
            ZaramSecurityViolation: If the gate denies the request.
        """
        # Prepare body text for gate inspection
        body_text = None
        if body is not None:
            if isinstance(body, (bytes, bytearray)):
                body_text = body.decode("utf-8", "replace")
            elif isinstance(body, str):
                body_text = body
            elif isinstance(body, (dict, list)):
                body_text = json.dumps(body, separators=(",", ":"))
            else:
                body_text = str(body)

        # Resolve final URL (gate.resolve folds params into URL)
        # We must use gate.resolve to get the exact URL that will be logged
        src = source or self._source
        try:
            # `params` is folded into the URL here and that URL is what is sent.
            # Passed on to aiohttp as well, the client would assemble a different
            # URL from the one checked and logged -- and for a search API the query
            # string *is* the query. `resolve` has no `data_class`; it classifies
            # the request itself, so the argument is accepted by this class's methods
            # for their callers' sake and not forwarded.
            approved_url = self._gate.resolve(
                url,
                params=params,
                method=method,
                body=body_text,
                source=src,
                grant=grant,
            )
        except EgressDenied as e:
            raise ZaramSecurityViolation(
                str(e),
                host=e.host,
                url=url,
                entry_id=e.entry_id,
            ) from e

        # Return the approved URL and body
        return approved_url, body_text

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Any] = None,
        source: Optional[str] = None,
        data_class: DataClass = DataClass.PROMPT,
        grant: Optional[SearchReadGrant] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ClientResponse:
        """Execute a governed request."""
        if self._closed:
            raise RuntimeError("Governed session is closed")

        session = await self._get_session()

        # Enforce egress gate
        approved_url, approved_body = await self._enforce_gate(
            method=method,
            url=url,
            headers=headers,
            body=body,
            source=source,
            data_class=data_class,
            grant=grant,
            params=params,
        )

        # Merge headers
        request_headers = {**self._default_headers, **(headers or {})}

        # Prepare body for aiohttp
        aiohttp_body = None
        if body is not None:
            if isinstance(body, (bytes, bytearray)):
                aiohttp_body = body
            elif isinstance(body, str):
                aiohttp_body = body
            elif isinstance(body, (dict, list)):
                aiohttp_body = json.dumps(body, separators=(",", ":"))
            else:
                aiohttp_body = str(body)

        # Execute the request
        return await session.request(
            method,
            approved_url,
            headers=request_headers,
            data=aiohttp_body,
            **kwargs,
        )

    # --- HTTP method shortcuts ---

    def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        source: Optional[str] = None,
        data_class: DataClass = DataClass.PROMPT,
        grant: Optional[SearchReadGrant] = None,
        **kwargs: Any,
    ) -> ClientResponse:
        """GET request through the egress gate."""
        return _GovernedCall(lambda: self._request(
            "GET",
            url,
            headers=headers,
            params=params,
            source=source,
            data_class=data_class,
            grant=grant,
            **kwargs,
        ))

    def post(
        self,
        url: str,
        *,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        source: Optional[str] = None,
        data_class: DataClass = DataClass.PROMPT,
        grant: Optional[SearchReadGrant] = None,
        **kwargs: Any,
    ) -> ClientResponse:
        """POST request through the egress gate."""
        body = json if json is not None else data
        return _GovernedCall(lambda: self._request(
            "POST",
            url,
            headers=headers,
            body=body,
            source=source,
            data_class=data_class,
            grant=grant,
            **kwargs,
        ))

    def put(
        self,
        url: str,
        *,
        json: Optional[Any] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        source: Optional[str] = None,
        data_class: DataClass = DataClass.PROMPT,
        grant: Optional[SearchReadGrant] = None,
        **kwargs: Any,
    ) -> ClientResponse:
        """PUT request through the egress gate."""
        body = json if json is not None else data
        return _GovernedCall(lambda: self._request(
            "PUT",
            url,
            headers=headers,
            body=body,
            source=source,
            data_class=data_class,
            grant=grant,
            **kwargs,
        ))

    def delete(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        source: Optional[str] = None,
        data_class: DataClass = DataClass.PROMPT,
        grant: Optional[SearchReadGrant] = None,
        **kwargs: Any,
    ) -> ClientResponse:
        """DELETE request through the egress gate."""
        return _GovernedCall(lambda: self._request(
            "DELETE",
            url,
            headers=headers,
            source=source,
            data_class=data_class,
            grant=grant,
            **kwargs,
        ))

    def head(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        source: Optional[str] = None,
        data_class: DataClass = DataClass.PROMPT,
        grant: Optional[SearchReadGrant] = None,
        **kwargs: Any,
    ) -> ClientResponse:
        """HEAD request through the egress gate."""
        return _GovernedCall(lambda: self._request(
            "HEAD",
            url,
            headers=headers,
            source=source,
            data_class=data_class,
            grant=grant,
            **kwargs,
        ))

    async def close(self) -> None:
        """Close the underlying session."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._closed = True

    async def __aenter__(self) -> "ZaramGovernedSession":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


def create_governed_session(
    egress_gate: EgressGate,
    *,
    source: str = "web_search",
    default_headers: Optional[Dict[str, str]] = None,
    timeout: Optional[aiohttp.ClientTimeout] = None,
) -> ZaramGovernedSession:
    """Factory function to create a governed session.

    Args:
        egress_gate: The EgressGate instance to enforce policy.
        source: Logical source identifier for egress logging.
        default_headers: Headers to include on every request.
        timeout: aiohttp ClientTimeout for the underlying session.

    Returns:
        A ZaramGovernedSession instance.
    """
    return ZaramGovernedSession(
        egress_gate,
        source=source,
        default_headers=default_headers,
        timeout=timeout,
    )