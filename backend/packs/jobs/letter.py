"""A covering letter, as document blocks.

The pack's *output template*, third of the four things `CLAUDE.md` says a pack
is. It produces `artifacts` blocks rather than a string, so the letter goes
through the one pipeline every other document uses — HTML first, then .docx or
PDF — and arrives with the same typography as an invoice or a proposal.

**It writes the frame, never the argument.** The paragraphs a model writes are
passed in; what this owns is the shape a letter has — who it is to, what it is
about, the closing, the name — and the fact that the shape is identical every
time. That split matters: the frame is knowledge about letters, which is what
a pack is for, and the argument is about this person and this job, which is
what recall and the model are for.

Nothing here invents a detail. A letter whose reference line names a salary
the posting never stated is rule 9's failure with a stamp on it, so every
field comes from a `Posting` that was read from real text, and an absent field
is simply absent from the letter.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional, Sequence

from artifacts.contracts import Heading

from .posting import Posting

__all__ = ["cover_letter_blocks", "follow_up_blocks"]


def _reference(posting: Posting) -> List[tuple]:
    """The scan-first block under the masthead: role, company, closing date.

    A reader who opens twenty of these a week reads this and nothing else
    first, which is why it is fields rather than a sentence.
    """
    meta: List[tuple] = []
    if posting.title:
        meta.append(("Role", posting.title))
    if posting.company:
        meta.append(("Company", posting.company))
    if posting.closes:
        meta.append(("Applications close", posting.closes.strftime("%d %B %Y")))
    if posting.apply_url:
        meta.append(("Posting", posting.apply_url))
    return meta


def cover_letter_blocks(
    posting: Posting,
    *,
    body: Sequence[str],
    sender: str = "",
    today: Optional[date] = None,
    greeting: str = "",
    closing: str = "Yours sincerely,",
) -> List[object]:
    """The letter, as blocks `render_document` understands.

    ``body`` is the argument — the paragraphs about why this person and this
    role. Empty is allowed and produces a letter with a frame and no case,
    which is a visibly unfinished document rather than an invented one.

    The greeting defaults to *"Dear Hiring Manager"* only when nothing better
    is known. A name would be better and the posting rarely carries one; a
    guessed name is worse than a generic greeting, because it is wrong at the
    top of the page.
    """
    today = today or date.today()
    who = posting.company or "the company"
    role = posting.title or "the role"

    blocks: List[object] = [
        Heading(text=f"Application for {role}", level=2),
        greeting or "Dear Hiring Manager,",
    ]

    if not body:
        # Said in the document rather than raised, because a caller that asked
        # for a letter with no argument has made a mistake worth seeing on the
        # page, and an exception here would lose the frame that is correct.
        blocks.append(
            f"[The case for this application has not been written yet — "
            f"{role} at {who}.]"
        )
    else:
        blocks.extend(str(paragraph) for paragraph in body if str(paragraph).strip())

    blocks.append(closing)
    if sender:
        blocks.append(sender)
    return blocks


def follow_up_blocks(
    posting: Posting,
    *,
    applied_on: date,
    sender: str = "",
    body: Sequence[str] = (),
) -> List[object]:
    """The seven-day follow-up.

    Short on purpose. A follow-up that restates the covering letter is read as
    a second application; one that says when you applied, what for, and that
    you are still interested is read as a reminder, which is what it is.
    """
    role = posting.title or "the role"
    who = posting.company or "your team"

    blocks: List[object] = [
        Heading(text=f"Following up — {role}", level=2),
        "Dear Hiring Manager,",
        (
            f"I applied for the {role} position at {who} on "
            f"{applied_on.strftime('%d %B')} and wanted to check the application "
            f"arrived safely."
        ),
    ]
    blocks.extend(str(p) for p in body if str(p).strip())
    blocks.append("I remain very interested and am happy to send anything further.")
    blocks.append("Yours sincerely,")
    if sender:
        blocks.append(sender)
    return blocks
