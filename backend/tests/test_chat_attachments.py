"""Files attached to a conversation, and the account given of what was read.

Two things are being graded, and only the second is unusual.

The ordinary half is that the store is session-scoped working state: an id from
another conversation resolves to nothing, eviction is reported rather than
silent, and an image is refused with a sentence rather than a status.

The half worth having is `compose`. LM Studio does the same job — whole
document into context when it fits, retrieval when it does not — and its own
documentation declines to say which happened or where the threshold is. **A
silently-summarised document is worse than a refused one, because the answer
looks complete.** So these assert on what the *user is told*, not only on what
the model is sent, and on the three quantities the repository has already paid
three times for merging: what is in the running, what order it is ranked in,
and what order it is presented in.
"""

from __future__ import annotations

import pytest

from attachments import (
    Attachment,
    AttachmentError,
    AttachmentStore,
    Mode,
    compose,
)


def attachment(text: str, name: str = "brief.txt", session: str = "s1") -> Attachment:
    return Attachment(
        id=f"att_{name}",
        session_id=session,
        name=name,
        suffix=".txt",
        path="",
        text=text,
        parser="plaintext",
    )


@pytest.fixture()
def store(tmp_path):
    return AttachmentStore(str(tmp_path / "attachments"))


# --------------------------------------------------------------------------- #
# The store
# --------------------------------------------------------------------------- #


