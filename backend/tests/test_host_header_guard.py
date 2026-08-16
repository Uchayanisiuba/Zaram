"""A web page must not be able to read the Spine.

Binding to 127.0.0.1 closed the loud hole — the API had been published on every
interface with no authentication, so anyone on a café network could read the
whole Spine. It does not close the quiet one.

**DNS rebinding.** A site the user visits points a hostname it controls at
127.0.0.1 and then makes ordinary requests to port 8420. The browser treats
them as *same-origin*, so CORS never runs; the requests carry the attacker's
hostname in `Host`. `GET /memory` is every stored fact, `GET /egress` is every
question ever asked, and `PUT /egress/policy` sets a destination to `allow`.
The same attack has been used against other local services that assumed
loopback was a boundary.

`Host` is the discriminator, because the browser is obliged to send the name it
was asked to fetch.

**What these tests do not claim.** There is still no authentication, so any
*process* on this machine can call the API. Loopback is a network boundary, not
an identity one. That needs a per-launch secret from the desktop host and is
recorded as the next step, not asserted here — a test named for a guarantee the
code does not make is worse than no test.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    from main import app

    return TestClient(app)


#: The endpoints worth naming individually, because each is a different loss.
SENSITIVE = [
    ("/memory", "every fact Zaram has stored"),
    ("/egress", "every request that ever left, with the literal text"),
    ("/egress/policy", "which destinations are permitted"),
    ("/health", "what is installed and connected"),
]


@pytest.mark.parametrize("path,what", SENSITIVE)
def test_a_rebound_hostname_is_refused(client: TestClient, path: str, what: str) -> None:
    response = client.get(path, headers={"Host": "evil.example.com"})

    assert response.status_code == 400, (
        f"GET {path} answered a request carrying an attacker's hostname. "
        f"That exposes {what} to any page the user visits."
    )


def test_a_write_is_refused_too(client: TestClient) -> None:
    """Reading is the obvious loss; writing is the worse one.

    Setting a host to `allow` through a rebound request would grant a
    destination permission the user never gave — rule 5 defeated from a web
    page.
    """
    response = client.put(
        "/egress/policy",
        json={"host": "attacker.example.com", "mode": "allow"},
        headers={"Host": "evil.example.com"},
    )

    assert response.status_code == 400


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "127.0.0.1:8420", "localhost:8420"])
def test_the_real_interface_still_works(client: TestClient, host: str) -> None:
    """The guard must not be stricter than the product.

    Both spellings and both forms — with and without the port — because the
    interface, the Electron host and a `curl` from the user's own terminal do
    not agree on which they send, and a guard that refuses one of them reads as
    the backend being down.
    """
    response = client.get("/health", headers={"Host": host})

    assert response.status_code == 200
