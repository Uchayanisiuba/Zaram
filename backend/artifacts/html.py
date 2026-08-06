"""HTML generation, and the claim anchors that make a document defensible.

HTML is the source of truth for every generated document. Everything else is a
rendering of it: WeasyPrint to PDF, python-docx to .docx. That gives one
pipeline instead of four, and makes preview faithful — the preview *is* the HTML
that produced the file.

The anchors
-----------
A claim drawn from a recalled fact is wrapped:

    <span data-zaram-claim="c1" data-zaram-source="memory:55b6">…</span>

The same mapping is stored on the artifact record, independently. That
duplication is deliberate and is the point of this module's design: export
formats lose markup. WeasyPrint flattens spans into styled text runs; Word
discards attributes it does not recognise. Provenance that lived only in the
file would survive the export and die on the first edit, leaving a document that
*looks* citable and is not — which is worse than one carrying no citations,
because a reader would rely on it.

So the file carries a human-readable rendering of provenance, and the record
carries the machine-readable one. Re-export always goes HTML → format, never
format → format.
"""

from __future__ import annotations

import html as html_escape
from typing import Iterable, List, Sequence

from .contracts import ArtifactSource, Claim

#: Attribute names, in one place. The exporters read these back out.
CLAIM_ATTR = "data-zaram-claim"
SOURCE_ATTR = "data-zaram-source"


def _esc(text: str) -> str:
    return html_escape.escape(text, quote=True)


def claim_entry_id(claim_id: str) -> str:
    """The id of a claim's entry in the Sources section.

    Exists so an exporter can turn "this sentence" into a link to "the source
    paragraph it came from" without inventing a naming scheme of its own, and so
    the preview's anchors and the .docx's bookmarks address the same thing.
    """
    return f"claim-{claim_id}"


def claim_span(claim: Claim) -> str:
    """One claim, wrapped so its origin travels with it."""
    return (
        f'<span {CLAIM_ATTR}="{_esc(claim.id)}" '
        f'{SOURCE_ATTR}="{_esc(claim.source_id)}">{_esc(claim.excerpt)}</span>'
    )


def render_document(
    *,
    title: str,
    blocks: Sequence[str | Claim],
    sources: Sequence[ArtifactSource] = (),
    claims: Sequence[Claim] = (),
) -> str:
    """Render a complete, self-contained HTML document.

    ``blocks`` may mix plain strings and Claims. A plain string is prose the
    model wrote from nothing in particular; a Claim is prose traceable to a
    fact, and gets an anchor.

    Self-contained because this same string is what the preview renders and what
    WeasyPrint consumes — an external stylesheet would make the two diverge, and
    would be a remote asset in a product that forbids them.
    """
    body: List[str] = []
    for block in blocks:
        if isinstance(block, Claim):
            body.append(f"<p>{claim_span(block)}</p>")
        else:
            body.append(f"<p>{_esc(block)}</p>")

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en"><head><meta charset="utf-8">',
            f"<title>{_esc(title)}</title>",
            f"<style>{_STYLE}</style>",
            "</head><body>",
            f"<h1>{_esc(title)}</h1>",
            *body,
            _sources_section(sources, claims),
            "</body></html>",
        ]
    )


def _sources_section(
    sources: Sequence[ArtifactSource], claims: Sequence[Claim]
) -> str:
    """The human-readable half of provenance, rendered into the file itself.

    This is what survives into the PDF and the .docx, because it is ordinary
    text rather than an attribute. It is not the machine-readable record — that
    is `Artifact.claims` — but it is what makes an exported file defensible on
    its own, away from Zaram.
    """
    if not sources and not claims:
        # Saying so beats an empty heading. A document that cites nothing is a
        # real and honest state; a "Sources" heading over nothing reads as a
        # rendering failure.
        return (
            '<section class="sources"><h2>Sources</h2>'
            "<p>Nothing was recalled for this document. It was written from "
            "what you provided, not from anything in the Spine.</p></section>"
        )

    items: List[str] = []
    for source in sources:
        label = _esc(source.title or source.url or source.kind)
        ref = _esc(source.url or source.kind)
        items.append(f"<li><strong>{label}</strong><br><code>{ref}</code></li>")

    claim_rows = "".join(
        f'<li id="{claim_entry_id(c.id)}"><em>“{_esc(c.excerpt)}”</em><br>'
        f"<code>{_esc(c.source_id)}</code>"
        + (f"<br>{_esc(c.source_excerpt)}" if c.source_excerpt else "")
        + "</li>"
        for c in claims
    )

    return (
        '<section class="sources">'
        "<h2>Sources</h2>"
        f"<ul>{''.join(items)}</ul>"
        + (f"<h2>Claims</h2><ul>{claim_rows}</ul>" if claim_rows else "")
        + "</section>"
    )


