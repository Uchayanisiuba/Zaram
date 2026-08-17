"""Ingest outcomes have to survive the request that produced them.

Without a store, "failures must be loud" reduces to whether somebody happened
to be watching the response stream. These tests are mostly about the two things
that make the record worth keeping: that a re-scan does not leave yesterday's
failure sitting beside today's success, and that the conversation notice fires
exactly once.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ingest.contracts import IngestOutcome, IngestStatus
from ingest.records import IngestRecords
from ingest.service_api import IngestService


@pytest.fixture
def records(tmp_path: Path) -> IngestRecords:
    return IngestRecords(str(tmp_path / "ingest.db"))


def _outcome(name: str, status: IngestStatus, **kwargs) -> IngestOutcome:
    return IngestOutcome(path=f"/docs/{name}", status=status, **kwargs)


class TestSources:
    def test_a_source_is_recorded_with_its_counts(self, records: IngestRecords):
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [
            _outcome("a.md", IngestStatus.INDEXED, chars=500),
            _outcome("b.pdf", IngestStatus.EMPTY, reason="No text layer."),
        ])

        sources = records.sources()

        assert len(sources) == 1
        assert sources[0]["counts"] == {"indexed": 1, "empty": 1}
        assert sources[0]["problems"] == 1
        assert sources[0]["total"] == 2

    def test_rescanning_replaces_rather_than_accumulates(self, records: IngestRecords):
        """A list showing yesterday's failure beside today's success cannot be
        read, and the user's question is always "what is wrong *now*"."""
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [_outcome("a.pdf", IngestStatus.EMPTY)])

        again = records.upsert_source("/docs")
        records.record_outcomes(again, [_outcome("a.pdf", IngestStatus.INDEXED, chars=900)])

        assert again == source_id, "the same folder must keep its id"
        outcomes = records.outcomes(source_id)
        assert len(outcomes) == 1
        assert outcomes[0]["status"] == "indexed"

    def test_a_rescan_keeps_the_policy_the_user_set(self, records: IngestRecords):
        """Re-scanning is not a reason to forget a deliberate privacy choice."""
        source_id = records.upsert_source("/docs")
        records.set_policy(source_id, "cloud_allowed")

        records.upsert_source("/docs")

        assert records.sources()[0]["policy"] == "cloud_allowed"

    def test_the_default_policy_is_local_only(self, records: IngestRecords):
        """Rule 5: default deny, per source."""
        records.upsert_source("/docs")

        assert records.sources()[0]["policy"] == "local_only"

    def test_an_unknown_policy_is_refused(self, records: IngestRecords):
        source_id = records.upsert_source("/docs")

        with pytest.raises(ValueError):
            records.set_policy(source_id, "sometimes")

    def test_removing_a_source_returns_its_facts(self, records: IngestRecords):
        """Rule 4: deleting the folder has to take its facts with it, and this
        store does not reach into the Spine to do that itself."""
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [
            _outcome("a.md", IngestStatus.INDEXED, fact_ids=("f1", "f2")),
            _outcome("b.md", IngestStatus.INDEXED, fact_ids=("f3",)),
        ])

        fact_ids = records.remove_source(source_id)

        assert sorted(fact_ids) == ["f1", "f2", "f3"]
        assert records.sources() == []
        assert records.outcomes(source_id) == []


class TestPartialRuns:
    """A drop sees the files that were dropped, not the whole source.

    The uploads directory is one shared source — one place, one privacy policy,
    per rule 5 — so every drop lands in it. `record_outcomes` replaces a
    source's rows wholesale, which is right for a folder scan that saw every
    file and wrong here: found by the second drop of a route test, which
    reported one file where two had been kept.
    """

    def test_a_second_drop_does_not_erase_the_first(self, records: IngestRecords):
        source_id = records.upsert_source("/uploads")
        records.merge_outcomes(source_id, [_outcome("first.txt", IngestStatus.INDEXED, chars=200)])
        records.merge_outcomes(source_id, [_outcome("second.txt", IngestStatus.INDEXED, chars=200)])

        assert {o["name"] for o in records.outcomes(source_id)} == {"first.txt", "second.txt"}

    def test_the_earlier_facts_stay_removable(self, records: IngestRecords):
        """The half that matters. `fact_ids` live on the outcome row and are
        the only route rule 4 has back to the Spine — deleting the row leaves
        those facts recallable with nothing able to reach them."""
        source_id = records.upsert_source("/uploads")
        records.merge_outcomes(source_id, [_outcome("first.txt", IngestStatus.INDEXED, fact_ids=("f1",))])
        records.merge_outcomes(source_id, [_outcome("second.txt", IngestStatus.INDEXED, fact_ids=("f2",))])

        assert sorted(records.remove_source(source_id)) == ["f1", "f2"]

    def test_the_same_file_again_replaces_its_own_row(self, records: IngestRecords):
        """Per file, the "what is wrong now" property still holds."""
        source_id = records.upsert_source("/uploads")
        records.merge_outcomes(source_id, [_outcome("a.pdf", IngestStatus.EMPTY)])
        records.merge_outcomes(source_id, [_outcome("a.pdf", IngestStatus.INDEXED, chars=900)])

        outcomes = records.outcomes(source_id)
        assert len(outcomes) == 1
        assert outcomes[0]["status"] == "indexed"


