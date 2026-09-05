"""Markdown reaches the document as structure, not as literal text.

The structured block types closed the gap in the renderer. They did not close
it in practice, because they are an API and a language model does not assemble
JSON — **it writes markdown.** Asked for a proposal it produces `## Scope of
Work`, and until something converts that, the block types are reachable only
from code that already knows to build them. That is the same "reachable only
from Python" shape `test_deck_api.py` was written about.

Two of these tests are worth more than the others.

`test_raw_html_from_a_model_cannot_reach_the_file` is the one to keep if any is
ever cut. `MarkdownIt("commonmark")` enables raw HTML by default — measured,
not assumed — so the naive construction passes `<script>` from a model's reply
straight into a file the user sends to a client.

`test_an_image_is_dropped_to_its_alt_text` guards a rule no markdown library
has any reason to know about: an image names a URL, and a generated document
that fetches one is a remote asset arriving inside a data file, where
`check-no-remote-assets.mjs` cannot see it because that scans source.
"""

from __future__ import annotations

from artifacts.contracts import BulletList, Heading, RichText, TableBlock
from artifacts.html import render_document
from artifacts.markdown_blocks import blocks_from_markdown, inline_html


def _kinds(blocks):
    return [type(b).__name__ for b in blocks]


class TestStructure:
    def test_a_heading_becomes_a_heading(self):
        blocks = blocks_from_markdown("## Scope of Work")
        assert _kinds(blocks) == ["Heading"]
        assert blocks[0].text.html == "Scope of Work"

    def test_a_bullet_list_becomes_a_list(self):
        blocks = blocks_from_markdown("- one\n- two")
        assert _kinds(blocks) == ["BulletList"]
        assert len(blocks[0].items) == 2
        assert blocks[0].ordered is False

    def test_a_numbered_list_is_ordered(self):
        assert blocks_from_markdown("1. one\n2. two")[0].ordered is True

    def test_a_table_becomes_a_table(self):
        blocks = blocks_from_markdown("| A | B |\n|---|---|\n| 1 | 2 |")
        assert _kinds(blocks) == ["TableBlock"]
        table = blocks[0]
        assert [c.html for c in table.header] == ["A", "B"]
        assert [c.html for c in table.rows[0]] == ["1", "2"]

    def test_prose_becomes_prose(self):
        assert _kinds(blocks_from_markdown("Just a sentence.")) == ["RichText"]

    def test_a_whole_document_keeps_its_order(self):
        blocks = blocks_from_markdown(
            "## Scope\n\nProse.\n\n- a\n- b\n\n### Fees\n\n| P | A |\n|---|---|\n| x | 1 |"
        )
        assert _kinds(blocks) == [
            "Heading", "RichText", "BulletList", "Heading", "TableBlock"
        ]


class TestHeadingLevels:
    """A model's depths are relative; a document's are absolute."""

    def test_the_shallowest_heading_becomes_h2(self):
        # One model opens with `#`, another with `##`, and both mean
        # "top-level section".
        assert blocks_from_markdown("# Scope")[0].level == 2
        assert blocks_from_markdown("## Scope")[0].level == 2

    def test_depth_below_the_shallowest_is_kept(self):
        blocks = blocks_from_markdown("## Scope\n\n### Fees")
        assert [b.level for b in blocks] == [2, 3]

    def test_deep_headings_clamp_rather_than_raise(self):
        # `####` in a reply is a formatting habit, not a request to refuse.
        blocks = blocks_from_markdown("# A\n\n#### B")
        assert [b.level for b in blocks] == [2, 3]

    def test_a_leading_heading_repeating_the_title_is_dropped(self):
        # The masthead has already set this as the <h1>. Keeping both gives the
        # page two titles and the .docx two competing Title styles.
        blocks = blocks_from_markdown("# Proposal\n\n## Scope", title="Proposal")
        assert _kinds(blocks) == ["Heading"]
        assert blocks[0].text.html == "Scope"
        assert blocks[0].level == 2

    def test_a_later_heading_repeating_the_title_is_kept(self):
        # A section *about* the title is a real section.
        blocks = blocks_from_markdown("## Scope\n\n## Proposal", title="Proposal")
        assert len(blocks) == 2


class TestInlineFormatting:
    def test_bold_and_italic_survive(self):
        assert inline_html("a **b** c").html == "a <strong>b</strong> c"
        assert inline_html("a *b* c").html == "a <em>b</em> c"

    def test_code_survives(self):
        assert inline_html("run `x`").html == "run <code>x</code>"

    def test_a_link_keeps_its_words(self):
        # Dropping <a> wholesale would silently delete words from the sentence.
        assert inline_html("see [the terms](http://x)").html == "see the terms"

    def test_formatting_survives_into_a_list_item(self):
        blocks = blocks_from_markdown("- a **b**")
        assert blocks[0].items[0].html == "a <strong>b</strong>"


