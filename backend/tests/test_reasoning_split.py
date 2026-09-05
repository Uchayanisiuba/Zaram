"""A model's thinking must reach the panel, and nothing else.

The assertions here are aimed at three specific failures rather than at coverage:

* a tag **split across tokens**, which is how citation markers already broke
  this codebase once and which puts the splitter in the wrong state for the rest
  of a reply rather than merely rendering one character oddly;
* **held text being dropped**, so a reply ending in a literal ``<`` loses its
  last characters and the model gets blamed;
* reasoning **leaking into the answer**, which is not a cosmetic bug here —
  answer text is what ``pushSpeech`` reads, so a leak is Kokoro reading the
  model's working aloud.
"""

from __future__ import annotations

import pytest

from core.reasoning import ANSWER, REASONING, ReasoningSplitter


def _drain(chunks):
    """Feed a whole stream and return the flattened, flushed result."""
    splitter = ReasoningSplitter()
    out = []
    for chunk in chunks:
        out.extend(splitter.feed(chunk))
    out.extend(splitter.flush())
    return out


def _joined(chunks, kind):
    return "".join(text for k, text in _drain(chunks) if k == kind)


class TestOrdinaryModels:
    def test_text_without_tags_is_all_answer(self):
        assert _drain(["Hello ", "world."]) == [(ANSWER, "Hello "), (ANSWER, "world.")]

    def test_a_model_that_never_reasons_produces_no_reasoning(self):
        # No detection, no guessing: the tag is the only signal, so its absence
        # is simply a model that does not reason.
        assert _joined(["The invoice is overdue."], REASONING) == ""

    def test_a_lone_angle_bracket_is_answer_text(self):
        assert _joined(["5 < 6 and 7 > 6"], ANSWER) == "5 < 6 and 7 > 6"


class TestReasoningModels:
    def test_thinking_is_separated_from_the_answer(self):
        chunks = ["<think>The rate is 400.</think>", "Your day rate is 400."]
        assert _joined(chunks, REASONING) == "The rate is 400."
        assert _joined(chunks, ANSWER) == "Your day rate is 400."

    def test_tags_never_appear_in_either_stream(self):
        chunks = ["<think>working</think>answer"]
        for _, text in _drain(chunks):
            assert "<think>" not in text
            assert "</think>" not in text

    def test_text_before_the_opening_tag_is_answer(self):
        chunks = ["Sure. <think>hmm</think> Done."]
        assert _joined(chunks, ANSWER) == "Sure.  Done."

    def test_several_thinking_blocks_in_one_reply(self):
        chunks = ["<think>one</think>A<think>two</think>B"]
        assert _joined(chunks, REASONING) == "onetwo"
        assert _joined(chunks, ANSWER) == "AB"


class TestTagsSplitAcrossTokens:
    """The failure citation markers already cost this repository once."""

    @pytest.mark.parametrize(
        "chunks",
        [
            ["<", "think>", "working", "</", "think>", "answer"],
            ["<th", "ink>work", "ing</th", "ink>ans", "wer"],
            ["<t", "h", "i", "n", "k", ">", "w", "</", "t", "h", "i", "n", "k", ">", "a"],
        ],
    )
    def test_a_tag_arriving_in_pieces_is_still_a_tag(self, chunks):
        result = _drain(chunks)
        for _, text in result:
            assert "<" not in text, f"a tag fragment leaked: {result}"
        assert "".join(t for k, t in result if k == REASONING).startswith("w")

    def test_a_split_tag_does_not_leave_the_splitter_in_the_wrong_state(self):
        # The real damage from a half-recognised tag is not one odd character,
        # it is every token after it being filed under the wrong heading.
        chunks = ["<thi", "nk>secret</thi", "nk>", "the visible answer"]
        assert _joined(chunks, ANSWER) == "the visible answer"
        assert "secret" not in _joined(chunks, ANSWER)

    def test_held_text_is_released_once_it_cannot_be_a_tag(self):
        splitter = ReasoningSplitter()
        # "<th" could still become "<think>", so it is held rather than emitted.
        assert splitter.feed("done <th") == [(ANSWER, "done ")]
        # "e" proves it never was, so the whole thing is released intact.
        assert splitter.feed("e case") == [(ANSWER, "<the case")]


class TestNothingIsLost:
    def test_a_reply_ending_mid_tag_keeps_its_characters(self):
        # A truncated final word reads as a model defect and would be blamed on
        # one. Whatever is held must come out.
        assert _joined(["The value is <"], ANSWER) == "The value is <"
        assert _joined(["ends with <thin"], ANSWER) == "ends with <thin"

    def test_an_unclosed_thinking_block_still_surfaces(self):
        # Generation stopped inside the working. It belongs in the panel, not
        # nowhere — and specifically not in the answer, where it would be spoken.
        chunks = ["<think>I was cut off"]
        assert _joined(chunks, REASONING) == "I was cut off"
        assert "I was cut off" not in _joined(chunks, ANSWER)

    def test_a_reply_that_is_all_working_says_so_rather_than_nothing(self):
        """This asserted ``== ""`` until 3 September 2026, and the empty string
        was the bug rather than the contract.

        It is the same stream as the test above, read from the user's side: a
        blank bubble with a collapsed *Thought process* beside it and nothing
        anywhere saying the model ran out. Reported from the running app twice
        in one sitting. The half worth keeping — the monologue never reaches
        the answer, where speech would read it aloud — is asserted above and is
        unchanged. See ``test_a_reply_that_is_all_thinking_says_so.py``.
        """
        assert _joined(["<think>I was cut off"], ANSWER) == ReasoningSplitter.NO_ANSWER

    def test_every_character_survives_except_the_tags(self):
        text = "before <think>middle</think> after"
        result = _drain([text])
        assert "".join(t for _, t in result) == text.replace("<think>", "").replace(
            "</think>", ""
        )


class TestOneInstancePerReply:
    def test_state_does_not_leak_between_replies(self):
        # A reply truncated inside <think> would otherwise carry the open tag
        # into the next question, and that answer would vanish into the panel.
        first = ReasoningSplitter()
        first.feed("<think>cut off")
        assert first.in_reasoning is True

        second = ReasoningSplitter()
        assert second.in_reasoning is False
        assert second.feed("A plain answer.") == [(ANSWER, "A plain answer.")]
