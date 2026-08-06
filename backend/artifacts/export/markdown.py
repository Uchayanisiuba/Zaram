"""HTML → Markdown. No dependencies, so it always works.

Worth having for a reason beyond completeness: it is the one format that is
always available, on every machine, with nothing installed. When PDF is blocked
on native libraries and the user wants something portable *now*, this is the
answer that does not require a packaging decision first.

Provenance survives as a reference-style footnote per claim. Markdown has no
attribute syntax, so the machine-readable anchor cannot travel — which is
exactly the case `strip_anchors` is named for. What travels is the human half:
the sentence is marked, and the mark resolves to the source at the bottom of the
file. That is legible in a plain-text editor with nothing else installed, which
is the property this format is for.
"""

from __future__ import annotations

from . import _reader
from .base import AVAILABLE, Availability


class MarkdownExporter:
    extension = "md"
    media_type = "text/markdown"
    label = "Markdown"

    def availability(self) -> Availability:
        return AVAILABLE

    def export(self, document_html: str, *, filename: str = "") -> bytes:
        doc = _reader.read(document_html)
        lines: list[str] = []

        # Claim id → footnote number, assigned in order of first appearance so
        # the footnotes read top to bottom like the document does.
        footnotes: dict[str, int] = {}
        sources_by_claim: dict[str, str] = {}

        for block in doc.source_blocks():
            if block.anchor and block.anchor.startswith("claim-"):
                sources_by_claim[block.anchor[len("claim-") :]] = block.text.strip()

        for block in doc.body_blocks():
            rendered = "".join(
                self._run(run, footnotes) for run in block.runs
            ).strip()
            if not rendered:
                continue

            if block.tag == "h1":
                lines += [f"# {rendered}", ""]
            elif block.tag in ("h2", "h3"):
                lines += [f"## {rendered}", ""]
            elif block.tag == "li":
                lines.append(f"- {rendered}")
            else:
                lines += [rendered, ""]

        lines += ["", "---", "", "## Sources", ""]

        source_lines = [
            f"- {b.text.strip()}"
            for b in doc.source_blocks()
            if b.tag == "li" and b.text.strip()
        ]
        lines += source_lines or [
            "Nothing was recalled for this document.",
        ]

        if footnotes:
            lines += ["", "## Claims", ""]
            for claim_id, number in sorted(footnotes.items(), key=lambda kv: kv[1]):
                source = sources_by_claim.get(claim_id, claim_id)
                lines.append(f"[^{number}]: {source}")

        return ("\n".join(lines).rstrip() + "\n").encode("utf-8")

    @staticmethod
    def _run(run: _reader.Run, footnotes: dict[str, int]) -> str:
        text = run.text
        if run.code:
            text = f"`{text.strip()}`"
        if run.bold:
            text = f"**{text}**"
        if run.italic:
            text = f"*{text}*"

        if run.claim_id:
            number = footnotes.setdefault(run.claim_id, len(footnotes) + 1)
            text = f"{text}[^{number}]"

        return text
