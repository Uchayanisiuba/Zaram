"""The routes the frontend calls are reachable on the *real* application.

Written after finding that `providers/api.py` — a complete router with its own
passing test file — was never included in the app. Every path answered 404 on
the running product for the whole life of the provider layer, and
`providers/tests/test_api.py` did not notice because it constructs its own
``FastAPI()`` and mounts the router itself. That is a fair way to test the
handlers and it cannot see the wiring, which is where the defect was.

Same shape as `scripts/check-installer-payload.mjs`: the unit tests are about
behaviour, and this one is about the thing nobody thought to assert — that the
behaviour is reachable.

**Asserted by asking, not by reading the routing table.** The first version of
this file compared paths against ``app.routes`` and failed against a correctly
mounted router, because this FastAPI version keeps an included router as a
single ``_IncludedRouter`` entry rather than flattening its paths into the
parent. A test that inspects an internal structure tests the structure; a
request tests the claim. The claim is "not 404".

Startup is deliberately not run. Without it the provider handlers answer 503 —
"the layer is still booting" — which is a *different answer from 404* and is
exactly the distinction under test. It also keeps this file fast enough to be
run without thinking about it, which a test that boots the kernel would not be.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


#: Paths whose absence would be silent. Not exhaustive on purpose: a missing
#: `/health` is noticed in seconds, and a missing `/providers/catalogue` is
#: noticed as an empty dropdown somebody assumes is a frontend bug.
EXPECTED_GET_ROUTES = [
    "/providers/models",
    "/providers/sources",
    "/providers/hardware",
    "/providers/health",
    "/providers/catalogue",
    "/providers/cloud",
    "/egress",
    "/egress/policy",
    "/egress/pending",
    "/egress/killswitch",
    "/routing/preference",
    "/readiness",
    "/health",
]


@pytest.fixture(scope="module")
def client() -> TestClient:
    from main import app

    return TestClient(app)


@pytest.mark.parametrize("path", EXPECTED_GET_ROUTES)
def test_route_is_reachable(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code != 404, (
        f"GET {path} answered 404 on the real app. A router defined but never "
        f"passed to include_router() does this while its own tests pass."
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/providers/cloud"),
        ("DELETE", "/providers/cloud"),
        ("POST", "/egress/killswitch"),
        ("POST", "/routing/preference"),
    ],
)
def test_write_route_is_reachable(client: TestClient, method: str, path: str) -> None:
    """The mutating half exists too.

    A GET-only mount would satisfy the check above while leaving every control
    in Settings unable to save anything — and that failure looks like a
    frontend bug, which is the worst place to spend an afternoon.

    Sent with no body and no client header, so the expected answers are 403 or
    422 rather than success. Both mean *the route is there and refused this
    particular request*, which is all this file claims.
    """
    response = client.request(method, path)
    assert response.status_code != 404, f"{method} {path} answered 404 on the real app."
    assert response.status_code != 405, (
        f"{method} {path} is not accepted by the handler mounted at that path."
    )
