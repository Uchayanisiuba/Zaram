"""Markdown as the document's content model, because that is what models write.

The structured block types exist so a document can hold a heading, a list and a
table. They are an API, and until something speaks it on the model's behalf a
caller has to assemble JSON by hand — which is not what a language model does
when asked for a proposal. **It writes markdown.** That mismatch is what
produced the original failure: `## Scope of Work` arriving as a paragraph of
literal text.

So this is the adapter, and it is deliberately thin. `markdown-it-py` does the
parsing — CommonMark plus GFM tables, MIT, already installed — and it is a far
better parser than anything worth writing here. This module maps its tokens
onto the block types and enforces two bounds a general-purpose renderer has no
reason to enforce.

**Raw HTML is disabled, and that is not the default.** `MarkdownIt("commonmark")`
sets `html: True`, so `<script>alert(1)</script>` in a model's reply passes
through untouched and lands in a file the user sends to a client. Measured, not
assumed. `{"html": False}` escapes it to text, and the test asserting that is
the one to keep if any other is ever cut.

**The inline tag set is exactly what `export/_reader.py` parses** — `strong`,
`em`, `code`, `br`. Anything else is unwrapped to its text. This is narrower
than "safe HTML" and the reason is not security: a tag the readers do not know
survives into the preview looking correct and disappears on export to .docx
with nothing reporting it. Restricting the set to what the readers already
handle is what keeps the preview and the exported file the same document.

`img` is dropped and its alt text kept. A markdown image names a URL, and a
generated document that fetches one is a remote asset arriving inside a data
file — the class `check-no-remote-assets.mjs` exists to prevent, by a route
that check cannot see because it scans source rather than output.

Deliberately unsupported: raw HTML blocks, footnotes, definition lists, images.
Each would need a block type the exporters cannot read, and the rule here is
that nothing may invent markup the readers would have to learn.
"""

from __future__ import annotations

import html as html_escape
from html.parser import HTMLParser
from typing import Any, List

from .contracts import BulletList, Heading, RichText, TableBlock

__all__ = ["blocks_from_markdown", "inline_html"]

#: The inline tags kept verbatim. Exactly `_reader._STYLE_TAGS` plus `br`.
#: A literal rather than an import, so that widening one is a deliberate edit
#: in two places rather than a silent consequence in one.
_KEEP = {"strong", "b", "em", "i", "code", "br"}


