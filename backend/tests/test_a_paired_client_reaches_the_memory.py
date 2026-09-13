"""A second client on this machine can hold Zaram's memory — and only that.

`core/pairing.py` had the rules and no caller for a month. This is the
caller, and what it asserts is the shape `docs/AGENT-UX.md` asked for
before the MCP server could be built: *a named client, a token the person
issues in Settings and can revoke, every call logged as egress to that
client*. Each of those is one test below.

The API secret stays what it was — the owner's interface — and a paired
credential opens the memory routes and nothing else. `GET /egress`,
`PUT /egress/policy` and `/health` are the three assets
`test_api_requires_the_credential.py` guards; they are guarded here against
the new credential too, because a door added for one purpose is a door.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.testclient import TestClient

import core.api_secret as api_secret
from core.paired_clients import PairedClients


class _Result:
    def __init__(self, content: str, relevance: float, **fields: Any):
        self.record = SimpleNamespace(
            id=f"fact-{content[:8]}",
            content=content,
            scope=fields.get("scope", "global"),
            origin=SimpleNamespace(value=fields.get("origin", "conversation")),
            source=fields.get("source", "user"),
            created_at=1.0,
        )
        self.relevance = relevance
        # The ranking blend, deliberately different from relevance, so a test
        # can tell which number the floor was applied to.
        self.score = 0.99


class _Spine:
    def __init__(self) -> None:
        self.asked: list[dict[str, Any]] = []
        self.results: list[_Result] = []
        self.written: list[dict[str, Any]] = []
        self._store = self

    async def retrieve(self, **kwargs: Any):
        self.asked.append(kwargs)
        return list(self.results)

    async def remember(self, **kwargs: Any) -> str:
        self.written.append(kwargs)
        return "fact-new"

    async def get(self, record_id: str):
        return SimpleNamespace(id=record_id, scope=None, created_at=0.0)


@pytest.fixture
def client(tmp_path, monkeypatch):
    from core.egress import get_gate
    from core.egress.log import EgressLog
    from projects.records import ProjectRecords

    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    main = importlib.import_module("main")
    monkeypatch.setattr(main, "project_records", ProjectRecords(str(tmp_path / "projects.db")))
    monkeypatch.setattr(main, "paired_clients", PairedClients(tmp_path / "clients.db"))
    spine = _Spine()
    monkeypatch.setattr(main.kernel, "memory_runtime", spine, raising=False)
    # Our own log, so the entries asserted on are the ones this test wrote.
    log = EgressLog(str(tmp_path / "egress.db"))
    monkeypatch.setattr(get_gate(), "_log", log, raising=False)

    test_client = TestClient(main.app)
    test_client.spine = spine  # type: ignore[attr-defined]
    test_client.main = main  # type: ignore[attr-defined]
    test_client.log = log  # type: ignore[attr-defined]
    return test_client


def _pair(client, name="Claude Code") -> str:
    """Issue a token as the owner, redeem it as the client. Returns the credential."""
    issued = client.post("/pairing/token").json()
    assert issued["expires_in"] == 60.0
    redeemed = client.post(
        "/pairing/redeem",
        json={"token": issued["token"], "name": name},
        headers={api_secret.HEADER: ""},  # the client has nothing yet
    )
    assert redeemed.status_code == 200, redeemed.text
    return redeemed.json()["credential"]


class TestPairing:
    def test_a_token_from_settings_becomes_a_named_client(self, client):
        credential = _pair(client, "Cline")
        listed = client.get("/pairing/clients").json()["clients"]
        assert [c["name"] for c in listed] == ["Cline"]
        assert listed[0]["is_active"] is True
        # The credential is returned once and appears nowhere the owner can
        # read it back from.
        assert "credential" not in listed[0]
        assert credential not in client.get("/pairing/clients").text

    def test_redeeming_needs_no_credential_but_does_need_a_token(self, client):
        response = client.post(
            "/pairing/redeem",
            json={"token": "not-a-token", "name": "x"},
            headers={api_secret.HEADER: ""},
        )
        assert response.status_code == 400
        assert "not valid" in response.json()["detail"]

    def test_issuing_and_listing_are_the_owners_alone(self, client):
        credential = _pair(client)
        headers = {api_secret.HEADER: credential}
        assert client.post("/pairing/token", headers=headers).status_code == 403
        assert client.get("/pairing/clients", headers=headers).status_code == 403


class TestWhatAPairedClientMayReach:
    def test_recall_answers_with_provenance(self, client):
        client.spine.results = [
            _Result("The Northwind day rate is 650", 0.81, scope="project:nw", source="brief.pdf"),
            _Result("unrelated but recently touched", 0.20),
        ]
        credential = _pair(client)
        response = client.post(
            "/memory/recall",
            json={"query": "what is the Northwind rate"},
            headers={api_secret.HEADER: credential},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        # The floor is applied to `relevance`, never to `score` — the second
        # result has a blend of 0.99 and a relevance of 0.20, and is cut.
        assert [f["content"] for f in body["facts"]] == ["The Northwind day rate is 650"]
        fact = body["facts"][0]
        assert fact["source"] == "brief.pdf"
        assert fact["origin"] == "conversation"
        assert fact["scope"] == "project:nw"
        assert fact["id"]
        from core.execution_engine import ExecutionEngine

        assert body["threshold"] == ExecutionEngine.MIN_RECALL_SCORE

    def test_remember_and_correct_are_open_and_the_rest_is_not(self, client):
        credential = _pair(client)
        headers = {api_secret.HEADER: credential}
        assert client.post("/memory", json={"text": "Pays net 45"}, headers=headers).status_code == 200
        assert client.spine.written[-1]["content"] == "Pays net 45"
        assert client.get("/projects", headers=headers).status_code == 200
        # The three assets the credential test guards, guarded against this
        # credential too. 403 rather than 401: the caller is known, and what
        # it is refused is named.
        for method, route in (("GET", "/memory"), ("GET", "/egress"), ("GET", "/health"),
                              ("PUT", "/egress/policy"), ("DELETE", "/pairing/clients/x")):
            response = client.request(method, route, headers=headers)
            assert response.status_code == 403, f"{method} {route} answered {response.status_code}"
            assert "paired for memory" in response.json()["detail"]

    def test_every_call_is_egress_to_that_client(self, client):
        client.spine.results = [_Result("a fact worth 40 bytes or so", 0.9)]
        credential = _pair(client, "Kilo")
        before = client.log.count()
        response = client.post(
            "/memory/recall", json={"query": "anything"}, headers={api_secret.HEADER: credential}
        )
        entries = client.log.entries(limit=5)
        assert client.log.count() == before + 1
        entry = entries[0]
        assert entry.host == "client:Kilo"
        assert entry.kind == "client"
        assert entry.url == "/memory/recall"
        # What left is the response, and the count is of that.
        assert entry.byte_count == len(response.content)
        assert entry.body is None  # never a second copy of the facts
        # The owner's own calls are not egress: nothing left the process.
        client.post("/memory/recall", json={"query": "anything"})
        assert client.log.count() == before + 1


class TestRevocation:
    def test_a_revoked_client_is_refused_by_the_next_call(self, client):
        credential = _pair(client)
        headers = {api_secret.HEADER: credential}
        assert client.get("/projects", headers=headers).status_code == 200
        listed = client.get("/pairing/clients").json()["clients"]
        assert client.delete(f"/pairing/clients/{listed[0]['id']}").status_code == 200
        assert client.get("/projects", headers=headers).status_code == 401
        # Kept, marked — "which clients have ever had access" stays answerable.
        after = client.get("/pairing/clients").json()["clients"]
        assert after[0]["is_active"] is False and after[0]["revoked_at"]

    def test_a_pairing_survives_a_restart(self, client, tmp_path):
        credential = _pair(client, "Claude Code")
        reloaded = PairedClients(tmp_path / "clients.db")
        assert reloaded.verify(credential).name == "Claude Code"
        assert reloaded.verify("something else") is None