class TestOutcomes:
    def test_problems_can_be_asked_for_on_their_own(self, records: IngestRecords):
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [
            _outcome("fine.md", IngestStatus.INDEXED, chars=500),
            _outcome("scan.pdf", IngestStatus.EMPTY, reason="No text layer."),
            _outcome("locked.docx", IngestStatus.FAILED, reason="Password-protected."),
            _outcome("photo.jpg", IngestStatus.UNSUPPORTED),
        ])

        problems = records.outcomes(source_id, problems_only=True)

        assert {o["name"] for o in problems} == {"scan.pdf", "locked.docx"}, (
            "unsupported is not a problem — the file simply is not a document"
        )

    def test_a_retry_replaces_one_outcome(self, records: IngestRecords):
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [
            _outcome("a.docx", IngestStatus.FAILED, reason="Could not be read.")
        ])
        outcome_id = records.outcomes(source_id)[0]["id"]

        changed = records.replace_outcome(
            outcome_id, _outcome("a.docx", IngestStatus.INDEXED, chars=1200)
        )

        assert changed
        updated = records.get_outcome(outcome_id)
        assert updated["status"] == "indexed"
        assert updated["chars"] == 1200
        assert updated["reason"] == "", "a fixed file must stop claiming a problem"


class TestTheConversationNotice:
    def test_a_scan_with_problems_produces_a_notice(self, records: IngestRecords):
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [
            _outcome("scan.pdf", IngestStatus.EMPTY, reason="No text layer.",
                     remedy="pip install zaram[ingest] (321 MB, one time)."),
        ])

        pending = records.pending_notice()

        assert pending is not None
        assert len(pending["problems"]) == 1

    def test_a_clean_scan_is_not_news(self, records: IngestRecords):
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [_outcome("a.md", IngestStatus.INDEXED)])

        assert records.pending_notice() is None

    def test_the_notice_fires_once(self, records: IngestRecords):
        """A warning that repeats is one the user learns to skip."""
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [_outcome("scan.pdf", IngestStatus.EMPTY)])

        assert records.pending_notice() is not None
        records.acknowledge_notice(source_id)
        assert records.pending_notice() is None

    def test_a_new_scan_is_news_again(self, records: IngestRecords):
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [_outcome("scan.pdf", IngestStatus.EMPTY)])
        records.acknowledge_notice(source_id)

        records.upsert_source("/docs")
        records.record_outcomes(source_id, [_outcome("other.pdf", IngestStatus.EMPTY)])

        assert records.pending_notice() is not None, (
            "a new run has new problems and the user has not heard about them"
        )


