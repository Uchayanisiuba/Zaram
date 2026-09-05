"""The context is measured, and where it cannot be, it says so.

**The declared maximum is the wrong number.** Ollama serves a default `num_ctx`
regardless of what a model advertises: `gemma4:12b` reports 262,144 through
`/api/show` and loads with 4,096 in `/api/ps`; `bge-m3` advertises more and was
observed loaded with 8,192 on this machine, 27 August 2026. Sizing a prompt
against the declared figure sizes it against a number no request will ever have.

`attachments/compose.py` said as much in its own comment and carried a constant
instead — *"Reading the loaded model's real `num_ctx` from `/api/ps` would make
this a measurement; until then it errs small"*. These tests are about that
measurement, and about the three things it must not do: guess when it cannot
read, report zero as a budget, or quietly hand the whole prompt's allowance to
one attached file.
"""

from __future__ import annotations

import pytest

from core.context_budget import (
    CHARS_PER_TOKEN,
    DOCUMENT_SHARE,
    FALLBACK_CONTEXT_TOKENS,
    ContextBudget,
    budget_for,
    estimate_tokens,
    loaded_context_length,
)


class _Response:
    def __init__(self, payload) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def _ps(monkeypatch, payload) -> None:
    monkeypatch.setattr(
        "core.context_budget.requests.get", lambda url, **kw: _Response(payload)
    )


def _unreachable(monkeypatch) -> None:
    def _boom(url, **kw):
        raise OSError("connection refused")

    monkeypatch.setattr("core.context_budget.requests.get", _boom)


class TestTheLoadedContextIsRead:
    def test_the_running_window_is_returned(self, monkeypatch):
        """The shape `/api/ps` really answers with, measured on this machine."""
        _ps(monkeypatch, {"models": [{"name": "bge-m3:latest", "context_length": 8192}]})

        assert loaded_context_length("bge-m3:latest") == 8192

    def test_a_bare_name_matches_the_tag_ollama_resolved(self, monkeypatch):
        """A request may name `bge-m3` while `/api/ps` reports `bge-m3:latest`.
        Treating those as different models would put every request on the
        fallback and quietly undo this whole module."""
        _ps(monkeypatch, {"models": [{"name": "bge-m3:latest", "context_length": 8192}]})

        assert loaded_context_length("bge-m3") == 8192

    def test_a_provider_prefixed_id_matches(self, monkeypatch):
        _ps(monkeypatch, {"models": [{"name": "gemma4:12b", "context_length": 4096}]})

        assert loaded_context_length("ollama:gemma4:12b") == 4096

    def test_a_different_tag_of_the_same_family_does_not_match(self, monkeypatch):
        """The tag is part of the name. Reading `gemma4:12b`'s 4,096 window as
        `gemma4:26b`'s would size a prompt against a model that is not
        answering it."""
        _ps(monkeypatch, {"models": [{"name": "gemma4:12b", "context_length": 4096}]})

        assert loaded_context_length("gemma4:26b-a4b-it-q4_K_M") is None


class TestUnknownIsNeverANumber:
    """The discipline `vram_bytes` keeps by refusing to report 0 for a card it
    cannot read, and `locality_of` keeps by refusing to say "local" for a model
    it cannot place."""

    def test_a_model_that_is_not_loaded_has_no_loaded_context(self, monkeypatch):
        _ps(monkeypatch, {"models": []})

        assert loaded_context_length("gemma4:12b") is None

    def test_an_unreachable_ollama_yields_none_rather_than_raising(self, monkeypatch):
        _unreachable(monkeypatch)

        assert loaded_context_length("gemma4:12b") is None

    def test_a_reply_we_do_not_understand_yields_none(self, monkeypatch):
        _ps(monkeypatch, {"models": "not a list"})

        assert loaded_context_length("gemma4:12b") is None

    def test_a_context_of_zero_is_unreadable_not_a_budget_of_nothing(self, monkeypatch):
        """Zero would make every document "too large" and every prompt refuse.
        It is the false-zero bug in a new place."""
        _ps(monkeypatch, {"models": [{"name": "gemma4:12b", "context_length": 0}]})

        assert loaded_context_length("gemma4:12b") is None

    def test_no_model_named_is_not_a_question_that_can_be_answered(self):
        assert loaded_context_length(None) is None
        assert loaded_context_length("") is None


class TestTheBudgetSaysWhetherItWasMeasured:
    def test_a_measured_window_is_marked_as_one(self, monkeypatch):
        _ps(monkeypatch, {"models": [{"name": "gemma4:12b", "context_length": 16384}]})

        budget = budget_for("gemma4:12b")

        assert budget.total_tokens == 16384
        assert budget.measured is True

    def test_an_unknown_window_falls_back_and_admits_it(self, monkeypatch):
        """`measured` is carried rather than inferred, so a fallback constant is
        never quoted back to a user as a fact about their machine."""
        _unreachable(monkeypatch)

        budget = budget_for("gemma4:12b")

        assert budget.total_tokens == FALLBACK_CONTEXT_TOKENS
        assert budget.measured is False

    def test_room_is_held_back_for_the_reply(self, monkeypatch):
        """A budget that spends the whole window on input leaves the model room
        to say nothing."""
        _ps(monkeypatch, {"models": [{"name": "m", "context_length": 8000}]})

        budget = budget_for("m")

        assert budget.reply_reserve_tokens > 0
        assert budget.input_tokens == 8000 - budget.reply_reserve_tokens