class TestWhatMustNotGetThrough:
    def test_raw_html_from_a_model_cannot_reach_the_file(self):
        # `MarkdownIt("commonmark")` enables raw HTML by default. This is the
        # test to keep if any other in this file is ever cut.
        blocks = blocks_from_markdown("<script>alert(1)</script>")
        html = render_document(title="T", blocks=blocks)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_an_event_handler_cannot_reach_the_file(self):
        html = render_document(
            title="T", blocks=blocks_from_markdown("text <b onclick=steal()>x</b>")
        )
        # The handler survives as *visible text*, which is the correct
        # degradation — the author sees what the model wrote. What must not
        # exist is a live tag carrying it.
        assert "<b onclick" not in html
        assert "&lt;b onclick=steal()&gt;" in html

    def test_an_image_is_dropped_to_its_alt_text(self):
        # A markdown image names a URL. A generated document that fetches one
        # is a remote asset arriving inside a data file.
        html = render_document(
            title="T", blocks=blocks_from_markdown("![a logo](http://tracker/x.png)")
        )
        assert "tracker" not in html
        # Not a bare `"img" not in html`: the stylesheet carries an `img{...}`
        # rule, so that substring is present in every document and the
        # assertion would have been measuring the CSS.
        assert "<img" not in html
        assert "a logo" in html

    def test_an_unknown_inline_tag_is_unwrapped_not_passed_through(self):
        # Narrower than "safe HTML" on purpose: a tag `export/_reader.py` does
        # not parse survives the preview and vanishes on export to .docx with
        # nothing reporting it.
        assert inline_html("~~struck~~").html == "~~struck~~"


class TestItReachesThePage:
    def test_a_markdown_document_renders_as_a_document(self):
        html = render_document(
            title="Proposal",
            blocks=blocks_from_markdown(
                "# Proposal\n\n## Scope\n\nA **three-phase** rollout.\n\n"
                "- Discovery\n- Build\n\n### Fees\n\n| Phase | Amount |\n"
                "|---|---|\n| Build | 1,020,000 |",
                title="Proposal",
            ),
        )
        assert "<h2>Scope</h2>" in html
        assert "<h3>Fees</h3>" in html
        assert "<strong>three-phase</strong>" in html
        assert "<ul><li>Discovery</li><li>Build</li></ul>" in html
        assert "<th>Phase</th>" in html
        # The title is not restated as a body heading.
        assert "<h2>Proposal</h2>" not in html

    def test_the_exporters_can_read_what_markdown_produced(self):
        from artifacts.export._reader import read as read_document

        html = render_document(
            title="P",
            blocks=blocks_from_markdown("## Scope\n\n- a\n- b\n\nProse."),
        )
        document = read_document(html)
        tags = [b.tag for b in document.body_blocks()]
        assert "h2" in tags
        assert tags.count("li") == 2

    def test_bold_survives_all_the_way_to_the_exporter(self):
        from artifacts.export._reader import read as read_document

        html = render_document(title="P", blocks=blocks_from_markdown("a **b**"))
        runs = [r for b in read_document(html).body_blocks() for r in b.runs]
        assert any(r.bold for r in runs), runs


class TestModelsThatFenceTheirOutput:
    """Found by running a real model, which is why the class exists.

    Asked to "output only the Markdown document", `qwen2.5-coder:14b` returned
    the whole statement of work wrapped in ```markdown. Every heading, list and
    table then parsed as *the contents of one code block* — the document
    collapsed into a single monospace paragraph, a worse version of the failure
    this module was written to fix.

    No hand-written test markdown would have produced that. gemma4:12b does not
    do it; the coder model does it every time. "All local models" is not one
    behaviour, and the adapter has to absorb the difference.
    """

    def test_a_whole_document_in_a_markdown_fence_is_unwrapped(self):
        blocks = blocks_from_markdown(
            "```markdown\n# Title\n\n## Scope\n\n- a\n- b\n```"
        )
        assert _kinds(blocks) == ["Heading", "Heading", "BulletList"]

    def test_an_unlabelled_fence_around_the_whole_document_is_unwrapped(self):
        # A model that fences its whole reply often labels it with nothing.
        blocks = blocks_from_markdown("```\n## Scope\n\n- a\n```")
        assert _kinds(blocks) == ["Heading", "BulletList"]

    def test_a_code_sample_inside_a_document_stays_code(self):
        # The bound is narrow on purpose: this unwraps only when the fence *is*
        # the document.
        blocks = blocks_from_markdown("Intro.\n\n```python\nx = 1\n```")
        assert len(blocks) == 2
        assert "<code>" in blocks[1].html

    def test_a_lone_code_sample_in_a_real_language_stays_code(self):
        blocks = blocks_from_markdown("```python\nx = 1\n```")
        assert "<code>" in blocks[0].html
        assert "x = 1" in blocks[0].html

    def test_a_fenced_table_survives_unwrapping(self):
        blocks = blocks_from_markdown(
            "```markdown\n## Fees\n\n| P | A |\n|---|---|\n| x | 1 |\n```"
        )
        assert _kinds(blocks) == ["Heading", "TableBlock"]