class TestNoticeText:
    def _service(self, records: IngestRecords) -> IngestService:
        return IngestService(records)

    def test_it_reads_like_something_a_person_would_say(self, records: IngestRecords):
        source_id = records.upsert_source("/docs/harbour")
        records.record_outcomes(source_id, [
            _outcome("scan-04.pdf", IngestStatus.EMPTY,
                     reason="No text layer — 2 pages of images (997 KB per page). It is a scan or a photo.",
                     remedy="Reading scans needs OCR: pip install zaram[ingest] (321 MB, one time)."),
        ])

        text = self._service(records).notice_text()

        assert text
        assert "scan-04.pdf" in text
        assert "harbour" in text
        # Names what happened, the fix, and the cost of the fix.
        assert "scan" in text.lower()
        assert "pip install zaram[ingest]" in text
        assert "321 MB" in text
        assert "Knowledge" in text

    def test_it_says_nothing_when_there_is_nothing_to_say(self, records: IngestRecords):
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [_outcome("a.md", IngestStatus.INDEXED)])

        assert self._service(records).notice_text() is None

    def test_it_is_returned_once(self, records: IngestRecords):
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [_outcome("scan.pdf", IngestStatus.EMPTY)])
        service = self._service(records)

        assert service.notice_text() is not None
        assert service.notice_text() is None

    def test_several_problems_are_counted_not_listed(self, records: IngestRecords):
        """A notice listing nine filenames is one nobody reads."""
        source_id = records.upsert_source("/docs")
        records.record_outcomes(source_id, [
            _outcome(f"scan-{i}.pdf", IngestStatus.EMPTY, reason="No text layer.")
            for i in range(9)
        ])

        text = self._service(records).notice_text()

        assert text and text.startswith("9 files")
        assert text.count(".pdf") == 1, "one example, not nine"


class TestStreamingScan:
    def test_progress_arrives_before_the_scan_finishes(self, tmp_path: Path):
        """The events are yielded as files complete, not replayed afterwards.

        A progress stream assembled after the walk is a bar that is always
        complete before it is shown — the same class of thing as a status
        indicator over hardcoded data.
        """
        folder = tmp_path / "docs"
        folder.mkdir()
        for i in range(4):
            (folder / f"note-{i}.md").write_text(f"Note {i} content.", encoding="utf-8")

        service = IngestService(IngestRecords(str(tmp_path / "ingest.db")))
        stream = service.stream_scan(str(folder))

        first = next(stream)
        assert first["type"] == "start" and first["total"] == 4

        second = next(stream)
        assert second["type"] == "file" and second["index"] == 1

        # The source is not recorded yet — the walk has not finished.
        assert service.records.sources() == [], (
            "a source row written before the walk completes would claim a "
            "folder was indexed even if the stream were abandoned"
        )

        rest = list(stream)
        assert rest[-1]["type"] == "done"
        assert len(service.records.sources()) == 1

    def test_a_missing_folder_is_an_error_event_not_an_exception(self, tmp_path: Path):
        service = IngestService(IngestRecords(str(tmp_path / "ingest.db")))

        events = list(service.stream_scan(str(tmp_path / "nope")))

        assert events == [{"type": "error", "message": f"{tmp_path / 'nope'} does not exist."}]

    def test_a_file_is_not_a_folder(self, tmp_path: Path):
        target = tmp_path / "a.md"
        target.write_text("x", encoding="utf-8")
        service = IngestService(IngestRecords(str(tmp_path / "ingest.db")))

        events = list(service.stream_scan(str(target)))

        assert events[0]["type"] == "error" and "not a folder" in events[0]["message"]


class TestRetry:
    def test_retrying_a_file_that_moved_says_so(self, tmp_path: Path):
        """Not "could not be read" — the user needs to know it is gone."""
        records = IngestRecords(str(tmp_path / "ingest.db"))
        source_id = records.upsert_source(str(tmp_path))
        records.record_outcomes(source_id, [
            IngestOutcome(path=str(tmp_path / "vanished.md"), status=IngestStatus.FAILED)
        ])
        outcome_id = records.outcomes(source_id)[0]["id"]

        updated = IngestService(records).retry(outcome_id)

        assert updated["status"] == "failed"
        assert "no longer where it was" in updated["reason"]

    def test_retrying_a_file_that_now_reads_fixes_it(self, tmp_path: Path):
        """The commonest reason a file failed is that it was open in Word."""
        records = IngestRecords(str(tmp_path / "ingest.db"))
        path = tmp_path / "recovered.md"
        path.write_text("This file is readable now.", encoding="utf-8")
        source_id = records.upsert_source(str(tmp_path))
        records.record_outcomes(source_id, [
            IngestOutcome(path=str(path), status=IngestStatus.FAILED, reason="Was locked.")
        ])
        outcome_id = records.outcomes(source_id)[0]["id"]

        updated = IngestService(records).retry(outcome_id)

        assert updated["status"] == "indexed"
        assert updated["reason"] == ""

    def test_retrying_something_unknown_returns_none(self, tmp_path: Path):
        records = IngestRecords(str(tmp_path / "ingest.db"))

        assert IngestService(records).retry("out-nope") is None
