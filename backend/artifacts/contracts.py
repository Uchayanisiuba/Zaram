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
from typing import Any, Dict, List, Optional


class ArtifactKind(str, Enum):
    """What the user asked for, not what the file extension is.

    Kept aligned with the frontend's `ArtifactKind` in `data/sampleArtifacts`.
    Divergence between the two is a bug, not a variation.
    """

    INVOICE = "invoice"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    CHART = "chart"


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
    #: KNOWN GAP, time-boxed: the deprioritisation that makes default-on
    #: indexing safe lives in recall ranking, and recall cannot rank by origin
    #: until facts carry it — which lands with memory scope (M8), because both
    #: add a field to the same rows and doing them separately means two
    #: migrations. Until M8, generated facts would be indexed with no ranking
    #: penalty, which is the Spine-contamination window the rule exists to
    #: prevent. So this defaults to False for now: not indexing is the safer
    #: interim than indexing unranked. Flip it to True in the M8 commit.
    indexed: bool = False

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
