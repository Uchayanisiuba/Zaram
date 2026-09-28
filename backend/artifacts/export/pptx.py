"""HTML → .pptx.

`CLAUDE.md` deferred PowerPoint with "later, only if asked". It was asked for on
10 August 2026, so it is here — and the way it is built is the interesting part.

**Headings are the slide boundaries.** There is no separate deck format and no
second authoring path: `<h1>` becomes the title slide, every `<h2>` starts a new
one, and the paragraphs and list items beneath it become that slide's bullets.
That falls out of HTML being the source of truth rather than being designed on
top of it, and it buys something a dedicated deck format would not — **any
document Zaram has already generated can be exported as slides**, because every
document has headings. A proposal becomes a pitch without being rewritten.

Tables and pictures land in their own section — 23 September 2026
-----------------------------------------------------------------
This used to read *"`_reader` collects tables separately from blocks, so their
position relative to the headings is not recoverable… that is a real loss of
ordering and it is preferred to the alternatives"*. It was a real loss, and by
the time anybody re-read the sentence it was not the only option available:
`Table.after_block` had been carrying the position for the Word exporter for
weeks, and this exporter was not reading the field. A cost accepted in a
docstring outlives the constraint that justified it, which is the general
lesson worth keeping — **the note is not evidence; the code is.**

So a fee table now follows the section it was written in, and pictures work
the same way. What is still deliberate is that each gets **its own slide**:
PowerPoint's content placeholder is the column a bullet list occupies, and a
table or a chart squeezed into it is unreadable from the back of a room.

It carries the same design as everything else — 4 September 2026
--------------------------------------------------------------
This used to read *"nothing here is a theme… a deck someone presents is one they
will restyle, and a hardcoded palette is one more thing to undo."* The
maintainer looked at the output and disagreed, and the measurement settles it
rather than the argument: the deck came out **4:3** — 10 by 7.5 inches, the
default `python-pptx` template — with **not one run carrying a font, a size or a
colour**. That is not restraint leaving room for someone's own template; it is
Office 2003 with the lights off.

The reasoning was wrong in a specific way worth naming. *Not styling* is not the
neutral choice — python-pptx's stock template is itself a design, just nobody's.
`theme.py` was written after exactly this discovery about Word, where the same
"leave it to the renderer" produced Calibri 11 and Word 2007 blue, and its
opening line applies here unchanged: **two renderers had two designs, and only
one of them was designed.** So the deck reads the same tokens as the HTML and
the Word file, and a proposal exported three ways looks like three views of one
document.

**16:9, because 4:3 is not a taste question.** Every projector, laptop and
conferencing tool made since about 2012 is widescreen; a 4:3 deck is pillarboxed
on all of them, which reads as a file made by accident.

What is still left alone: the layouts themselves. Slide masters, backgrounds and
placeholder geometry stay the template's, so a user who applies their own theme
in PowerPoint gets it applied to a deck whose structure is ordinary. Type and
colour are what carry the identity; moving the boxes would be the "one more
thing to undo" the old note was actually right about.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import _reader, pptx_theme
from .. import theme
from .base import Availability, module_available

#: Layout indices in python-pptx's default template. Named because `slide_layouts[1]`
#: at a call site is unreadable and wrong-by-one is silent.
_TITLE_SLIDE = 0
_TITLE_AND_CONTENT = 1
_TITLE_ONLY = 5
#: Used for the slides this exporter composes itself — a statement, a row of
#: metrics, a section divider. A placeholder layout would have to be deformed to
#: hold any of them, and geometry that fights a user's applied theme is exactly
#: what `pptx_theme` declines to write. A blank layout has nothing to fight.
_BLANK = 6

#: 16:9, in inches. The height is the template's own 7.5; only the width moves,
#: so every placeholder the layouts define keeps its vertical position.
_WIDESCREEN_IN = (13.333, 7.5)

#: Type sizes for a room, not for a page.
#:
#: `theme.py`'s sizes are print sizes — 11pt body, 20pt title — and a deck read
#: from the back of a room is a different instrument. What is shared is the
#: *faces* and the *colours*, which is what makes the three exports look like
#: one document; the scale is this format's own.
_TITLE_PT = 32.0
_COVER_TITLE_PT = 40.0
_BULLET_PT = 18.0
_TABLE_PT = 12.0

#: Past this, a slide is a wall of text nobody reads from the back of a room.
#: Overflow continues on a slide marked "(cont.)" rather than being dropped or
#: shrunk to fit — losing content silently is the one outcome that is not
#: recoverable by the person editing the deck afterwards.
_MAX_BULLETS = 8

#: Deck sizes for the design blocks. `theme.py`'s are print sizes, and the note
#: on `_TITLE_PT` above gives the rule this follows: the faces and the colours
#: are shared, the scale is this format's own.
_STATEMENT_PT = 28.0
_METRIC_PT = 54.0
_METRIC_LABEL_PT = 12.0
_CALLOUT_PT = 20.0
_DIVIDER_PT = 40.0


#: Roles that earn a slide of their own rather than becoming a bullet.
#: `divider` is absent on purpose — it opens a section as well as getting a
#: slide, so `_outline` handles it beside the headings instead.
_DESIGNED_ROLES = {"statement", "metric", "callout"}


def _is_metric(item: object) -> bool:
    return isinstance(item, _reader.Block) and item.role == "metric"


@dataclass
class _Section:
    """One heading and everything under it, in the order it was written."""

    heading: str
    bullets: List[str] = field(default_factory=list)
    #: True when the heading came from a `Divider` rather than from an ordinary
    #: `<h2>`. A divider gets a slide to itself before its content, which is the
    #: structural half of a deck not looking flat — fourteen content slides in a
    #: row read as one undifferentiated block however well each is typeset.
    divider: bool = False
    #: Tables and pictures, each with the block position it opened at, so a
    #: chart written above a fee table is still above it on the slides.
    extras: List[Tuple[int, object]] = field(default_factory=list)

    def ordered_extras(self) -> List[object]:
        """Everything that gets its own slide, in the order it was written.

        Consecutive metrics are merged into one list, because a row of figures
        is one slide and four slides each holding a single number is the deck
        this change exists to stop making. Merging here rather than in
        `_outline` keeps the grouping next to the reason for it, and keeps
        `extras` a plain record of position.
        """
        merged: List[object] = []
        for _, item in sorted(self.extras, key=lambda pair: pair[0]):
            if _is_metric(item) and merged and isinstance(merged[-1], list):
                merged[-1].append(item)
            elif _is_metric(item):
                merged.append([item])
            else:
                merged.append(item)
        return merged


class PptxExporter:
    extension = "pptx"
    media_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    label = "PowerPoint"

    def availability(self) -> Availability:
        return module_available("pptx", needed_for="PowerPoint export")

    def export(self, document_html: str, *, filename: str = "") -> bytes:
        from pptx import Presentation

        from pptx.util import Inches

        doc = _reader.read(document_html)
        deck = Presentation()
        deck.slide_width = Inches(_WIDESCREEN_IN[0])
        deck.slide_height = Inches(_WIDESCREEN_IN[1])
        # Before any slide is added, not after: a layout copies the colour scheme
        # onto its placeholders as it is instantiated, so a theme written later
        # reaches the master and misses every slide already built from it.
        pptx_theme.apply(deck)

        title, sections, leading = self._outline(doc)

        cover = deck.slides.add_slide(deck.slide_layouts[_TITLE_SLIDE])
        cover.shapes.title.text = title or "Untitled"
        self._style(cover.shapes.title, size=_COVER_TITLE_PT, colour=theme.INK, bold=True)
        # Placeholder 1 is the subtitle. Cleared rather than left holding
        # "Click to add subtitle", which is what ships in the template and what
        # would otherwise be presented to a room.
        if len(cover.placeholders) > 1:
            cover.placeholders[1].text = ""

        # A table or picture that opened before the first heading. Rare, and it
        # goes straight after the cover rather than inventing a section header
        # nobody wrote.
        for item in leading:
            self._extra_slide(deck, item, section=title)

        for section in sections:
            if section.divider:
                self._divider_slide(deck, section.heading)
            # A divider with no prose under it has already had its slide. The
            # rule below — an empty heading is still a section marker — was
            # written before dividers existed, and a divider *is* that marker;
            # honouring both produced two consecutive slides with one title and
            # nothing on the second. Found by reading the output, which is the
            # only place it was visible.
            chunks = self._chunk(section.bullets)
            if section.divider and not any(chunk for chunk in chunks):
                chunks = []
            for index, chunk in enumerate(chunks):
                slide = deck.slides.add_slide(deck.slide_layouts[_TITLE_AND_CONTENT])
                slide.shapes.title.text = (
                    section.heading if index == 0 else f"{section.heading} (cont.)"
                )
                # The accent on section titles and nowhere else, which is the
                # same rule `theme.ACCENT` follows on the page: one accent, used
                # for the thing that says what this is.
                self._style(slide.shapes.title, size=_TITLE_PT, colour=theme.ACCENT, bold=True)
                frame = slide.placeholders[1].text_frame
                frame.clear()
                for position, bullet in enumerate(chunk):
                    paragraph = frame.paragraphs[0] if position == 0 else frame.add_paragraph()
                    paragraph.text = bullet
                    paragraph.level = 0
                self._style(slide.placeholders[1], size=_BULLET_PT, colour=theme.INK)

            for item in section.ordered_extras():
                self._extra_slide(deck, item, section=section.heading)

        buffer = io.BytesIO()
        deck.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _outline(
        doc: _reader.Document,
    ) -> Tuple[str, List[_Section], List[object]]:
        """Title, the sections under it, and anything that came before them.

        Content before the first `<h2>` is gathered under the document title, so
        an opening paragraph is not thrown away for arriving early.

        Tables and pictures arrive on their own lists rather than in the block
        stream — `Table.after_block` records why — so this walks **every**
        block, including the ones in the Sources section that never become a
        slide, and keeps which section was open at each position. Dropping the
        sources blocks from the walk would shift every index after them and
        move a fee table into the wrong part of the deck.
        """
        title = ""
        sections: List[_Section] = []
        current: Optional[_Section] = None
        #: The section open when each block was read, by block index. Recorded
        #: before the block is processed, because a table at position `i`
        #: opened *before* block `i` was read — and one entry longer than
        #: `blocks`, because a table at the very end opens after the last one.
        section_at: List[int] = []

        #: Design blocks that will each get a slide, paired with the position
        #: they were read at — the same `(position, item)` shape `extras` already
        #: carries for tables and pictures, so they sort into one order together.
        designed: List[Tuple[int, object]] = []

        for index, block in enumerate(doc.blocks):
            section_at.append(len(sections) - 1)
            if block.in_sources:
                continue

            text = block.text.strip()
            if not text:
                continue

            if block.tag == "h1" and not title:
                title = text
                continue

            if block.role == "divider":
                # A divider opens a section *and* gets a slide, which is why it
                # is handled before the heading branch below rather than by it.
                current = _Section(heading=text, divider=True)
                sections.append(current)
                continue

            if block.tag in ("h1", "h2", "h3"):
                current = _Section(heading=text)
                sections.append(current)
                continue

            if block.role in _DESIGNED_ROLES:
                # Not a bullet. This is the whole point: a statement flattened
                # into a bullet is a statement with its emphasis removed, which
                # is the failure the block type was added to fix.
                designed.append((index, block))
                continue

            if current is None:
                current = _Section(heading=title or "Overview")
                sections.append(current)
            current.bullets.append(text)

        section_at.append(len(sections) - 1)

        extras: List[Tuple[int, object]] = list(designed)
        extras += [(table.after_block, table) for table in doc.tables]
        extras += [
            (image.after_block, image)
            for image in doc.images
            # The letterhead's mark is chrome the masthead draws, not content.
            # A slide of somebody's logo is not what they asked for.
            if "logo" not in image.role.split()
        ]

        leading: List[object] = []
        for position, item in sorted(extras, key=lambda pair: pair[0]):
            index = section_at[min(position, len(section_at) - 1)] if section_at else -1
            if index < 0:
                leading.append(item)
            else:
                sections[index].extras.append((position, item))

        # A heading with nothing under it is still a slide: it is a section
        # marker, and dropping it loses the deck's structure.
        return title, sections, leading

    @staticmethod
    def _extra_slide(deck, item: object, *, section: str = "") -> None:
        """Whatever this is, on a slide of its own.

        ``section`` is the heading the item was written under, used only where
        the item itself supplies no title. A table in a section called "What it
        costs" is a slide called "What it costs"; calling it "Table" is what a
        renderer says when nobody asked a person.
        """
        if isinstance(item, list):
            PptxExporter._metric_slide(deck, item)
        elif isinstance(item, _reader.Image):
            PptxExporter._picture_slide(deck, item)
        elif isinstance(item, _reader.Block):
            if item.role == "statement":
                PptxExporter._statement_slide(deck, item)
            elif item.role == "callout":
                PptxExporter._callout_slide(deck, item)
            else:
                # A role this exporter has not learned still reaches a reader.
                # Silence would be a slide the author cannot see is missing.
                PptxExporter._statement_slide(deck, item)
        else:
            PptxExporter._table_slide(deck, item, section=section)

    # -- the composed slides -------------------------------------------------
    #
    # Each of these draws its own shapes on `_BLANK` rather than filling a
    # placeholder. That is the one place this exporter writes geometry, and
    # `pptx_theme`'s note says why it is allowed here and nowhere else: a
    # placeholder is something a user's own theme can re-apply, so deforming one
    # is a fight; a blank slide is not.

    @staticmethod
    def _statement_slide(deck, block) -> None:
        """One sentence, centred, with nothing to read but it."""
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

        slide = deck.slides.add_slide(deck.slide_layouts[_BLANK])
        box = slide.shapes.add_textbox(
            Inches(1.4), Inches(1.8), deck.slide_width - Inches(2.8), Inches(3.9)
        )
        frame = box.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        paragraph = frame.paragraphs[0]
        paragraph.alignment = PP_ALIGN.LEFT
        paragraph.text = block.text.strip()
        PptxExporter._style(box, size=_STATEMENT_PT, colour=theme.INK, bold=False)
        for line in frame.paragraphs:
            line.line_spacing = 1.25

        # The accent rule, which is what ties this slide to the same block on the
        # page. A shape rather than a border: PowerPoint has no left border on a
        # text box, and a 1-inch-wide rectangle is exactly what the CSS draws.
        PptxExporter._accent_bar(slide, Inches(1.0), Inches(1.9), Inches(0.045), Inches(3.7), theme.ACCENT)

    @staticmethod
    def _metric_slide(deck, blocks) -> None:
        """A row of figures, each under nothing and over its own label.

        The value/label split is read off `Run.bold` — set deliberately by
        `html._metric_block` — so nothing here parses a string. Columns are
        divided evenly across the usable width, which is why the count is
        bounded: five on a 16:9 slide gives each label less room than its words.
        """
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

        pairs = []
        for block in blocks[:4]:
            value = "".join(r.text for r in block.runs if r.bold).strip()
            label = "".join(r.text for r in block.runs if not r.bold).strip()
            if value or label:
                pairs.append((value or label, label if value else ""))
        if not pairs:
            return

        slide = deck.slides.add_slide(deck.slide_layouts[_BLANK])
        margin = Inches(1.0)
        usable = deck.slide_width - margin * 2
        width = int(usable / len(pairs))

        for position, (value, label) in enumerate(pairs):
            box = slide.shapes.add_textbox(
                margin + width * position, Inches(2.5), width - Inches(0.3), Inches(2.2)
            )
            frame = box.text_frame
            frame.word_wrap = True
            frame.vertical_anchor = MSO_ANCHOR.TOP

            figure = frame.paragraphs[0]
            figure.text = value
            figure.alignment = PP_ALIGN.LEFT
            PptxExporter._run_style(figure, _METRIC_PT, theme.ACCENT, bold=True,
                                    face=theme.WORD_SANS)

            if not label:
                continue
            caption = frame.add_paragraph()
            caption.text = label.upper()
            caption.alignment = PP_ALIGN.LEFT
            caption.space_before = Pt(4)
            PptxExporter._run_style(caption, _METRIC_LABEL_PT, theme.MUTED, bold=True,
                                    face=theme.WORD_SANS)

    @staticmethod
    def _callout_slide(deck, block) -> None:
        """The panel, at the scale of a room."""
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import MSO_ANCHOR

        warn = block.tone == "warn"
        slide = deck.slides.add_slide(deck.slide_layouts[_BLANK])

        left, top = Inches(1.1), Inches(2.2)
        width = deck.slide_width - Inches(2.2)
        height = Inches(3.1)

        panel = slide.shapes.add_textbox(left, top, width, height)
        panel.fill.solid()
        panel.fill.fore_color.rgb = RGBColor.from_string(
            (theme.WASH_WARN if warn else theme.WASH).upper()
        )
        panel.line.fill.background()
        frame = panel.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        frame.margin_left = Inches(0.35)
        frame.margin_right = Inches(0.3)
        frame.paragraphs[0].text = block.text.strip()
        PptxExporter._style(panel, size=_CALLOUT_PT, colour=theme.INK, bold=False)
        for line in frame.paragraphs:
            line.line_spacing = 1.3
        for line in frame.paragraphs:
            for run in line.runs:
                run.font.name = theme.WORD_SANS

        PptxExporter._accent_bar(
            slide, left, top, Inches(0.05), height,
            theme.CAUTION if warn else theme.ACCENT,
        )

    @staticmethod
    def _divider_slide(deck, heading: str) -> None:
        """A section opener: the title, a rule, and deliberately nothing else."""
        from pptx.util import Inches
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

        slide = deck.slides.add_slide(deck.slide_layouts[_BLANK])
        box = slide.shapes.add_textbox(
            Inches(1.0), Inches(2.9), deck.slide_width - Inches(2.0), Inches(1.4)
        )
        frame = box.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = MSO_ANCHOR.BOTTOM
        frame.paragraphs[0].text = heading.strip()
        frame.paragraphs[0].alignment = PP_ALIGN.LEFT
        PptxExporter._style(box, size=_DIVIDER_PT, colour=theme.INK, bold=True)

        PptxExporter._accent_bar(
            slide, Inches(1.05), Inches(4.35), Inches(2.2), Inches(0.045), theme.ACCENT
        )

    @staticmethod
    def _accent_bar(slide, left, top, width, height, colour: str) -> None:
        """A filled rectangle standing in for a CSS border.

        PowerPoint has no left border on a text box, and the rule is what makes
        a statement on a slide recognisably the same block as the statement on
        the page. A rectangle with no outline is exactly what the CSS draws.
        """
        from pptx.dml.color import RGBColor
        from pptx.enum.shapes import MSO_SHAPE

        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
        bar.fill.solid()
        bar.fill.fore_color.rgb = RGBColor.from_string(colour.upper())
        bar.line.fill.background()
        bar.shadow.inherit = False

    @staticmethod
    def _run_style(paragraph, size: float, colour: str, *, bold: bool, face: str) -> None:
        """Style every run in one paragraph.

        `_style` works on a shape and covers all of its text, which is what the
        title and bullet placeholders need. A metric's two paragraphs are two
        different sizes in one frame, so they are styled one at a time.
        """
        from pptx.dml.color import RGBColor
        from pptx.util import Pt

        for run in paragraph.runs:
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.name = face
            run.font.color.rgb = RGBColor.from_string(colour.upper())

    @staticmethod
    def _picture_slide(deck, image: _reader.Image) -> None:
        """One picture, centred, as large as the slide allows.

        Never enlarged past its own size: a 300-pixel chart blown up to fill a
        widescreen slide is worse than a small sharp one, and PowerPoint gives
        no way to tell the difference back to whoever made it.
        """
        from pptx.util import Inches

        if not image.data:
            return

        slide = deck.slides.add_slide(deck.slide_layouts[_TITLE_ONLY])
        slide.shapes.title.text = image.alt or "Figure"
        PptxExporter._style(
            slide.shapes.title, size=_TITLE_PT, colour=theme.ACCENT, bold=True
        )

        try:
            picture = slide.shapes.add_picture(
                io.BytesIO(image.data), Inches(0.6), Inches(1.8)
            )
        except Exception:
            # python-pptx refuses a format it cannot measure, and a picture
            # that will not go in is not worth failing an export over. The
            # slide keeps its title, so the deck says where something was
            # rather than closing over the gap.
            return

        box_width = deck.slide_width - Inches(1.2)
        box_height = deck.slide_height - Inches(2.4)
        scale = min(box_width / picture.width, box_height / picture.height, 1.0)
        picture.width = int(picture.width * scale)
        picture.height = int(picture.height * scale)
        picture.left = int((deck.slide_width - picture.width) / 2)

    @staticmethod
    def _style(shape, *, size: float, colour: str, bold: bool = False) -> None:
        """Set face, size and colour on every run in a shape.

        **Every run, and every paragraph, including the empty ones.** A run is
        created when text is assigned, so a paragraph styled before its text
        exists keeps the template's Calibri — which is how a deck ends up
        styled everywhere except the one line somebody actually reads. Setting
        it on the paragraph's own font as well covers a paragraph that has no
        runs yet.

        `theme.WORD_SERIF` rather than the CSS stack, for the reason `theme.py`
        gives about Word: PowerPoint stores one name and substitutes silently
        if it is absent, so a stack is meaningless and the honest choice is the
        face most likely to be on the machine that opens the file.
        """
        from pptx.dml.color import RGBColor
        from pptx.util import Pt

        frame = getattr(shape, "text_frame", None)
        if frame is None:
            return
        rgb = RGBColor.from_string(colour.upper())
        for paragraph in frame.paragraphs:
            for font in [paragraph.font, *(run.font for run in paragraph.runs)]:
                font.name = theme.WORD_SERIF
                font.size = Pt(size)
                font.bold = bold
                font.color.rgb = rgb

    @staticmethod
    def _chunk(bullets: List[str]) -> List[List[str]]:
        if not bullets:
            return [[]]
        return [bullets[i : i + _MAX_BULLETS] for i in range(0, len(bullets), _MAX_BULLETS)]

    @staticmethod
    def _table_slide(deck, table: _reader.Table, *, section: str = "") -> None:
        from pptx.util import Inches

        grid = ([table.header] if table.header else []) + [list(r) for r in table.rows]
        if not grid:
            return

        columns = max(len(row) for row in grid)
        slide = deck.slides.add_slide(deck.slide_layouts[_TITLE_ONLY])
        # The caption if the composer wrote one, then the section it sits in,
        # and "Table" only when there is genuinely nothing to call it. A GFM
        # table has no caption syntax at all, so the middle case is the common
        # one rather than the fallback.
        slide.shapes.title.text = table.caption or section or "Table"
        # Styled like every other section title. Measured and missed the first
        # time: the deck came out themed on four slides and stock on the fifth,
        # which is worse than uniformly stock because it reads as a rendering
        # fault rather than as a plain template.
        PptxExporter._style(
            slide.shapes.title, size=_TITLE_PT, colour=theme.ACCENT, bold=True
        )

        shape = slide.shapes.add_table(
            len(grid), columns, Inches(0.6), Inches(1.8), Inches(9), Inches(0.4 * len(grid))
        )
        for r, row in enumerate(grid):
            for c in range(columns):
                cell = shape.table.cell(r, c)
                cell.text = str(row[c]) if c < len(row) else ""
                # A header row is set in the muted grey the page uses for the
                # same job, rather than in the template's reversed-out white on
                # a solid band. Reading a table off a slide is scanning, and the
                # page already decided what scanning looks like here.
                PptxExporter._style(
                    cell,
                    size=_TABLE_PT,
                    colour=theme.MUTED if (r == 0 and table.header) else theme.INK,
                    bold=bool(r == 0 and table.header),
                )
