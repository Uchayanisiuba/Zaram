"""`ZaramGovernedSession` asks the real gate the real question and sends its answer.

10 October 2026, found auditing a batch of changes. The session called
`gate.resolve(..., data_class=...)`, which `resolve` does not accept, so the first
real request would have raised `TypeError`; it handed `params` to aiohttp instead of
to the gate, so the checked and logged URL lacked the query string -- which for a
search API *is* the query; and its shortcuts were coroutines, so the
`async with session.post(...)` every provider writes was a `TypeError` too. The tests
that passed stubbed all three away.

The gate here has `EgressGate.resolve`'s real signature, so a keyword it does not take
fails the way it would in the product.
"""

from __future__ import annotations

import asyncio
import inspect
import urllib.parse

import pytest

from core.egress import EgressDenied, EgressGate
from network.session import ZaramGovernedSession, ZaramSecurityViolation


class _Gate:
    """`EgressGate.resolve`, with the same parameters and the same URL folding."""

    def __init__(self, deny: bool = False):
        self.deny = deny
        self.asked: list[dict] = []

    def resolve(self, url, *, params=None, method="GET", body=None, source="unknown", grant=None):
        self.asked.append({"url": url, "params": params, "method": method, "body": body, "source": source})
        if self.deny:
            raise EgressDenied("denied by test", host=urllib.parse.urlparse(url).hostname or "")
        if params:
            return f"{url}?{urllib.parse.urlencode(params)}"
        return url


class _Response:
    status = 200

    def __init__(self):
        self.released = False

    def release(self):
        self.released = True


class _Client:
    """What aiohttp would be handed. Records it, answers without a network."""

    closed = False

    def __init__(self):
        self.sent: list[tuple] = []
        self.response = _Response()

    async def request(self, method, url, **kwargs):
        self.sent.append((method, url, kwargs))
        return self.response

    async def close(self):
        self.closed = True


def _session(gate):
    session = ZaramGovernedSession(gate)
    client = _Client()

    async def _get_session():
        return client

    session._get_session = _get_session  # type: ignore[method-assign]
    return session, client


def test_the_gate_double_has_the_real_resolve_signature():
    # If `resolve` changes, this double must change with it, or it tests nothing.
    assert list(inspect.signature(_Gate.resolve).parameters)[2:] == [
        p for p in inspect.signature(EgressGate.resolve).parameters if p != "self" and p != "url"
    ]


def test_the_query_string_is_what_the_gate_saw_and_what_was_sent():
    async def go():
        gate = _Gate()
        session, client = _session(gate)
        async with session.get("https://api.example/search", params={"q": "my client's rate"}, source="brave") as resp:
            assert resp.status == 200
        return gate, client

    gate, client = asyncio.run(go())
    assert gate.asked[0]["params"] == {"q": "my client's rate"}
    method, url, kwargs = client.sent[0]
    assert url == "https://api.example/search?q=my+client%27s+rate"
    assert "params" not in kwargs, "aiohttp must not assemble a second URL from the same params"


def test_the_body_reaches_the_gate_and_is_sent():
    async def go():
        gate = _Gate()
        session, client = _session(gate)
        resp = await session.post("https://api.example/search", json={"query": "x"}, source="tavily")
        return gate, client, resp

    gate, client, resp = asyncio.run(go())
    assert gate.asked[0]["body"] == '{"query":"x"}'
    assert client.sent[0][2]["data"] == '{"query":"x"}'
    assert resp is client.response


def test_leaving_async_with_releases_the_response():
    async def go():
        session, client = _session(_Gate())
        async with session.get("https://api.example/x"):
            pass
        return client

    assert asyncio.run(go()).response.released is True


def test_a_denial_stops_the_request_before_anything_is_sent():
    async def go():
        session, client = _session(_Gate(deny=True))
        with pytest.raises(ZaramSecurityViolation):
            async with session.get("https://api.example/x", params={"q": "y"}):
                pass
        return client

    assert asyncio.run(go()).sent == []