class TestTheStoreIsWorkingState:
    def test_a_document_is_parsed_and_held(self, store):
        item, evicted = store.add("s1", "note.txt", b"The day rate is 500 pounds.")

        assert item.text.strip() == "The day rate is 500 pounds."
        assert item.parser
        assert evicted == []

    def test_an_id_from_another_conversation_resolves_to_nothing(self, store):
        item, _ = store.add("s1", "note.txt", b"Something private.")

        found, missing = store.resolve("s2", [item.id])

        # Not merely absent from the results — reported missing, so the reply
        # says the file was not used rather than answering as though it were.
        assert found == []
        assert missing == [item.id]

    def test_eviction_is_reported_rather_than_silent(self, store):
        from attachments import MAX_PER_SESSION

        for index in range(MAX_PER_SESSION):
            store.add("s1", f"f{index}.txt", f"document number {index}".encode())

        _, evicted = store.add("s1", "one-too-many.txt", b"the newest document")

        assert [e.name for e in evicted] == ["f0.txt"]
        assert store.get(evicted[0].id) is None

    def test_removing_one_takes_the_bytes_with_it(self, store, tmp_path):
        from pathlib import Path

        item, _ = store.add("s1", "note.txt", b"Something private.")
        on_disk = Path(item.path)
        assert on_disk.exists()

        assert store.remove(item.id) is True
        assert not on_disk.exists()

    def test_an_image_is_refused_by_naming_what_is_missing(self, store):
        with pytest.raises(AttachmentError) as raised:
            store.add("s1", "receipt.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64)

        message = str(raised.value)
        assert "receipt.png" in message
        # The distinction that makes the refusal worth reading: this is a path
        # Zaram has not built, not a thing it cannot do.
        assert "image" in message.lower()

    def test_an_unreadable_format_says_what_is_readable(self, store):
        with pytest.raises(AttachmentError) as raised:
            store.add("s1", "archive.zip", b"PK\x03\x04" + b"0" * 64)

        assert ".pdf" in str(raised.value)

    def test_a_file_that_yields_no_text_is_refused_not_attached(self, store):
        with pytest.raises(AttachmentError):
            store.add("s1", "blank.txt", b"   \n\n   \n")

    def test_the_scratch_directory_does_not_survive_a_restart(self, tmp_path):
        root = tmp_path / "attachments"
        first = AttachmentStore(str(root))
        first.add("s1", "note.txt", b"Something private.")
        assert any(root.iterdir())

        # Rule 7d: what is on disk between runs is nothing.
        AttachmentStore(str(root))

        assert list(root.iterdir()) == []


# --------------------------------------------------------------------------- #
# What the model sees, and what the user is told about it
# --------------------------------------------------------------------------- #


class TestAShortDocumentIsReadWhole:
    def test_the_text_arrives_verbatim(self):
        result = compose([attachment("The day rate is 500 pounds.")], "what is the rate?")

        assert result.mode == Mode.FULL
        assert "The day rate is 500 pounds." in result.block

    def test_the_user_is_told_it_was_read_whole(self):
        result = compose([attachment("The day rate is 500 pounds.")], "what is the rate?")

        # Said even when nothing was left out. A disclosure that appears only
        # on the lossy path teaches the user that silence means "all of it",
        # which makes the one time it fails to fire unreadable.
        assert result.notice() == "Read brief.txt in full."

    def test_the_block_says_the_file_was_attached_and_not_remembered(self):
        result = compose([attachment("The day rate is 500 pounds.")], "rate?")

        # Rule 7d reaching the prompt: a file handed over in this exchange must
        # not be presented to the model as something Zaram recalled, or it
        # starts being cited as a stored fact.
        assert "attached" in result.block.lower()
        assert "not from memory" in result.block.lower()


class TestALongDocumentIsSearchedAndSaidSo:
    #: A document that genuinely does not fit: 120 clauses, about 15,000
    #: characters, against a budget of roughly 5,400. One of them answers the
    #: question and the rest are *near* it without answering it — the corpus
    #: rule this repository already paid for learning, applied to a fixture.
    #:
    #: The first version of this had forty short clauses and fitted whole,
    #: so two tests asserting the excerpt path were grading the full one. The
    #: sizes here are checked below rather than assumed, because a fixture that
    #: silently stops exercising its branch is how a test starts proving
    #: nothing.
    PASSAGES = 120

    #: The question every test in this class asks.
    QUESTION = "what notice period is needed to terminate the agreement?"

    #: Where the only passage that answers it sits. Late on purpose: rank order
    #: and document order have to disagree, or the test that asserts document
    #: order passes whichever one the code produces.
    ANSWER_AT = 90

    @classmethod
    def _long_document(cls) -> str:
        # Filler that is *near* the question without answering it, and
        # deliberately shares the question's common words. Raw term overlap
        # scores these above the real answer \u2014 "what", "is", "needed",
        # "period", "agreement", "the", "to" are all here \u2014 so a ranking
        # that does not weight by rarity picks filler, which is the defect
        # this fixture exists to catch.
        filler = [
            f"Clause {i}. The supplier is to be notified of what is needed "
            f"for the agreement to proceed, and what period is needed for "
            f"delivery of consignment {i} under the schedule agreed between "
            f"the parties."
            for i in range(cls.PASSAGES)
        ]
        # The answer. Its discriminating words \u2014 "terminate", "notice",
        # "ninety" \u2014 appear nowhere else, so rarity points straight at it.
        filler[cls.ANSWER_AT] = (
            f"Clause {cls.ANSWER_AT}. Either party may terminate this "
            "agreement by giving ninety days written notice."
        )
        return "\n\n".join(filler)

    @staticmethod
    def _clause_numbers(block: str) -> list[int]:
        """Which clauses reached the model, in the order they appear."""
        import re

        return [int(n) for n in re.findall(r"Clause (\d+)\.", block)]

    def test_the_fixture_ranks_the_answer_above_the_filler(self):
        # Check the instrument. If the answer is not what ranking selects,
        # every assertion below about *which* passage was chosen is vacuous.
        from attachments.compose import _passages, _rank

        passages = _passages(self._long_document())
        assert _rank(passages, self.QUESTION)[0] == self.ANSWER_AT

    def test_the_fixture_really_does_exceed_the_budget(self):
        from attachments import BUDGET_CHARS

        # Check the instrument. Without this, both tests below pass on the
        # full-document path while claiming to grade the excerpt one.
        assert len(self._long_document()) > BUDGET_CHARS * 2

    def test_only_part_of_it_reaches_the_model(self):
        item = attachment(self._long_document(), name="agreement.txt")

        result = compose([item], self.QUESTION)

        assert result.mode == Mode.EXCERPT
        assert len(result.block) < item.chars

    def test_the_part_that_answers_the_question_is_the_part_chosen(self):
        item = attachment(self._long_document(), name="agreement.txt")

        result = compose([item], self.QUESTION)

        # The point of ranking by rarity rather than raw overlap. The filler
        # shares seven of the question's words and the answer shares three;
        # raw overlap therefore prefers filler, and only rarity \u2014 which
        # scores a term appearing in all 120 passages at zero \u2014 finds this.
        assert "ninety days written notice" in result.block

    def test_the_selected_passages_arrive_in_document_order(self):
        item = attachment(self._long_document(), name="agreement.txt")

        result = compose([item], self.QUESTION)
        clauses = self._clause_numbers(result.block)

        # Rank decides *which*; document order decides *how they are shown*.
        # A contract read out of order is a different contract, and a model
        # will reason about the relationship between adjacent clauses.
        assert len(clauses) > 1
        assert clauses == sorted(clauses)
        # The load-bearing half: the highest-ranked passage is *not* first.
        # Without this the assertion above passes whenever ranking happens to
        # agree with the document, which is what the first version of this
        # test did \u2014 it survived the reordering being removed entirely.
        assert clauses[0] != self.ANSWER_AT
        assert self.ANSWER_AT in clauses

    def test_the_user_is_told_how_much_was_used(self):
        item = attachment(self._long_document(), name="agreement.txt")

        result = compose([item], self.QUESTION)
        notice = result.notice()

        assert "agreement.txt" in notice
        assert "too long to read at once" in notice
        assert f"of its {self.PASSAGES} sections" in notice

    def test_the_gaps_are_marked_in_what_the_model_sees(self):
        item = attachment(self._long_document(), name="agreement.txt")

        result = compose([item], self.QUESTION)

        # Otherwise two distant clauses read as consecutive ones, and a model
        # will happily reason about the relationship between them.
        #
        # Counted rather than searched for: the block's own header explains
        # the marker by using it, so `"[…]" in block` is true even when no
        # gap is marked at all. That is what the first version asserted.
        assert result.block.count("[…]") > 1


class TestSeveralFilesAtOnce:
    def test_the_budget_is_shared_rather_than_granted_per_file(self):
        body = "\n\n".join(f"Paragraph {i} of the first document." for i in range(200))
        one = attachment(body, name="one.txt")
        two = attachment(body, name="two.txt")

        alone = compose([one], "paragraph", budget_chars=3000)
        together = compose([one, two], "paragraph", budget_chars=3000)

        # Measured on the document itself rather than on `block`, which also
        # holds a header \u2014 `2 * len(alone.block)` counts that header twice
        # while `together` has one, so the comparison held whatever the budget
        # did. Attaching a second document must not double what is sent.
        assert together.reads[0].chars_used < alone.reads[0].chars_used
        assert sum(r.chars_used for r in together.reads) <= alone.reads[0].chars_used * 1.2

    def test_each_file_gets_its_own_account(self):
        short = attachment("The rate is 500.", name="rate.txt")
        long_one = attachment("\n\n".join(f"Paragraph {i}." for i in range(200)), name="long.txt")

        notice = compose([short, long_one], "rate", budget_chars=1200).notice()

        assert "Read rate.txt in full." in notice
        assert "long.txt" in notice and "too long" in notice


class TestAFileThatIsNoLongerHeld:
    def test_is_named_rather_than_ignored(self):
        result = compose([], "what does it say?", missing=["att_gone"])

        # The failure being guarded against: the process restarted, the id no
        # longer resolves, and Zaram answers from memory alone while the chip
        # is still on screen. The answer would look like an answer about the
        # document.
        assert "no longer held" in result.notice()

    def test_and_the_answer_is_not_composed_as_though_it_were_present(self):
        result = compose([], "what does it say?", missing=["att_gone"])

        assert result.block == ""
        assert result.mode == Mode.NONE


class TestNothingAttached:
    def test_adds_nothing_to_the_prompt_and_says_nothing(self):
        result = compose([], "an ordinary question")

        assert result.block == ""
        assert result.notice() == ""
