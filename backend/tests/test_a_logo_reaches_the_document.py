"""The user's logo, from upload to the top of a generated page.

Asked for by the maintainer on 4 September 2026: *"the user can attach their
logo and Zaram can use it in the header"*.

**Almost all of it already existed and none of it was reachable.**
`artifacts/letterhead.py` validates an upload, refuses SVG with a written
reason, bounds the size, and returns a `data:` URI; `_masthead` in `html.py`
renders that URI as an `<img class="logo">`; `word_theme.py` carries it into
Word. `Letterhead` was constructed in exactly two places in `main.py`, both
from per-request fields, both without a logo, under a comment saying where
branding is captured was still an open decision. It had been decided —
`docs/MILESTONES.md`, *"Where branding is captured"* — and never built.

That is sixteen for the count in `CLAUDE.md`: a complete, tested subsystem with
no caller. So the assertions here are deliberately end-to-end rather than
per-unit. `test_template_profile.py` and `test_artifact_exporters.py` already
prove the pieces work in isolation, and proving it again is exactly the kind of
green suite that let this sit unreachable in the first place.
"""

from __future__ import annotations

import base64
import json

import pytest

from artifacts.letterhead_store import LetterheadStore, set_letterhead_path

#: A 1x1 PNG. Small enough to inline, real enough that `logo_data_uri` accepts
#: it — the validator checks the declared type rather than sniffing, but a file
#: that is not an image would be a lie in the fixture.
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def client():
    """The real app, without booting the kernel.

    `TestClient(app)` rather than `with TestClient(app)`, for the reason
    `test_conversation_api.py` records: the context-manager form runs the
    lifespan and boots provider discovery, the Spine and a model preload — 23
    seconds for one test. These four routes need none of it.
    """
    from starlette.testclient import TestClient

    import main

    return TestClient(main.app)


@pytest.fixture
def store(tmp_path):
    """A store on a real file, pointed at by the singleton the routes use."""
    path = str(tmp_path / "letterhead.json")
    set_letterhead_path(path)
    yield LetterheadStore(path)
    set_letterhead_path("")


class TestTheStore:
    def test_nothing_configured_is_no_letterhead_rather_than_an_empty_one(self, store):
        """None and an empty object render differently, so they must stay
        different. `_masthead` gives None a titled document under a rule, and
        an empty `Letterhead` an empty branding block where the logo goes."""
        assert store.is_empty() is True
        assert store.as_letterhead() is None

    def test_it_survives_a_restart(self, store, tmp_path):
        store.set_identity(name="Northwind Studio", lines=["12 Dock Road", "Lagos"])
        store.set_logo("data:image/png;base64,AAAA")

        reopened = LetterheadStore(str(tmp_path / "letterhead.json"))
        assert reopened.name == "Northwind Studio"
        assert reopened.lines == ["12 Dock Road", "Lagos"]
        assert reopened.logo == "data:image/png;base64,AAAA"

    def test_absent_leaves_a_field_alone_and_empty_clears_it(self, store):
        """The `CharacterUpdate` contract, kept the same on purpose.

        Two stores in one product disagreeing about what `None` means is how a
        user ends up unable to remove a business name they mistyped.
        """
        store.set_identity(name="Northwind", lines=["12 Dock Road"])
        store.set_identity(name=None)
        assert store.name == "Northwind"
        store.set_identity(name="")
        assert store.name == ""
        assert store.lines == ["12 Dock Road"]

    def test_a_logo_edited_into_the_file_by_hand_cannot_point_at_the_internet(
        self, tmp_path
    ):
        """The one strict read, and the reason it is in the store.

        This value is interpolated into an `<img src>` in a document that gets
        sent to a client. `check-no-remote-assets.mjs` scans source and cannot
        see a JSON file, so a remote URL written into this file — by hand, or
        by anything else running as this user — has to be refused where it is
        read or not at all.
        """
        path = tmp_path / "letterhead.json"
        for hostile in (
            "https://tracker.example/pixel.png",
            "javascript:alert(1)",
            "data:text/html;base64,PHNjcmlwdD4=",
        ):
            path.write_text(json.dumps({"logo": hostile}), encoding="utf-8")
            assert LetterheadStore(str(path)).logo == ""

    def test_describe_does_not_carry_the_pixels(self, store):
        """Settings asks constantly whether a logo exists and never needs the
        megabyte to answer."""
        store.set_logo("data:image/png;base64," + "A" * 5000)
        described = store.describe()
        assert described["has_logo"] is True
        assert "logo" not in described


