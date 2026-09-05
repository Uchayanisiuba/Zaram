"""Reading an attached document's *shape*, so a new one can be made in it.

"Write my CV like this one." "Draft the proposal in the same format as the
Harbour Lane one." Both are ordinary requests and neither worked: an attached
file reached the model as *text to answer questions about*, so the reference's
wording leaked into the reply and its structure did not.

**Structure, not styling, and the line is the point.** What this extracts is
the section order — the headings, as they appear, in the order they appear.
What it deliberately does not extract is the visual design, because that is
Zaram's and has to stay Zaram's:

* A model asked to reproduce a layout produces a different one each time, and
  an invoice that looks different every month reads as unprofessional.
* Model-authored markup can reference a remote font or image, which is a
  request leaving the machine that the egress log cannot see.
* The claim anchors that make a sentence traceable are inserted by the
  composer, not by the model.

So the reference answers *"what sections does this kind of document have"* and
`artifacts/html.py` keeps answering *"what does it look like"*.

Read from the whole file, never from the excerpt
------------------------------------------------
`compose` gives a long document a budget and selects passages by overlap with
the question. That is right for answering a question and wrong for reading a
shape: the selection is free to drop the very headings the outline is made of,
so a forty-page reference would produce an outline of whichever three sections
happened to match the wording of the request. The outline is therefore taken
from `Attachment.text` in full, before any budget applies, and only the
resulting list of headings is charged against the context.

Heuristics, and what they refuse to do
--------------------------------------
There is no heading markup in plain text, so this is inference. It is written
to fail towards *fewer* headings rather than more: a line wrongly promoted to a
heading becomes a section in the generated document that its author never had,
which is a fabricated structure, while a heading that is missed only makes the
exemplar thinner. `Missing` is not needed here — an empty outline is a real
answer meaning "this file has no structure to copy", and the caller says so.
"""

from __future__ import annotations

import re
from typing import List, Sequence

#: The longest a line may be and still be read as a heading.
#:
#: Headings are labels. A line of eighty characters is a sentence that happens
#: to be short, and admitting it is how the outline fills with prose.
_MAX_HEADING_CHARS = 72

#: How many headings are carried. Enough for a real document's contents page;
#: past this the exemplar stops being a shape and becomes a second document in
#: the context.
_MAX_HEADINGS = 24

#: `# Heading`, `## Heading` — the one unambiguous case.
_MARKDOWN = re.compile(r"^\s{0,3}(#{1,4})\s+(.+?)\s*#*\s*$")

#: `1. Scope`, `2 Fees`, `IV. Terms`, `3.1 Payment`.
_NUMBERED = re.compile(r"^\s*((?:\d+\.?)+|[IVXLC]+\.)\s+(\S.*)$")

#: Punctuation that ends a sentence. A line ending in one of these is prose,
#: whatever else it looks like — including a colon, which introduces the thing
#: it precedes rather than naming a section.
_SENTENCE_END = ".,;:!?"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_heading(line: str, following: str) -> bool:
    """Whether a plain line is a section heading.

    Two signals, and both are required, because either alone is common in
    ordinary prose: the line is short and unpunctuated *and* what follows it is
    a break or a new paragraph. A short unpunctuated line in the middle of a
    paragraph is a line of an address or a name in a list.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > _MAX_HEADING_CHARS:
        return False
    if stripped[-1] in _SENTENCE_END:
        return False
    # A line with no letters is a rule, a page number or a stray figure.
    if not any(character.isalpha() for character in stripped):
        return False
    # Nine words is generous for a heading and short for a sentence.
    if len(stripped.split()) > 9:
        return False
    return not following.strip()


def outline_of(text: str) -> List[str]:
    """The headings of a document, in order, as they were written.

    Duplicates are dropped rather than repeated: a running header on every page
    of a PDF arrives as the same line forty times, and forty copies of it is
    not a structure.
    """
    lines = (text or "").splitlines()
    headings: List[str] = []
    seen: set[str] = set()

    for index, line in enumerate(lines):
        following = lines[index + 1] if index + 1 < len(lines) else ""

        markdown = _MARKDOWN.match(line)
        numbered = _NUMBERED.match(line)
        if markdown:
            heading = _clean(markdown.group(2))
        elif numbered and _is_heading(numbered.group(2), following):
            # The number is kept: "3.1 Payment" and "Payment" are different
            # facts about the reference, and the numbering is part of the shape
            # somebody is asking to copy.
            heading = _clean(line)
        elif _is_heading(line, following):
            heading = _clean(line)
        else:
            continue

        key = heading.casefold()
        if not heading or key in seen:
            continue
        seen.add(key)
        headings.append(heading)
        if len(headings) >= _MAX_HEADINGS:
            break

    return headings


def structure_line(headings: Sequence[str]) -> str:
    """The outline as one line for the prompt, or `""` when there is none.

    One line rather than a list, because it sits inside a block that is already
    a list of files and a nested list reads as content rather than as a note
    about the file above it.
    """
    if not headings:
        return ""
    return "Its sections, in order: " + " · ".join(headings)


#: Said once, under the attached files, when at least one of them has a shape.
#:
#: **Conditional in its wording rather than in its presence**, and that is
#: deliberate. Deciding whether *this* request is a "write me one like this"
#: request would mean classifying intent in the API layer — a second classifier
#: beside the planner's, disagreeing with it on exactly the ambiguous cases.
#: The sentence costs a few tokens on every attachment and is inert unless the
#: user actually asked for a document.
#:
#: The last clause is the one that matters: the reference supplies a shape, not
#: sentences. Without it a model asked to "write mine like this" returns the
#: reference with the names changed, which is somebody else's document with the
#: user's name on it.
REFERENCE_NOTE = (
    "If the user asks for a document in the same shape or format as one of the "
    "files above, follow that file's sections and their order, and write the "
    "content from what the user has told you. Never copy its sentences or "
    "carry over its names, figures or dates."
)
