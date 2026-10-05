"""A repository is the largest thing Zaram can send, so it is its own class.

`docs/MILESTONES.md` recorded the reasoning before the GitHub work: it cannot
ride on `PROMPT`, on `IMAGE` or on a generic tool grant. These tests assert the
shape `IMAGE` already has -- and, as importantly, what `REPO` must *not* have.
"""

from __future__ import annotations

import pytest

from core.egress import DataClass, EgressPolicy, Mode

HOST = "github.com"


@pytest.fixture
def policy(tmp_path):
    return EgressPolicy(str(tmp_path / "policy.json"))


def test_it_is_denied_for_a_host_nobody_mentioned(policy):
    assert policy.decide(HOST, DataClass.REPO).mode is Mode.DENY


def test_connecting_the_host_does_not_grant_it(policy):
    """Allowing github.com for reading a page is not allowing a push to it.
    The first push is a separate decision, asked on the request itself."""
    policy.set(HOST, Mode.ALLOW)
    decision = policy.decide(HOST, DataClass.REPO)
    assert decision.mode is Mode.ASK
    assert decision.remember is True
    assert "repos" in decision.reason


def test_the_grant_is_per_host_and_per_class(policy):
    policy.set(HOST, Mode.ALLOW, DataClass.REPO)
    assert policy.decide(HOST, DataClass.REPO).mode is Mode.ALLOW
    assert policy.decide("gitlab.com", DataClass.REPO).mode is Mode.DENY
    # And it does not widen what the host receives of anything else.
    assert policy.decide(HOST, DataClass.IMAGE).mode is not Mode.ALLOW
    assert policy.decide(HOST, DataClass.SPINE).mode is not Mode.ALLOW


def test_a_blocked_host_stays_blocked_even_with_a_repo_grant(policy):
    policy.set(HOST, Mode.ALLOW, DataClass.REPO)
    policy.set(HOST, Mode.DENY)
    assert policy.decide(HOST, DataClass.REPO).mode is Mode.DENY


def test_there_is_no_standing_allow_for_pushing_anywhere(policy):
    """The same refusal the Spine has, and for the same reason: a class-wide
    allow is the hard stop turned into a checkbox."""
    with pytest.raises(ValueError):
        policy.set_class_default(DataClass.REPO, Mode.ALLOW)
    assert policy.class_default(DataClass.REPO) is None


def test_the_kill_switch_still_wins(policy):
    policy.set(HOST, Mode.ALLOW, DataClass.REPO)
    policy.set_kill_switch(True)
    assert policy.decide(HOST, DataClass.REPO).mode is Mode.DENY


def test_the_grant_survives_a_restart(tmp_path):
    path = str(tmp_path / "policy.json")
    EgressPolicy(path).set(HOST, Mode.ALLOW, DataClass.REPO)
    assert EgressPolicy(path).decide(HOST, DataClass.REPO).mode is Mode.ALLOW


def test_the_route_accepts_it_as_a_class(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    import core.egress as egress_pkg

    policy = EgressPolicy(str(tmp_path / "p.json"))
    monkeypatch.setattr(
        egress_pkg, "get_gate",
        lambda: SimpleNamespace(policy=policy, log=SimpleNamespace(hosts=lambda: [])),
        raising=False,
    )
    from main import app

    response = TestClient(app).put(
        "/egress/policy", json={"host": HOST, "mode": "allow", "data_class": "repo"}
    )
    assert response.status_code == 200
    assert policy.decide(HOST, DataClass.REPO).mode is Mode.ALLOW
