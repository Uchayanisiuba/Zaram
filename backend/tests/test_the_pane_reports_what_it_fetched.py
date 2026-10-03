"""The browser pane's requests reach the egress log.

Built 3 October 2026 with the pane itself.

**This route exists because `EgressGate` cannot see these requests.** The
gate intercepts what the *backend* sends; a `BrowserView` is a separate
Chromium process fetching directly, so nothing it does passes through Python
at all. Rule 3 — *every byte that leaves is logged* — stops being satisfied
by the backend alone the moment the product has a browser in it, and the
only place that can see these is the Electron session making them.

`CLAUDE.md` names this exact shape already, for a VRM's `uri` fetches: *"a
request `EgressGate` cannot see, since that intercepts what the backend
sends"*. Same hole, second instance, closed where it can be.

The route records and does not decide. Whether a page may be opened is
settled before the request is made — `electron/services/browserPolicy.js`
has the shape and 42 tests — and a recorder that could also refuse would be
a second gate free to disagree with the first.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture()
def client():
    return TestClient(main.app)


def entries_for(client, host):
    rows = client.get("/egress").json()
    items = rows.get("entries", rows) if isinstance(rows, dict) else rows
    return [e for e in items if e.get("host") == host]


class TestItRecords:
    def test_a_browsed_page_lands_in_the_log(self, client):
        response = client.post(
            "/egress/browse", json={"host": "en.wikipedia.org", "path": "/wiki/Lagos"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["recorded"] is True
        assert entries_for(client, "en.wikipedia.org")

    def test_a_sub_resource_nobody_chose_is_recorded_too(self, client):
        """The reason the class exists. One news page is sixty requests to
        companies the person never picked, and those are the rows the log is
        for."""
        client.post(
            "/egress/browse",
            json={
                "host": "ads.doubleclick.net",
                "path": "/beacon.gif",
                "initiator": "https://news.example.com/story",
            },
        )
        found = entries_for(client, "ads.doubleclick.net")
        assert found, "a sub-resource was not recorded"

    def test_it_says_which_page_pulled_it_in(self, client):
        client.post(
            "/egress/browse",
            json={"host": "fonts.gstatic.com", "path": "/x.woff2",
                  "initiator": "https://news.example.com/story"},
        )
        found = entries_for(client, "fonts.gstatic.com")[-1]
        meta = found.get("meta") or {}
        assert "news.example.com" in str(meta.get("initiator", "")), meta

    def test_it_is_marked_as_browsing(self, client):
        client.post("/egress/browse", json={"host": "example.org", "path": "/"})
        found = entries_for(client, "example.org")[-1]
        assert found.get("source") == "browser-pane"


class TestWhatItWillNotWriteDown:
    def test_a_query_string_in_the_path_is_dropped(self, client):
        """It carries what somebody searched for, and the log is read on
        screen and pasted into support threads. The caller strips it; this
        strips it again, because the one that forgets is the one that
        matters."""
        client.post(
            "/egress/browse",
            json={"host": "search.example.com", "path": "/find?q=my+medical+question"},
        )
        found = entries_for(client, "search.example.com")[-1]
        assert "medical" not in str(found), found

    def test_a_fragment_goes_too(self, client):
        client.post("/egress/browse", json={"host": "docs.example.com", "path": "/a#secret-note"})
        found = entries_for(client, "docs.example.com")[-1]
        assert "secret-note" not in str(found)

    def test_a_request_with_no_host_is_refused(self, client):
        assert client.post("/egress/browse", json={"host": "  "}).status_code == 400


class TestTheStandingAnswerIsReadable:
    """The pane has to know whether browsing is allowed before it opens a
    page, and `GET /egress/policy` is where it looks."""

    def test_the_policy_reports_class_defaults(self, client):
        body = client.get("/egress/policy").json()
        assert "class_defaults" in body, (
            "the browser pane reads this to know whether it may open a page"
        )
        assert isinstance(body["class_defaults"], dict)

    def test_an_unset_class_is_absent_rather_than_null(self, client):
        """Absent means "no standing answer", which is not the same as a
        standing answer of deny — one is "nobody has said", the other is
        "somebody said no"."""
        defaults = client.get("/egress/policy").json()["class_defaults"]
        assert all(v is not None for v in defaults.values())

    def test_the_spine_never_appears_there(self, client):
        """`set_class_default` refuses it, and this is the second place that
        would show it if the refusal were ever removed. The hard stop
        CLAUDE.md keeps by name is the first time Spine facts go to a
        destination that has not had them."""
        assert "spine" not in client.get("/egress/policy").json()["class_defaults"]
