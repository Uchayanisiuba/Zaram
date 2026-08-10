"""M7 — ingest. Folder in, facts out, and every failure visible.

The tests that matter here are the failure ones. Extraction working is easy to
check and easy to believe; what the milestone actually asks for is that a file
which gave nothing back *says so*, with a reason and a remedy. Silent ingestion
failure is the most likely reason a user concludes the product does not know
their material and leaves.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from ingest import (
    IngestStatus,
    chunk,
    discover,
    formats,
    grade,
    ingest_folder,
    parse_file,
    supported_suffixes,
)
from ingest.contracts import ParseResult
from ingest.quality import MIN_CHARS_PER_PAGE


# --- the walk -------------------------------------------------------------- #
class TestDiscover:
    def test_finds_supported_files_and_ignores_the_rest(self, tmp_path: Path):
        (tmp_path / "notes.md").write_text("hello", encoding="utf-8")
        (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "deep.txt").write_text("nested", encoding="utf-8")

        found = {p.name for p in discover(tmp_path)}

        assert found == {"notes.md", "deep.txt"}

    def test_office_lock_files_are_not_documents(self, tmp_path: Path):
        """`~$name.docx` is written while a file is open and never opens."""
        (tmp_path / "real.txt").write_text("content", encoding="utf-8")
        (tmp_path / "~$real.docx").write_bytes(b"lock")

        assert [p.name for p in discover(tmp_path)] == ["real.txt"]

    def test_noise_directories_are_skipped(self, tmp_path: Path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "readme.md").write_text("x", encoding="utf-8")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "COMMIT_EDITMSG").write_text("x", encoding="utf-8")
        (tmp_path / "keep.md").write_text("x", encoding="utf-8")

        assert [p.name for p in discover(tmp_path)] == ["keep.md"]

    def test_the_order_is_stable(self, tmp_path: Path):
        for name in ("c.txt", "a.txt", "b.txt"):
            (tmp_path / name).write_text("x", encoding="utf-8")

        assert discover(tmp_path) == discover(tmp_path)


# --- the quality floor ----------------------------------------------------- #
class TestQualityFloor:
    def test_zero_characters_is_empty_not_success(self):
        status, reason, remedy = grade(ParseResult(text="", pages=3), size_bytes=5_000_000)

        assert status is IngestStatus.EMPTY
        assert reason, "an empty file must carry a reason"
        assert remedy, "and a remedy"

    def test_an_image_only_scan_is_described_as_one(self):
        """The reason has to be about the file, not about the parser."""
        _, reason, _ = grade(ParseResult(text="", pages=2), size_bytes=2_000_000)

        assert "scan" in reason.lower() or "photo" in reason.lower()
        assert "KB per page" in reason

    def test_the_remedy_names_the_fix_and_its_cost(self):
        """"Install the extra" on metered data is not a decision anyone can make."""
        _, _, remedy = grade(ParseResult(text="", pages=1), size_bytes=1_000_000)

        assert "pip install" in remedy
        assert "MB" in remedy

    def test_a_scan_with_a_text_stamp_is_sparse(self):
        """169 characters across four pages — measured, a real signed NDA."""
        status, reason, _ = grade(ParseResult(text="x" * 169, pages=4))

        assert status is IngestStatus.SPARSE
        assert "169" in reason

    def test_a_sparse_but_real_document_is_not_flagged(self):
        """A pitch deck at 98.6 chars/page is a pitch deck, not a failure.

        This is the assertion that stops the floor being a guessed constant. A
        threshold at 200 chars/page looks reasonable and would reject a real
        pitch deck, a cast sheet and a treatment — all measured on real
        material. See `quality.py` for the distribution.
        """
        status, _, _ = grade(ParseResult(text="x" * 1380, pages=14))

        assert status is IngestStatus.INDEXED

    def test_the_floor_sits_between_the_two_measured_populations(self):
        assert 42.2 < MIN_CHARS_PER_PAGE < 98.6, (
            "the floor must separate scans-with-a-stamp (23.2, 42.2 chars/page) "
            "from legitimately sparse documents (98.6 and up). Both numbers are "
            "measured; see quality.py."
        )

    def test_an_unpaged_file_is_graded_on_its_whole_length(self):
        assert grade(ParseResult(text="hi", pages=0))[0] is IngestStatus.SPARSE
        assert grade(ParseResult(text="x" * 500, pages=0))[0] is IngestStatus.INDEXED


# --- parsing --------------------------------------------------------------- #
class TestParsing:
    def test_plain_text(self, tmp_path: Path):
        path = tmp_path / "note.md"
        path.write_text("# Title\n\nSome body text.", encoding="utf-8")

        result, reason, _ = parse_file(path)

        assert reason == ""
        assert result is not None and "Some body text." in result.text

    def test_undecodable_bytes_do_not_lose_the_file(self, tmp_path: Path):
        path = tmp_path / "messy.txt"
        path.write_bytes(b"good text \xff\xfe more text")

        result, _, _ = parse_file(path)

        assert result is not None
        assert "good text" in result.text and "more text" in result.text

    def test_an_unknown_suffix_is_unsupported_not_failed(self, tmp_path: Path):
        path = tmp_path / "thing.xyz"
        path.write_text("x", encoding="utf-8")

        result, reason, _ = parse_file(path)

        assert result is None
        assert "No parser handles" in reason

    def test_a_password_protected_docx_says_so(self, tmp_path: Path):
        """Six of 35 real .docx files on the measured machine were exactly this.

        `BadZipFile` reaching a user as "failed" tells them nothing. The OLE2
        magic identifies it precisely, and no parser opens these without the
        password — so the ingest extra is *not* offered as the remedy here.
        """
        path = tmp_path / "locked.docx"
        path.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)

        result, reason, remedy = parse_file(path)

        assert result is None
        assert "password-protected" in reason.lower()
        assert "pip install zaram[ingest]" not in remedy

    def test_a_corrupt_docx_is_not_reported_as_a_scan(self, tmp_path: Path):
        """"Could not open" and "opened and found nothing" have different fixes."""
        path = tmp_path / "broken.docx"
        path.write_bytes(b"PK\x03\x04" + b"garbage" * 20)

        result, reason, _ = parse_file(path)

        assert result is None
        assert "corrupt" in reason.lower() or "readable" in reason.lower()

    def test_a_real_docx_reads_its_tables(self, tmp_path: Path):
        """Invoices keep their figures in tables. Dropping them extracts the
        letterhead and none of the numbers."""
        docx = pytest.importorskip("docx")

        path = tmp_path / "invoice.docx"
        document = docx.Document()
        document.add_paragraph("Invoice for Harbour Lane Studio")
        table = document.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Day rate"
        table.rows[0].cells[1].text = "425000"
        document.save(str(path))

        result, _, _ = parse_file(path)

        assert result is not None
        assert "Harbour Lane Studio" in result.text
        assert "425000" in result.text, "the figure is the whole point of the file"

    def test_an_xlsx_is_not_graded_by_sheet_count(self, tmp_path: Path):
        """A sheet is not a page.

        Grading a ten-sheet workbook of short rows at 40 characters per "page"
        would tell the user their spreadsheet was a scan.
        """
        openpyxl = pytest.importorskip("openpyxl")

        path = tmp_path / "book.xlsx"
        workbook = openpyxl.Workbook()
        for i in range(6):
            sheet = workbook.create_sheet(f"S{i}")
            sheet["A1"] = "short"
        workbook.save(str(path))

        result, _, _ = parse_file(path)

        assert result is not None
        assert result.pages == 0
        assert grade(result)[0] is not IngestStatus.SPARSE


# --- chunking -------------------------------------------------------------- #
class TestChunking:
    def test_short_text_is_one_chunk(self):
        assert chunk("a short note") == ["a short note"]

    def test_empty_text_yields_nothing(self):
        assert chunk("") == []
        assert chunk("   \n  ") == []

    def test_long_text_is_split_and_nothing_is_lost(self):
        text = "\n\n".join(f"Paragraph {i} with some content in it." for i in range(200))

        chunks = chunk(text)

        assert len(chunks) > 1
        assert "Paragraph 0" in chunks[0]
        assert "Paragraph 199" in chunks[-1]

    def test_chunks_overlap_so_a_straddling_sentence_is_findable(self):
        text = "x" * 4000

        chunks = chunk(text, size=1000, overlap=100)

        assert len(chunks) >= 4
        # Total length exceeds the source precisely because of the overlap.
        assert sum(len(c) for c in chunks) > len(text)

    def test_a_pathological_document_still_terminates(self):
        """No paragraph breaks, no sentence ends, one enormous line."""
        assert len(chunk("z" * 50_000)) > 1


# --- the folder walk end to end -------------------------------------------- #
class TestIngestFolder:
    def _folder(self, tmp_path: Path) -> Path:
        (tmp_path / "brief.md").write_text(
            "The day rate for Harbour Lane Studio is 425000 naira.", encoding="utf-8"
        )
        (tmp_path / "tiny.txt").write_text("hi", encoding="utf-8")
        (tmp_path / "locked.docx").write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
        return tmp_path

    def test_every_file_gets_an_outcome(self, tmp_path: Path):
        """Not just the ones that worked. A report listing only successes is
        how a user concludes the product read everything."""
        report = ingest_folder(self._folder(tmp_path))

        assert len(report.outcomes) == 3
        assert {o.name for o in report.outcomes} == {"brief.md", "tiny.txt", "locked.docx"}

    def test_a_failure_does_not_stop_the_walk(self, tmp_path: Path):
        report = ingest_folder(self._folder(tmp_path))

        indexed = [o for o in report.outcomes if o.status is IngestStatus.INDEXED]
        assert [o.name for o in indexed] == ["brief.md"]

    def test_problems_are_separable_for_knowledge(self, tmp_path: Path):
        report = ingest_folder(self._folder(tmp_path))

        problems = {o.name: o.status for o in report.problems}
        assert problems == {
            "tiny.txt": IngestStatus.SPARSE,
            "locked.docx": IngestStatus.FAILED,
        }

    def test_every_problem_carries_a_reason(self, tmp_path: Path):
        report = ingest_folder(self._folder(tmp_path))

        for outcome in report.problems:
            assert outcome.reason, f"{outcome.name} is a problem with no reason shown"

    def test_facts_are_stored_with_their_origin(self, tmp_path: Path):
        """Rule 7b: every fact carries its origin."""
        stored: list[tuple[str, dict]] = []

        def store_fact(text, metadata):
            stored.append((text, metadata))
            return f"fact-{len(stored)}"

        report = ingest_folder(self._folder(tmp_path), store_fact=store_fact)

        assert stored, "nothing reached the Spine"
        assert all(m["origin"] == "user_document" for _, m in stored)
        assert all(m["source_name"] for _, m in stored)
        indexed = next(o for o in report.outcomes if o.name == "brief.md")
        assert indexed.fact_ids, "the outcome must record what it produced"

    def test_a_sparse_file_is_still_indexed(self, tmp_path: Path):
        """The floor warns; it does not reject.

        Withholding sparse content would make the quality floor a second,
        quieter way to lose a file — the exact failure the module exists to
        prevent.
        """
        stored: list[str] = []
        ingest_folder(
            self._folder(tmp_path), store_fact=lambda t, m: stored.append(t) or "id"
        )

        assert any("hi" == t for t in stored), "the sparse file was silently dropped"

    def test_a_failed_file_stores_nothing(self, tmp_path: Path):
        stored: list[dict] = []
        ingest_folder(
            self._folder(tmp_path), store_fact=lambda t, m: stored.append(m) or "id"
        )

        assert not any("locked.docx" in m["source_name"] for m in stored)

    def test_progress_is_reported_per_file(self, tmp_path: Path):
        """Knowledge shows a folder indexing as it happens, not after."""
        seen = []
        ingest_folder(self._folder(tmp_path), on_outcome=seen.append)

        assert len(seen) == 3

    def test_a_broken_progress_callback_does_not_cost_the_ingest(self, tmp_path: Path):
        def boom(outcome):
            raise RuntimeError("UI exploded")

        report = ingest_folder(self._folder(tmp_path), on_outcome=boom)

        assert len(report.outcomes) == 3

    def test_a_storage_failure_loses_one_chunk_not_the_document(self, tmp_path: Path):
        (tmp_path / "long.md").write_text("Sentence. " * 900, encoding="utf-8")
        calls = {"n": 0}

        def flaky(text, metadata):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("store exploded")
            return f"fact-{calls['n']}"

        report = ingest_folder(tmp_path, store_fact=flaky)

        outcome = next(o for o in report.outcomes if o.name == "long.md")
        assert len(outcome.fact_ids) >= 2, "one bad chunk should not lose the rest"

    def test_the_report_counts_cannot_disagree_with_its_outcomes(self, tmp_path: Path):
        report = ingest_folder(self._folder(tmp_path))
        data = report.to_dict()

        assert data["total"] == len(data["outcomes"])
        assert sum(data["counts"].values()) == data["total"]
        assert data["problems"] == len(report.problems)

    def test_an_empty_folder_is_not_an_error(self, tmp_path: Path):
        report = ingest_folder(tmp_path)

        assert report.outcomes == ()
        assert report.problems == ()


# --- what runs here -------------------------------------------------------- #
class TestFormats:
    def test_unavailability_is_a_return_value_with_a_reason(self):
        """The same shape `export.formats()` uses."""
        rows = {row["name"]: row for row in formats()}

        assert rows["plaintext"]["available"] is True
        for row in rows.values():
            if not row["available"]:
                assert row["remedy"], f"{row['name']} is unavailable and says nothing"

    def test_docling_is_offered_by_name_when_absent(self):
        rows = {row["name"]: row for row in formats()}
        docling = rows["docling"]

        if not docling["available"]:
            assert "zaram[ingest]" in docling["remedy"]
            assert "MB" in docling["remedy"]

    def test_supported_suffixes_reflects_what_is_installed(self):
        """Promising `.pptx` with the extra absent produces a folder scan that
        lists files it will then fail on one by one."""
        suffixes = supported_suffixes()

        assert ".md" in suffixes and ".txt" in suffixes
        from ingest.parsers import ocr_available

        assert (".pptx" in suffixes) == ocr_available()
