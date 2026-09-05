"""What the Spine holds that should never have entered it.

The door check is fixed — `test_prompts_are_not_facts.py` — but a Spine that
was filling up before the fix still holds the results. Those are not inert:
recall reaches them, so they come back as citations in new answers. Measured on
a live question about AI news, three of the ten sources behind the reply were
the user's own old prompts.

`GET /memory/traffic` proposes and never applies, which is the whole design.
Rule 4 gives the user authority over stored facts, and a sweep that deleted
them would be the wrong shape even when every deletion is correct.
"""

from __future__ import annotations

import importlib

import pytest
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    main = importlib.import_module("main")
    return TestClient(main.app)


def test_the_route_is_served_by_the_real_app(client):
    """The reachability check this codebase has needed nine times.

    A sweep nothing serves is a sweep that does not exist, however well its
    predicate is tested.
    """
    response = client.get("/memory/traffic")
    assert response.status_code in (200, 503), response.status_code


def test_it_proposes_and_changes_nothing(client):
    """Read-only, asserted by counting before and after.

    A future edit that made this delete would be a background job removing the
    user's facts, which is precisely what `/memory/maintenance` already refuses
    to be.
    """
    before = client.get("/memory")
    first = client.get("/memory/traffic")
    if first.status_code == 503:
        pytest.skip("no memory runtime in this process — nothing to sweep")

    client.get("/memory/traffic")
    after = client.get("/memory")

    assert before.status_code == after.status_code
    if before.status_code == 200:
        def count(payload):
            body = payload.json()
            rows = body.get("records") or body.get("memories") or body.get("results") or []
            return len(rows)

        assert count(before) == count(after), "the sweep removed something"


def test_the_payload_says_nothing_was_changed(client):
    """The wording is load-bearing.

    A bare count invites a "delete all" button, and that button is what rule 4
    exists to prevent. The response says what it found and how the user removes
    it, one fact at a time.
    """
    response = client.get("/memory/traffic")
    if response.status_code == 503:
        pytest.skip("no memory runtime in this process")

    body = response.json()
    assert "traffic" in body
    assert isinstance(body["traffic"], list)
    assert "Nothing has been changed" in body["note"]
    assert "DELETE /memory/" in body["note"]


def test_it_uses_the_same_predicate_as_the_door(client):
    """Two answers to one question is the failure this codebase keeps paying
    for. The sweep must not carry its own copy of "is this a fact"."""
    import inspect

    import main

    source = inspect.getsource(main.memory_traffic)
    assert "_carries_new_information" in source, (
        "the sweep has grown its own idea of what a fact is; it must reuse the "
        "predicate the door uses, or the two will disagree"
    )
