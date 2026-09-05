"""HTML → HTML. The source of truth, handed over unchanged.

The shortest exporter in the product, and the one whose *absence* was the
oddity: HTML is what every other format is rendered from, it is what the
preview shows, and it was the one thing the user could not have a copy of.

**Unchanged, deliberately.** Not reformatted, not minified, not stripped of the
claim anchors. This file is the artifact's `html` field byte for byte, so a user
who opens it sees exactly what the preview showed and exactly what WeasyPrint
consumed. Any transformation here would create a fourth rendering that can
disagree with the other three.

The anchors stay for the same reason. `strip_anchors` exists for formats that
cannot carry custom markup — .docx, .md — and HTML is not one of them. This is
the only export that keeps provenance machine-readable, which makes it the
format to hand to anything that wants to check the document rather than read it.

Self-contained, because the source is: styles are inlined in a `<style>` block
and images are `data:` URIs, so the file opens correctly with no network and no
sibling files. That is a property of `html.py`, not something re-established
here, and it is why this can be a passthrough at all.
"""

from __future__ import annotations

from .base import AVAILABLE, Availability


class HtmlExporter:
    extension = "html"
    media_type = "text/html; charset=utf-8"
    label = "Web page"

    def availability(self) -> Availability:
        # Nothing to import and nothing to detect. Along with Markdown, one of
        # the two formats that cannot be unavailable on any machine.
        return AVAILABLE

    def export(self, document_html: str, *, filename: str = "") -> bytes:
        return document_html.encode("utf-8")