def render_spreadsheet(
    *,
    title: str,
    header: Sequence[str],
    rows: Iterable[Sequence[object]],
    caption: str = "",
    sources: Sequence[ArtifactSource] = (),
    claims: Sequence[Claim] = (),
) -> str:
    """A tabular artifact, as HTML.

    A spreadsheet goes through HTML like everything else, for one reason that is
    not consistency for its own sake: the preview. A user who is shown their
    numbers before the .xlsx is written is being shown the same table the
    exporter reads, not a second rendering that can disagree with it.

    ``<th>`` for the header row is load-bearing, not styling — the reader
    distinguishes a header from a data row by the tag, and the exporter freezes
    and filters on it.
    """
    head = "".join(f"<th>{_esc(str(cell))}</th>" for cell in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{_esc(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )

    table = (
        "<table>"
        + (f"<caption>{_esc(caption)}</caption>" if caption else "")
        + (f"<thead><tr>{head}</tr></thead>" if head else "")
        + f"<tbody>{body}</tbody></table>"
    )

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en"><head><meta charset="utf-8">',
            f"<title>{_esc(title)}</title>",
            f"<style>{_STYLE}{_TABLE_STYLE}</style>",
            "</head><body>",
            f"<h1>{_esc(title)}</h1>",
            table,
            _sources_section(sources, claims),
            "</body></html>",
        ]
    )


def render_chart(
    *,
    title: str,
    png: bytes,
    header: Sequence[str] = (),
    rows: Iterable[Sequence[object]] = (),
    sources: Sequence[ArtifactSource] = (),
    claims: Sequence[Claim] = (),
) -> str:
    """A chart, as HTML: the image, and the numbers behind it.

    The image is embedded as a data URI. Not for tidiness — a remote asset is
    forbidden, and a relative path to a sibling file breaks the moment the HTML
    is previewed from memory rather than from disk, which is how the preview
    works.

    The data table below the image is deliberate. A chart is a claim about
    numbers, and a chart whose numbers cannot be read is the least defensible
    thing this product can emit. The table is what makes the picture checkable.
    """
    import base64

    encoded = base64.b64encode(png).decode("ascii")
    data_table = ""
    if header:
        data_table = (
            "<table><thead><tr>"
            + "".join(f"<th>{_esc(str(c))}</th>" for c in header)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>"
                + "".join(f"<td>{_esc(str(cell))}</td>" for cell in row)
                + "</tr>"
                for row in rows
            )
            + "</tbody></table>"
        )

    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en"><head><meta charset="utf-8">',
            f"<title>{_esc(title)}</title>",
            f"<style>{_STYLE}{_TABLE_STYLE}</style>",
            "</head><body>",
            f"<h1>{_esc(title)}</h1>",
            f'<img alt="{_esc(title)}" src="data:image/png;base64,{encoded}">',
            data_table,
            _sources_section(sources, claims),
            "</body></html>",
        ]
    )


def extract_claim_ids(document_html: str) -> List[str]:
    """Claim ids present in the markup, in order of appearance.

    Used by the tests that prove the anchors reached the HTML, and by any
    exporter that needs to walk them. Deliberately a plain scan rather than a
    parser dependency — the markup is ours and the attribute is fixed.
    """
    import re

    return re.findall(rf'{CLAIM_ATTR}="([^"]+)"', document_html)


def strip_anchors(document_html: str) -> str:
    """The HTML with claim spans unwrapped, for exporters that cannot carry them.

    Named for what it costs rather than what it does. Any exporter calling this
    is producing a file whose provenance survives only in the Sources section
    and on the artifact record.
    """
    import re

    return re.sub(
        rf'<span {CLAIM_ATTR}="[^"]*" {SOURCE_ATTR}="[^"]*">(.*?)</span>',
        r"\1",
        document_html,
        flags=re.DOTALL,
    )


_STYLE = (
    "body{font:14px/1.6 Georgia,serif;max-width:44em;margin:3em auto;color:#111}"
    "h1{font-size:1.6em;margin-bottom:1em}"
    "h2{font-size:1.05em;margin-top:2em;text-transform:uppercase;"
    "letter-spacing:.06em;color:#555}"
    ".sources{margin-top:3em;border-top:1px solid #ddd;padding-top:1em;"
    "font-size:.85em;color:#444}"
    ".sources code{font-size:.9em;color:#777}"
    f"span[{SOURCE_ATTR}]{{border-bottom:1px dotted #999}}"
)

_TABLE_STYLE = (
    "table{border-collapse:collapse;width:100%;font:13px/1.5 system-ui,sans-serif}"
    "caption{text-align:left;padding-bottom:.6em;color:#555}"
    "th,td{border:1px solid #ddd;padding:.4em .6em;text-align:left}"
    "th{background:#f5f5f5;font-weight:600}"
    "img{max-width:100%;height:auto;margin:1em 0}"
)
