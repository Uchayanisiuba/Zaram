"""The API refuses a caller that cannot present this launch's credential.

**What this closes.** Loopback stopped the café network. The `Host` guard —
`test_host_header_guard.py` — stopped a web page reaching the API by pointing
a hostname it controls at 127.0.0.1. Neither did anything about a *process*,
and there was no authentication at all, so anything running as this user could
read every fact in the Spine, every question in the egress log, or write a
destination policy. `X-Zaram-Client` was the only thing that looked like a
credential and it is enforced nowhere.

The routes named here are the three that make the exposure concrete rather
than theoretical, and they are deliberately the same three the rebinding test
uses. Same assets, second door.
"""

from __future__ import annotations

import importlib

import pytest
from starlette.testclient import TestClient

import core.api_secret as api_secret


@pytest.fixture(scope="module")
def client():
    main = importlib.import_module("main")
    return TestClient(main.app)


#: What a local attacker would actually reach for: the facts, the history of
#: what left, and the control over what may leave next.
THE_VALUABLE = ["/memory", "/egress", "/health"]


@pytest.mark.parametrize("route", THE_VALUABLE)
def test_no_credential_is_refused(client, route):
    """`conftest` adds the header to every request, so it is removed here.

    Passing `None` is not enough — `setdefault` would fill it back in. The
    header has to be present and wrong, or explicitly overridden with a value
    the middleware will reject.
    """
    response = client.get(route, headers={api_secret.HEADER: ""})
    assert response.status_code == 401, (
        f"{route} answered {response.status_code} to a caller with no credential"
    )


@pytest.mark.parametrize("route", THE_VALUABLE)
def test_a_wrong_credential_is_refused(client, route):
    response = client.get(route, headers={api_secret.HEADER: "not-the-secret"})
    assert response.status_code == 401


def test_the_right_credential_is_accepted(client):
    """The other half of the same assertion, and the one that fails if this
    middleware is ever made unconditional by accident."""
    response = client.get("/health", headers={api_secret.HEADER: api_secret.api_secret()})
    assert response.status_code == 200
    # Only that it was *let through*. Whether the kernel reports online depends
    # on whether the runtime was bootstrapped in this process, which is a
    # different question from whether the caller was authorised — and asserting
    # it here would make an auth test fail for a reason that has nothing to do
    # with auth.
    assert "kernel" in response.json()


def test_health_is_not_exempt(client):
    """`/health` was the tempting exemption and it is not one.

    It reports capabilities, configured providers, model names and speech
    state — a description of the user's setup. The desktop host mints the
    secret, so it can present it, and default-deny is the rule.
    """
    assert client.get("/health", headers={api_secret.HEADER: ""}).status_code == 401


def test_a_rebound_host_is_still_refused_as_a_host_problem(client):
    """Ordering, asserted rather than assumed.

    The host guard must stay *outside* this one. A rebinding attempt should be
    told its host is wrong, because that is the more useful and more specific
    refusal — and if this middleware were outermost, every such request would
    come back 401 and the rebinding test would be silently measuring the wrong
    guard.
    """
    response = client.get(
        "/memory",
        headers={"Host": "attacker.example.com", api_secret.HEADER: api_secret.api_secret()},
    )
    assert response.status_code == 400


def test_the_client_label_is_not_a_credential(client):
    """`X-Zaram-Client` is sent by the interface and enforced nowhere.

    Written down as a test because it is the exact thing a reader is most
    likely to mistake for authentication — it is on every mutating call in
    `settingsClient.ts` and it looks the part.
    """
    response = client.get(
        "/memory",
        headers={api_secret.HEADER: "", "X-Zaram-Client": "zaram-ui"},
    )
    assert response.status_code == 401


class TestTheSecretItself:
    def test_the_environment_wins(self, monkeypatch):
        """Packaged builds set this and nothing else, so nothing is on disk."""
        monkeypatch.setenv(api_secret.SECRET_ENV, "  from-the-desktop-host  ")
        api_secret.reset_cache()
        try:
            assert api_secret.api_secret() == "from-the-desktop-host"
        finally:
            api_secret.reset_cache()

    def test_comparison_rejects_empty_and_none(self):
        assert api_secret.matches(None) is False
        assert api_secret.matches("") is False

    def test_a_generated_secret_is_not_guessable(self, monkeypatch, tmp_path):
        """No env var, so the development fallback runs. The property worth
        asserting is entropy, not the storage — a short or predictable value
        would be worse than none, because it would look like protection."""
        monkeypatch.delenv(api_secret.SECRET_ENV, raising=False)
        monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
        api_secret.reset_cache()
        try:
            minted = api_secret.api_secret()
            assert len(minted) >= 32
            assert (tmp_path / api_secret.SECRET_FILENAME).read_text().strip() == minted
        finally:
            api_secret.reset_cache()

    def test_startup_writes_the_file_before_anyone_asks(self, monkeypatch, tmp_path):
        """The deadlock, asserted.

        `matches()` returns False for an absent header without resolving
        anything, so a backend that only ever sees unauthenticated requests
        would never write the file the dev server has to read — and could
        therefore never be authenticated against. Observed live: 401 to
        everything, and no `api-secret` on disk.
        """
        monkeypatch.delenv(api_secret.SECRET_ENV, raising=False)
        monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
        api_secret.reset_cache()
        try:
            assert not (tmp_path / api_secret.SECRET_FILENAME).exists()
            # The thing an unauthenticated request does, and only that.
            assert api_secret.matches(None) is False
            assert not (tmp_path / api_secret.SECRET_FILENAME).exists(), (
                "a failed comparison should not mint anything"
            )

            api_secret.ensure_resolved()
            assert (tmp_path / api_secret.SECRET_FILENAME).exists(), (
                "startup did not leave a credential the dev server could read"
            )
        finally:
            api_secret.reset_cache()

    def test_the_fallback_is_stable_across_readers(self, monkeypatch, tmp_path):
        """The dev server and the backend are started independently and must
        agree. Whichever creates the file, the other reads it."""
        monkeypatch.delenv(api_secret.SECRET_ENV, raising=False)
        monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
        api_secret.reset_cache()
        try:
            first = api_secret.api_secret()
            api_secret.reset_cache()
            assert api_secret.api_secret() == first
        finally:
            api_secret.reset_cache()
