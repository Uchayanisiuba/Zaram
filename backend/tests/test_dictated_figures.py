"""A dictated amount is flagged, never corrected.

The cases below are **the transcripts Whisper actually produced**, not invented
examples. One sentence, one voice, one model, three runs through the real route
(`test_speech_roundtrip.py`):

    said:  My day rate for Harbour Lane is four hundred and twenty five thousand naira.
    heard: My day rate for Harbor Lane is 425,000 Nira.
    heard: My day rate for Harbor Lane is 400 and 25,000 Nira.
    heard: My day rate for Harbor Lane is $400,000 and $25,000.

Using the real outputs matters. A test built from imagined transcripts would
assert against a failure mode nobody observed, and the observed one — an
invented currency symbol — is the one that survives every downstream check.
"""

from __future__ import annotations

import pytest

from voice.stt.figures import figures_in, needs_confirmation

#: Verbatim, from the roundtrip runs.
OBSERVED = [
    "My day rate for Harbor Lane is 425,000 Nira.",
    "My day rate for Harbor Lane is 400 and 25,000 Nira.",
    "My day rate for Harbor Lane is $400,000 and $25,000.",
]


class TestTheObservedFailures:
    @pytest.mark.parametrize("transcript", OBSERVED)
    def test_every_observed_transcript_is_flagged(self, transcript: str):
        assert needs_confirmation(transcript), (
            f"{transcript!r} carries an amount and was not flagged; this is a "
            "transcript Whisper really produced"
        )

    def test_the_invented_currency_is_reported_as_its_own_finding(self):
        """The worst case, isolated.

        `$400,000` is two claims — *which currency* and *how much* — and only
        the first was wrong. A checker that merged them into "an amount" would
        report the finding that was right and hide the one that was not.
        """
        found = figures_in("My day rate for Harbor Lane is $400,000 and $25,000.")
        kinds = {f.kind for f in found}

        assert "currency symbol" in kinds, "the invented $ was not reported"
        assert "number" in kinds
        assert sum(1 for f in found if f.kind == "currency symbol") == 2, (
            "both invented currency symbols must be reported, not just the first"
        )

    def test_a_spelled_out_amount_is_flagged_before_it_becomes_digits(self):
        """The phrase that parsed three different ways carries no digits at all."""
        assert needs_confirmation("four hundred and twenty five thousand naira")

    def test_the_correct_currency_is_flagged_too(self):
        """Not "the currency is wrong" — "a machine chose a currency from audio".

        Flagging only `$` would teach the user that an unflagged `₦` had been
        verified, which nothing verified.
        """
        assert needs_confirmation("My day rate is ₦425,000.")
        assert needs_confirmation("My day rate is 425,000 naira.")


class TestItDoesNotCorrect:
    @pytest.mark.parametrize("transcript", OBSERVED)
    def test_the_text_is_never_rewritten(self, transcript: str):
        """`figures_in` reports spans and returns the text untouched.

        Rewriting `$` to `₦` would be guessing intent from audio that has
        already proven unreliable — a confident wrong correction, which is worse
        than a flagged wrong transcript because it removes the prompt to look.
        """
        for figure in figures_in(transcript):
            assert transcript[figure.start : figure.end].strip() == figure.text, (
                "a reported span does not match the source text, so something "
                "is transforming the transcript"
            )


class TestProseIsLeftAlone:
    @pytest.mark.parametrize(
        "transcript",
        [
            "Remind me to call the client about the brief.",
            "The lighting pass on the interior shot still needs work.",
            "Send Harbour Lane the revised treatment tomorrow morning.",
        ],
    )
    def test_ordinary_dictation_is_not_flagged(self, transcript: str):
        """Speech is *for* prose. A warning on every note would be ignored.

        This is the assertion that keeps the broad patterns honest: erring
        toward flagging is correct, flagging everything is not, because a
        warning the user always sees is a warning they stop reading.
        """
        assert not needs_confirmation(transcript), (
            f"{transcript!r} is prose and was flagged; the check is too broad "
            "and will be ignored"
        )

    def test_an_empty_transcript_is_not_flagged(self):
        assert not needs_confirmation("")
