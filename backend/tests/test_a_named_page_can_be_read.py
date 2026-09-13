"""`read_page`: a page the person names is read; one the model names meets the policy.

The maintainer typed *"pmnewsnigeria.com tell what on this page"* on 13
September 2026 and Zaram, honestly, said it could not reach the page.
`packs/web` is what can. Three contracts, each the interesting half of one
rule:

* **Rule 7j** — an address in the person's own message is a destination
  they chose, and travels on a grant of that exact URL past default-deny.
* **Third-party text never widens permission** — an address the model
  produces gets no grant and meets the per-host policy; a refusal is the
  tool's answer, in a sentence, not an exception.
* **Every byte is logged** — the fetch goes through the gate's own path,
  never a socket of its own, which `test_egress_chokepoint.py` enforces.

And the planner: a message that names a page takes the tool plan, ahead of
search, because the person asked for the page and not for a search about it.
"""

from __future__ import annotations

import pytest

from core.egress import EgressDenied
from core.egress.gate import SearchReadGrant
from core.planner import IntentPlanner
from packs.web import READ_PAGE, WebTools, set_named_urls
from packs.web.active import normalise, urls_in

PAGE = b"""<html><head><title>PM News</title></head><body>
<nav>Home Politics Sport</nav>
<h1>Osun election: tribunal upholds result</h1>
<p>The tribunal sitting in Osogbo upheld the governorship result on Tuesday.</p>
<p>Counsel for the petitioners said they would appeal.</p>
<footer>Copyright</footer></body></html>"""


class TestAddressesInAMessage:
    def test_bare_hosts_and_full_urls_are_both_addresses(self):
        found = urls_in("pmnewsnigeria.com tell what is on this page, and https://Example.org/a/b?x=1#frag.")
        assert found == {"https://pmnewsnigeria.com", "https://example.org/a/b?x=1"}

    def test_a_filename_is_not_a_site(self):
        assert urls_in("fix calc.py and the tests in test_calc.py") == frozenset()

    def test_normalisation_agrees_with_itself(self):
        assert normalise("PMNewsNigeria.com/") == normalise("https://pmnewsnigeria.com") == "https://pmnewsnigeria.com"


def _fetch_recording(calls: list, *, deny_unnamed: bool):
    def fetch(url, grant):
        calls.append((url, grant))
        if grant is None and deny_unnamed:
            raise EgressDenied(f"no policy exists for {url}, and the default is to refuse", "somewhere.example")
        return PAGE
    return fetch


class TestTheGrant:
    def test_a_page_the_person_named_is_read_on_a_grant_of_that_url(self):
        calls: list = []
        set_named_urls("pmnewsnigeria.com tell me what is on this page")
        result = WebTools(fetch=_fetch_recording(calls, deny_unnamed=True)).call_tool(READ_PAGE, {"url": "pmnewsnigeria.com"})
        (url, grant) = calls[0]
        assert url == "https://pmnewsnigeria.com"
        assert isinstance(grant, SearchReadGrant) and grant.urls == {"https://pmnewsnigeria.com"}
        assert "you named" in grant.because  # the log names the consent, not a search
        assert result["named_by_person"] is True
        assert "upheld the governorship result" in result["text"]
        assert "Home Politics Sport" not in result["text"]  # the furniture is gone
        assert "Copyright" not in result["text"]

    def test_a_page_the_model_named_gets_no_grant_and_a_refusal_is_an_answer(self):
        calls: list = []
        set_named_urls("what happened in the Osun election?")
        result = WebTools(fetch=_fetch_recording(calls, deny_unnamed=True)).call_tool(READ_PAGE, {"url": "https://somewhere.example/osun"})
        assert calls[0][1] is None
        assert result["refused"] is True
        assert "did not open" in result["error"] and "Settings" in result["error"]
        assert "text" not in result

    def test_a_page_the_model_named_is_read_when_the_policy_allows(self):
        calls: list = []
        set_named_urls("nothing named here")
        result = WebTools(fetch=_fetch_recording(calls, deny_unnamed=False)).call_tool(READ_PAGE, {"url": "https://allowed.example/x"})
        assert result["named_by_person"] is False
        assert "tribunal" in result["text"]

    def test_the_real_fetch_is_the_gates_own_path(self, monkeypatch):
        """No socket of its own: the tool asks the gate, with the grant."""
        seen: dict = {}

        class _Gate:
            def request(self, url, *, headers, timeout, source, grant, **kw):
                seen.update(url=url, source=source, grant=grant)
                return PAGE

        monkeypatch.setattr("core.egress.get_gate", lambda: _Gate())
        set_named_urls("read https://pmnewsnigeria.com/story please")
        WebTools().call_tool(READ_PAGE, {"url": "https://pmnewsnigeria.com/story"})
        assert seen["url"] == "https://pmnewsnigeria.com/story"
        assert seen["source"] == "web.read_page"
        assert seen["grant"].urls == {"https://pmnewsnigeria.com/story"}

    def test_a_page_with_no_prose_says_so(self):
        set_named_urls("app.example")
        result = WebTools(fetch=lambda u, g: b"<html><body><script>x()</script></body></html>").call_tool(READ_PAGE, {"url": "app.example"})
        assert "no readable text" in result["error"]


class TestThePlanner:
    def _ids(self, plan):
        return [s.capability_id for s in plan.steps]

    def test_a_message_naming_a_page_takes_the_tool_plan_ahead_of_search(self, monkeypatch):
        planner = IntentPlanner()
        monkeypatch.setattr("core.planner.needs_search", lambda p: True, raising=False)
        assert self._ids(planner.create_plan("pmnewsnigeria.com tell me what is on this page")) == [
            "mcp.list_tools", "reasoning.generate",
        ]

    def test_a_drawing_of_a_site_is_still_a_drawing(self):
        assert self._ids(IntentPlanner().create_plan("draw me a picture of bbc.com's homepage")) == ["image.generate"]

    def test_a_plain_question_is_unchanged(self):
        assert "mcp.list_tools" not in self._ids(IntentPlanner().create_plan("what does clause 4 say?"))


@pytest.mark.asyncio
async def test_read_page_is_offered_from_the_real_boot():
    from core.bootstrapper import KernelBootstrapper

    kernel = KernelBootstrapper()
    await kernel.boot()
    try:
        listed = await kernel.mcp_runtime.execute("mcp.list_tools", {"query": "read a web page"})
        offered = {(t["server"], t["name"]) for t in listed["tools"]}
    finally:
        await kernel.shutdown()
    assert ("web", READ_PAGE) in offered, sorted(offered)
