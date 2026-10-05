"""Browsing had a standing answer in the policy and no way to change it.

`EgressPolicy.set_class_default` landed on 3 October and the browser pane reads
the result, but no route called it -- so the pane was refused by default and the
control that could change that lived only in a Python object. This is the route,
and the tests are mostly about what it must still refuse.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.egress import DataClass, EgressPolicy


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    import core.egress as egress_pkg

    policy = EgressPolicy(str(tmp_path / "policy.json"))
    monkeypatch.setattr(
        egress_pkg,
        "get_gate",
        lambda: SimpleNamespace(policy=policy, log=SimpleNamespace(hosts=lambda: [])),
        raising=False,
    )
    from main import app

    return TestClient(app), policy


def test_turning_it_on_sets_the_standing_answer(client):
    http, policy = client
    assert http.put("/egress/class-default", json={"data_class": "browse", "allow": True}).status_code == 200
    assert policy.class_default(DataClass.BROWSE).value == "allow"


def test_turning_it_off_removes_the_answer(client):
    http, policy = client
    http.put("/egress/class-default", json={"data_class": "browse", "allow": True})
    http.put("/egress/class-default", json={"data_class": "browse", "allow": False})
    assert policy.class_default(DataClass.BROWSE) is None


def test_the_spine_cannot_be_given_a_standing_allow(client):
    """The one write that could delete rule 7j's hard stop. Refused in the
    policy, surfaced as a 400 with the policy's own sentence."""
    http, policy = client
    response = http.put("/egress/class-default", json={"data_class": "spine", "allow": True})
    assert response.status_code == 400
    assert "hard stop" in response.json()["detail"]
    assert policy.class_default(DataClass.SPINE) is None


def test_prompts_cannot_either(client):
    http, _ = client
    assert http.put("/egress/class-default", json={"data_class": "prompt", "allow": True}).status_code == 400


def test_an_unknown_class_is_named_not_defaulted(client):
    http, _ = client
    response = http.put("/egress/class-default", json={"data_class": "telepathy", "allow": True})
    assert response.status_code == 400
    assert "browse" in response.json()["detail"]
