"""A page a model wrote is run, once, somewhere it can be killed.

5 October 2026: a game the resident model wrote froze the window on its first
line of work -- twenty-three loops with no `++` -- and the maintainer was the
first to run it. These tests launch a real browser, like
`test_zaram_can_drive_its_own_app.py`, and are skipped only where there is none.
"""

from __future__ import annotations

import http.server
import threading

import pytest

from core.page_check import check_page
from packs.code.apps import find_browser

pytestmark = pytest.mark.skipif(
    find_browser() is None, reason="no Chrome or Edge on this machine to run a page in"
)

#: Short, so the suite is not made to wait fourteen seconds for a hang.
FAST = dict(settle_seconds=1.5, hang_budget_seconds=6.0)


def page(script: str) -> str:
    return f"<!doctype html><html><body><canvas id=c></canvas><script>{script}</script></body></html>"


def test_a_page_that_works_is_ok():
    verdict = check_page(page("var n=0;for(var i=0;i<1000;i++){n+=i}document.title=String(n)"), **FAST)
    assert verdict.checked and verdict.ok is True
    assert not verdict.hung and verdict.errors == []


def test_a_loop_that_never_ends_is_a_hang_and_the_check_still_returns():
    # The exact mistake from the page that started this: the counter is never
    # increased. The check has to come back, not freeze with the page.
    verdict = check_page(page("for(let i=0;i<16;i){ }"), **FAST)
    assert verdict.checked and verdict.ok is False
    assert verdict.hung is True
    assert any("never recovered" in p for p in verdict.problems())


def test_an_error_is_reported_with_what_it_said():
    verdict = check_page(page("startTheGame();"), **FAST)
    assert verdict.ok is False and not verdict.hung
    assert any("startTheGame" in e for e in verdict.errors)


def test_a_rejected_promise_and_a_console_error_are_errors_too():
    verdict = check_page(
        page("Promise.reject(new Error('no level'));console.error('world failed')"), **FAST
    )
    assert verdict.ok is False
    joined = " ".join(verdict.errors)
    assert "no level" in joined and "world failed" in joined


def test_a_slow_start_that_finishes_is_ok_and_is_reported_with_its_length():
    verdict = check_page(
        page("var t=Date.now();while(Date.now()-t<3500){}"),
        settle_seconds=1.5,
        hang_budget_seconds=12.0,
    )
    assert verdict.ok is True and not verdict.hung
    assert verdict.blocked_seconds >= 3.0
    assert "held still" in verdict.note


def test_a_graphics_message_is_set_aside_not_blamed_on_the_page():
    verdict = check_page(page("console.error('Error creating WebGL context.')"), **FAST)
    assert verdict.ok is True
    assert any("WebGL" in i for i in verdict.ignored)


def test_the_page_runs_in_a_sealed_frame():
    # An opaque origin: reading storage throws unless the page's own shim ran.
    verdict = check_page(page("try{localStorage.getItem('x');throw new Error('same-origin')}catch(e){if(e.message==='same-origin')throw e}"), **FAST)
    assert verdict.ok is True


def test_nothing_the_page_asks_for_leaves_the_machine():
    # A page with no policy of its own, asking a listening server for an image.
    # Loopback is the strictest place to prove it: it is the one address a
    # browser normally bypasses its proxy for.
    hits: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        port = server.server_address[1]
        check_page(page(f"new Image().src='http://127.0.0.1:{port}/beacon';fetch('http://127.0.0.1:{port}/f',{{mode:'no-cors'}}).catch(function(){{}})"), **FAST)
    finally:
        server.shutdown()
    assert hits == []


def test_an_empty_or_oversized_page_is_unchecked_not_ok():
    for doc in ("", "   "):
        v = check_page(doc)
        assert v.checked is False and v.ok is None and v.note
    big = check_page("x" * (9 * 1024 * 1024))
    assert big.checked is False and big.ok is None


def test_no_browser_is_unchecked_not_ok(monkeypatch):
    monkeypatch.setattr("core.page_check.find_browser", lambda: None)
    v = check_page(page("1"))
    assert v.checked is False and v.ok is None
    assert "Chrome" in v.note


def test_a_browser_that_will_not_clean_up_does_not_take_the_verdict_with_it(monkeypatch):
    # Found running the real Voxel World through the check: a hung renderer held
    # the profile open, the cleanup raised, and the traceback replaced the
    # verdict. Cleanup failing is a nuisance, never the answer.
    from packs.code.driving import DrivingTools

    real_shut = DrivingTools._shut

    def broken(self, session):
        # The browser really is shut -- a test that left one running per run
        # leaked a browser tree every time the suite ran -- and then the
        # cleanup reports that it could not finish.
        real_shut(self, session)
        raise PermissionError("the profile is in use")

    monkeypatch.setattr(DrivingTools, "_shut", broken)
    verdict = check_page(page("var a = 1;"), **FAST)
    assert verdict.checked and verdict.ok is True
