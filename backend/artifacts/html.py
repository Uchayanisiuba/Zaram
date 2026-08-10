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
from .letterhead import Letterhead

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
    #: The user's branding. Optional and additive: every existing caller keeps
    #: working and gets the improved typography without knowing this exists.
    letterhead: "Letterhead | None" = None,
    #: Label/value pairs for the scan-first block — reference number, dates,
    #: parties. Ordered, because the caller knows what matters on this document.
    meta: Sequence[tuple[str, str]] = (),
    #: What kind of document this is, set small and uppercase opposite the
    #: letterhead: "Invoice", "Quote", "Proposal".
    kind_label: str = "",
    #: Whether to print the Sources and Claims section **into the file itself**.
    #:
    #: **Off by default, and the default is the decision.** A document is
    #: written for its recipient. An invoice goes to a client, and a client has
    #: no use for `memory:55b6` at the foot of it — it is internal working,
    #: it looks unfinished, and it discloses how the number was arrived at to
    #: someone who is not owed that.
    #:
    #: This does **not** weaken rule 2. Rule 2 is about traceability, and its
    #: operational test (`test_provenance_invariant.py`) is about the *stream*:
    #: anything injected into a model's context must be accounted for by a
    #: source event. Traceability survives here in two stronger places — the
    #: machine-readable `Artifact.claims` on the record, and Zaram's own preview,
    #: which renders provenance as chrome around the document exactly as
    #: `CitationPanel` does around a reply. The author checks it there; the
    #: recipient never needed it.
    #:
    #: Turned **on** for the documents where a citation is part of the genre — a
    #: research brief, a report, a proposal that argues from evidence. That is a
    #: property of the document kind, so the caller decides it.
    include_provenance: bool = False,
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
            # One wrapper so the screen preview can draw a sheet of paper around
            # the content while print leaves the page box to do it.
            '<div class="sheet">',
            _masthead(title, letterhead, kind_label),
            _meta_block(meta),
            *body,
            _sources_section(sources, claims) if include_provenance else "",
            "</div>",
            "</body></html>",
        ]
    )


def _masthead(title: str, letterhead: "Letterhead | None", kind_label: str) -> str:
    """The top of the page: who it is from, what it is, and what it is called.

    Rendered **even when there is no letterhead**, because a bare `<h1>` sitting
    at the top of a page is exactly what made the old output read as unfinished.
    With nothing configured this is still a titled document under a rule; with a
    logo and an address it is a letterhead.
    """
    left: List[str] = []
    if letterhead is not None and letterhead.logo:
        # `alt` carries the business name so the logo is not silent to a screen
        # reader or in a text extraction of the PDF.
        left.append(
            f'<img class="logo" alt="{_esc(letterhead.name or "Logo")}" '
            f'src="{_esc(letterhead.logo)}">'
        )
    if letterhead is not None and letterhead.name:
        left.append(f'<div class="name">{_esc(letterhead.name)}</div>')
    if letterhead is not None:
        left.extend(
            f'<div class="line">{_esc(line)}</div>' for line in letterhead.lines if line
        )

    who = f'<div class="who">{"".join(left)}</div>' if left else "<div></div>"
    kind = f'<div class="kind">{_esc(kind_label)}</div>' if kind_label else ""

    return f'<header class="masthead">{who}{kind}</header><h1>{_esc(title)}</h1>'


def _meta_block(meta: Sequence[tuple[str, str]]) -> str:
    """Reference, dates, parties — the fields a reader scans before reading.

    A list of pairs rather than a dataclass with `invoice_number` and `due_date`,
    because the fields differ by document and by country and a schema written
    here would be wrong somewhere. The caller knows what this document is.
    """
    if not meta:
        return ""
    pairs = "".join(
        f"<div><dt>{_esc(label)}</dt><dd>{_esc(value)}</dd></div>"
        for label, value in meta
        if label and value
    )
    return f'<dl class="meta">{pairs}</dl>' if pairs else ""


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


