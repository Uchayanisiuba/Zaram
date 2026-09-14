"""A document request is answered to a brief for its kind, and the structure
the model writes reaches the file.

Why the documents were not good, in two halves. The instruction for every
document was the same — *plain paragraphs, title on its own line* — so a
proposal and a memo came back as the same flat prose; and the runtime
stripped the headings and lists the model wrote anyway, while the API path
had kept them since it was built. `artifacts.briefs` is the first half;
`_blocks` keeping markdown is the second. A third: a document request is
now a routing distinction, so the strongest model the user has can be
assigned to it (`TaskSlot.DOCUMENT`), which is the reason the docstring on
`TaskSlot` gives for a slot to exist at all.

Rule 9 is written into the brief and asserted here: a skeleton must not
license inventing what fills it.
"""

from __future__ import annotations

import pytest

from artifacts.briefs import BRIEFS, brief_for, instruction
from artifacts.contracts import ArtifactKind, Claim
from artifacts.records import ArtifactRecords
from artifacts.service import ArtifactService
from artifacts.store import ArtifactStore
from core.planner import INTENT_SPECIALISATION, IntentType, _document_body_prompt
from core.user_settings import TaskSlot
from runtimes.documents.runtime import GENERATE, DocumentsRuntime, _blocks


class TestTheBriefNamesTheKind:
    @pytest.mark.parametrize(
        "request_, key",
        [
            ("write that up as a proposal", "proposal"),
            ("draft a statement of work for the Northwind job", "statement of work"),
            ("put this in a memo to the team", "memo"),
            ("write a cover letter for the role", "cover letter"),
            ("write a letter to the landlord", "letter"),
            ("a brief summary of what we decided", "summary"),
            ("give me a creative brief for the campaign", "brief"),
            ("turn this into meeting notes", "meeting notes"),
        ],
    )
    def test_the_kind_a_request_names(self, request_, key):
        assert brief_for(request_) is BRIEFS[key]

    def test_a_request_naming_no_kind_gets_no_brief(self):
        assert brief_for("write that up") is None

    def test_words_match_on_boundaries_not_substrings(self):
        assert brief_for("this is disproportionate") is None
        assert brief_for("the pitch-deck") is not BRIEFS["report"]

    def test_every_brief_has_a_name_and_either_sections_or_a_shape(self):
        for key, brief in BRIEFS.items():
            assert brief.name, key
            assert brief.sections or brief.shape, key
            assert brief.words, key


class TestTheInstructionIsTheBrief:
    def test_a_proposal_is_asked_for_by_its_sections_in_markdown(self):
        text = instruction("write that up as a proposal")
        assert "# Title" in text
        for section in BRIEFS["proposal"].sections:
            assert f"## {section}" in text
        assert "plain paragraphs" not in text

    def test_a_letter_is_asked_for_without_headings(self):
        text = instruction("write a letter to the landlord")
        assert "no headings" in text
        assert "## " not in text

    def test_rule_nine_is_in_every_instruction(self):
        for request_ in ("write that up as a proposal", "write a letter", "write that up"):
            text = instruction(request_)
            assert "rather than writing one" in text or "rather than inventing" in text
            assert "[to confirm]" in text
            assert "Do not add a preamble" in text

    def test_the_planner_uses_it(self):
        assert _document_body_prompt("write that up as a memo") == instruction("write that up as a memo")


class TestADocumentRequestIsARoutingDistinction:
    def test_the_intent_maps_to_the_slot(self):
        """The one condition under which a slot may exist: the router
        consults it. `main._assigned_slot` looks the specialisation up in
        `TaskSlot`, so the two spellings must agree."""
        assert INTENT_SPECIALISATION[IntentType.DOCUMENT] == TaskSlot.DOCUMENT.value

    def test_the_pairing_offer_fills_it(self):
        from providers.pairing import PAIRINGS, SLOTS, recommend

        assert "document" in SLOTS
        for provider_id, pairing in PAIRINGS.items():
            assert pairing.document, provider_id
        picks = recommend("nvidia_nim", ["moonshotai/kimi-k2-instruct"])
        assert picks["document"]["model"] == "moonshotai/kimi-k2-instruct"


class TestTheStructureReachesTheFile:
    @pytest.fixture
    def runtime(self, tmp_path):
        service = ArtifactService(
            ArtifactRecords(str(tmp_path / "artifacts.db")), ArtifactStore(tmp_path / "out")
        )
        return DocumentsRuntime(service)

    ANSWER = (
        "# Proposal for the Harbour Lane redesign\n\n"
        "## Summary\n\n"
        "A four-week redesign of the studio's site, delivered in two phases.\n\n"
        "## Scope and deliverables\n\n"
        "- Discovery and wireframes\n"
        "- Visual design, three rounds\n"
        "- Build and handover\n\n"
        "## Fees\n\n"
        "| Phase | Fee |\n|---|---|\n| Design | £2,400 |\n| Build | £3,600 |\n\n"
        "## Next steps\n\n"
        "Confirm the start date and we begin the following Monday."
    )

    async def test_headings_lists_and_tables_are_kept(self, runtime, tmp_path):
        result = await runtime.execute(
            GENERATE,
            # `context_resolved` is what the engine sets when prior turns were
            # in front of the model; without it rule 9 refuses "that", rightly.
            {
                "prompt": "write that up as a proposal",
                "answer": self.ANSWER,
                "format": "html",
                "context_resolved": True,
            },
        )
        assert result["success"], result.get("error")
        assert result["artifact"]["kind"] == ArtifactKind.DOCUMENT.value
        html = (tmp_path / "out" / result["artifact"]["filename"]).read_text(encoding="utf-8")
        assert "<h2>Summary</h2>" in html
        assert "<li>Discovery and wireframes</li>" in html
        assert "<table" in html and "£2,400" in html
        assert "## Summary" not in html and "- Discovery" not in html
        # The title is the masthead's, once.
        assert html.count("Proposal for the Harbour Lane redesign") >= 1
        assert "<h2>Proposal for the Harbour Lane redesign</h2>" not in html

    def test_a_claim_is_anchored_inside_the_structure(self):
        claim = Claim(id="c1", source_id="m1", excerpt="The studio's day rate is £400.")
        body = "# T\n\n## Fees\n\nThe studio's day rate is **£400**.\n\nPaid monthly."
        blocks = _blocks(body, [claim], title="T")
        assert any(b is claim for b in blocks), blocks
        assert any(type(b).__name__ == "Heading" for b in blocks)

    def test_plain_prose_still_splits_into_paragraphs(self):
        blocks = _blocks("Title\n\nOne paragraph.\n\nAnother.", [], title="Title")
        assert blocks == ["One paragraph.", "Another."]
