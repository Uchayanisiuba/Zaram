"""Zaram presses the button itself — slice 9 of the code pack.

`look_at_app` takes one screenshot of one URL, which is enough to check a
layout and not enough to check a behaviour. The states that hold defects are
several interactions deep — open the panel, choose a type, fill a field,
press the button — and no URL reaches them. Asked for on 3 October 2026,
after a bug was found exactly that way by hand.

**This test launches a real browser and drives a real page.** It is slower
than a stubbed protocol and it is the only version worth having: every
interesting failure here is in the join between Chrome and the code —
whether a dispatched event reaches a framework's handler, whether a ref
survives a re-render, whether reading races the load. A fake answers all
three the way the author expected. The spike that preceded this module hit
the third one immediately.

Skipped, not failed, where no Chrome or Edge is installed: that is a fact
about the machine and the capability says so for itself at runtime.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from packs.code.apps import find_browser
from packs.code.driving import (
    CLICK_IN_APP,
    CLOSE_BROWSER,
    MUTATIVE,
    OPEN_IN_BROWSER,
    READ_APP_CONSOLE,
    READ_APP_PAGE,
    TOOL_NAMES,
    TYPE_IN_APP,
    DrivingTools,
)

pytestmark = pytest.mark.skipif(
    find_browser() is None, reason="no Chrome or Edge on this machine to drive"
)

PAGE = b"""<!doctype html><html><body>
<h1>Driveable</h1>
<button id="go" onclick="document.getElementById('out').textContent='pressed'">Press me</button>
<button id="nope" disabled>Cannot</button>
<input id="folder" placeholder="repository folder" value="old value">
<p id="out">not yet</p>
<script>
  console.log('page loaded');
  console.error('something went wrong');
</script>
</body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server's interface
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *_a):
        """Silent. The server's own logging is not this test's output."""


@pytest.fixture(scope="module")
def served():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


QUIET = b"<!doctype html><html><body><p>nothing to say</p></body></html>"


class _QuietHandler(_Handler):
    """A page that logs nothing, so the empty-console note has something true
    to be asserted against."""

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(QUIET)))
        self.end_headers()
        self.wfile.write(QUIET)


@pytest.fixture(scope="module")
def quiet():
    server = HTTPServer(("127.0.0.1", 0), _QuietHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


@pytest.fixture(scope="module")
def _shared():
    """One browser for the reading and acting tests.

    Launched once rather than per test. Each launch is a real Chrome, and a
    dozen of them starting and stopping inside one file is both slow and
    unstable on Windows — the previous process's handles outlive it, so the
    next launch contends with a profile that is still being deleted. Tests
    that are *about* the session lifecycle use `driving` below and get their
    own instance.
    """
    tools = DrivingTools()
    yield tools
    tools.close_all()


@pytest.fixture
def opened(_shared, served):
    """The shared browser, back at a freshly loaded page.

    Re-opening resets whatever the last test clicked, so order does not
    matter and a failure is about the test that reports it.
    """
    page = _shared.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
    assert "error" not in page, page
    return _shared


@pytest.fixture
def driving():
    """A browser of this test's own, for the lifecycle assertions."""
    tools = DrivingTools()
    yield tools
    tools.close_all()


ROOT = Path("C:/project") if Path("C:/").exists() else Path("/project")


def ref_for(page: dict, name: str) -> str:
    """The ref of the element whose label contains `name`."""
    for element in page["elements"]:
        if name.lower() in (element.get("name") or "").lower():
            return element["ref"]
    raise AssertionError(f"no element named {name!r} in {page['elements']}")


class TestItRefusesWhatIsNotYours:
    """The boundary, asserted before anything that proves the capability.

    Loopback is not a setting here. The moment this drives a page on the open
    web it stops being "look at your own app" and becomes a browser agent,
    which is a different product with an egress story this one has not got.
    """

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com",
            "http://example.com",
            # The shapes `_is_loopback` was written against: something that
            # merely begins with a loopback-looking string.
            "http://127.0.0.1.evil.test/",
            "http://localhost@evil.test/",
        ],
    )
    def test_only_localhost_is_driven(self, driving, url):
        out = driving.call(OPEN_IN_BROWSER, {"url": url}, ROOT)
        assert "error" in out
        assert "localhost" in out["error"]

    def test_nothing_acts_before_a_page_is_open(self, driving):
        for name in (READ_APP_PAGE, CLICK_IN_APP, TYPE_IN_APP, READ_APP_CONSOLE):
            out = driving.call(name, {"ref": "e1", "text": "x"}, ROOT)
            assert "error" in out, name
            assert OPEN_IN_BROWSER in out["error"]


class TestItReadsThePage:
    def test_it_lists_what_can_be_acted_on(self, opened, served):
        page = opened.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        assert "error" not in page, page
        names = [e["name"] for e in page["elements"]]
        assert "Press me" in names
        assert "Cannot" in names

    def test_it_says_which_element_is_disabled(self, opened, served):
        """The fact a screenshot cannot give you.

        A greyed rectangle is something a vision model guesses at; this is
        the difference between "the button did nothing" being a defect and
        being the answer.
        """
        page = opened.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        by_name = {e["name"]: e for e in page["elements"]}
        assert by_name["Cannot"]["disabled"] is True
        assert by_name["Press me"]["disabled"] is False

    def test_it_carries_what_a_field_already_holds(self, opened, served):
        page = opened.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        field = next(e for e in page["elements"] if e["tag"] == "input")
        assert field["value"] == "old value"

    def test_it_carries_the_visible_text(self, opened, served):
        page = opened.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        assert "Driveable" in page["text"]
        assert "not yet" in page["text"]


