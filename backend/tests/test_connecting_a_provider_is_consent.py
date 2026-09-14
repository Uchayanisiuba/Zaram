"""Connecting a provider is the consent — rule 7j, finally enforced.

`CLAUDE.md`, rule 7j: *"Connecting a cloud provider — choosing it, pasting a
key for it, pressing Connect — is rule 5's explicit per-item decision about
that provider's host. Requiring a second, separate host rule afterwards
asks the same question twice and reads as the product being broken: it
happened to the maintainer, on their own build, with nothing on screen
explaining why."*

It happened again on 14 September 2026, on the first-run key form this
time: the key stored, the first question was refused by default-deny, and
the only remedy was an amber line in a Settings section the first run does
not show. *"I copy the key and it doesn't work."*

Three contracts. Connecting grants the host the ``prompt`` class and no
other — an image is its own consent. A host the person deliberately denied
stays denied; a key is not a louder opinion than a rule. And a loopback
server gets no rule, because it needs none.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.egress import DataClass, EgressGate, EgressLog, EgressPolicy, Mode, set_gate


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ZARAM_DATA_DIR", str(tmp_path))
    import core.paths as paths

    for cache in ("_data_dir", "_DATA_DIR"):
        if hasattr(paths, cache):
            monkeypatch.setattr(paths, cache, None, raising=False)

    from providers import api, cloud_config

    monkeypatch.setattr(cloud_config, "_connections", {}, raising=False)
    monkeypatch.setattr(cloud_config, "_providers_runtime", None, raising=False)
    monkeypatch.setattr(cloud_config, "_reload_engine", lambda: None, raising=False)
    monkeypatch.setattr(cloud_config, "_register_adapter", lambda c: None, raising=False)

    policy = EgressPolicy(str(tmp_path / "policy.json"))
    set_gate(EgressGate(EgressLog(str(tmp_path / "egress.db")), policy))
    app = FastAPI()
    app.include_router(api.router)
    try:
        yield TestClient(app), policy
    finally:
        set_gate(None)


def _connect(client, **body):
    return client.post("/providers/cloud", json=body, headers={"X-Zaram-Client": "zaram-desktop"})


class TestPastingAKeyIsTheDecision:
    def test_the_connected_host_may_receive_prompts(self, client):
        c, policy = client
        assert not policy.has_rule("integrate.api.nvidia.com")
        r = _connect(c, provider_id="nvidia_nim", api_key="nvapi-not-a-real-key")
        assert r.status_code == 200, r.text
        assert policy.has_rule("integrate.api.nvidia.com", DataClass.PROMPT)
        assert policy.rules()["integrate.api.nvidia.com"] == Mode.ALLOW.value

    def test_only_prompts_an_image_is_its_own_consent(self, client):
        c, policy = client
        _connect(c, provider_id="openrouter", api_key="a-key")
        assert policy.has_rule("openrouter.ai", DataClass.PROMPT)
        assert not policy.has_rule("openrouter.ai", DataClass.IMAGE)

    def test_a_host_the_person_denied_stays_denied(self, client):
        c, policy = client
        policy.set("api.groq.com", Mode.DENY, DataClass.PROMPT)
        _connect(c, provider_id="groq", api_key="gsk-not-real")
        assert policy.rules()["api.groq.com"] == Mode.DENY.value

    def test_a_loopback_server_gets_no_rule(self, client):
        c, policy = client
        r = _connect(c, provider_id="lm_studio")
        assert r.status_code == 200, r.text
        assert policy.rules() == {}
