"""Reading the page, not the search result's description of it.

**Why this exists.** Every connector truncates what it returns to 300
characters, and nothing anywhere fetched a page body — so 300 characters was
the entire evidence base for any answer Zaram gave about the world. That is
enough exactly when the question is prominent enough for the answer to be in
the search snippet, and it fails silently otherwise.

Measured on the maintainer's own questions, all four with search behaving as
designed:

    "Who won the American election?"      answer is in the snippet   -> right
    "Who won the Osun state election?"    answer is in the article   -> wrong

Same mechanism, different prominence. The model was not hallucinating in the
usual sense; it was handed three sentences that did not contain the answer, and
filled the gap from its weights. **A regional election is not a harder question
than a national one — it is a less quoted one**, and a product whose pitch is
provenance cannot be reliable only about famous things.

What this does not do
---------------------
**It does not decide what is true.** It widens the evidence, and the refusal
instruction in `_augment_with_sources` is what stops the model going beyond it.
More text makes that instruction usable; it does not make it optional.

**It fetches few pages, not many.** Three, in parallel, with a short timeout.
Reading ten would be slower than the answer is worth and would multiply the
egress for a question the first three usually settle. The cap is a product
decision about latency and disclosure, not a technical limit.

Every byte is logged
--------------------
Fetching a page is egress in exactly the sense rule 3 means, and more of it
than the search query was. It goes through `gated_session`, so the per-host
policy applies to the *page's* host — which is frequently not the search
engine's — and each fetch lands in the egress log. A host the user has not
allowed is refused here like anywhere else, and that refusal costs the answer
some evidence rather than costing the user a disclosure.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

__all__ = ["read_pages", "extract_text", "DEFAULT_LIMIT", "MAX_CHARS"]

#: How many results are read in full. Three covers the disagreement case — one
#: page can be wrong, two agreeing is worth something — without turning one
#: question into ten downloads.
DEFAULT_LIMIT = 3

#: Per page. Past this a document is a book, and the tail of it is not what the
#: question was about. Also a guard: an unbounded fetch into a prompt is how a
#: single page becomes the whole context window.
MAX_CHARS = 6000

#: A slow page must not hold up the answer. The snippet is still there, so the
#: cost of giving up is a thinner source rather than a missing one.
PER_PAGE_TIMEOUT = 6.0

#: Only these are worth fetching as HTML. A PDF or an image would need the
#: ingest parsers, which are a different layer with a different cost; sending
#: their bytes through an HTML extractor would produce confident nonsense,
#: which is the one output worse than a short snippet.
_READABLE_SUFFIXES = ("", ".htm", ".html", ".php", ".asp", ".aspx", ".jsp")

#: Stripped before any text is taken. Navigation and cookie banners are the
#: bulk of a modern page and none of it is the article — left in, they crowd
#: out the paragraphs that answer the question.
_NOISE = (
    "script", "style", "noscript", "nav", "header", "footer", "aside",
    "form", "button", "svg", "iframe", "template",
)

#: Where prose actually lives. Taken in document order so the result reads as
#: the page reads.
_CONTENT = ("p", "h1", "h2", "h3", "h4", "li", "blockquote", "td", "dd")


def _looks_readable(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    path = (parsed.path or "").lower().rstrip("/")
    suffix = path[path.rfind("."):] if "." in path.rsplit("/", 1)[-1] else ""
    return suffix in _READABLE_SUFFIXES


def extract_text(html: str, *, max_chars: int = MAX_CHARS) -> str:
    """The readable prose of a page, in document order.

    `lxml` rather than a regular expression or `html.parser`: real pages are
    malformed in ways that defeat both, and lxml's parser is the one already in
    `requirements.txt` for the ingest layer. BSD licensed, so it raises no
    question under the no-AGPL rule.

    Deliberately not a readability implementation. Scoring blocks by text
    density is a real improvement and a real dependency; taking every paragraph
    after removing the furniture gets most of the benefit, and its failure mode
    is *extra* text rather than a missing article — which is the right way round
    when the alternative is 300 characters.
    """
    if not html or not html.strip():
        return ""

    try:
        from lxml import html as lxml_html
    except ImportError:  # pragma: no cover - lxml is a declared dependency
        logger.warning("lxml unavailable; deep read is disabled")
        return ""

    try:
        tree = lxml_html.fromstring(html)
    except Exception:
        return ""

    for element in tree.iter(*_NOISE):
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)

    seen: set[str] = set()
    pieces: list[str] = []
    total = 0
    for element in tree.iter(*_CONTENT):
        text = " ".join((element.text_content() or "").split())
        # Nested content elements repeat their children's text — a <li> inside
        # a <td>, which real pages are full of. Without this a table of results
        # arrives three times and crowds out everything after it.
        if len(text) < 40 or text in seen:
            continue
        seen.add(text)
        pieces.append(text)
        total += len(text) + 1
        if total >= max_chars:
            break

    return "\n".join(pieces)[:max_chars]


async def _read_one(session: Any, result: Any) -> None:
    """Replace one result's snippet with its page text, or leave it alone."""
    url = getattr(result, "url", "") or ""
    if not _looks_readable(url):
        return

    try:
        async with session.get(url, timeout=PER_PAGE_TIMEOUT) as response:
            if response.status != 200:
                return
            # Some servers lie about content type on error pages; the extractor
            # returning nothing is the backstop, so this only skips the obvious.
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type and "html" not in content_type:
                return
            html = await response.text()
    except Exception as error:
        # A page that will not load costs this result its depth and nothing
        # else. Never let one slow server fail the answer — the snippet the
        # connector already returned is still there.
        logger.debug("deep read skipped %s: %s", url, error)
        return

    text = extract_text(html)
    if not text:
        return

    existing = getattr(result, "snippet", "") or ""
    # Only ever an improvement. A page whose extracted prose is shorter than the
    # search engine's own description of it is a page the extractor did badly
    # on, and keeping the snippet is the safer of the two.
    if len(text) > len(existing):
        try:
            result.snippet = text
        except Exception:
            # Frozen results exist in this codebase and have bitten before —
            # `ranker.py` would have raised `FrozenInstanceError` on its first
            # result. Depth is not worth an exception on the answer path.
            logger.debug("deep read could not attach text to %s", url)