class TestItActs:
    def test_a_click_changes_the_page(self, opened, served):
        page = opened.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        assert "not yet" in page["text"]

        after = opened.call(CLICK_IN_APP, {"ref": ref_for(page, "Press me")}, ROOT)

        assert "error" not in after, after
        # The page afterwards is the answer, so checking the work costs no
        # second call.
        assert "pressed" in after["text"]
        assert "not yet" not in after["text"]

    def test_typing_replaces_rather_than_appends(self, opened, served):
        """What a person means by "type the folder in".

        Appending is what a naive insert does, and it is worst on a retry —
        the second attempt silently produces a path made of two paths.
        """
        page = opened.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        ref = next(e["ref"] for e in page["elements"] if e["tag"] == "input")

        after = opened.call(TYPE_IN_APP, {"ref": ref, "text": "C:/RideShare"}, ROOT)

        assert "error" not in after, after
        field = next(e for e in after["elements"] if e["ref"] == ref)
        assert field["value"] == "C:/RideShare"

    def test_it_refuses_a_disabled_element_rather_than_clicking_nothing(self, opened, served):
        """Said, not swallowed.

        A disabled control eats the event and leaves the page identical,
        which reads to a model exactly like a real defect — so it goes
        hunting for a bug that is not there. Naming it is the whole value.
        """
        page = opened.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        out = opened.call(CLICK_IN_APP, {"ref": ref_for(page, "Cannot")}, ROOT)
        assert "error" in out
        assert "disabled" in out["error"]

    def test_a_ref_from_a_page_that_has_moved_on_fails_loudly(self, opened, served):
        """Never resolve to whatever is at those coordinates now.

        A ref is stamped on the element by the read and a re-render drops it.
        Falling back to coordinates would click the thing that happens to
        have slid into that spot, which is the failure that teaches somebody
        to distrust the whole tool.
        """
        opened.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        out = opened.call(CLICK_IN_APP, {"ref": "e999"}, ROOT)
        assert "error" in out
        assert "read the page again" in out["error"].lower()


class TestItReadsTheConsole:
    def test_it_captures_what_the_page_logged(self, opened, served):
        """Including what was logged before anything attached.

        The recorder is installed with `addScriptToEvaluateOnNewDocument`, so
        it is in place before the page's own scripts run. A listener attached
        afterwards would miss the load-time error, which is the one that
        matters most.
        """
        opened.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        out = opened.call(READ_APP_CONSOLE, {}, ROOT)

        assert "error" not in out, out
        text = json.dumps(out["lines"])
        assert "page loaded" in text
        assert "something went wrong" in text
        assert out["errors"] == 1

    def test_an_empty_console_says_so(self, _shared, quiet):
        """An empty list and a recorder that never ran look identical.

        From the model's side both are `[]`, and only one of them means "the
        page is fine". The note is what tells them apart, so it is asserted
        against a page that genuinely logs nothing rather than assumed.
        """
        _shared.call(OPEN_IN_BROWSER, {"url": quiet}, ROOT)
        out = _shared.call(READ_APP_CONSOLE, {}, ROOT)

        assert out["lines"] == []
        assert out["errors"] == 0
        assert "nothing has been logged" in out["note"]


class TestTheSession:
    def test_one_browser_per_project_and_it_closes(self, driving, served):
        driving.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        assert len(driving._sessions) == 1

        closed = driving.call(CLOSE_BROWSER, {}, ROOT)
        assert closed["closed"] is True
        assert driving._sessions == {}

    def test_opening_twice_reuses_the_browser(self, driving, served):
        """A second browser per project is a state nobody can reason about
        from a transcript, and two dev sessions on one app is a bug report
        waiting to be filed against the wrong thing."""
        driving.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        first = driving._sessions[str(ROOT)].process.pid

        driving.call(OPEN_IN_BROWSER, {"url": served}, ROOT)

        assert len(driving._sessions) == 1
        assert driving._sessions[str(ROOT)].process.pid == first

    def test_closing_what_was_never_open_is_not_an_error(self, driving):
        out = driving.call(CLOSE_BROWSER, {}, ROOT)
        assert out["closed"] is False
        assert "no page was open" in out["note"]

    def test_the_browser_brings_none_of_the_persons_sign_ins(self, driving, served):
        """A profile of its own, every time.

        Driving a dev app that shares a domain with something the person is
        signed into must not be able to act as them. The profile is a fresh
        temporary directory, so there is nothing to act with.
        """
        driving.call(OPEN_IN_BROWSER, {"url": served}, ROOT)
        profile = driving._sessions[str(ROOT)].profile
        assert "zaram-driving-" in profile
        assert Path(profile).exists()

        driving.call(CLOSE_BROWSER, {}, ROOT)
        # Taken with it, so nothing the dev app stored outlives the session.
        assert not Path(profile).exists()


class TestWhatTheTierTableSays:
    def test_acting_is_separated_from_looking(self):
        """Reading a loopback page Zaram started is what `look_at_app`
        already does. Pressing a button in it is not, and the tier table
        says so — so the two sets have to stay distinguishable in code
        rather than in a comment."""
        assert MUTATIVE == {CLICK_IN_APP, TYPE_IN_APP}
        assert MUTATIVE < TOOL_NAMES
        assert OPEN_IN_BROWSER not in MUTATIVE
        assert READ_APP_PAGE not in MUTATIVE