# --------------------------------------------------------------------------- #
# The document stylesheet.
#
# **This used to be eight lines and it is why generated documents looked like a
# web page printed by accident.** The old rule was
# `body{font:14px/1.6 Georgia,serif;max-width:44em;margin:3em auto}` — screen
# conventions, on something whose destination is paper. There was no `@page` at
# all, which meant no paper size, no print margins, no page numbers, no running
# header, no letterhead. The model was blamed for this; the model writes the
# words and every visual property of the output was decided here.
#
# Three constraints shape what follows, and each rules out the obvious answer:
#
# *No remote assets.* `check-no-remote-assets.mjs` bans them and the product
# refuses them, so there are no web fonts. System stacks only — which is not a
# compromise for print, because the stacks below resolve to fonts that were
# designed for documents on every platform Zaram runs on.
#
# *One stylesheet for two media.* The same string is the preview and the PDF
# source, so `@media screen` and `@media print` do the work rather than two
# templates that drift. What the user sees is what downloads, which is the whole
# argument for HTML being the source of truth.
#
# *Print rules are not decoration.* `orphans`/`widows`, `break-inside` and
# `break-after` are what stop a table splitting across a page boundary mid-row
# or a heading stranding itself at the foot of a page. They are invisible when
# they work, which is why they were missing.
# --------------------------------------------------------------------------- #

#: Serif for body text, because a document is read in long lines and on paper.
#: Charter and Palatino ship on macOS, Cambria and Georgia on Windows; the last
#: two entries are the generic fallbacks that keep Linux honest.
_SERIF = "Charter,'Bitstream Charter','Palatino Linotype',Palatino,Cambria,Georgia,serif"
#: Sans for labels, table headers and the metadata block — the parts a reader
#: scans rather than reads.
_SANS = "'Segoe UI',Inter,-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif"

_PAGE_STYLE = (
    # A4 because that is the paper everywhere Zaram's first users are. The
    # margins are the classic document proportions: a wider foot than head, so
    # the text block sits slightly above centre and does not look like it is
    # sliding off the page.
    "@page{size:A4;margin:22mm 20mm 24mm 20mm;"
    "@bottom-center{content:counter(page) ' of ' counter(pages);"
    f"font:9pt {_SANS};color:#888}}}}"
)

_STYLE = (
    ":root{--ink:#14171a;--muted:#5b6570;--rule:#d8dde2;--accent:#0f766e}"
    f"body{{font:11.5pt/1.65 {_SERIF};color:var(--ink);"
    "-webkit-font-smoothing:antialiased;margin:0}"
    # Screen: emulate a sheet of paper so the preview reads as a document rather
    # than as a web page. Print: the page box already does this, so the frame is
    # removed or it would print a border around every page.
    "@media screen{"
    "body{background:#eceef1;padding:28px 16px}"
    ".sheet{background:#fff;max-width:210mm;min-height:297mm;margin:0 auto;"
    "padding:22mm 20mm 24mm;box-shadow:0 1px 3px rgba(0,0,0,.14),0 8px 28px rgba(0,0,0,.10);"
    "border-radius:2px}"
    "}"
    "@media print{body{background:none;padding:0}"
    ".sheet{max-width:none;min-height:0;margin:0;padding:0;box-shadow:none}}"
    # The masthead. Present even with no letterhead configured, because the
    # title has to sit on something — a bare <h1> at the top of a page is what
    # made the old output look unfinished.
    ".masthead{display:flex;justify-content:space-between;align-items:flex-end;"
    "gap:24px;border-bottom:2px solid var(--ink);padding-bottom:10px;margin-bottom:26px}"
    f".masthead .who{{font:600 10.5pt/1.35 {_SANS};letter-spacing:.02em}}"
    ".masthead .who .line{color:var(--muted);font-weight:400}"
    # Constrained by height, not width: a logo is wide or tall and only the
    # height decides whether the masthead stays one band. 18mm is the tallest a
    # mark can be before it starts competing with the document title.
    ".masthead .logo{max-height:18mm;max-width:70mm;width:auto;height:auto;"
    "display:block;margin-bottom:6px}"
    ".masthead .name{margin-bottom:2px}"
    f".masthead .kind{{font:600 9pt/1.3 {_SANS};text-transform:uppercase;"
    "letter-spacing:.14em;color:var(--accent);text-align:right;white-space:nowrap}"
    "h1{font-size:20pt;line-height:1.2;font-weight:600;margin:0 0 4px;"
    "letter-spacing:-.01em}"
    # A heading must never be the last thing on a page.
    "h1,h2,h3{break-after:avoid;page-break-after:avoid}"
    f"h2{{font:600 9pt/1.3 {_SANS};text-transform:uppercase;letter-spacing:.12em;"
    "color:var(--muted);margin:26px 0 8px}"
    "p{margin:0 0 .85em;orphans:3;widows:3}"
    # The metadata block: reference, dates, parties. Scanned, not read, so it is
    # set in the sans face and in columns rather than as prose.
    f".meta{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));"
    f"gap:12px 24px;margin:0 0 26px;font:9.5pt/1.45 {_SANS}}}"
    ".meta dt{color:var(--muted);text-transform:uppercase;letter-spacing:.08em;"
    "font-size:8pt;margin-bottom:2px}"
    ".meta dd{margin:0;color:var(--ink);font-weight:500}"
    # Provenance, kept but made to look deliberate rather than like a debug dump.
    ".sources{margin-top:32px;border-top:1px solid var(--rule);padding-top:12px;"
    f"font:9pt/1.5 {_SANS};color:var(--muted);break-inside:avoid}}"
    ".sources ul{margin:0;padding-left:1.1em}"
    ".sources li{margin-bottom:6px}"
    ".sources code{font-size:8.5pt;color:#8a939c}"
    # The claim underline is provenance made visible in the file itself, so it
    # has to survive print — where a dotted grey rule is nearly invisible.
    f"span[{SOURCE_ATTR}]{{border-bottom:1px solid rgba(15,118,110,.45)}}"
    "@media print{" f"span[{SOURCE_ATTR}]{{border-bottom:1px solid #999}}}}"
) + _PAGE_STYLE

