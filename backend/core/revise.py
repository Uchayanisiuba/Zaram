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

__all__ = ["Revision", "revision_prompt", "MAX_REPLY_CHARS", "MAX_CODE_REPLY_CHARS", "MAX_QUESTION_CHARS"]

#: Enough of the earlier reply for the correction to bite; a reply longer
#: than this is cut from the end and said to be, so the model does not
#: revise text it never saw as though it had.
MAX_REPLY_CHARS = 12_000
#: **A reply that carries code gets the whole of it -- 5 October 2026.** A page
#: revised from its first 12,000 characters comes back without its ending: the
#: "Block World" reply that prompted this was 12,771. Cutting prose loses
#: detail; cutting code loses the program, and the model then rewrites the
#: missing part from nothing. 40,000 characters is roughly 10,000 tokens, which
#: the context resolution already sizes for on any model that would answer.
#: Raised to 100,000 on 11 October 2026: a page is now changed by edits whose
#: SEARCH parts must match it exactly, so the model has to see all of it, and
#: the games that prompted this ran to 60,000-69,000 characters -- cut at
#: 40,000, every fix rebuilt the missing end from nothing. ~25,000 tokens.
MAX_CODE_REPLY_CHARS = 100_000
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
    limit = MAX_CODE_REPLY_CHARS if "```" in (revision.reply or "") else MAX_REPLY_CHARS
    reply, reply_cut = _bounded(revision.reply, limit)
    correction = (correction or "").strip()

    reply_note = " (the start of it; the rest was longer than fits here)" if reply_cut else ""
    question_note = " (the start of it)" if question_cut else ""
    if _carries_a_page(reply):
        # **A page is changed, not written again -- 11 October 2026.** A
        # 15,000-character game rewritten to add two characters took eighteen
        # minutes and could break what worked; the window applies these edits
        # to the page above (`frontend/src/lib/pageEdits.ts`).
        closing = (
            "Make the correction to the page above. Reply with only what changes, as "
            "SEARCH/REPLACE blocks (lines copied exactly from the page, then the lines "
            "that replace them, the file named on the line above each block when there "
            "are several); Zaram applies them and runs the result. Write the whole page "
            "again only if most of it changes. Say in a sentence what you changed."
        )
    else:
        closing = (
            "Give the corrected answer to their original question in full, as the "
            "answer itself rather than a note about what changed. Where your earlier "
            "answer changed files in the project, make the correction in those files "
            "too, using the tools, and say what changed."
        )
    return (
        "The person is revising an earlier answer of yours.\n\n"
        f"They asked{question_note}:\n{question}\n\n"
        f"You answered{reply_note}:\n{reply}\n\n"
        f"Their correction:\n{correction}\n\n"
        f"{closing}"
    )


def _carries_a_page(reply: str) -> bool:
    """Whether the earlier answer contains a page the window runs."""
    lowered = (reply or "").lower()
    return "```html" in lowered and ("<html" in lowered or "<!doctype" in lowered or "<body" in lowered)