class TestTheRouteReachesTheStore:
    def test_an_uploaded_logo_is_validated_and_kept(self, client, store):
        response = client.post(
            "/letterhead/logo",
            json={
                "data": base64.b64encode(PNG_1PX).decode("ascii"),
                "content_type": "image/png",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["has_logo"] is True

        # Read from disk rather than from the fixture's own instance. The route
        # writes through the singleton, so the object this test happens to hold
        # is a second copy loaded before the request — and asserting on it would
        # be asserting that this test's variable changed, which it has no reason
        # to. Reopening the file proves the upload persisted, which is the thing
        # that actually has to be true after a restart.
        assert LetterheadStore(store._path).logo.startswith("data:image/png;base64,")

    def test_svg_is_refused_in_words_the_user_can_read(self, client, store):
        """The refusal text is the useful part and is passed through as-is.

        `logo_data_uri` explains that SVG can reference files from the internet
        and that a generated document must not fetch anything. A route that
        replaced that with a code would be throwing away the only sentence that
        tells the user what to do instead.
        """
        response = client.post(
            "/letterhead/logo",
            json={
                "data": base64.b64encode(b"<svg/>").decode("ascii"),
                "content_type": "image/svg+xml",
            },
        )
        assert response.status_code == 400
        assert "internet" in response.json()["detail"].lower()

    def test_the_identity_round_trips(self, client, store):
        response = client.put(
            "/letterhead", json={"name": "Northwind Studio", "lines": ["12 Dock Road"]}
        )
        assert response.status_code == 200, response.text
        assert client.get("/letterhead").json()["name"] == "Northwind Studio"

    def test_no_logo_is_an_ordinary_state_and_not_a_404(self, client, store):
        """A 404 here would put an error in the console of every user who has
        not set one, which is most of them on the first day."""
        response = client.get("/letterhead/logo")
        assert response.status_code == 200
        assert response.json()["logo"] == ""


class TestItReachesTheDocument:
    def test_a_generated_document_wears_the_stored_logo(self, store):
        """The assertion the sixteen unreachable subsystems would all have
        failed."""
        from artifacts.html import render_document

        store.set_identity(name="Northwind Studio", lines=["12 Dock Road"])
        store.set_logo("data:image/png;base64,AAAA")

        html = render_document(
            title="Customer Portal Rebuild",
            blocks=["Body text."],
            letterhead=store.as_letterhead(),
            kind_label="Proposal",
        )
        assert 'class="logo"' in html
        assert "data:image/png;base64,AAAA" in html
        assert "Northwind Studio" in html

    def test_a_request_that_names_a_business_still_wins(self, store):
        """Per-request beats stored, because someone trading under two names
        has to be able to say which one this document is from."""
        from main import _letterhead_for

        store.set_identity(name="Northwind Studio")
        chosen = _letterhead_for("Harbour Row Ltd", [])
        assert chosen.name == "Harbour Row Ltd"

    def test_a_request_that_names_nothing_gets_the_stored_one(self, store):
        """The half that was missing. Every document generated from chat comes
        through here with no `from_name`, which is why the logo never appeared
        on anything."""
        from main import _letterhead_for

        store.set_identity(name="Northwind Studio")
        store.set_logo("data:image/png;base64,AAAA")
        chosen = _letterhead_for("", [])
        assert chosen is not None
        assert chosen.name == "Northwind Studio"
        assert chosen.logo == "data:image/png;base64,AAAA"

    def test_nothing_configured_still_generates_a_document(self, store):
        """The absence of branding must not read as a rendering failure."""
        from main import _letterhead_for

        assert _letterhead_for("", []) is None
