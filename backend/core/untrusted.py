"""Where content came from, and what that permits it to do.

CLAUDE.md already carries this rule for one surface: *a tool description is
third-party text*, and ranking is not a security boundary. The same reasoning
applies to everything else that enters the system without the user typing it —
an uploaded PDF, a parsed invoice, a retrieved chunk, a tool's output.

It matters more now than it did. Obligation extraction reads commitments out of
documents, and template extraction reads a company's identity out of one. Both
turn a file somebody else wrote into something Zaram acts on. A hostile invoice
is a way to put a deadline in someone's week, or a different bank account on
their letterhead.

**The rule: only what the user typed may instruct.** Everything else is data to
be shown, extracted from and reasoned about — never a source of permission.
Relevance is not consent, and neither is being well-phrased.

**What this module deliberately does not do is filter.** `scan` reports; it
never rewrites and never silently drops. Two reasons. Stripping text that looks
like an instruction would corrupt legitimate documents — a contract genuinely
containing "ignore all previous terms" is a real sentence about terms. And a
filter that quietly removes things trains nobody: the user never learns the
document was suspicious, which is the fact worth surfacing. Detection here is
for *marking*, so an interface can say "this came from a file, and it contains
something that reads like an instruction to me."

Never treat a clean scan as a guarantee. It catches the blatant cases; the rule
that carries the weight is `may_instruct`, which does not consult the text at
all — it consults where the text came from, which cannot be spoofed by writing
a better sentence.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import List

__all__ = ["Provenance", "may_instruct", "scan", "Suspicion"]


class Provenance(str, Enum):
    """How a piece of content entered the system.

    Not a trust *score*. A number invites comparison and thresholds, and this
    is a boundary rather than a ranking — the point of the whole file is that
    no amount of relevance promotes a document into an instruction.
    """

    #: The user typed it, in this session, into Zaram.
    USER_TYPED = "user_typed"
    #: Read out of a file the user ingested. Written by whoever wrote the file,
    #: which is very often not the user.
    DOCUMENT = "document"
    #: Returned by retrieval over the Spine. Its own origin is recorded
    #: separately (rule 7b); as *input to a decision* it is still not typed.
    RECALLED = "recalled"
    #: Returned by a tool, including an MCP server whose description and output
    #: are both written by a third party.
    TOOL_OUTPUT = "tool_output"
    #: Produced by a model, including Zaram's own generation.
    GENERATED = "generated"


def may_instruct(provenance: Provenance) -> bool:
    """Whether content of this provenance may change what the system does.

    Written as an allow-list of exactly one value rather than a denial of the
    other four, so that a provenance added later is refused by default. A new
    input channel arriving with instruction rights because nobody remembered to
    deny it is the failure this shape prevents.
    """
    return provenance is Provenance.USER_TYPED


class Suspicion(str, Enum):
    """What a passage looks like it is trying to do."""

    #: "ignore previous instructions", "disregard the above"
    OVERRIDE = "override"
    #: Addressed at the assistant rather than at the reader.
    ADDRESSED_TO_SYSTEM = "addressed_to_system"
    #: Asks for data to be sent, posted or emailed somewhere.
    EXFILTRATION = "exfiltration"
    #: Asks for a permission, policy or setting to be changed.
    PERMISSION_CHANGE = "permission_change"


_PATTERNS = (
    (
        Suspicion.OVERRIDE,
        re.compile(
            r"\b(?:ignore|disregard|forget|override)\b[^.\n]{0,40}"
            r"\b(?:previous|prior|earlier|above|all)\b[^.\n]{0,20}"
            r"\b(?:instruction|prompt|rule|direction|context)s?\b",
            re.IGNORECASE,
        ),
    ),
    (
        Suspicion.ADDRESSED_TO_SYSTEM,
        re.compile(
            r"(?:^|\n)\s*(?:zaram|assistant|ai|system|claude|chatgpt|gpt)\s*[,:]\s*\S",
            re.IGNORECASE,
        ),
    ),
    (
        Suspicion.EXFILTRATION,
        re.compile(
            r"\b(?:send|email|post|upload|transmit|forward|exfiltrate)\b"
            r"[^.\n]{0,40}\b(?:to|at)\b[^.\n]{0,20}"
            r"(?:https?://|www\.|[\w.-]+@[\w.-]+\.\w+)",
            re.IGNORECASE,
        ),
    ),
    (
        Suspicion.PERMISSION_CHANGE,
        re.compile(
            r"\b(?:set|change|update|grant|enable|allow|disable)\b[^.\n]{0,30}"
            r"\b(?:policy|permission|access|egress|setting|allow[\s-]?list|trust)\b",
            re.IGNORECASE,
        ),
    ),
)


def scan(text: str) -> List[Suspicion]:
    """What in this text reads like an instruction rather than content.

    Reports, in a stable order, with no duplicates. An empty list means nothing
    blatant was found — it does not mean the text is safe, and no caller should
    treat it as clearance. `may_instruct` is the boundary; this is a label.
    """
    if not text:
        return []
    return [kind for kind, pattern in _PATTERNS if pattern.search(text)]
