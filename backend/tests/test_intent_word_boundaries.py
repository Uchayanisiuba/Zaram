"""Keywords are words, not letter sequences inside other words.

The router matched keywords with ``kw in prompt_lower``. "invoice" contains
"voice", so every invoice request routed to text-to-speech and came back as
``[FALLBACK] speech.tts failed: empty_text`` with no model call at all. "essay"
contains "say"; "profile" contains "file"; "research" contains "search".

Found by running the thing: "Write a 1200-word essay on cartography" produced a
one-step plan of ``speech.tts`` and no LLM invocation. The business layer is
built on the word "invoice", so this would have taken M9 and M9a down with it.
"""

from __future__ import annotations

import pytest

from core.planner import IntentRouter, IntentType


@pytest.fixture
def router() -> IntentRouter:
    return IntentRouter()


class TestOrdinaryPromptsReachTheModel:
    """The regression itself. Each of these used to be captured by a keyword."""

    @pytest.mark.parametrize(
        "prompt,used_to_hit",
        [
            ("Draft an invoice for the Meridian project", "voice"),
            ("I have already sent that invoice", "voice"),
            ("Chase the unpaid invoices from last month", "voice"),
            ("Write a 1200-word essay on cartography", "say"),
            ("Update my profile details", "file"),
            ("Can you research the pricing options", "search"),
            # "already" contains "read"; the brief is not being read here.
            ("I already sent the brief", "read"),
            ("What is the codebase structure", "code"),
            ("The overrun cost us two days", "run"),
        ],
    )
    def test_routes_to_the_model(self, router, prompt, used_to_hit):
        result = router.classify(prompt)

        assert result.intent_type is IntentType.CONVERSATION, (
            f"{prompt!r} routed to {result.intent_type.value} — the substring "
            f"{used_to_hit!r} matched inside a longer word again"
        )
        assert result.capabilities == ["reasoning.generate"]


class TestGenuineIntentsStillRoute:
    """The half a "did the bad thing stop" test would miss.

    Removing the false positives is worthless if it also removed the true ones.
    """

    @pytest.mark.parametrize(
        "prompt,expected",
        [
            ("Say that out loud", IntentType.SPEECH),
            ("Read this aloud to me", IntentType.SPEECH),
            ("Speak the answer", IntentType.SPEECH),
            ("Look at this screenshot", IntentType.VISION),
            ("Analyse the image I just sent", IntentType.VISION),
            ("Open the file in that folder", IntentType.FILESYSTEM),
        ],
    )
    def test_still_classified(self, router, prompt, expected):
        assert router.classify(prompt).intent_type is expected

    def test_read_aloud_beats_bare_read(self, router):
        """Longest-match ordering, which the alternation depends on.

        "Read this aloud to me" contains both the speech phrase and the
        filesystem word "read". It used to land in filesystem. Speech is checked
        first, but only matches if the phrase is found at all.
        """
        assert router.classify("Read this aloud to me").intent_type is IntentType.SPEECH


class TestMatcher:
    def test_matches_whole_words_only(self):
        assert IntentRouter._matches("draft an invoice", {"voice"}) == []
        assert IntentRouter._matches("use my voice", {"voice"}) == ["voice"]

    def test_is_case_insensitive(self):
        assert IntentRouter._matches("send the Invoice", {"voice"}) == []
        assert IntentRouter._matches("SPEAK now", {"speak"}) == ["SPEAK"]

    def test_punctuation_is_a_boundary(self):
        assert IntentRouter._matches("say: hello", {"say"}) == ["say"]
        assert IntentRouter._matches("(voice)", {"voice"}) == ["voice"]

    def test_multi_word_phrases_match(self):
        assert IntentRouter._matches("read aloud please", {"read aloud"}) == ["read aloud"]
