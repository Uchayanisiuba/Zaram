"""A correction that regenerates the reply it points at.

`docs/AGENT-UX.md`, *Revise*: the industry has three shapes for changing an
earlier answer — edit the question, a plain next turn, and a correction
applied to a specific output — and Zaram lacked the third. This is the
prompt for it. It is precision rather than capability: the conversation
share already puts the previous reply in front of the model, so what a
plain follow-up cannot say is *which* reply, that the answer to the
original question should be produced again in full, and that where the
earlier answer changed files the correction belongs in the files too.

**The earlier reply is session state and arrives in the request.** It is
never re-read from a store — rule 7d — and it is bounded on the way in, for
the same reason a manner is: an unbounded field is the cheapest way to fill
a window. One function, so the interface, the transport and the tests all
agree on what a revision looks like to the model.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Revision", "revision_prompt", "MAX_REPLY_CHARS", "MAX_QUESTION_CHARS"]

#: Enough of the earlier reply for the correction to bite; a reply longer
#: than this is cut from the end and said to be, so the model does not
#: revise text it never saw as though it had.
MAX_REPLY_CHARS = 12_000
MAX_QUESTION_CHARS = 4_000


@dataclass(frozen=True)
class Revision:
    """What is being revised: the question as asked and the reply as given."""

    question: str
    reply: str


def _bounded(text: str, limit: int) -> tuple[str, bool]:
    text = (text or "").strip()
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip(), True


def revision_prompt(revision: Revision, correction: str) -> str:
    """The one prompt a revision sends down the ordinary plan path.

    Ordinary path on purpose: recall runs again from it, so a fact corrected
    in between changes the revision (rule 4); a coding project offers its
    tools, so *"it should also accept negatives"* reaches the files; and
    every byte is gated and logged as any question is. Nothing here is a
    second way to generate.
    """
    question, question_cut = _bounded(revision.question, MAX_QUESTION_CHARS)
    reply, reply_cut = _bounded(revision.reply, MAX_REPLY_CHARS)
    correction = (correction or "").strip()

    reply_note = " (the start of it; the rest was longer than fits here)" if reply_cut else ""
    question_note = " (the start of it)" if question_cut else ""
    return (
        "The person is revising an earlier answer of yours.\n\n"
        f"They asked{question_note}:\n{question}\n\n"
        f"You answered{reply_note}:\n{reply}\n\n"
        f"Their correction:\n{correction}\n\n"
        "Give the corrected answer to their original question in full, as the "
        "answer itself rather than a note about what changed. Where your earlier "
        "answer changed files in the project, make the correction in those files "
        "too, using the tools, and say what changed."
    )