# --------------------------------------------------------------------------- #
# Tables, as printed documents actually set them.
#
# The old rules boxed every cell in a 1px grid, which is a spreadsheet
# convention and reads as a screenshot on paper. Real invoices, statements and
# reports rule *horizontally* — a line under the header and hairlines between
# rows — and let the columns align themselves.
#
# Three details that separate a document from a table dump, all of them
# invisible until they are wrong:
#
# *Tabular figures.* `font-variant-numeric:tabular-nums` makes every digit the
# same width, so a column of amounts aligns on the decimal without a monospace
# face. Proportional digits in a money column is the single most obvious tell
# that a document was generated by something that had not thought about it.
#
# *A repeating header.* `thead{display:table-header-group}` makes the column
# headings reappear at the top of each page. A three-page invoice whose line
# items lose their headers on page two is a document the client has to guess at.
#
# *Rows that do not split.* `break-inside:avoid` on `tr`, so a line item is
# never cut in half by a page boundary.
# --------------------------------------------------------------------------- #

_TABLE_STYLE = (
    f"table{{border-collapse:collapse;width:100%;font:10pt/1.45 {_SANS};"
    "margin:14px 0 18px;font-variant-numeric:tabular-nums}"
    f"caption{{text-align:left;padding-bottom:8px;color:var(--muted);"
    f"font:600 9pt/1.3 {_SANS};text-transform:uppercase;letter-spacing:.1em}}"
    "thead{display:table-header-group}"
    "tr{break-inside:avoid;page-break-inside:avoid}"
    "th{text-align:left;font-weight:600;color:var(--muted);"
    "text-transform:uppercase;letter-spacing:.07em;font-size:8pt;"
    "border-bottom:1.5px solid var(--ink);padding:0 8px 6px}"
    "td{padding:7px 8px;border-bottom:1px solid var(--rule);vertical-align:top}"
    # Numeric columns right-align. Detected by class rather than by guessing at
    # content, because a caller knows which column is money and a heuristic that
    # reads cell text would right-align a reference number that happens to be
    # digits.
    "th.num,td.num{text-align:right;white-space:nowrap}"
    # The totals block: the one number the reader is looking for.
    "tfoot td{border-bottom:none;padding-top:8px;font-weight:500}"
    "tfoot tr:last-child td{border-top:1.5px solid var(--ink);font-weight:700;"
    "font-size:11pt}"
    "img{max-width:100%;height:auto;margin:1em 0}"
)