class _Whitelist(HTMLParser):
    """Keep `_KEEP` tags, unwrap the rest, drop images to their alt text.

    Unwrapping rather than dropping is the important half: a link's *text* is
    part of the sentence, so discarding `<a>` wholesale would silently delete
    words from the document.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "img":
            alt = dict(attrs).get("alt") or ""
            if alt:
                self.out.append(html_escape.escape(alt, quote=True))
            return
        if tag in _KEEP:
            self.out.append("<br>" if tag == "br" else f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _KEEP and tag != "br":
            self.out.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        # Re-escaped on the way out. `convert_charrefs` has already turned
        # `&amp;` back into `&`, so passing it through unescaped would undo the
        # parser's own escaping of the model's text.
        self.out.append(html_escape.escape(data, quote=True))


def _md():
    """The parser. Raw HTML off, GFM tables on."""
    from markdown_it import MarkdownIt

    return MarkdownIt("commonmark", {"html": False}).enable("table")


def inline_html(markdown: str) -> RichText:
    """One line of markdown as safe inline HTML."""
    parser = _Whitelist()
    parser.feed(_md().renderInline(markdown or ""))
    parser.close()
    return RichText("".join(parser.out))


#: Info strings on a whole-document fence that mean "this is the document",
#: not "this is a code sample". An empty info string counts: a model that
#: fences its whole reply often labels it with nothing.
_DOCUMENT_FENCES = {"", "markdown", "md", "text", "plaintext"}


def _unfence(markdown: str) -> str:
    """Unwrap a document that a model wrapped entirely in a code fence.

    **Found by running a real model, and it is the reason that test exists.**
    Asked to "output only the Markdown document", `qwen2.5-coder:14b` returned
    the whole statement of work inside ```` ```markdown ````. Every heading,
    list and table then parsed as the *contents of one code block* — the
    document collapsed to a single monospace paragraph, which is a worse
    version of the original failure this module was written to fix, and no
    amount of hand-written test markdown would ever have produced it.

    The bound is narrow on purpose: this unwraps only when the fence **is** the
    document — one fence, nothing outside it, and an info string that is not a
    programming language. A document containing a code sample keeps it as code,
    which is why the check is on the token stream rather than on whether the
    text happens to start with a backtick.
    """
    tokens = [t for t in _md().parse(markdown) if t.level == 0]
    if len(tokens) != 1:
        return markdown
    fence = tokens[0]
    if fence.type != "fence":
        return markdown
    if (fence.info or "").strip().lower() not in _DOCUMENT_FENCES:
        return markdown
    return fence.content


def blocks_from_markdown(
    markdown: str, *, base_level: int = 2, title: str = ""
) -> List[Any]:
    """A markdown document as blocks `render_document` understands.

    Two normalisations, both of which exist because **a model's heading depths
    are relative and a document's are absolute.**

    *The shallowest heading present becomes ``base_level``.* One model opens a
    proposal with `# Scope`, another with `## Scope`, and both mean "top-level
    section". Mapping `#` to h2 unconditionally would render the second one's
    sections a level deeper than the first's for no reason the author chose.
    Depths below that clamp to 3 — `####` in a reply is a formatting habit, not
    a request the product should refuse, and the stylesheet defines two heading
    levels because a generated document does not need six.

    *A leading heading matching ``title`` is dropped.* Asked for a proposal, a
    model writes `# Proposal` first, and the masthead has already set that as
    the `<h1>`. Keeping both gives the page two titles and the .docx two
    competing Title styles. `export/docx.py` already drops exactly this
    duplicate on the way out; doing it here means the preview and the export
    agree rather than differing by one line.

    ``base_level`` defaults to 2 because `<h1>` is the title, set once by the
    masthead, and `Heading` refuses level 1 outright.
    """
    md = _md()
    tokens = md.parse(_unfence(markdown or ""))
    blocks: List[Any] = []

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token.type == "heading_open":
            # Depth is carried, not resolved. The level a heading gets depends
            # on the shallowest heading in the *whole* document, which is not
            # known until the parse finishes.
            blocks.append(_PendingHeading(int(token.tag[1:]), inline_html(tokens[i + 1].content)))
            i += 3
            continue

        if token.type == "paragraph_open":
            rich = inline_html(tokens[i + 1].content)
            if rich.html.strip():
                blocks.append(rich)
            i += 3
            continue

        if token.type in ("bullet_list_open", "ordered_list_open"):
            ordered = token.type == "ordered_list_open"
            depth, items, j = 0, [], i
            while j < len(tokens):
                t = tokens[j]
                if t.type in ("bullet_list_open", "ordered_list_open"):
                    depth += 1
                elif t.type in ("bullet_list_close", "ordered_list_close"):
                    depth -= 1
                    if depth == 0:
                        break
                elif t.type == "inline" and depth == 1:
                    items.append(inline_html(t.content))
                j += 1
            blocks.append(BulletList(items=items, ordered=ordered))
            i = j + 1
            continue

        if token.type == "table_open":
            header: List[Any] = []
            rows: List[List[Any]] = []
            row: List[Any] = []
            in_head, j = False, i
            while j < len(tokens) and tokens[j].type != "table_close":
                t = tokens[j]
                if t.type == "thead_open":
                    in_head = True
                elif t.type == "thead_close":
                    in_head = False
                elif t.type == "tr_open":
                    row = []
                elif t.type == "tr_close":
                    if in_head and not header:
                        header.extend(row)
                    else:
                        rows.append(row)
                elif t.type == "inline":
                    row.append(inline_html(t.content))
                j += 1
            blocks.append(TableBlock(header=header, rows=rows))
            i = j + 1
            continue

        if token.type == "fence":
            # A code block is prose in a monospace face rather than a block type
            # of its own: `_reader` has no `pre`, so inventing one would export
            # as nothing. `code` is in the kept set, so this survives to .docx.
            body = html_escape.escape(token.content.rstrip("\n"), quote=True)
            blocks.append(RichText(f"<code>{body}</code>"))
            i += 1
            continue

        i += 1

    return _resolve_headings(blocks, base_level=base_level, title=title)


class _PendingHeading:
    """A heading whose depth is known and whose level is not yet."""

    __slots__ = ("depth", "text")

    def __init__(self, depth: int, text: RichText) -> None:
        self.depth = depth
        self.text = text


def _resolve_headings(
    blocks: List[Any], *, base_level: int, title: str
) -> List[Any]:
    """Turn pending headings into real ones, once every depth has been seen."""
    if title:
        for index, block in enumerate(blocks):
            if not isinstance(block, _PendingHeading):
                # Only a *leading* heading can be the title restated. A heading
                # halfway down that happens to repeat the title is a section
                # about it, and dropping that would delete a real section.
                break
            if block.text.html.strip().casefold() == html_escape.escape(
                title, quote=True
            ).strip().casefold():
                blocks = blocks[:index] + blocks[index + 1 :]
                break
            break

    depths = [b.depth for b in blocks if isinstance(b, _PendingHeading)]
    shallowest = min(depths) if depths else 1

    return [
        Heading(text=b.text, level=min(3, base_level + (b.depth - shallowest)))
        if isinstance(b, _PendingHeading)
        else b
        for b in blocks
    ]
