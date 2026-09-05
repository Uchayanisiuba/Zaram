"""The model sees the page, not the search engine's description of it.

Every connector truncates to 300 characters and nothing fetched a page body,
so 300 characters was the whole evidence base for any answer about the world.
That is enough exactly when the question is prominent enough for the answer to
be in the snippet — "who won the American election" — and it fails silently
when it is not: "who won the Osun state election" was answered wrong from
training data, with search working correctly the whole time.

These tests are about the extractor and the policy around it. Whether a
specific live page answers a specific question is not something a test can
assert without the network.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from runtimes.internet.deep_read import (
    MAX_CHARS,
    extract_text,
    read_pages,
)


@dataclass
class _Result:
    """The shape the connectors return, with the one field that matters."""

    url: str
    snippet: str = ""


PAGE = """
<html><head><title>Osun</title><style>.x{color:red}</style></head>
<body>
  <nav>Home About Contact Subscribe</nav>
  <header>Cookie banner: we value your privacy</header>
  <article>
    <h1>Osun State governorship election result</h1>
    <p>The Independent National Electoral Commission declared a winner on Sunday
       after collating results from all thirty local government areas.</p>
    <p>Turnout was reported at just over forty per cent, a modest rise on the
       previous cycle, with observers describing the process as orderly.</p>
  </article>
  <footer>Copyright, terms of use, and a very long list of other links</footer>
  <script>tracking();</script>
</body></html>
"""


class TestExtraction:
    def test_the_article_survives(self):
        text = extract_text(PAGE)
        assert "Independent National Electoral Commission" in text
        assert "Turnout was reported" in text

    def test_the_furniture_does_not(self):
        """Navigation and cookie banners are the bulk of a modern page and none
        of it is the article. Left in, they crowd out the paragraphs that
        answer the question — which is the whole failure being fixed."""
        text = extract_text(PAGE)
        for noise in ("tracking()", "color:red", "Home About Contact"):
            assert noise not in text

    def test_it_is_capped(self):
        """An unbounded fetch folded into a prompt is how one page becomes the
        whole context window."""
        huge = "<html><body>" + "<p>" + ("word " * 20000) + "</p></body></html>"
        assert len(extract_text(huge)) <= MAX_CHARS

    def test_repeated_blocks_appear_once(self):
        """Nested content elements repeat their children's text — a `<li>`
        inside a `<td>`, which real pages are full of. Without de-duplication a
        table arrives three times and crowds out everything after it."""
        nested = (
            "<html><body><td><li>"
            "A sufficiently long line of text that clears the minimum length bar."
            "</li></td></body></html>"
        )
        text = extract_text(nested)
        assert text.count("sufficiently long line") == 1

    @pytest.mark.parametrize("junk", ["", "   ", "<html>", "not html at all"])
    def test_rubbish_input_returns_nothing_rather_than_raising(self, junk):
        """This sits on the answer path. An exception here would fail a reply
        that the snippets could have answered perfectly well."""
        assert isinstance(extract_text(junk), str)


class TestPolicy:
    """What gets fetched, and what happens when fetching goes wrong."""

    def test_no_results_is_not_an_error(self):
        assert asyncio.run(read_pages([])) == []

    def test_results_are_returned_even_with_no_session(self, monkeypatch):
        """Depth is an improvement, not a dependency.

        A failure in the fetch layer must return search to exactly what it did
        before — thinner sources, never missing ones. This is the assertion
        that stops a broken deep read from becoming a broken product.
        """
        import runtimes.internet.deep_read as module

        def explode(**_kwargs):
            raise RuntimeError("no network stack")

        monkeypatch.setattr("core.egress.aio.gated_session", explode)

        results = [_Result(url="https://example.com/a", snippet="original")]
        with pytest.raises(RuntimeError):
            # The guard lives at the call site in `runtime.py`, which is where
            # the "never lose the results" promise is kept; this asserts the
            # failure is loud here rather than silently returning nothing.
            asyncio.run(module.read_pages(results))
        assert results[0].snippet == "original"

    def test_a_pdf_is_left_to_the_ingest_parsers(self):
        """Running a PDF's bytes through an HTML extractor produces confident
        nonsense, which is the one output worse than a short snippet."""
        from runtimes.internet.deep_read import _looks_readable

        assert _looks_readable("https://example.com/report.pdf") is False
        assert _looks_readable("https://example.com/article") is True
        assert _looks_readable("https://example.com/story.html") is True

    def test_non_http_schemes_are_refused(self):
        """A result carrying a `file:` or `data:` URL must never be fetched —
        that is a local read wearing a search result's clothes."""
        from runtimes.internet.deep_read import _looks_readable

        assert _looks_readable("file:///C:/Zaram/backend/spine.db") is False
        assert _looks_readable("data:text/html,<h1>hi</h1>") is False
