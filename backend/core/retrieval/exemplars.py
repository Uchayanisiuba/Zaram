"""Task exemplars — the phrasings each intent is recognised by.

This is data, not logic, and it is meant to be edited. CLAUDE.md: exemplars are
user-editable, because the alternative is a user whose phrasing routes wrongly
having no recourse except different words.

How to write one
----------------
An exemplar is **a thing a user would actually type**, not a description of a
category. "generate a document" is a label; "write that up as a proposal" is an
exemplar. The query is compared against these directly, so a list of category
names measures how close the user came to naming the category — which is a
different question from what they want.

Cover the phrasings that differ *in wording*, not in meaning. Ten ways of saying
"make me a chart" add nothing, because they already sit near each other in the
embedding space. One example each of "chart", "graph", "plot the numbers" and
"how has revenue moved" adds four directions.

The keyword traps these replace
-------------------------------
The keyword classifier this supersedes routed "invoice" to speech because it
contains "voice", "essay" to speech via "say", "profile" to filesystem via
"file", and "research" to filesystem via "search". Word-boundary matching fixed
those four. It cannot fix the general case, which is that "could you put
together something I can send the client" contains no keyword at all.
"""

from __future__ import annotations

from typing import Dict, List, Sequence

#: The namespace intents live in. Tools will live in `tool:<server>`.
INTENT_NAMESPACE = "intent"


#: intent name → phrasings. Keys match `IntentType` values in `core.planner`,
#: with the addition of `document`.
INTENT_EXEMPLARS: Dict[str, List[str]] = {
    "document": [
        "write that up as a proposal",
        "turn this into a document I can send",
        "draft an invoice for the work we discussed",
        "put together a report on this",
        "make me a spreadsheet of those numbers",
        "export this as a Word file",
        "can you write this up formally",
        "chart the revenue by month",
        "give me something I can send the client",
        "produce a quote for that job",
    ],
    "vision": [
        "what is in this image",
        "look at this screenshot and tell me what is wrong",
        "describe the photo I just shared",
        "read the text in this picture",
        "what does this diagram show",
    ],
    #: Drawing a picture, which is a different request from looking at one.
    #:
    #: The two neighbours are the difficulty, and they are close in embedding
    #: space for an obvious reason: `vision` is also about images, and
    #: `document` also produces a file. So every phrasing here carries a verb
    #: of *making* — draw, generate, design, create — attached to a noun that
    #: is a picture rather than a page.
    #:
    #: **"Chart" and "graph" are deliberately absent and belong to
    #: `document`.** A chart is derived from numbers the user already has and
    #: comes with the data table that makes it checkable; a picture is drawn
    #: from a description and has nothing behind it to check. "Draw me a chart
    #: of last quarter" must keep routing to `document`, and the exemplars are
    #: where that is decided.
    "image": [
        "draw me a picture of a lighthouse at dawn",
        "generate an image of a city street in the rain",
        "make me a logo for my studio",
        "create an illustration to go with this post",
        "design a header image for the proposal",
        "can you paint something in a watercolour style",
        "render a photorealistic mockup of the product",
    ],
    "speech": [
        "read that out loud",
        "say this back to me",
        "can you speak the answer",
        "turn this into audio",
    ],
    "filesystem": [
        "find the file I saved last week",
        "open the folder with the contracts",
        "what is in my documents directory",
        "locate the spreadsheet from March",
    ],
    "tool": [
        "commit this and push it",
        "run the tests",
        "check the git history",
        "execute that command in the terminal",
    ],
    "search": [
        "what is the latest news on this",
        "look up the current exchange rate",
        "find recent articles about it",
        "what happened this week",
    ],
    "conversation": [
        "what do you think about this approach",
        "explain how that works",
        "help me think through a decision",
        "why did that happen",
        "summarise what we agreed",
        "remind me what the client said about the deadline",
    ],
    #: Written to sit clear of its two neighbours, which is the whole
    #: difficulty here. `tool` is *acting on* a repository — committing,
    #: running tests — while these are questions *about code*, and
    #: `conversation` already owns "explain how that works", so an exemplar
    #: like "explain this" would land between the two and be discarded as
    #: ambiguous by the router's separation floor. Every phrasing below
    #: therefore carries something only a coding question carries: a stack
    #: trace, a function, a refactor, a language.
    "code": [
        "why does this function return None",
        "write a python script that renames these files",
        "refactor this class so it is easier to test",
        "what does this stack trace mean",
        "fix the bug in this loop",
        "add type hints to this module",
        "how do I write this as a SQL query",
        "is there a cleaner way to write this code",
    ],
}


def intent_candidates(exemplars: Dict[str, Sequence[str]] | None = None):
    """Build the index candidates for intent routing.

    Imported lazily by the router so this module stays plain data — something a
    user could eventually edit through Settings without touching code.
    """
    from .index import Candidate

    source = exemplars if exemplars is not None else INTENT_EXEMPLARS
    return [
        Candidate(
            id=intent,
            namespace=INTENT_NAMESPACE,
            exemplars=list(phrasings),
            payload={"intent": intent},
        )
        for intent, phrasings in source.items()
    ]
