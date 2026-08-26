"""Deciding how much of an attached document the model sees, and saying which.

LM Studio does the same thing and does not tell you: short files go into the
context whole, long ones trigger retrieval, and its own documentation declines
to say what the threshold is or how you would know which happened. That is the
gap this module exists to be the opposite of.

**A silently-summarised document is worse than a refused one**, because the
answer looks complete. So every path here produces two things — the block the
model sees, and a sentence for the user saying what was read. They are built
together, from the same decision, so one cannot drift from the other.

Three quantities, kept apart
----------------------------
The repository has paid three times for merging a ranking score with a
selection or citation threshold, and this module is built to keep them
separate:

* **Membership** — every paragraph of the document is a candidate. Nothing is
  filtered out before scoring.
* **Ordering** — paragraphs are ranked by rare-term overlap with the question,
  purely to decide which ones fit in the budget.
* **Presentation** — whatever survives is restored to *document order* before
  it reaches the model, because a contract read out of order is a different
  contract. The rank is never shown and never cited.

Why rarity rather than a stopword list
--------------------------------------
`_keyword_match` in the Spine is naive term overlap and its own comment records
the problem: function words score against everything. A hand-written stopword
list is a guess about which words do not matter. Rarity *within this document*
is a measurement of it — a term appearing in most paragraphs cannot
discriminate between them, whatever the word is, and a term appearing in two
paragraphs of forty points straight at them. It also handles the case a
stopword list cannot: "payment" is a rare term in a brief and a useless one in
an invoice, and only the document knows which it is in.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .contracts import Attachment, AttachmentKind

#: Tokens of context assumed available for attached documents.
#:
#: **This is a budget, not a measurement, and it is deliberately low.** Ollama
#: serves a default `num_ctx` of 4096 regardless of what a model declares —
#: measured on this machine, where `gemma4:12b` reports a 262144-token maximum
#: through `/api/show` and loads with `context_length: 4096` in `/api/ps`. So
#: the declared maximum is the wrong number to reason with, and using it would
#: overflow the context on almost every real document.
#:
#: Roughly half of that default is left for the question, the identity
#: preamble, recalled facts and the reply itself, none of which are free.
#: Reading the loaded model's real `num_ctx` from `/api/ps` would make this a
#: measurement; until then it errs small, and erring small costs an excerpt
#: where the whole would have fitted rather than a truncation nobody sees.
BUDGET_TOKENS = 1800

#: Characters per token, conservative on purpose.
#:
#: English averages nearer 4; 3 is used so the estimate errs toward *fewer*
#: characters fitting, which produces an excerpt where the whole might have
#: gone in. The opposite error silently drops the end of a document, and the
#: end of a contract is where the termination clause lives.
CHARS_PER_TOKEN = 3

BUDGET_CHARS = BUDGET_TOKENS * CHARS_PER_TOKEN

#: Paragraphs are split on blank lines, then anything still enormous is broken
#: on sentence ends, so one unbroken wall of text cannot occupy the whole
#: budget by itself.
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9][a-z0-9'\-]*")

#: Longest a single passage may be before it is broken up.
_MAX_PASSAGE = 900

#: What stands where text was left out. Shown to the model, and counted by the
#: tests — the block's own header explains the marker by using it, so a test
#: asking whether it appears at all is answered by the header alone.
GAP = "[…]"


class Mode:
    """How much of a document reached the model."""

    #: The whole thing, verbatim.
    FULL = "full"
    #: Selected passages, in document order.
    EXCERPT = "excerpt"
    #: Nothing — no attachments on this request.
    NONE = "none"
    #: An image. Never excerpted: a picture is looked at or it is not.
    IMAGE = "image"


@dataclass
class DocumentRead:
    """What happened to one attached document."""

    name: str
    mode: str
    #: Characters of this document that reached the model.
    chars_used: int
    #: Characters it holds in total.
    chars_total: int
    #: How many passages were selected. 0 in `FULL`, where the question does
    #: not arise.
    passages: int = 0
    #: How many passages the document has in total.
    passages_total: int = 0
    pages: int = 0


@dataclass
class Composition:
    """The block the model sees and the sentence the user reads."""

    block: str
    mode: str
    reads: List[DocumentRead] = field(default_factory=list)
    #: Ids that resolved to nothing — evicted, or from a restarted process.
    missing: List[str] = field(default_factory=list)

    def notice(self) -> str:
        """What the user is told, before the answer rather than after it.

        Written as a statement of what Zaram did. Not a confidence, not a
        percentage, and never silence: the whole point is that "I read all of
        it" and "I searched it and used three parts" are different answers to
        *"what does this document say"*, and only the user can judge whether
        the second one is good enough.
        """
        parts: List[str] = []
        for read in self.reads:
            if read.mode == Mode.IMAGE:
                # Named rather than counted. "Looked at" is the honest verb:
                # the model was shown the picture, and what it made of it is
                # in the answer rather than in this line.
                parts.append(f"Looked at {read.name}.")
            elif read.mode == Mode.FULL:
                parts.append(f"Read {read.name} in full.")
            else:
                pages = f" ({read.pages} pages)" if read.pages else ""
                parts.append(
                    f"{read.name}{pages} is too long to read at once, so Zaram "
                    f"searched it and used {read.passages} of its "
                    f"{read.passages_total} sections."
                )
        if self.missing:
            count = len(self.missing)
            parts.append(
                f"{count} attached "
                f"{'file is' if count == 1 else 'files are'} no longer held — "
                "it was not used for this answer."
            )
        return " ".join(parts)


def _passages(text: str) -> List[str]:
    """The document as addressable pieces, in order.

    Blank lines first, because that is where a writer put the boundaries, then
    sentence ends for anything still too long to be a unit of selection.
    """
    out: List[str] = []
    for block in _PARAGRAPH_SPLIT.split(text):
        block = block.strip()
        if not block:
            continue
        if len(block) <= _MAX_PASSAGE:
            out.append(block)
            continue
        current = ""
        for sentence in _SENTENCE_SPLIT.split(block):
            if current and len(current) + len(sentence) + 1 > _MAX_PASSAGE:
                out.append(current.strip())
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current.strip():
            out.append(current.strip())
    return out


def _terms(text: str) -> List[str]:
    return _WORD.findall(text.lower())


def _rarity(passages: Sequence[str]) -> Dict[str, float]:
    """How much each term discriminates between passages of *this* document.

    Standard inverse document frequency, over passages rather than over a
    corpus. A term in every passage scores 0 and cannot move a ranking, which
    is what makes a stopword list unnecessary — and, more usefully, what makes
    "payment" informative in a brief and inert in an invoice without anybody
    deciding that in advance.
    """
    total = len(passages)
    seen: Dict[str, int] = {}
    for passage in passages:
        for term in set(_terms(passage)):
            seen[term] = seen.get(term, 0) + 1
    return {
        term: math.log((total + 1) / (count + 1))
        for term, count in seen.items()
    }


def _rank(passages: Sequence[str], question: str) -> List[int]:
    """Passage indices, most relevant first. Ordering only.

    Ties keep document order, so a question sharing nothing with the document
    produces the beginning of it rather than an arbitrary shuffle — which is
    both the more useful answer and the more predictable one.
    """
    rarity = _rarity(passages)
    wanted = set(_terms(question))
    scored = []
    for index, passage in enumerate(passages):
        present = set(_terms(passage))
        score = sum(rarity.get(term, 0.0) for term in wanted & present)
        scored.append((-score, index))
    scored.sort()
    return [index for _, index in scored]


def _select(passages: Sequence[str], question: str, budget: int) -> List[int]:
    """Which passages fit, chosen by rank and returned in document order.

    The reordering at the end is the part that matters. Handing a model the
    third clause of a contract before the first is handing it a different
    contract, and the rank that chose them says nothing a reader needs.
    """
    chosen: List[int] = []
    used = 0
    for index in _rank(passages, question):
        cost = len(passages[index]) + 2
        if used + cost > budget:
            continue
        chosen.append(index)
        used += cost
    return sorted(chosen)


def _picture_read(item: Attachment) -> DocumentRead:
    """An image's line in the account. It was looked at, whole or not at all."""
    return DocumentRead(
        name=item.name,
        mode=Mode.IMAGE,
        chars_used=0,
        chars_total=0,
    )