async def read_pages(
    results: Iterable[Any],
    *,
    limit: int = DEFAULT_LIMIT,
    source: str = "internet.deep_read",
) -> list[Any]:
    """Fetch the top `limit` results in full, in parallel. Returns `results`.

    Mutates in place and returns the same list, so a caller that forgets the
    return value still gets the benefit — this sits on the answer path and a
    silently-dropped result would be indistinguishable from the feature being
    off, which is the shape this codebase keeps finding.
    """
    items = list(results)
    if not items:
        return items

    try:
        from core.egress.aio import gated_session
        from core.egress.gate import SearchReadGrant
    except ImportError:  # pragma: no cover
        return items

    # The capability, built from the URLs this search actually returned.
    #
    # Only these exact URLs may be read past default-deny, and only as bodyless
    # GETs — `SearchReadGrant.permits` enforces both. A host the user has
    # deliberately blocked is still blocked, because the gate consults the
    # grant only where no rule exists. Nothing from the Spine can travel on
    # one: there is no field for it.
    readable = [r for r in items[:limit] if _looks_readable(getattr(r, "url", "") or "")]
    if not readable:
        return items

    grant = SearchReadGrant.of(getattr(r, "url", "") for r in readable)
    session = gated_session(source=source, grant=grant)
    try:
        await asyncio.gather(
            *(_read_one(session, result) for result in readable),
            # One page's failure must not cancel the others.
            return_exceptions=True,
        )
    finally:
        close = getattr(session, "close", None)
        if close is not None:
            try:
                await close()
            except Exception:
                pass

    return items
