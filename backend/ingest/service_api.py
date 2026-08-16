"""Ingest as the app uses it: records, the Spine, and a progress stream.

`service.py` is deliberately pure — it walks, parses, grades, and hands every
result to an injected `store_fact`. This is the layer that knows about the
Spine and the record store, so the pure half stays testable without either.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator

from .contracts import IngestOutcome, IngestReport, IngestStatus
from .records import IngestRecords
from .service import _ingest_one, discover, ingest_folder, iter_ingest_folder

logger = logging.getLogger(__name__)

#: Where dropped, uploaded and pasted content is kept.
#:
#: **One directory, so it is one source with one policy.** A source row is a
#: *place*, and the per-source privacy rule attaches to it — that is the whole
#: reason `upsert_source` keys on an absolute path and preserves the policy
#: across re-scans. Recording each dropped file under its own parent folder
#: would scatter a user's decisions across a source row per download folder,
#: and rule 5 asks them once per place, not once per file.
#:
#: The bytes genuinely live here, so the row points at something real and
#: "delete this source" means something. Already excluded from the installer
#: payload and from git.
UPLOADS_DIRNAME = "uploads"


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

    # -- drop, paste and upload --------------------------------------------- #

    def uploads_dir(self) -> Path:
        """The staging directory, created on demand."""
        from core.paths import data_dir

        directory = Path(data_dir()) / UPLOADS_DIRNAME
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    @staticmethod
    def safe_name(name: str) -> str:
        """A filename that cannot escape the directory it is written into.

        **A filename is third-party text**, exactly as a tool description is.
        It arrives over HTTP from whatever produced it, and `../../` in it
        would write outside the uploads directory — over a database, a policy
        file, or the backend's own source. `Path(name).name` discards every
        directory component, and the separator and null checks catch the forms
        that survive it on one platform but not the other.

        Empty or wholly unusable input becomes a generated name rather than an
        error: the file's bytes are the thing the user asked to keep, and
        refusing the whole upload because its name was strange would lose them.
        """
        cleaned = Path(str(name or "").replace("\\", "/")).name
        cleaned = cleaned.replace("\x00", "").strip().strip(".")
        # Reserved device names on Windows resolve to a device, not a file.
        stem = cleaned.split(".")[0].upper()
        reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
        if not cleaned or stem in reserved:
            return f"dropped-{uuid.uuid4().hex[:8]}.txt"
        return cleaned[:200]

    def _unused_path(self, name: str) -> Path:
        """A path in the uploads directory that is not already taken.

        **Never overwrite.** The generative-safety rule says a filename
        collision increments or asks, and it applies with more force here:
        these are the user's own documents, and two people's `invoice.pdf` are
        not the same invoice. Incrementing is the right half of that rule for
        an ingest path, where asking would interrupt a drop of forty files.
        """
        directory = self.uploads_dir()
        candidate = directory / name
        if not candidate.exists():
            return candidate

        stem, suffix = candidate.stem, candidate.suffix
        for index in range(2, 1000):
            attempt = directory / f"{stem} ({index}){suffix}"
            if not attempt.exists():
                return attempt
        return directory / f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"

    def save_upload(self, name: str, data: bytes) -> Path:
        """Write dropped or uploaded bytes into the staging directory."""
        path = self._unused_path(self.safe_name(name))
        path.write_bytes(data)
        return path

    def save_text(self, text: str, name: str = "") -> Path:
        """Write pasted text as a file, so one ingest path serves everything.

        Pasted text could be stored straight into the Spine without ever
        touching the disk, and that would be a second ingest path with its own
        chunking, its own grading and its own way of going wrong. It goes
        through the same parser, grader and chunker as every other document
        instead — the plaintext parser exists and this is what it is for.
        """
        chosen = self.safe_name(name) if name else ""
        if not chosen.lower().endswith(".txt"):
            chosen = f"{chosen or 'pasted-' + time.strftime('%Y-%m-%d-%H%M%S')}.txt"
        path = self._unused_path(chosen)
        path.write_text(text, encoding="utf-8")
        return path

    def stream_ingest_paths(self, paths: list[Path]) -> Iterator[dict[str, Any]]:
        """Ingest specific files, streaming an event each, as `stream_scan` does.

        The same NDJSON shape as the folder scan on purpose: the interface
        already parses it, the progress is already per-file, and a drop of
        thirty documents wants exactly the report a folder of thirty does.
        """
        yield {"type": "start", "root": str(self.uploads_dir()), "total": len(paths)}

        started = time.perf_counter()
        outcomes: list[IngestOutcome] = []
        store = self._store_fact if self._memory is not None else None

        for index, path in enumerate(paths, start=1):
            outcome = _ingest_one(Path(path), store)
            outcomes.append(outcome)
            yield {"type": "file", "index": index, "total": len(paths), **outcome.to_dict()}

        report = IngestReport(
            root=str(self.uploads_dir()),
            outcomes=tuple(outcomes),
            seconds=time.perf_counter() - started,
        )
        # One source for the staging directory, as with a scanned folder, and
        # recorded only once the run finished — a row written up front would
        # claim files were indexed if the stream were abandoned halfway.
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
    from core.paths import in_data_dir

    return in_data_dir("ingest.db", "ZARAM_INGEST_DB")
