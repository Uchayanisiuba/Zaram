"""Generating an artifact: render, export, write, record.

The one place those four steps happen in that order, so there is one place to
read when asking what actually occurs when a user says "write that up".

Order matters, and it is the file first
---------------------------------------
The file is created before the record is stored. The two orderings fail
differently, and only one of them fails honestly:

- **Record first.** If the file write then fails, Work shows a row for a
  document that does not exist. The user clicks download and gets nothing. The
  surface is lying, and it will keep lying until someone notices.
- **File first.** If the record insert then fails, there is a file in the output
  directory that Work does not list. The user has their document — it is sitting
  in the folder Zaram told them about — and Zaram has under-claimed rather than
  over-claimed.

Under-claiming is recoverable and visible. Over-claiming is neither. So: file,
then record, and a failure between the two is logged loudly enough to be found.

What this does not do
---------------------
It does not index anything into the Spine. `Artifact.indexed` defaults to False
until M8 gives facts an origin to rank by, and this service is not the place to
quietly work around that — see the note on the field itself.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from . import export
from .contracts import Artifact, ArtifactKind, ArtifactSource, Claim
from .html import render_chart, render_document, render_spreadsheet
from .records import ArtifactRecords
from .store import ArtifactStore

logger = logging.getLogger(__name__)

#: The file a kind is written as, when the caller does not say. Chosen for what
#: the user can open, not for what is easiest to produce: .docx over .pdf
#: because PDF needs native libraries that are not present on Windows yet, and
#: because a document someone may want to edit should arrive editable.
DEFAULT_FORMAT = {
    ArtifactKind.DOCUMENT: "docx",
    ArtifactKind.INVOICE: "docx",
    ArtifactKind.SPREADSHEET: "xlsx",
    ArtifactKind.CHART: "png",
}


class ArtifactService:
    """Turns a request for a document into a file and a record of it."""

    def __init__(self, records: ArtifactRecords, store: ArtifactStore) -> None:
        self._records = records
        self._store = store

    @property
    def records(self) -> ArtifactRecords:
        return self._records

    @property
    def store(self) -> ArtifactStore:
        return self._store

    def create_document(
        self,
        *,
        title: str,
        blocks: Sequence[object],
        filename: str = "",
        kind: ArtifactKind = ArtifactKind.DOCUMENT,
        fmt: Optional[str] = None,
        project_id: str = "",
        conversation_id: str = "",
        conversation_title: str = "",
        sources: Sequence[ArtifactSource] = (),
        claims: Sequence[Claim] = (),
    ) -> Artifact:
        """Prose with claims in it. The common case."""
        html = render_document(
            title=title, blocks=list(blocks), sources=sources, claims=claims
        )
        return self._persist(
            html=html,
            title=title,
            filename=filename,
            kind=kind,
            fmt=fmt,
            project_id=project_id,
            conversation_id=conversation_id,
            conversation_title=conversation_title,
            sources=sources,
            claims=claims,
        )

    def create_spreadsheet(
        self,
        *,
        title: str,
        header: Sequence[str],
        rows: Sequence[Sequence[object]],
        caption: str = "",
        filename: str = "",
        fmt: Optional[str] = None,
        project_id: str = "",
        conversation_id: str = "",
        conversation_title: str = "",
        sources: Sequence[ArtifactSource] = (),
        claims: Sequence[Claim] = (),
    ) -> Artifact:
        html = render_spreadsheet(
            title=title,
            header=header,
            rows=rows,
            caption=caption,
            sources=sources,
            claims=claims,
        )
        return self._persist(
            html=html,
            title=title,
            filename=filename,
            kind=ArtifactKind.SPREADSHEET,
            fmt=fmt,
            project_id=project_id,
            conversation_id=conversation_id,
            conversation_title=conversation_title,
            sources=sources,
            claims=claims,
        )

    def create_chart(
        self,
        *,
        title: str,
        png: bytes,
        header: Sequence[str] = (),
        rows: Sequence[Sequence[object]] = (),
        filename: str = "",
        project_id: str = "",
        conversation_id: str = "",
        conversation_title: str = "",
        sources: Sequence[ArtifactSource] = (),
        claims: Sequence[Claim] = (),
    ) -> Artifact:
        html = render_chart(
            title=title,
            png=png,
            header=header,
            rows=rows,
            sources=sources,
            claims=claims,
        )
        return self._persist(
            html=html,
            title=title,
            filename=filename,
            kind=ArtifactKind.CHART,
            fmt="png",
            project_id=project_id,
            conversation_id=conversation_id,
            conversation_title=conversation_title,
            sources=sources,
            claims=claims,
        )

    # ------------------------------------------------------------------ shared

    def _persist(
        self,
        *,
        html: str,
        title: str,
        filename: str,
        kind: ArtifactKind,
        fmt: Optional[str],
        project_id: str,
        conversation_id: str,
        conversation_title: str,
        sources: Sequence[ArtifactSource],
        claims: Sequence[Claim],
    ) -> Artifact:
        extension = fmt or DEFAULT_FORMAT[kind]

        artifact = Artifact(
            filename=filename or _slug(title),
            kind=kind,
            project_id=project_id,
            html=html,
            conversation_id=conversation_id,
            conversation_title=conversation_title,
            sources=list(sources),
            claims=list(claims),
        )

        # File first. `export.write` goes through ArtifactStore, which creates
        # and never replaces, so the name it returns may not be the one asked
        # for — the record follows the file, never the other way round.
        export.write(artifact, extension, self._store, filename=artifact.filename)

        try:
            self._records.put(artifact)
        except Exception:
            # The document exists and the user can open it; only the listing is
            # missing. Loud, because a silent version of this is a folder that
            # slowly fills with files Work has never heard of.
            logger.exception(
                "Wrote %s but failed to record it. The file is on disk at %s and "
                "will not appear in Work.",
                artifact.filename,
                artifact.path,
            )
            raise

        return artifact

    def re_export(self, artifact_id: str, fmt: str) -> Artifact:
        """The same document in another format, from the stored HTML.

        From the HTML rather than from the file, and not by re-asking a model.
        A user requesting the PDF of something generated last month must get
        that document, not a fresh one written by a model that has since changed
        its mind — and not a conversion of the .docx, which would have lost the
        claim anchors on the way out.

        The result is a *new* artifact. It is a different file with a different
        name, and pretending one record describes two files on disk is how a
        download serves the wrong one.
        """
        original = self._records.get(artifact_id)
        if original is None:
            raise KeyError(f"no artifact {artifact_id!r}")

        copy = Artifact(
            filename=original.filename.rsplit(".", 1)[0],
            kind=original.kind,
            project_id=original.project_id,
            html=original.html,
            conversation_id=original.conversation_id,
            conversation_title=original.conversation_title,
            sources=list(original.sources),
            claims=list(original.claims),
        )
        export.write(copy, fmt, self._store, filename=copy.filename)
        self._records.put(copy)
        return copy


def _slug(title: str) -> str:
    """A filename from a title. The store sanitises after this; this is only
    about producing something a person recognises in a folder listing."""
    kept = [character if character.isalnum() else "-" for character in title.lower()]
    slug = "".join(kept)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")[:60] or "untitled"
