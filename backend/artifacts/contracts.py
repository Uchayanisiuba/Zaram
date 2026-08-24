"""The artifact model.

An artifact is something the user made: a document, spreadsheet or chart, with
the conversation that produced it and the sources it drew on. Work displays
these; the in-conversation file cards display the same records.

Replaces ``runtimes/artifacts/``, which was deleted rather than extended. That
module kept artifacts in a dict, and exposed ``delete()`` and an ``update()``
that ``setattr``'d any attribute passed to it. CLAUDE.md requires the write path
to have no delete or overwrite capability *at all*, and a capability that exists
is the violation whether or not anything calls it.

Design decisions taken before writing this, with their reasons:

**HTML is the source of truth.** Every artifact stores the HTML it was rendered
from, and every export is HTML → format. Never format → format: re-exporting a
.docx as PDF by converting the .docx loses the claim anchors, because export
formats do not preserve custom markup.

**The exported file is never the system of record for provenance.** The claim
anchors live in the HTML *and* in ``claims`` below, independently. WeasyPrint
flattens spans and Word discards unknown attributes, so a file-only provenance
chain survives the first export and dies silently on the first edit — leaving a
document that looks citable and is not. That is worse than no citations at all:
someone would defend a figure in a meeting on the strength of a link pointing at
nothing.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence


class ArtifactKind(str, Enum):
    """What the user asked for, not what the file extension is.

    Kept aligned with the frontend's `ArtifactKind` in `data/sampleArtifacts`.
    Divergence between the two is a bug, not a variation.
    """

    INVOICE = "invoice"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    CHART = "chart"
    #: Slides. A *kind*, not a format — the .pptx exporter reads headings, so
    #: any document can be exported as slides. This exists for the case where
    #: the user asked for a deck, so the outline is what gets previewed and
    #: `.pptx` is what gets written by default.
    DECK = "deck"


class Origin(str, Enum):
    """Where the content came from. Rule 7b.

    Three values. ``GENERATED`` is what this pipeline produces; the other two
    exist because the same tag is carried by facts, and a fact derived from an
    indexed artifact inherits the artifact's origin.

    Note what this is *not*: it is not a trust level and not a quality signal.
    It is a statement of provenance that recall uses to deprioritise Zaram's own
    restatements where a user source says the same thing.
    """

    USER_DOCUMENT = "user_document"
    CONVERSATION = "conversation"
    GENERATED = "generated"


@dataclass(frozen=True)
class ArtifactSource:
    """A source the artifact drew on.

    Mirrors ``ChatSource`` in the frontend's chatClient deliberately —
    provenance is one idea, not two, and a document's citations and a reply's
    citations are the same thing rendered differently.
    """

    kind: str
    url: Optional[str] = None
    title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "url": self.url, "title": self.title}


@dataclass(frozen=True)
class Claim:
    """One statement in the document, and the fact it came from.

    Finer-grained than ``ArtifactSource``: sources say what the document drew
    on, claims say which sentence came from which fact. This is what makes a
    generated document defensible rather than merely attributed.

    ``source_revision`` is the load-bearing field for staleness, and it is here
    from the first version specifically so that staleness detection can be added
    without migrating every artifact ever written.

    The failure it exists to catch: a proposal generated in March cites a fact;
    the user corrects that fact in April; the proposal now cites something that
    is no longer true and says so with a citation. That is the correction loop
    failing at exactly the point it is supposed to work. Detecting it means
    asking the memory store whether ``source_id`` still resolves to
    ``source_revision`` — which is answerable only if the revision was recorded
    at generation time.

    ``verified_at`` is the cheap cache of that answer, not the answer itself.
    Nothing computes it yet; the field exists so that when something does, no
    stored artifact has to be rewritten.
    """

    id: str
    source_id: str
    #: The sentence as it appears in the document.
    excerpt: str
    #: The source text it was drawn from, so a reader can compare without
    #: leaving the document.
    source_excerpt: str = ""
    #: Identity of the source *version* cited. Compare against the live fact to
    #: detect supersession. None means the source had no revision concept.
    source_revision: Optional[str] = None
    #: When the claim was last confirmed to still match its source. None means
    #: never checked — which is every claim today, and is honest.
    verified_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "excerpt": self.excerpt,
            "source_excerpt": self.source_excerpt,
            "source_revision": self.source_revision,
            "verified_at": self.verified_at,
        }


# --------------------------------------------------------------------------- #
# The document's content model.
#
# `render_document` used to take `Sequence[str | Claim]` and wrap **every**
# member in `<p>`, escaping it on the way. There was no way to express a
# heading, a list or a table, so a model asked for a proposal produced markdown
# that came out as literal text: a paragraph reading `## Scope of Work`, another
# reading `- Discovery`, and a table rendered as one mangled block of pipes.
#
# That was the whole reason generated documents read as basic. The page design
# was never the problem — the A4 page box, the serif measure, the masthead and
# the table rules were all already here. **The vocabulary to reach them was
# missing at the one end that writes.**
#
# It was missing only at that end. `export/_reader.py` already parses
# `h1, h2, h3, p, li` plus `table/caption/tr/td/th`, and `export/docx.py`
# already maps headings to Word heading styles and `li` to "List Bullet". The
# readers were built for a document that the writer could not produce, which is
# this repository's signature shape arriving from the far side.
#
# So these types are deliberately **not a new format**. Each one names markup
# the exporters already understand, and nothing here invents a tag they would
# have to learn.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RichText:
    """Inline HTML that has already been made safe, and is not escaped again.

    Every other piece of text in a document goes through `_esc`. This one does
    not, so the *only* thing permitted to construct it is a converter that
    guarantees two properties, and `markdown_blocks.py` is currently the only
    one:

    * text content is escaped;
    * the tag set is exactly `strong`, `em`, `code` and `br` — the inline
      vocabulary `export/_reader.py` parses, and nothing else.

    That second bound is the load-bearing one and it is narrower than "safe
    HTML". A tag the readers do not know is not a security problem, it is a
    *silent* problem: it survives into the HTML, looks correct in the preview,
    and vanishes on export to .docx with nothing reporting it. Restricting the
    set to what the readers already handle is what makes the preview and the
    exported file agree.

    `img` is dropped rather than passed through, and its alt text kept. A
    markdown image points at a URL, and a document that fetches one is a remote
    asset — the class `check-no-remote-assets.mjs` exists to keep out, arriving
    inside a data file where that check cannot see it.
    """

    html: str


@dataclass(frozen=True)
class Heading:
    """A section heading.

    ``level`` is 2 or 3. There is no level 1: `<h1>` is the document title, set
    once by the masthead, and a second one would give the .docx two competing
    Title styles and the PDF outline two roots.
    """

    text: str
    level: int = 2

    def __post_init__(self) -> None:
        if self.level not in (2, 3):
            raise ValueError("heading level must be 2 or 3; h1 is the title")


@dataclass(frozen=True)
class BulletList:
    """A list. ``ordered`` picks `<ol>` over `<ul>`.

    Items may be Claims, so a cited fact can sit in a list rather than being
    forced into prose to keep its anchor — which is what the old model made a
    caller do.
    """

    items: Sequence[Any] = ()
    ordered: bool = False


@dataclass(frozen=True)
class TableBlock:
    """A table inside a prose document.

    Distinct from an `ArtifactKind.SPREADSHEET`, which *is* a table. This is a
    table **in** a document — a fee schedule inside a proposal, a milestone list
    inside a statement of work.

    ``numeric_columns`` carries the `.num` class the stylesheet already defines
    for right-aligned tabular figures. It is passed by the caller rather than
    guessed from cell contents, for the reason `_TABLE_STYLE` records: a
    heuristic reading digits would right-align a reference number.
    """

    header: Sequence[str] = ()
    rows: Sequence[Sequence[str]] = ()
    caption: str = ""
    numeric_columns: Sequence[int] = ()


@dataclass(frozen=True)
class PageBreak:
    """Start the next block on a new page.

    Carries no content. Present because a covering letter and the document it
    covers are one file, and the break between them is a decision the author
    makes rather than a consequence of how the text happened to flow.
    """


#: Everything `render_document` accepts as a member of ``blocks``.
#:
#: `str` and `Claim` stay first and stay supported unchanged: every existing
#: caller keeps working, which is what let this land without touching the
#: invoice, deck or spreadsheet paths.
DocumentBlock = Any


@dataclass
class Artifact:
    """A generated file, its provenance, and where it lives.

    Immutable in practice: the store writes one and never rewrites it. There is
    deliberately no ``update`` and no ``delete`` anywhere in this package — see
    ``store.py``, and the source-scan test that fails the build if either
    appears.
    """

    id: str = field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    filename: str = ""
    kind: ArtifactKind = ArtifactKind.DOCUMENT
    project_id: str = ""

    #: Always GENERATED from this pipeline. Present as a field rather than
    #: hardcoded at the read site because facts derived from this artifact
    #: inherit it, and inheritance needs something to read.
    origin: Origin = Origin.GENERATED

    created_at: float = field(default_factory=time.time)
    size_bytes: int = 0

    #: Absolute path, under the output root. Set by the store, never by callers.
    path: Optional[str] = None

    #: The HTML this was rendered from. Source of truth for every re-export.
    html: str = ""

    conversation_id: str = ""
    conversation_title: str = ""

    sources: List[ArtifactSource] = field(default_factory=list)
    claims: List[Claim] = field(default_factory=list)

    #: Generated artifacts are indexed by default (rule 7b). The protection
    #: against Zaram citing its own restatements is origin tagging, not
    #: exclusion.
    #:
    #: Flipped to True in the M8 commit, as planned, and only once the thing
    #: that makes default-on safe actually existed: facts now carry
    #: `Origin`, and `MemoryRankerImpl` applies `GENERATED_PENALTY` so a user
    #: document outranks Zaram's restatement of it where both are relevant.
    #: The penalty lands on the ranking score and never on relevance — a
    #: generated fact that genuinely answers the question is still relevant,
    #: and pushing it under the citation floor would be exclusion by another
    #: name.
    #:
    #: `remember_override` remains the user's veto. It is an override, never a
    #: gate.
    indexed: bool = True

    #: The "Don't remember this" override on the file card. None means the user
    #: has not expressed a preference — distinct from False, which is a refusal.
    remember_override: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.filename,
            "kind": self.kind.value,
            "project_id": self.project_id,
            "origin": self.origin.value,
            "created_at": self.created_at,
            "size_bytes": self.size_bytes,
            "path": self.path,
            "conversation_id": self.conversation_id,
            "conversation_title": self.conversation_title,
            "sources": [s.to_dict() for s in self.sources],
            "claims": [c.to_dict() for c in self.claims],
            "indexed": self.indexed,
            "remember_override": self.remember_override,
            # `html` is deliberately omitted: it is the re-export source, can be
            # large, and Work does not need it to draw a row. Fetch it by id.
        }