class TestDocumentsGetAShareNotTheWholeInput:
    """The mistake this property exists to prevent.

    The input budget also covers the identity preamble, the facts recall
    injects, and the question. Handing all of it to the composer lets one long
    document crowd out the memory that makes the answer worth having.
    """

    def test_documents_get_less_than_the_whole_input_budget(self):
        budget = ContextBudget(total_tokens=4096, measured=True, reply_reserve_tokens=1024)

        assert budget.document_tokens < budget.input_tokens

    def test_the_share_reproduces_the_constant_it_replaces(self):
        """`compose.py` used a flat 1,800 tokens, chosen as "roughly half" of
        Ollama's 4,096 default. At that context this yields 1,843 — so nothing
        about today's behaviour changes, and the judgement is now a proportion
        rather than a number that cannot grow."""
        budget = ContextBudget(
            total_tokens=FALLBACK_CONTEXT_TOKENS, measured=False, reply_reserve_tokens=1024
        )

        assert 1750 <= budget.document_tokens <= 1900

    def test_a_larger_loaded_context_buys_a_larger_share(self):
        """The point of measuring. A model loaded with 16k should not be held to
        a constant chosen for 4k."""
        small = ContextBudget(total_tokens=4096, measured=True, reply_reserve_tokens=1024)
        large = ContextBudget(total_tokens=16384, measured=True, reply_reserve_tokens=4096)

        assert large.document_tokens > small.document_tokens * 3

    def test_characters_are_what_the_composer_counts_in(self):
        budget = ContextBudget(total_tokens=4096, measured=True, reply_reserve_tokens=1024)

        assert budget.document_chars == budget.document_tokens * CHARS_PER_TOKEN


class TestEstimationErrsTowardFewerCharactersFitting:
    def test_the_estimate_overstates_rather_than_understates(self):
        """English averages nearer four characters per token. Three is used so
        the estimate errs toward an excerpt where the whole would have gone in.
        The opposite error silently drops the end of a document, and the end of
        a contract is where the termination clause lives."""
        text = "a" * 400

        assert estimate_tokens(text) == 400 // CHARS_PER_TOKEN + 1
        assert estimate_tokens(text) > 400 / 4

    def test_a_partial_token_still_costs_one(self):
        assert estimate_tokens("a") == 1

    def test_nothing_costs_nothing(self):
        assert estimate_tokens("") == 0

    def test_fitting_is_answered_against_the_input_budget(self):
        budget = ContextBudget(total_tokens=400, measured=True, reply_reserve_tokens=100)

        assert budget.fits("a" * (budget.input_tokens * CHARS_PER_TOKEN))
        assert not budget.fits("a" * (budget.input_tokens * CHARS_PER_TOKEN + CHARS_PER_TOKEN))

    def test_an_overspent_budget_reports_zero_rather_than_a_negative(self):
        """A negative budget is not a smaller budget — it is a request that will
        not fit, and a caller doing arithmetic on the difference should be
        deciding what to drop."""
        budget = ContextBudget(total_tokens=100, measured=True, reply_reserve_tokens=25)

        assert budget.remaining_after("a" * 10_000) == 0


class TestTheDestinationCannotLeaveTheMachine:
    """`test_egress_chokepoint.py` exempts this module because its destination
    is loopback. That exemption has to be a **fact about the code**, not an
    intention — `base_url` is a parameter, so without enforcement it is a
    promise any caller can break, and rule 3 becomes unenforceable through a
    module nobody thinks of as a network client.
    """

    def test_a_remote_host_is_refused_without_asking_it_anything(self, monkeypatch):
        asked = []

        def _record(url, **kw):
            asked.append(url)
            raise AssertionError("a request was made to a non-loopback host")

        monkeypatch.setattr("core.context_budget.requests.get", _record)

        assert loaded_context_length("m", base_url="http://evil.test:11434") is None
        assert asked == []

    def test_a_host_that_merely_starts_with_loopback_is_not_loopback(self, monkeypatch):
        """`http://127.0.0.1.evil.test` begins with something that looks like
        loopback and resolves anywhere. Parsed, never prefix-matched."""
        monkeypatch.setattr(
            "core.context_budget.requests.get",
            lambda *a, **k: pytest.fail("asked a spoofed host"),
        )

        assert loaded_context_length("m", base_url="http://127.0.0.1.evil.test") is None

    def test_credentials_cannot_smuggle_a_remote_host_past_the_check(self, monkeypatch):
        """`http://127.0.0.1@evil.test` has userinfo that looks like the host.
        `urlparse` puts the real host after the `@`."""
        monkeypatch.setattr(
            "core.context_budget.requests.get",
            lambda *a, **k: pytest.fail("asked a host hidden behind userinfo"),
        )

        assert loaded_context_length("m", base_url="http://127.0.0.1@evil.test") is None

    @pytest.mark.parametrize(
        "base_url",
        [
            "http://127.0.0.1:11434",
            "http://localhost:11434",
            "http://[::1]:11434",
        ],
    )
    def test_the_loopback_spellings_are_allowed(self, monkeypatch, base_url):
        _ps(monkeypatch, {"models": [{"name": "m", "context_length": 2048}]})

        assert loaded_context_length("m", base_url=base_url) == 2048

    def test_a_malformed_url_is_refused_rather_than_raising(self, monkeypatch):
        monkeypatch.setattr(
            "core.context_budget.requests.get",
            lambda *a, **k: pytest.fail("asked something unparseable"),
        )

        assert loaded_context_length("m", base_url="::::") is None