def compose(
    attachments: Sequence[Attachment],
    question: str,
    missing: Sequence[str] = (),
    budget_chars: int = BUDGET_CHARS,
) -> Composition:
    """Build the document block for one request, and the account of it.

    The budget is shared across attachments rather than granted per file, so
    attaching four documents does not quietly quadruple what is sent. Divided
    evenly: a request that reaches for four files is asking about all four, and
    spending it all on whichever happens to be first would answer about one.
    """
    # Images are not documents and are separated before anything is sized.
    #
    # They have no text to excerpt and no character cost against the context
    # budget - they reach the model as their own field on the request. Sizing
    # them here would divide the document budget by files that never spend any
    # of it, and excerpting one is not a coherent operation.
    pictures = [a for a in attachments if a.kind == AttachmentKind.IMAGE.value]
    documents = [a for a in attachments if a.kind != AttachmentKind.IMAGE.value]

    if not documents:
        return Composition(
            block="",
            mode=Mode.NONE,
            reads=[_picture_read(p) for p in pictures],
            missing=list(missing),
        )

    attachments = documents
    share = max(600, budget_chars // len(attachments))
    sections: List[str] = []
    reads: List[DocumentRead] = []
    modes: set[str] = set()

    for item in attachments:
        passages = _passages(item.text)
        if item.chars <= share:
            body = item.text.strip()
            reads.append(
                DocumentRead(
                    name=item.name,
                    mode=Mode.FULL,
                    chars_used=len(body),
                    chars_total=item.chars,
                    passages_total=len(passages),
                    pages=item.pages,
                )
            )
            modes.add(Mode.FULL)
        else:
            picked = _select(passages, question, share)
            body = f"\n\n{GAP}\n\n".join(passages[i] for i in picked)
            reads.append(
                DocumentRead(
                    name=item.name,
                    mode=Mode.EXCERPT,
                    chars_used=len(body),
                    chars_total=item.chars,
                    passages=len(picked),
                    passages_total=len(passages),
                    pages=item.pages,
                )
            )
            modes.add(Mode.EXCERPT)

        sections.append(f"--- {item.name} ---\n{body}")

    # Named as attached rather than as retrieved. The model must not present
    # a file the user handed it in this exchange as something Zaram remembered
    # — that is rule 7d's confusion arriving in the prompt, and it is how a
    # document read once starts being cited as a stored fact.
    block = (
        "=== FILES ATTACHED TO THIS MESSAGE ===\n"
        "The user attached these to this message. They are not from memory and "
        f"not from the web. Where a passage is separated by {GAP}, text between "
        "the passages was not included.\n\n"
        + "\n\n".join(sections)
        + "\n"
        + "=" * 38
    )

    mode = Mode.EXCERPT if Mode.EXCERPT in modes else Mode.FULL
    reads.extend(_picture_read(p) for p in pictures)
    return Composition(block=block, mode=mode, reads=reads, missing=list(missing))
