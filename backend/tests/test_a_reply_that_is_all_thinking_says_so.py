"""A model that stops before answering does not leave a blank bubble.

Reported by the maintainer on 3 September 2026: *"I asked Zaram to generate a
portfolio website based on my CV, it spent so much time thinking and gave me no
response. It did that twice."*

Nothing failed. `Qwen3.8-27B-exl3-2.20bpw` thought at length and the stream
ended before it wrote `</think>`, so every token belonged to the working and the
answer was empty. `OpenAICompatibleEngine._tokens` already closes an
unterminated block — without it the splitter holds the whole reply and the user
sees *nothing at all* — and the previous session recorded that as *"the honest
failure rather than the safe one"*.

**It was the safer failure and it was not honest yet.** What reached the screen
was an empty assistant message with a collapsed *Thought process* beside it and
no sentence anywhere saying the model had run out. `CLAUDE.md` asks generation
to fail rather than invent; a failure nobody can read is the quiet half of the
same rule.

Two things this is careful about, both asserted below. It fires on *no answer
was ever produced*, not on `in_reasoning` at flush time — the engine has already
closed the tag by then, so the flag says nothing useful. And it stays silent
when there was no thinking either, because an empty reply with no working is a
different failure — a refusal, a dropped connection — already reported in words
of its own, and a vaguer message must not be spoken over a specific one.
"""

from __future__ import annotations

from core.reasoning import ANSWER, CLOSE_TAG, OPEN_TAG, REASONING, ReasoningSplitter


def drain(*chunks: str) -> list[tuple[str, str]]:
    """Everything a reply produces, fed a piece at a time."""
    splitter = ReasoningSplitter()
    out: list[tuple[str, str]] = []
    for chunk in chunks:
        out.extend(splitter.feed(chunk))
    out.extend(splitter.flush())
    return out


def texts(events: list[tuple[str, str]], kind: str) -> str:
    return "".join(text for k, text in events if k == kind)


class TestTheReportedFailure:
    def test_thinking_that_never_closes_still_produces_an_answer(self):
        """The stream the maintainer got: an open tag and no closing one."""
        events = drain(OPEN_TAG, "The user wants a portfolio site. ", "Let me plan ")
        assert texts(events, ANSWER) == ReasoningSplitter.NO_ANSWER
        assert "portfolio site" in texts(events, REASONING)

    def test_it_fires_after_the_engine_closes_the_tag_for_the_model(self):
        """The real shape, and the reason `in_reasoning` cannot be the test.

        `OpenAICompatibleEngine` appends `</think>` when the model never wrote
        one, so the splitter finishes *out* of reasoning mode with an empty
        answer. A check on that flag would pass this test's input straight
        through and leave the bubble blank.
        """
        events = drain(OPEN_TAG, "Working through it. ", CLOSE_TAG)
        assert texts(events, ANSWER) == ReasoningSplitter.NO_ANSWER

    def test_the_working_is_still_delivered(self):
        """The panel is where the sentence sends the user, so it must have
        something in it."""
        events = drain(OPEN_TAG, "Step one. Step two.")
        assert texts(events, REASONING) == "Step one. Step two."


class TestItStaysQuietWhereItShould:
    def test_a_reply_with_an_answer_is_untouched(self):
        events = drain(OPEN_TAG, "thinking", CLOSE_TAG, "Here is the page.")
        assert texts(events, ANSWER) == "Here is the page."
        assert ReasoningSplitter.NO_ANSWER not in texts(events, ANSWER)

    def test_a_model_that_never_reasons_is_untouched(self):
        events = drain("Plain answer, no tags.")
        assert texts(events, ANSWER) == "Plain answer, no tags."

    def test_an_empty_stream_says_nothing(self):
        """No thinking and no answer is somebody else's failure to report.

        An error, a refusal, a dropped connection — each already arrives with a
        message that names what happened, and this must not talk over it.
        """
        assert drain() == []
        assert drain("") == []

    def test_a_one_word_answer_counts_as_an_answer(self):
        """The trailing buffer is released by `flush`, and that release has to
        count — otherwise the shortest replies get told they do not exist."""
        events = drain(OPEN_TAG, "thinking", CLOSE_TAG, "Yes")
        assert texts(events, ANSWER) == "Yes"

    def test_whitespace_after_the_tag_is_not_an_answer(self):
        """A reasoning model's template puts a newline after the closing tag.

        That newline is punctuation, not a reply, and counting it would hide
        exactly the case this file exists for behind a blank line.
        """
        events = drain(OPEN_TAG, "thinking", CLOSE_TAG, "\n\n")
        assert ReasoningSplitter.NO_ANSWER in texts(events, ANSWER)
