"""What a document of each kind is made of, so the model fills a skeleton
rather than inventing one.

**Why the documents were not good.** "Write that up as a proposal" reached
the model as one instruction — *write the body, plain paragraphs, title on
its own line* — whatever the document was. A proposal, a statement of work,
a memo and a letter all came back as the same flat prose, and the runtime
then stripped every heading the model reached for anyway. There is no
document model the way Flux is an image model: a document is HTML a language
model wrote, so its quality is **the model plus the brief**, and the brief
was the same for everything.

This module is the brief. Each kind names the sections a reader of that kind
of document expects to find, in the order they expect them, and the
instruction asks for exactly those as markdown headings — which
`artifacts.markdown_blocks` already turns into the document's real
structure, with lists and tables intact. The API path has taken markdown
since it was built; the chat path now does too.

**A skeleton is not licence to fill it — rule 9.** The instruction says, in
as many words, to leave out a section nothing was said about rather than
write one, and to mark a single missing fact as *[to confirm]* rather than
supply one. A confident proposal for a client nobody mentioned is the
failure this codebase has already paid for; a skeleton makes that failure
*easier* unless the brief forbids it, so the brief forbids it first.

**Deliberately a table, not a pack.** A pack adds parsers, tools, templates
and exemplars for one vertical; this is the base layer's answer for the
document types everyone writes. A pack may add to `BRIEFS` or replace an
entry, and the freelance pack's proposal will, with exemplars from real
ones. Nothing here knows about projects or clients.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Brief:
    """One kind of document: what it is called, and what it is made of."""

    #: The kind, in the user's words — "a proposal".
    name: str
    #: Sections in reading order. Empty for a kind with no fixed sections
    #: (a letter, a summary), which then carries its shape in `shape`.
    sections: Tuple[str, ...] = ()
    #: How the whole thing reads, in one sentence the model can follow.
    shape: str = ""
    #: Words in a request that name this kind. Matched on word boundaries —
    #: "proposal" must not match "disproportionate", and `runtime._kind_from`
    #: records why substrings are a trap here ("invoice" contains "voice").
    words: Tuple[str, ...] = field(default=(), compare=False)


BRIEFS: Dict[str, Brief] = {
    "proposal": Brief(
        name="a proposal",
        sections=(
            "Summary",
            "What you need",
            "What we propose",
            "Scope and deliverables",
            "Timeline",
            "Fees",
            "Assumptions and exclusions",
            "Next steps",
        ),
        shape="Written to the client, in the first person. Specific about what is and is not included.",
        words=("proposal", "pitch"),
    ),
    "statement of work": Brief(
        name="a statement of work",
        sections=(
            "Purpose",
            "Scope",
            "Deliverables",
            "Milestones and dates",
            "Acceptance",
            "Fees and payment terms",
            "Responsibilities",
            "Changes",
        ),
        shape="Precise and checkable: every deliverable named, every date a date.",
        words=("statement of work", "sow", "scope of work"),
    ),
    "report": Brief(
        name="a report",
        sections=("Summary", "Findings", "Analysis", "Recommendations", "Next steps"),
        shape="Findings before opinions. Each recommendation follows from a finding above it.",
        words=("report", "write-up", "writeup"),
    ),
    "memo": Brief(
        name="a memo",
        sections=("Purpose", "Key points", "What happens next"),
        shape="Open with To, From, Date and Subject on their own lines. Short; a page at most.",
        words=("memo", "memorandum"),
    ),
    "brief": Brief(
        name="a brief",
        sections=("Objective", "Audience", "Key message", "Deliverables", "Constraints", "Timeline"),
        shape="For whoever will do the work: what, for whom, by when, within what.",
        words=("brief", "creative brief", "project brief"),
    ),
    "meeting notes": Brief(
        name="meeting notes",
        sections=("Attendees", "Decisions", "Discussion", "Actions"),
        shape="Decisions and actions are lists. Each action names who and by when.",
        words=("meeting notes", "minutes", "notes from the meeting", "notes of the meeting"),
    ),
    "plan": Brief(
        name="a plan",
        sections=("Goal", "Milestones", "Tasks", "Risks", "Next steps"),
        shape="Milestones dated where dates were given; tasks as a list under each.",
        words=("plan", "roadmap", "project plan"),
    ),
    "letter": Brief(
        name="a letter",
        shape=(
            "A letter, not a report: the date, the recipient's name and address on their own "
            "lines, a greeting, the body as paragraphs with no headings, and a sign-off."
        ),
        words=("letter",),
    ),
    "cover letter": Brief(
        name="a cover letter",
        shape=(
            "Three or four paragraphs and no headings: the role and why it interests you, what "
            "you bring to it with one or two specifics, and a short close. Under a page."
        ),
        words=("cover letter", "covering letter", "application letter"),
    ),
    "email": Brief(
        name="an email",
        shape="A subject line first, then a greeting, the message in short paragraphs, and a sign-off. No headings.",
        words=("email", "e-mail", "mail"),
    ),
    "summary": Brief(
        name="a summary",
        shape="The key points as a short list, then one paragraph that says what they add up to. No headings.",
        words=("summary", "summarise", "summarize", "tl;dr", "recap"),
    ),
    "press release": Brief(
        name="a press release",
        sections=("Headline", "Lead", "Body", "Quote", "About", "Contact"),
        shape="The first paragraph carries who, what, when and where. One quotation, attributed.",
        words=("press release", "announcement"),
    ),
    "article": Brief(
        name="an article",
        shape="An introduction, sections with headings of your choosing, and a conclusion. Written to be read, not skimmed.",
        words=("article", "blog post", "post", "essay"),
    ),
}

def brief_for(request: str) -> Optional[Brief]:
    """The brief a request names, or ``None`` for a document of no fixed kind.

    The longest phrase that matches wins, so "cover letter" beats "letter"
    and "a brief summary" is a summary, not a brief. Decided per request
    rather than by a fixed order of kinds, because a kind's longest phrase
    says nothing about which of its phrases the request used.
    """
    lowered = (request or "").lower()
    best: Optional[Tuple[int, str]] = None
    for key, brief in BRIEFS.items():
        for word in brief.words:
            if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", lowered):
                if best is None or len(word) > best[0]:
                    best = (len(word), key)
    return BRIEFS[best[1]] if best else None


#: What every brief ends with — the part that keeps a skeleton honest.
_RULES = (
    "Write it from what we have discussed and from anything recalled above. "
    "Leave out a section we said nothing about rather than writing one; where a "
    "single fact a sentence needs is missing — a name, a figure, a date — write "
    "[to confirm] in its place rather than inventing it. "
    "Do not add a preamble, do not explain what you are about to write, and do "
    "not describe yourself. Output the document and nothing else."
)


def instruction(request: str) -> str:
    """The instruction that writes the document the request asks for.

    Markdown, because `artifacts.markdown_blocks` turns it into headings,
    lists and tables the exporters already render — the chat path used to
    ask for plain paragraphs and strip the structure the model produced
    anyway. The title is the first line as `# Title`; the sections are `##`.
    """
    brief = brief_for(request)
    head = f"The user asked: {request.strip()}\n\n"
    if brief is None:
        return (
            head
            + "Write the document itself, in markdown. Start with its title on the first "
            "line as `# Title`. Use `##` headings where the content has natural sections, "
            "and lists or tables where they read better than prose. "
            + _RULES
        )
    if brief.sections:
        skeleton = "\n".join(f"## {s}" for s in brief.sections)
        return (
            head
            + f"Write {brief.name}, in markdown. Start with its title on the first line as "
            f"`# Title`. {brief.shape} Use these sections, as `##` headings, in this order:\n\n"
            f"{skeleton}\n\n"
            "Use lists or tables inside a section where they read better than prose. "
            + _RULES
        )
    return (
        head
        + f"Write {brief.name}, in markdown, with its title on the first line as `# Title`. "
        f"{brief.shape} "
        + _RULES
    )
