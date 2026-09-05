"""Handing the user's data back, in formats that outlive Zaram.

Rule 7: the Spine is exportable in an open format, no lock-in. That rule is
only true if export is available *before* someone wants to leave. An export
that exists solely in the uninstaller makes leaving the price of admission to
your own data, which is the arrangement the rule was written against.

**This is not the uninstaller's zip, and the difference matters.** That one
copies the SQLite files: fine as a backup, restorable by unzipping, and
unreadable without Zaram. It does not satisfy rule 7 and was never meant to.
This produces JSON Lines and CSV — openable in a text editor, a spreadsheet, or
by whatever the user moves to next.

**Superseded facts are included, and that is deliberate.** They carry the
record that Zaram had something wrong and the user corrected it, which is the
half rule 4 exists to protect. An export that quietly drops them hands back a
tidier history than the one that happened.

**What is not exported is stated rather than omitted.** The manifest lists
every section, including the ones that came back empty and the ones this
version cannot produce. A user checking whether their data really is all here
should not have to infer it from an absence — and an export that silently
skips a section is indistinguishable from one where that section was empty.

Nothing here writes to disk. It yields named documents, so the caller decides
where they land, and the whole thing is testable without a filesystem.
"""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

__all__ = ["ExportDocument", "build_export", "EXPORT_FORMAT_VERSION"]

#: Bumped when the shape of an exported record changes in a way that would
#: break something reading last month's export. Written into the manifest so a
#: reader can tell, rather than guessing from the fields present.
EXPORT_FORMAT_VERSION = 1


@dataclass(frozen=True)
class ExportDocument:
    """One file in the export, with the bytes already rendered."""

    name: str
    content: str
    #: One line for the manifest and the interface: what this holds, in a
    #: sentence a person can check against their expectations.
    describes: str
    #: How many records it holds. Zero is a real answer and is exported as a
    #: file with a header rather than skipped, so "empty" is distinguishable
    #: from "not included".
    count: int = 0


def _jsonl(rows: Iterable[Dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows)


def _csv(rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> str:
    buffer = io.StringIO()
    # QUOTE_ALL so a comma inside a clause or an address cannot silently split
    # a column when the file is opened in a spreadsheet.
    writer = csv.DictWriter(
        buffer, fieldnames=list(columns), quoting=csv.QUOTE_ALL, lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _fact_row(record: Any) -> Dict[str, Any]:
    """One fact, flattened to something readable without Zaram's classes.

    Every field a reader would need to reconstruct the correction history is
    here: what replaced what, when the user said so, and when it was actually
    true. Exporting the content alone would hand back a list of sentences with
    no way to tell which ones Zaram no longer believes.
    """
    return {
        "id": getattr(record, "id", ""),
        "content": getattr(record, "content", ""),
        "created_at": getattr(record, "created_at", None),
        "scope": getattr(record, "scope", "global"),
        "origin": getattr(
            getattr(record, "origin", None), "value", getattr(record, "origin", "")
        ),
        "source": getattr(record, "source", ""),
        "tags": list(getattr(record, "tags", []) or []),
        "importance": getattr(record, "importance", None),
        "pinned": bool(getattr(record, "pinned", False)),
        # The correction record. Rule 4's more interesting half.
        "superseded_by": getattr(record, "superseded_by", None),
        "superseded_at": getattr(record, "superseded_at", None),
        # Valid time, distinct from the above: when it was true, not when we
        # were told.
        "valid_from": getattr(record, "valid_from", None),
        "valid_until": getattr(record, "valid_until", None),
    }


def build_export(
    *,
    facts: Sequence[Any] = (),
    egress_entries: Sequence[Dict[str, Any]] = (),
    obligations: Sequence[Dict[str, Any]] = (),
    generated_files: Sequence[str] = (),
    unavailable: Sequence[str] = (),
) -> List[ExportDocument]:
    """Everything Zaram holds, as a list of files to write.

    `unavailable` names sections this build cannot produce, so the manifest can
    say so out loud instead of leaving a gap the user has to notice.
    """
    documents: List[ExportDocument] = []

    fact_rows = [_fact_row(record) for record in facts]
    live = sum(1 for row in fact_rows if not row["superseded_by"])
    documents.append(
        ExportDocument(
            name="memory/facts.jsonl",
            content=_jsonl(fact_rows),
            describes=(
                f"Everything Zaram learned — {live} current, "
                f"{len(fact_rows) - live} corrected and kept for the record. "
                "One JSON object per line."
            ),
            count=len(fact_rows),
        )
    )

    documents.append(
        ExportDocument(
            name="memory/facts.csv",
            content=_csv(
                fact_rows,
                (
                    "id",
                    "content",
                    "scope",
                    "origin",
                    "created_at",
                    "valid_from",
                    "valid_until",
                    "superseded_by",
                ),
            ),
            describes="The same facts, for a spreadsheet. Opens in Excel or Numbers.",
            count=len(fact_rows),
        )
    )

    documents.append(
        ExportDocument(
            name="egress/log.jsonl",
            content=_jsonl(egress_entries),
            describes=(
                "Every byte that left this machine, in order — what was sent, "
                "where, and whether you approved it."
            ),
            count=len(egress_entries),
        )
    )

    documents.append(
        ExportDocument(
            name="obligations/obligations.csv",
            content=_csv(
                obligations,
                ("id", "kind", "summary", "due", "scope", "source_document_id"),
            ),
            describes="Dates and commitments Zaram read out of your documents.",
            count=len(obligations),
        )
    )

    manifest = {
        "exported_at": time.time(),
        "exported_at_readable": time.strftime("%d %B %Y, %H:%M"),
        "format_version": EXPORT_FORMAT_VERSION,
        "what_this_is": (
            "Everything Zaram holds about you, in open formats. JSON Lines "
            "files hold one record per line; CSV files open in any "
            "spreadsheet. Nothing here needs Zaram to read it."
        ),
        "contents": [
            {"file": doc.name, "records": doc.count, "describes": doc.describes}
            for doc in documents
        ],
        # Named rather than omitted. A section missing without explanation is
        # indistinguishable from one that was empty.
        "not_included": list(unavailable),
        "your_original_documents": (
            "Not copied — they are still wherever you keep them. This export "
            "holds what Zaram learned from them, not the files themselves."
        ),
        "generated_files": list(generated_files),
    }
    documents.append(
        ExportDocument(
            name="manifest.json",
            content=json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            describes="What is in this export, and what is not.",
            count=1,
        )
    )

    return documents
