"""Ingest as the app uses it: records, the Spine, and a progress stream.

`service.py` is deliberately pure — it walks, parses, grades, and hands every
result to an injected `store_fact`. This is the layer that knows about the
Spine and the record store, so the pure half stays testable without either.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Iterator

from .contracts import IngestOutcome, IngestReport, IngestStatus
from .records import IngestRecords
from .service import discover, ingest_folder, iter_ingest_folder

logger = logging.getLogger(__name__)


class IngestService:
    """Point at a folder, put its text in the Spine, remember what happened."""

    def __init__(self, records: IngestRecords, memory_runtime: Any | None = None) -> None:
        self._records = records
        self._memory = memory_runtime

    @property
    def records(self) -> IngestRecords:
        return self._records

    def attach_memory(self, memory_runtime: Any | None) -> None:
        """Point this at the Spine.

        Late-bound because the kernel boots after the app object is built, and
        an ingest that silently stored nothing because the runtime was not
        ready yet would look exactly like a successful one.
        """
        self._memory = memory_runtime

    # -- storing ------------------------------------------------------------ #

    def _store_fact(self, text: str, metadata: dict[str, Any]) -> str:
        """One chunk into the Spine, with its origin and scope (rules 7b, 7i).

        `origin` is a first-class field now rather than only a metadata key, so
        recall can say *"from your client brief"* rather than *"from a proposal
        Zaram generated in April"* without parsing a dict.
        """
        if self._memory is None:
            return ""
        from core.async_bridge import run_sync
        from runtimes.memory.contracts import MemoryType, Origin

        return run_sync(
            self._memory.remember(
                content=text,
                memory_type=MemoryType.SEMANTIC,
                metadata=metadata,
                tags=["ingest", metadata.get("source_name", "")],
                origin=Origin.USER_DOCUMENT,
                # A folder is indexed *into* a project when one is active. The
                # source carries it; nothing invents one when it is absent.
                scope=metadata.get("scope"),
            )
        )

    # -- running ------------------------------------------------------------ #

    def scan(
        self, root: str, on_outcome: Callable[[IngestOutcome], None] | None = None
    ) -> tuple[str, IngestReport]:
        """Ingest a folder and record the result. Returns (source_id, report)."""
        report = ingest_folder(
            root,
            store_fact=self._store_fact if self._memory is not None else None,
            on_outcome=on_outcome,
        )
        source_id = self._records.upsert_source(report.root, seconds=report.seconds)
        self._records.record_outcomes(source_id, list(report.outcomes))
        return source_id, report

    def stream_scan(self, root: str) -> Iterator[dict[str, Any]]:
        """Ingest, yielding an event per file as it finishes.

        Progress is per file rather than a percentage because that is what the
        user can act on: a name and what happened to it. A bar that reaches 90%
        and stops tells them nothing about which document is missing.
        """
        root_path = Path(root)
        if not root_path.exists():
            yield {"type": "error", "message": f"{root} does not exist."}
            return
        if not root_path.is_dir():
            yield {"type": "error", "message": f"{root} is not a folder."}
            return

        try:
            files = discover(root_path)
        except PermissionError:
            yield {"type": "error", "message": f"{root} could not be read."}
            return

        yield {"type": "start", "root": str(root_path.resolve()), "total": len(files)}

        started = time.perf_counter()
        outcomes: list[IngestOutcome] = []
        for index, outcome in enumerate(
            iter_ingest_folder(
                root_path,
                store_fact=self._store_fact if self._memory is not None else None,
                paths=files,
            ),
            start=1,
        ):
            outcomes.append(outcome)
            # Yielded as it happens, not replayed afterwards.
            yield {"type": "file", "index": index, "total": len(files), **outcome.to_dict()}

        report = IngestReport(
            root=str(root_path),
            outcomes=tuple(outcomes),
            seconds=time.perf_counter() - started,
        )
        # Recorded only once the walk finished. A source row written up front
        # would claim a folder was indexed if the stream were abandoned
        # halfway — the same under-claiming rule the artifact store follows.
        source_id = self._records.upsert_source(report.root, seconds=report.seconds)
        self._records.record_outcomes(source_id, list(report.outcomes))

        yield {"type": "done", "source_id": source_id, **report.to_dict()}

    def retry(self, outcome_id: str) -> dict[str, Any] | None:
        """Re-read one file. What the retry button on a failure does.

        Worth having even when nothing about Zaram changed: the commonest
        reason a file failed is that it was open in Word at the time.
        """
        record = self._records.get_outcome(outcome_id)
        if record is None:
            return None

        path = Path(record["path"])
        if not path.exists():
            outcome = IngestOutcome(
                path=record["path"],
                status=IngestStatus.FAILED,
                reason="The file is no longer where it was — it may have been moved or renamed.",
            )
            self._records.replace_outcome(outcome_id, outcome)
            return self._records.get_outcome(outcome_id)

        report = ingest_folder(
            path.parent,
            store_fact=self._store_fact if self._memory is not None else None,
            paths=[path],
        )
        if report.outcomes:
            self._records.replace_outcome(outcome_id, report.outcomes[0])
        return self._records.get_outcome(outcome_id)

    # -- the conversation notice -------------------------------------------- #

    def notice_text(self) -> str | None:
        """One sentence for the transcript, or None when there is nothing to say.

        Written as something a person would say. It names the count, the worst
        single case, and where to go — and it is emitted once per scan, because
        a warning that repeats is one the user learns to skip.
        """
        pending = self._records.pending_notice()
        if not pending:
            return None

        problems = pending["problems"]
        self._records.acknowledge_notice(pending["source_id"])

        worst = problems[0]
        count = len(problems)
        folder = pending["name"]

        if count == 1:
            head = f"One file in {folder} didn't give me anything to work with: {worst['name']}."
        else:
            head = (
                f"{count} files in {folder} didn't give me much to work with — "
                f"{worst['name']} among them."
            )

        parts = [head]
        if worst.get("reason"):
            parts.append(worst["reason"])
        if worst.get("remedy"):
            parts.append(worst["remedy"])
        parts.append("They're listed under Knowledge if you want to look.")
        return " ".join(parts)


def default_db_path() -> str:
    return os.getenv(
        "ZARAM_INGEST_DB",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ingest.db"),
    )
