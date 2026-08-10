"""Documents Runtime — the first tool a user can actually reach.

Generative tier, which is what makes it the right one to be first. From
CLAUDE.md's risk table: generative tools create new artifacts and change
nothing that already exists, so they require *nothing* before shipping — no
undo, no sandbox, no confirmation dialog. Mutative and egressive tools need all
three, and none of that exists yet.

The safety is structural rather than promised, and it lives underneath this
module: files go to one output directory, `ArtifactStore` has no capability to
delete or overwrite, a name collision increments, and every path is confined to
the output root before anything is opened. This runtime adds no way around any
of that — it calls `ArtifactService` and nothing else.

What it does not do
-------------------
**It does not ask a model to write the document.** By the time a step reaches
here the answer has already been generated in the conversation; this turns that
answer into a file. Re-asking would produce a *different* document from the one
the user just read and approved of, which is the kind of surprise that makes a
tool untrustworthy even when each individual output is fine.

**It does not invent claims.** Claims arrive from recall, already carrying their
source. A claim this runtime made up would be a citation to nothing — the exact
failure the provenance chain exists to prevent, dressed as a feature.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional

from artifacts.contracts import Artifact, ArtifactKind, ArtifactSource, Claim
from artifacts.service import ArtifactService
from core.contracts import (
    Capability,
    CapabilityLocality,
    Runtime,
    RuntimeMetadata,
    RuntimeState,
)
from core.event_bus import EventBus

logger = logging.getLogger(__name__)

RUNTIME_ID = "documents"
RUNTIME_VERSION = "1.0.0"

#: The capability the planner routes a `document` intent to.
GENERATE = "document.generate"

#: Words that name a format, so "as a spreadsheet" picks .xlsx without the user
#: having to know what an extension is. Deliberately small: this is a shortcut
#: for people who said what they wanted, not a classifier. Anything unmatched
#: falls to the kind's default, which is the honest behaviour — guessing at
#: format from a vague request produces a file nobody asked for.
_KIND_WORDS = {
    ArtifactKind.SPREADSHEET: ("spreadsheet", "xlsx", "excel", "csv", "table of"),
    ArtifactKind.INVOICE: ("invoice", "bill", "quote", "estimate"),
    ArtifactKind.CHART: ("chart", "graph", "plot"),
}


class DocumentsRuntime(Runtime):
    """Turns an answer into a file, and records where the file came from."""

    def __init__(self, service: ArtifactService, event_bus: Optional[EventBus] = None):
        self._service = service
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED
        self._start_time = time.time()
        self._generated = 0

    # ------------------------------------------------------------- lifecycle

    def get_runtime_id(self) -> str:
        return RUNTIME_ID

    def get_version(self) -> str:
        return RUNTIME_VERSION

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id=RUNTIME_ID,
            version=RUNTIME_VERSION,
            priority="normal",
            capabilities=[
                Capability(
                    id=GENERATE,
                    runtime_id=RUNTIME_ID,
                    category="document",
                    # Local without qualification: generation never touches the
                    # network. The document is written from what is already on
                    # the machine, which is the claim the product makes.
                    locality=CapabilityLocality.LOCAL,
                )
            ],
            dependencies=[],
            auto_start=True,
        )

    def get_state(self) -> RuntimeState:
        return self._state

    async def initialize(self) -> None:
        self._state = RuntimeState.READY
        logger.info(
            "Documents Runtime ready; output directory %s", self._service.store.root
        )

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        self._state = RuntimeState.STOPPED

    async def health_check(self) -> Dict[str, Any]:
        from artifacts import export

        return {
            "status": "healthy" if self._state == RuntimeState.READY else "degraded",
            "runtime_id": RUNTIME_ID,
            "generated": self._generated,
            "output_dir": str(self._service.store.root),
            # Which formats can actually be produced here, with the reasons for
            # the ones that cannot. Disabled capabilities are visible.
            "formats": {
                extension: {"available": a.ok, "reason": a.reason}
                for extension, a in export.formats()
            },
        }

    # --------------------------------------------------------------- execute

    async def execute(
        self, capability_id: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if capability_id != GENERATE:
            return {"success": False, "error": f"unknown capability {capability_id}"}

        prompt = (input_data.get("prompt") or "").strip()
        answer = (input_data.get("answer") or "").strip()

        # The document is the *answer*, not the request. Falling back to the
        # prompt when there is no answer yet produces a document containing the
        # user's own question, which looks like a bug because it is one.
        body = answer or input_data.get("body") or ""
        if not body.strip():
            return {
                "success": False,
                "error": (
                    "There was nothing to write up yet. Ask the question first, "
                    "then say what you want made from the answer."
                ),
            }

        # Rule 9: generation must fail rather than invent.
        unresolved = _unresolved_reference(prompt, body, input_data)
        if unresolved:
            return {"success": False, "error": unresolved}

        kind = _kind_from(prompt)

        # A chart is a claim about numbers, and this runtime has prose. There
        # is no data path into it yet — that arrives with the business layer,
        # where the figures come from invoices and expenses rather than from a
        # model restating them.
        #
        # Refusing is the point. Quietly producing a document because a chart
        # was impossible would give the user a file they did not ask for and no
        # reason why, and inventing numbers to plot from prose would be worse
        # than either. Say what is missing and offer the thing that works.
        if kind is ArtifactKind.CHART:
            return {
                "success": False,
                "error": (
                    "I can't chart that yet — a chart needs the figures as data, "
                    "and what we have here is prose. Ask me to write it up as a "
                    "document or a spreadsheet and I can do that now."
                ),
            }

        title = input_data.get("title") or _title_from(prompt, body)

        claims = _claims_from(input_data.get("claims") or [])
        sources = _sources_from(input_data.get("sources") or [])

        try:
            artifact = self._service.create_document(
                title=title,
                blocks=_blocks(body, claims, title),
                kind=kind,
                fmt=input_data.get("format"),
                project_id=input_data.get("project_id", ""),
                conversation_id=input_data.get("session_id", ""),
                conversation_title=input_data.get("conversation_title", "") or title,
                sources=sources,
                claims=claims,
            )
        except Exception as error:
            # Named, because "generation failed" tells a user nothing and this
            # is the one tool that writes to their disk.
            logger.exception("Document generation failed")
            return {"success": False, "error": f"could not write the document: {error}"}

        self._generated += 1
        logger.info("Generated %s (%d bytes)", artifact.filename, artifact.size_bytes)

        return {"success": True, "artifact": _card(artifact)}


# ------------------------------------------------------------------ helpers


def _card(artifact: Artifact) -> Dict[str, Any]:
    """What the conversation shows: the file card.

    The same record Work draws a row from, minus the HTML. One shape for both,
    because they are the same thing shown twice, and two shapes would drift —
    which they immediately did: `exists` was missing here while the `/artifacts`
    listing had it, so a card for a file written one second earlier rendered
    "file not found where it was written". The card reads the field rather than
    assuming a successful write, so an absent field is a *false* claim, not a
    missing one.
    """
    import os

    payload = artifact.to_dict()
    payload["exists"] = bool(artifact.path) and os.path.isfile(artifact.path)
    payload["download_url"] = f"/artifacts/{artifact.id}/download"
    return payload


def _kind_from(prompt: str) -> ArtifactKind:
    lowered = prompt.lower()
    for kind, words in _KIND_WORDS.items():
        if any(word in lowered for word in words):
            return kind
    return ArtifactKind.DOCUMENT


#: A request that points at something rather than describing it. These are the
#: prompts that carry no content of their own, so a document made from one is a
#: document made from whatever the model happened to have.
_REFERENTIAL = re.compile(
    r"\b(that|this|those|these|it|the above|what we (just )?(said|discussed))\b",
    re.IGNORECASE,
)

#: Below this the "answer" is too thin to be a document about anything. A model
#: that had no context often produces a short, fluent, entirely invented opener.
_MIN_BODY_WORDS = 12


def _unresolved_reference(
    prompt: str, body: str, input_data: Dict[str, Any]
) -> Optional[str]:
    """Refuse when the request points at something we cannot show we resolved.

    Rule 9. "Write that up as a proposal" carries no content: everything the
    document will say has to come from context. When that context is missing,
    the model does not fail — it writes something fluent about a client that
    does not exist, and the user forwards it.

    The check is deliberately narrow, and only fires when **both** hold: the
    request is referential, and the engine did not supply resolved context.
    A request that describes its own subject ("draft an invoice for the
    Northwind job at 85,000 a day") is not referential and never reaches here.

    Why not check whether the body "looks invented" — because that cannot be
    done. Invented text is fluent by construction; that is the whole problem.
    What *is* checkable is whether anything was resolved to write from, so that
    is what this asks.
    """
    if not _REFERENTIAL.search(prompt):
        return None

    # The engine sets this when it put prior turns in front of the model.
    # Present means "that" had something to refer to.
    if input_data.get("context_resolved"):
        return None

    if len(body.split()) >= _MIN_BODY_WORDS:
        # Something substantial was generated and the engine did not claim to
        # have resolved context. Not proof of invention, but not proof against
        # it either — and a rule that only fires when it is certain would never
        # fire. Naming what is missing costs one exchange; the alternative cost
        # the user their credibility with a client.
        return (
            "I'd be guessing. You asked me to write up something we discussed, "
            "but I couldn't find that conversation to work from — so anything I "
            "produced would be invented and would look convincing. Tell me what "
            "the document should cover, or ask the question again in this "
            "session and then say \"write that up\"."
        )

    return (
        "There isn't enough here to make a document from. Tell me what it "
        "should say, or ask the question first and then say \"write that up\"."
    )


def _plain(text: str) -> str:
    """Strip the markdown a chat model emits by habit.

    The model is asked for plain paragraphs and mostly complies, but it still
    reaches for `**bold**` and `## headings`. Those are instructions in
    Markdown and literal characters everywhere else, so left alone they reach
    the .docx as asterisks and hashes in the middle of a sentence the user is
    about to send a client.

    Deliberately not a Markdown parser. The pipeline's source of truth is HTML
    and the model was told not to use Markdown; this removes the two constructs
    it produces anyway, and anything more elaborate would be building a second
    document pipeline to undo the first.
    """
    cleaned = re.sub(r"^\s{0,3}#{1,6}\s*", "", text.strip())
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", cleaned)
    return cleaned.strip()


def _title_from(prompt: str, body: str) -> str:
    """A title from the answer's first line, falling back to the request.

    Not a model call. A title is worth little to get exactly right and the user
    can rename the file; spending a generation round trip on it would make
    every document slower for no gain.
    """
    for line in body.splitlines():
        stripped = _plain(line)
        if len(stripped) > 3:
            return stripped[:80]

    cleaned = prompt.strip().rstrip("?.!")
    return (cleaned[:80] or "Untitled document").capitalize()


def _blocks(body: str, claims: List[Claim], title: str = "") -> List[object]:
    """Split prose into paragraphs, substituting claims where they appear.

    A claim whose excerpt appears verbatim in the answer becomes the anchored
    block, so the citation lands on the sentence it belongs to rather than
    being appended at the end. Matching on the excerpt is crude and is meant to
    be: recall produced both the claim and the text, so when they disagree the
    honest outcome is an unanchored paragraph plus a Sources entry, not a
    citation attached to the nearest thing that looked similar.

    Paragraphs equal to the title are dropped. The title is taken from the
    answer's first line and then rendered as the document's `<h1>`, so keeping
    it in the body prints it twice — and a model that repeats its own heading,
    as they do, printed it three times.
    """
    by_excerpt = {c.excerpt.strip(): c for c in claims if c.excerpt.strip()}
    blocks: List[object] = []
    normalised_title = title.strip().lower()

    for paragraph in body.split("\n\n"):
        text = _plain(paragraph)
        if not text:
            continue

        if normalised_title:
            if text.lower() == normalised_title:
                continue
            # The title is taken from the first *line*, but a model often puts
            # that line and the opening sentence in the same block with a
            # single newline between them. Comparing whole blocks misses that
            # and the heading prints twice, so strip it line-wise too.
            first, _, rest = text.partition("\n")
            if _plain(first).lower() == normalised_title:
                text = _plain(rest)
                if not text:
                    continue

        blocks.append(by_excerpt.get(text, text))

    return blocks or [_plain(body)]


def _claims_from(raw: Any) -> List[Claim]:
    claims: List[Claim] = []
    for item in raw or []:
        if isinstance(item, Claim):
            claims.append(item)
        elif isinstance(item, dict) and item.get("id") and item.get("source_id"):
            claims.append(
                Claim(
                    id=str(item["id"]),
                    source_id=str(item["source_id"]),
                    excerpt=str(item.get("excerpt", "")),
                    source_excerpt=str(item.get("source_excerpt", "")),
                    source_revision=item.get("source_revision"),
                )
            )
    return claims


def _sources_from(raw: Any) -> List[ArtifactSource]:
    sources: List[ArtifactSource] = []
    for item in raw or []:
        if isinstance(item, ArtifactSource):
            sources.append(item)
        elif isinstance(item, dict):
            sources.append(
                ArtifactSource(
                    kind=str(item.get("kind", "memory")),
                    url=item.get("url"),
                    title=item.get("title"),
                )
            )
    return sources
