"""Handing the data back so it survives Zaram.

The load-bearing tests are the ones checking that corrected facts are included
and that missing sections are named. An export that quietly tidies the history
or silently omits a section is one the user cannot check, which defeats the
point of having it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional

from core.export import EXPORT_FORMAT_VERSION, build_export


@dataclass
class Fact:
    id: str
    content: str
    scope: str = "global"
    origin: str = "conversation"
    source: str = "user"
    created_at: float = 1_770_000_000.0
    importance: float = 0.5
    pinned: bool = False
    tags: List[str] = field(default_factory=list)
    superseded_by: Optional[str] = None
    superseded_at: Optional[float] = None
    valid_from: Optional[float] = None
    valid_until: Optional[float] = None


def _by_name(documents):
    return {doc.name: doc for doc in documents}


class TestOpenFormats:
    def test_facts_are_valid_json_lines(self):
        docs = _by_name(build_export(facts=[Fact("a", "My day rate is £600")]))
        lines = docs["memory/facts.jsonl"].content.strip().splitlines()

        assert len(lines) == 1
        assert json.loads(lines[0])["content"] == "My day rate is £600"

    def test_facts_are_also_a_spreadsheet(self):
        docs = _by_name(build_export(facts=[Fact("a", "My day rate is £600")]))
        csv_text = docs["memory/facts.csv"].content

        assert csv_text.splitlines()[0].startswith('"id","content"')
        assert "£600" in csv_text

    def test_a_comma_in_the_content_cannot_split_a_column(self):
        """Addresses and clauses contain commas; quoting everything is what
        stops a spreadsheet silently shifting a row."""
        docs = _by_name(build_export(facts=[Fact("a", "71 Bankside, Lagos, Nigeria")]))
        rows = docs["memory/facts.csv"].content.strip().splitlines()
        assert rows[1].count('"') >= 4
        assert "71 Bankside, Lagos, Nigeria" in rows[1]

    def test_nothing_in_the_export_requires_zaram_to_read(self):
        for doc in build_export(facts=[Fact("a", "x")]):
            assert doc.name.endswith((".jsonl", ".csv", ".json"))


class TestTheCorrectionRecordSurvives:
    def test_superseded_facts_are_included(self):
        """They carry the record that Zaram was wrong and the user said so —
        the half rule 4 exists to protect."""
        facts = [
            Fact("old", "My day rate is £500", superseded_by="new", superseded_at=99.0),
            Fact("new", "My day rate is £600"),
        ]
        content = _by_name(build_export(facts=facts))["memory/facts.jsonl"].content
        assert "£500" in content and "£600" in content

    def test_the_chain_is_reconstructable_from_the_file_alone(self):
        facts = [
            Fact("old", "£500", superseded_by="new", superseded_at=99.0, valid_until=50.0),
            Fact("new", "£600", valid_from=50.0),
        ]
        rows = [
            json.loads(line)
            for line in _by_name(build_export(facts=facts))[
                "memory/facts.jsonl"
            ].content.strip().splitlines()
        ]
        old = next(r for r in rows if r["id"] == "old")

        assert old["superseded_by"] == "new"
        assert old["superseded_at"] == 99.0
        # Valid time exported separately from recorded time, or the reader
        # cannot tell when it was true from when we were told.
        assert old["valid_until"] == 50.0

    def test_the_description_counts_current_and_corrected_separately(self):
        facts = [Fact("old", "a", superseded_by="new"), Fact("new", "b")]
        described = _by_name(build_export(facts=facts))["memory/facts.jsonl"].describes
        assert "1 current" in described and "1 corrected" in described


class TestTheManifestIsHonest:
    def test_it_lists_every_data_file_with_a_count(self):
        """The manifest does not list itself — it is the index, not an entry.
        Everything else must appear, or a user comparing the manifest against
        the folder cannot tell a missing section from an undocumented one."""
        docs = build_export(facts=[Fact("a", "x")])
        manifest = json.loads(_by_name(docs)["manifest.json"].content)

        listed = {entry["file"] for entry in manifest["contents"]}
        assert listed == {doc.name for doc in docs if doc.name != "manifest.json"}
        assert all(entry["describes"] for entry in manifest["contents"])

    def test_sections_this_build_cannot_produce_are_named(self):
        """A section missing without explanation is indistinguishable from one
        that was empty."""
        docs = build_export(facts=[], unavailable=["Conversation history"])
        manifest = json.loads(_by_name(docs)["manifest.json"].content)
        assert manifest["not_included"] == ["Conversation history"]

    def test_it_says_original_documents_are_not_copied(self):
        manifest = json.loads(
            _by_name(build_export(facts=[]))["manifest.json"].content
        )
        assert "still wherever you keep them" in manifest["your_original_documents"]

    def test_it_carries_a_format_version(self):
        manifest = json.loads(
            _by_name(build_export(facts=[]))["manifest.json"].content
        )
        assert manifest["format_version"] == EXPORT_FORMAT_VERSION

    def test_it_says_when_in_a_form_a_person_reads(self):
        manifest = json.loads(
            _by_name(build_export(facts=[]))["manifest.json"].content
        )
        assert manifest["exported_at_readable"]


class TestEmptyIsNotMissing:
    def test_an_empty_section_still_produces_a_file(self):
        """Empty must be distinguishable from not-included."""
        docs = _by_name(build_export(facts=[]))

        assert "memory/facts.jsonl" in docs
        assert docs["memory/facts.jsonl"].count == 0
        # The CSV keeps its header, so the columns are visible even with no rows.
        assert docs["memory/facts.csv"].content.strip().startswith('"id"')

    def test_the_egress_log_is_always_present(self):
        """It is the record of what left the machine. Its absence from an
        export would be the one gap nobody could verify afterwards."""
        assert "egress/log.jsonl" in _by_name(build_export())


class TestOtherSections:
    def test_the_egress_log_exports_as_json_lines(self):
        docs = _by_name(
            build_export(egress_entries=[{"host": "api.example.com", "bytes": 1650}])
        )
        row = json.loads(docs["egress/log.jsonl"].content.strip())
        assert row["host"] == "api.example.com"

    def test_obligations_export_with_their_source_document(self):
        docs = _by_name(
            build_export(
                obligations=[
                    {
                        "id": "o1",
                        "kind": "payment",
                        "summary": "Payment of NGN 1,250,000.50 due",
                        "due": "2026-03-31",
                        "scope": "project:harbour",
                        "source_document_id": "inv-0042",
                    }
                ]
            )
        )
        content = docs["obligations/obligations.csv"].content
        assert "inv-0042" in content
        assert "2026-03-31" in content
