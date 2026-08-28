# backend/tests/test_query_classifier.py
import pytest

from core.query_classifier import needs_search, SEARCH_MARKER


def test_rejects_too_short():
    assert needs_search("") is False
    assert needs_search("ab") is False
    assert needs_search("   ") is False


def test_rejects_already_augmented_prompt():
    prompt = f"{SEARCH_MARKER}\nSource:\nTitle: Foo"
    assert needs_search(prompt) is False


def test_time_signals_trigger_search():
    assert needs_search("Latest news about AI") is True
    assert needs_search("What is the current weather?") is True
    assert needs_search("Breaking changes in React today") is True
    assert needs_search("Recent updates to Kubernetes") is True


def test_factual_signals_trigger_search():
    assert needs_search("Who is the current CEO of OpenAI?") is True
    assert needs_search("What is the price of Bitcoin?") is True
    assert needs_search("When was Python 3.14 released?") is True
    assert needs_search("How many people live in Tokyo?") is True


def test_realtime_keywords_trigger_search():
    assert needs_search("NASDAQ closes at record high") is True
    assert needs_search("Will there be an election next month?") is True
    assert needs_search("Local traffic on I-95") is True
    assert needs_search("Market analysis for semiconductor stocks") is True


def test_year_references_trigger_search():
    assert needs_search("What happened in 2026?") is True
    assert needs_search("Future of AI in 2030") is True


def test_timeless_questions_do_not_trigger_search():
    assert needs_search("Explain recursion") is False
    assert needs_search("How does Python work?") is False
    assert needs_search("What is polymorphism?") is False
    assert needs_search("Describe the water cycle") is False


class TestAQuestionTheSystemAlreadyAnswers:
    """Zaram supplies today's date, so asking for it is not a search.

    **Measured 28 August 2026.** Asked *"What is today's date?"*, Zaram
    answered **"Today's date is 28 August 2026"** — correct, from the fact
    `core.identity._today_line` puts in the system prompt — and rendered the
    amber card underneath saying *"this answer comes only from what the model
    already knows."* The reply and the warning about the reply contradicted
    each other on screen, and the warning was the wrong one: the answer came
    from Zaram, not from the weights.

    Two patterns matched it. `_TIME_RE` on the bare word "today", and
    `_FACTUAL_RE` on "what is the".
    """

    @pytest.mark.parametrize(
        "prompt",
        [
            "What is today's date?",
            "what's the date",
            "What day is it?",
            "what is the date today",
            "what year is it",
            "what month is it",
            "Today's date",
            "what is the current date",
            "do you know what day it is",
            "please tell me what the date is",
            "What day of the week is it?",
            "which year are we in",
        ],
    )
    def test_the_date_is_not_looked_up(self, prompt):
        assert needs_search(prompt) is False

    @pytest.mark.parametrize(
        "prompt",
        [
            "What happened today?",
            "what is the news today",
            "what's the bitcoin price today",
            "who is the president",
            "what is the weather",
            "latest Qwen release",
            "what is the date of the next election",
        ],
    )
    def test_the_exemption_does_not_swallow_a_real_search(self, prompt):
        """The exemption is anchored to the whole question, and this is why.

        `_TIME_RE` matches "today" *anywhere*, which is how the original defect
        happened. An unanchored exemption would be the same defect with the
        sign reversed — and reversed is worse, because a missing warning is
        quieter than a false one.
        """
        assert needs_search(prompt) is True


class TestTheExemptionIsCoupledToTheSuppliedFact:
    """It is only correct while the system actually supplies the date.

    The exemption is not "date questions are unimportant". It is "Zaram already
    told the model the answer". If `identity.py` stops putting the date in the
    prompt, this exemption starts suppressing a warning that would then be
    true, so the two must not drift apart silently.
    """

    def test_identity_still_supplies_the_date(self):
        from core.identity import identity_preamble

        preamble = identity_preamble(today="28 August 2026")

        assert "28 August 2026" in preamble
        assert "supplied by the system" in preamble

    def test_the_time_of_day_is_not_supplied_and_is_not_exempted(self):
        """Scope check. `_today_line` carries a date and nothing finer, so the
        exemption must not have quietly grown to cover the clock."""
        from core.query_classifier import _ANSWERED_BY_SUPPLIED_DATE

        assert _ANSWERED_BY_SUPPLIED_DATE.match("what time is it") is None
