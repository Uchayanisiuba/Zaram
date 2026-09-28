"""The design, applied to PowerPoint — because `python-pptx` ships Office 2007's.

`word_theme` opens with the same sentence about Word, and this is the sibling it
never had. Measured on a generated proposal, 28 September 2026, by reading
`ppt/theme/theme1.xml` out of the file Zaram had just produced:

    theme name   Office Theme
    major latin  Calibri          minor latin  Calibri
    dk2/accents  1F497D  4F81BD  C0504D  9BBB59  8064A2  4BACC6  F79646

That accent row is the **Office 2007** palette, and `word_theme` already
diagnosed what it costs: *"a period signal… a reader who has seen a hundred
documents knows the look without being able to name it."*

Why `pptx.py` setting fonts and colours was not enough
-----------------------------------------------------
It already styles the title and bullet runs from `theme.py`, and that is real —
the deck is not Calibri on screen. What it cannot reach is everything it does
not name: the table style, the background, the bullet glyphs, the hyperlink
colour, and any shape added later by whoever inherits this. Those all resolve
through the theme, so they were all still 2007.

**And the direction of the fix matters more than the fix.** `pptx.py`'s own
docstring worried that a hardcoded palette is "one more thing to undo" for a
user who applies their own theme in PowerPoint. That instinct was right and
aimed at the wrong layer. Direct run formatting is precisely what *survives* a
user's theme — it is the thing that cannot be undone without selecting every
shape. Theme-level colour and type is the kind PowerPoint replaces wholesale
when somebody applies their own. So writing the design into the theme makes the
deck **more** restylable, not less, which is what that note actually wanted.

What is still left alone, and now for a better reason
----------------------------------------------------
Placeholder geometry, masters and layouts stay the template's. That is not
timidity: a layout the user's own theme also defines is a layout PowerPoint can
re-apply, and geometry Zaram invented is geometry that fights it. Where a slide
genuinely needs different proportions — a statement, a row of metrics —
`pptx.py` positions its own shapes on a blank layout rather than deforming a
placeholder, so the two approaches do not overlap.

A template file was the other option and was not taken, for the reason
`word_theme` gives in as many words: it puts the design in a binary nobody can
review in a diff. Every value below is a line someone can read, argue with, and
test, and `tests/test_the_deck_carries_the_design.py` asserts the emitted XML
rather than the intent.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

from .. import theme

#: The theme part is reached through the slide master's relationships. There is
#: no `Presentation.theme` — `python-pptx` models the part as an opaque blob,
#: which is why this module edits XML text rather than an element tree.
_THEME_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme"

#: What the scheme slots are *for*, which is the part that makes rewriting them
#: safe. `dk1` is body text, `lt1` is the page; `dk2`/`lt2` are the pair Office
#: uses for a dark-on-light inversion, and the accents are the categorical
#: sequence. Getting `dk1` wrong is the expensive one: every placeholder's text
#: colour resolves to it, so a mistake there is a deck nobody can read.
_TEXT_DARK = theme.INK
_TEXT_LIGHT = "ffffff"
_ALT_DARK = theme.MUTED
_ALT_LIGHT = theme.WASH

#: PowerPoint's own name for the table style `python-pptx` applies by default:
#: "Medium Style 2 – Accent 1", which is banded rows in the accent colour with a
#: solid header. It is the single most recognisable "made in PowerPoint" mark on
#: a slide, and it is applied by GUID rather than by name, so it has to be
#: replaced by GUID.
_BANDED_TABLE = "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"
#: "No Style, Table Grid" — borders and nothing else, which is the base
#: `style_table` draws its own rules on top of. Chosen over "No Style, No Grid"
#: because a table with neither a style nor borders is invisible to anybody who
#: opens the deck and starts editing.
_PLAIN_TABLE = "{5940675A-B579-460E-94D1-54222C63F5DA}"


def apply(deck) -> None:
    """Put Zaram's design into the deck's theme.

    One entry point, mirroring `word_theme.apply`, and called once from
    `PptxExporter.export` before any slide is added — the theme has to be in
    place first, or the layouts copy the old scheme onto their placeholders as
    they are instantiated.
    """
    part = _theme_part(deck)
    if part is None:
        # A deck built from somebody else's template might not relate a theme.
        # Nothing to restyle is not an error: the runs `pptx.py` sets directly
        # still carry the design, which is the state this module improves on
        # rather than the state it requires.
        return

    xml = part.blob.decode("utf-8")
    xml = _colour_scheme(xml)
    xml = _font_scheme(xml)
    xml = _scheme_name(xml)
    part._blob = xml.encode("utf-8")


def _theme_part(deck):
    try:
        return deck.slide_master.part.part_related_by(_THEME_REL)
    except KeyError:
        return None


# --------------------------------------------------------------------------- #
# Colour
# --------------------------------------------------------------------------- #


def _colour_scheme(xml: str) -> str:
    """Replace the whole `<a:clrScheme>` rather than patch values inside it.

    Patching would mean matching `<a:sysClr>` for some slots and `<a:srgbClr>`
    for others — `dk1` and `lt1` ship as `windowText` and `window`, which are
    *system* colours and resolve to whatever the viewer's OS says. That is the
    one thing a document must not do: a deck whose body text follows the
    reader's theme is a deck that is white-on-white for somebody in dark mode.
    Writing explicit `srgbClr` for every slot is the fix and replacing the
    element is the only clean way to do it.
    """
    accents = "".join(
        f"<a:accent{index}><a:srgbClr val=\"{colour.upper()}\"/></a:accent{index}>"
        for index, colour in enumerate(_accents(theme.SERIES), start=1)
    )
    scheme = (
        '<a:clrScheme name="Zaram">'
        f'<a:dk1><a:srgbClr val="{_TEXT_DARK.upper()}"/></a:dk1>'
        f'<a:lt1><a:srgbClr val="{_TEXT_LIGHT.upper()}"/></a:lt1>'
        f'<a:dk2><a:srgbClr val="{_ALT_DARK.upper()}"/></a:dk2>'
        f'<a:lt2><a:srgbClr val="{_ALT_LIGHT.upper()}"/></a:lt2>'
        f"{accents}"
        # The link colour is the accent, and the visited colour is the muted
        # grey rather than Office's purple. A generated deck has no browsing
        # history, so "visited" only ever fires on a link the presenter clicked
        # in the room — and marking that in purple tells the audience something
        # about the presenter instead of about the deck.
        f'<a:hlink><a:srgbClr val="{theme.ACCENT.upper()}"/></a:hlink>'
        f'<a:folHlink><a:srgbClr val="{theme.MUTED.upper()}"/></a:folHlink>'
        "</a:clrScheme>"
    )
    return re.sub(r"<a:clrScheme\b.*?</a:clrScheme>", scheme, xml, count=1, flags=re.S)


def _accents(series: Sequence[str]) -> Iterable[str]:
    """Exactly six, because the schema wants `accent1` through `accent6`.

    `theme.SERIES` is six today. Padding rather than raising is deliberate: a
    future edit that leaves five there should produce a slightly duller deck,
    not an exporter that refuses to write a file.
    """
    values = list(series)[:6]
    while len(values) < 6:
        values.append(theme.MUTED)
    return values


# --------------------------------------------------------------------------- #
# Type
# --------------------------------------------------------------------------- #


def _font_scheme(xml: str) -> str:
    """Set the major and minor Latin faces, and touch nothing else.

    The font scheme also carries a script table — Japanese, Hangul, Thai and a
    dozen more, each naming the face PowerPoint should substitute for text in
    that script. Those are *correct*, they are not Zaram's to choose, and
    replacing the element wholesale would delete them: a deck with a line of
    Japanese in it would fall back to whatever the renderer guessed. So only
    the two `<a:latin>` elements move, one inside `<a:majorFont>` and one
    inside `<a:minorFont>`.

    Major is the sans and minor is the serif, which is the opposite of what the
    names suggest. Major is titles, and `theme.py` sets titles and labels in
    the sans face; minor is body, and body is the serif. `pptx.py` reads the
    same tokens, so the two agree by construction rather than by coincidence.
    """
    xml = _latin_in(xml, "majorFont", theme.WORD_SANS)
    xml = _latin_in(xml, "minorFont", theme.WORD_SERIF)
    return xml


def _latin_in(xml: str, group: str, typeface: str) -> str:
    """Rewrite the `<a:latin>` inside one font group.

    Scoped to the group's own span so `majorFont` and `minorFont` cannot be
    confused for each other — they contain identically-shaped elements, and a
    global substitution would set both to whichever ran last.
    """
    match = re.search(rf"<a:{group}\b.*?</a:{group}>", xml, flags=re.S)
    if match is None:
        return xml
    group_xml = match.group(0)
    replaced = re.sub(
        r"<a:latin\b[^/>]*/>",
        f'<a:latin typeface="{typeface}"/>',
        group_xml,
        count=1,
    )
    return xml[: match.start()] + replaced + xml[match.end() :]


def _scheme_name(xml: str) -> str:
    """Name the theme.

    Cosmetic and worth doing: the name is what PowerPoint shows in its Themes
    gallery, so a deck whose design is Zaram's and whose theme is called
    "Office Theme" is a deck that lies quietly in a dropdown.
    """
    return re.sub(
        r'(<a:theme\b[^>]*?\sname=")[^"]*(")', r"\1Zaram\2", xml, count=1
    )


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #


def style_table(table, *, numeric_columns: Sequence[int] = ()) -> None:
    """A table that looks like the one in the PDF, not like a PowerPoint table.

    `word_theme.style_table` is the same function for the same reason, and the
    differences are the format's: PowerPoint applies a *style* by GUID where
    Word applies one by name, and it has no equivalent of Word's cell-level
    border XML that is worth reaching for — banding and the header fill are
    what actually read from a distance, so those are what is set.

    Direct formatting is used here, unavoidably. There is no style slot for
    "this column is figures", and right-aligning numbers is not decoration: a
    column of fees that does not line up on the decimal cannot be read down.
    """
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Pt

    _plain_style(table)

    # Banding off. It is on by default and it is the loudest thing in a stock
    # PowerPoint table — alternate rows filled in the accent colour, which turns
    # a fee schedule into a striped block.
    table.horz_banding = False
    table.first_row = True

    numeric = set(numeric_columns)
    header_colour = RGBColor.from_string(theme.MUTED.upper())
    ink = RGBColor.from_string(theme.INK.upper())

    for row_index, row in enumerate(table.rows):
        for column_index, cell in enumerate(row.cells):
            cell.fill.background()
            for paragraph in cell.text_frame.paragraphs:
                if column_index in numeric:
                    paragraph.alignment = PP_ALIGN.RIGHT
                for run in paragraph.runs:
                    font = run.font
                    font.name = theme.WORD_SANS if row_index == 0 else theme.WORD_SERIF
                    font.size = Pt(theme.SMALL_PT + 2)
                    font.bold = row_index == 0
                    font.color.rgb = header_colour if row_index == 0 else ink


def _plain_style(table) -> None:
    """Swap the banded accent style for borders-only.

    `python-pptx` exposes no API for this, so the style id is written into the
    table's XML directly. Guarded rather than assumed: if the shape does not
    carry a style id, the default was already something else and forcing one
    would be a change nobody asked for.
    """
    frame = table._graphic_frame._element  # noqa: SLF001 — no public accessor exists
    for element in frame.iter():
        if element.tag.endswith("}tableStyleId") and (element.text or "") == _BANDED_TABLE:
            element.text = _PLAIN_TABLE
