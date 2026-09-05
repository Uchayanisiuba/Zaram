# backend/tests/test_cloud_generation_invariant.py
"""The cloud generation invariant — Spine content may leave, but never quietly.

`test_outbound_query_invariant.py` guards a *narrower* property than its name
suggests: nothing from the Spine may reach a **search query**. That holds
structurally because recalled facts live in `system_prompt` and the search path
never reads it.

**`system_prompt` is exactly what a generation call sends.** While the only
engine was `OllamaEngine` on loopback, that was not egress and the distinction
never had to be made. `OpenAICompatibleEngine` makes it: every cloud generation
carries recalled facts off the machine *by design* — `CLAUDE.md` asks for
"carries project context into the cloud request" and in the same breath for
"showing the user exactly what leaves before it does".

So the invariant here is not "memory must not leave". It is:

    memory may leave, and it may only leave through the gate,
    with the user's confirmation, and having been logged first.

That is a claim about what the code *cannot* do, which is why it is asserted
structurally rather than by reading the engine and agreeing that it looks
right. Each test below breaks a different one of those clauses.
"""

from __future__ import annotations

import json

import pytest

from core.egress import EgressGate, EgressLog, EgressPolicy, Mode
from runtimes.models.engines.base_engine import ERROR_PREFIX
from runtimes.models.engines.openai_compatible_engine import (
    MissingApiKey,
    OpenAICompatibleEngine,
)

#: A string that exists only in the Spine. Recall puts it in `system_prompt`;
#: if a request reaches the network without this having been shown and logged,
#: the user's memory left the machine unannounced.
SECRET = "zzq-spine-only-marker-8f2a"

CLOUD_HOST = "api.example-cloud.test"
CLOUD_URL = f"https://{CLOUD_HOST}"


@pytest.fixture
def gate(tmp_path):
    """A real gate with its own log and policy. Not a mock.

    The property under test is that the *gate* is unavoidable, so substituting
    a double for it would assert only that the engine calls something.
    """
    return EgressGate(
        log=EgressLog(str(tmp_path / "egress.db")),
        policy=EgressPolicy(str(tmp_path / "policy.json")),
    )


@pytest.fixture
def engine(gate):
    return OpenAICompatibleEngine(
        base_url=CLOUD_URL,
        api_key="sk-test-key-not-real",
        default_model="test-model",
        gate=gate,
        source="chat",
    )


def _sent(monkeypatch) -> list[dict]:
    """Fail loudly if anything actually opens a socket.

    Patched at `urllib.request.urlopen` inside the gate — the real transport,
    and the lowest point the request passes through. Stubbing a method on the
    engine would prove only that *that* method was not called; this proves **no
    HTTP request happened**, whatever route the code took to not make one.

    That the patch target lives in `core.egress.gate` rather than in the engine
    is itself the property under test: the engine has no HTTP client, because
    `test_egress_chokepoint.py` does not let a shipped module have one.
    """
    calls: list[dict] = []

    def fake_urlopen(request, **kwargs):
        calls.append({"url": getattr(request, "full_url", str(request))})
        raise AssertionError(
            "a request reached the network in a test that expected it to be "
            "refused before the socket opened"
        )

    monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)
    return calls


class TestNothingLeavesWithoutTheGate:
    def test_an_unapproved_host_is_refused_before_any_request(self, engine, monkeypatch):
        """Default deny, rule 5, at the only path that sends memory.

        The policy has never heard of this host, so the answer is no — and the
        refusal has to happen *before* the socket, not after a response comes
        back. `_sent` raises if anything reaches `requests.post`.
        """
        _sent(monkeypatch)

        chunks = list(engine.stream_response("what did I quote them?", SECRET))

        assert len(chunks) == 1
        assert chunks[0].startswith(ERROR_PREFIX)
        assert CLOUD_HOST in chunks[0]

    def test_the_refusal_is_reported_not_raised(self, engine, monkeypatch):
        """A declined send is an answer, not a crash.

        It arrives in the transcript where the user asked the question, per the
        engine contract's in-band error convention. An exception here would
        tear down the stream and lose whatever had already been generated.
        """
        _sent(monkeypatch)

        chunks = list(engine.stream_response("hello", SECRET))

        assert chunks and all(isinstance(c, str) for c in chunks)


class TestTheUserSeesWhatLeaves:
    def test_the_confirmation_is_shown_the_literal_system_prompt(self, engine, gate, monkeypatch):
        """M10's requirement, asserted on the object the dialog will render.

        The confirmation receives the request *including* the body, and the
        body contains the recalled facts. A dialog that showed the destination
        but not the text would be a consent screen for a question the user
        cannot actually answer.
        """
        _sent(monkeypatch)
        gate.policy.set(CLOUD_HOST, Mode.ASK)

        shown: list[str] = []

        def confirm(request):
            shown.append(request.literal_text)
            return False  # decline, so nothing is sent

        gate.set_confirm(confirm)

        list(engine.stream_response("what did I quote them?", SECRET))

        assert shown, "the user was never asked"
        assert SECRET in shown[0], (
            "the confirmation did not contain the recalled fact that was about "
            "to leave the machine"
        )

    def test_the_user_is_asked_exactly_once_per_message(self, engine, gate, monkeypatch):
        """One request, one dialog.

        The first draft checked the gate explicitly and then called
        `stream_lines`, which checks again — so an approved host was logged
        twice and an `ask` host would have shown **two confirmation dialogs for
        one message**. Nothing else in this file caught it, because every other
        test either denies (short-circuiting at the first check) or allows
        (where a duplicate is invisible in the assertions).

        This matters beyond tidiness. A user shown the same request twice does
        not conclude the software is careful — they conclude it is broken and
        stop reading the dialog, which is the single outcome M10 cannot
        survive: a consent screen nobody reads is worse than none, because it
        launders the consent.
        """
        _sent(monkeypatch)
        gate.policy.set(CLOUD_HOST, Mode.ASK)

        asked: list[str] = []
        gate.set_confirm(lambda request: (asked.append(request.host), False)[1])

        list(engine.stream_response("what did I quote them?", SECRET))

        assert len(asked) == 1, f"the user was asked {len(asked)} times for one message"

    def test_one_message_writes_one_log_entry(self, engine, gate, monkeypatch):
        """The same defect seen from the log's side.

        A duplicated decision makes the egress log over-report — and a log that
        says a request happened twice is as untrustworthy as one that misses a
        request, because the user cannot tell which entries are real.
        """
        gate.policy.set(CLOUD_HOST, Mode.ALLOW)

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def __iter__(self):
                yield b"data: [DONE]\n"

        monkeypatch.setattr(
            "core.egress.gate.urllib.request.urlopen", lambda request, **kw: _Resp()
        )

        list(engine.stream_response("what did I quote them?", SECRET))

        assert len(gate.log.entries(10)) == 1

    def test_declining_sends_nothing(self, engine, gate, monkeypatch):
        _sent(monkeypatch)
        gate.policy.set(CLOUD_HOST, Mode.ASK)
        gate.set_confirm(lambda request: False)

        chunks = list(engine.stream_response("what did I quote them?", SECRET))

        assert chunks[0].startswith(ERROR_PREFIX)

    def test_with_no_confirmation_handler_installed_nothing_leaves(
        self, engine, gate, monkeypatch
    ):
        """The resting state before M10's dialog exists, and it is deliberate.

        A gate with no confirm handler refuses. So cloud generation can be
        wired, reachable and tested while the interface that makes it safe is
        still being built — and the failure mode of shipping it half-done is
        "it declines", not "it sends your client's rates to a third party".
        """
        _sent(monkeypatch)
        gate.policy.set(CLOUD_HOST, Mode.ASK)
        # No set_confirm call at all.

        chunks = list(engine.stream_response("what did I quote them?", SECRET))

        assert chunks[0].startswith(ERROR_PREFIX)


class TestItIsLoggedBeforeItIsSent:
    def test_the_recalled_fact_is_in_the_log_body(self, engine, gate, monkeypatch):
        """Rule 3, on the literal text rather than on the fact of a request.

        "A request was made to api.example-cloud.test" cannot answer the only
        question a privacy-conscious user has. The body is what answers it.
        """
        _sent(monkeypatch)
        gate.policy.set(CLOUD_HOST, Mode.ASK)
        gate.set_confirm(lambda request: False)

        list(engine.stream_response("what did I quote them?", SECRET))

        entries = gate.log.entries(10)
        assert entries, "nothing was logged"
        assert any(SECRET in (e.body or "") for e in entries), (
            "the egress log does not contain the text that was about to leave"
        )

    def test_a_refusal_is_logged_too(self, engine, gate, monkeypatch):
        """A log that only records successes cannot show what was attempted."""
        _sent(monkeypatch)

        list(engine.stream_response("what did I quote them?", SECRET))

        decisions = {e.decision for e in gate.log.entries(10)}
        assert decisions, "an unapproved attempt left no trace"
        assert decisions <= {"denied", "cancelled"}

    def test_the_api_key_is_never_written_to_the_log(self, engine, gate, monkeypatch):
        """The log is append-only and tamper-evident, which makes it the worst
        possible place to put a secret: a credential you cannot delete is one
        you cannot rotate away from.

        The key travels in the `Authorization` header, which the gate does not
        record. This asserts the outcome rather than the mechanism.
        """
        _sent(monkeypatch)
        gate.policy.set(CLOUD_HOST, Mode.ASK)
        gate.set_confirm(lambda request: False)

        list(engine.stream_response("hello", SECRET))

        for entry in gate.log.entries(10):
            assert "sk-test-key-not-real" not in (entry.body or "")
            assert "sk-test-key-not-real" not in (entry.url or "")


class TestWhatIsSentIsWhatWasShown:
    def test_the_body_checked_is_the_body_posted(self, engine, gate, monkeypatch):
        """The dialog cannot survive the text being rebuilt after approval.

        If the body were constructed once for the gate and again for the
        request, a change between them would mean the user approved something
        other than what left — which is worse than not asking, because it
        looks like consent.
        """
        gate.policy.set(CLOUD_HOST, Mode.ALLOW)

        posted: dict = {}

        class _Resp:
            """Stands in for the object `urlopen` returns: a line iterator."""

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def __iter__(self):
                yield b'data: {"choices":[{"delta":{"content":"ok"}}]}\n'
                yield b"data: [DONE]\n"

        def fake_urlopen(request, **kwargs):
            posted["url"] = request.full_url
            posted["data"] = request.data
            posted["headers"] = dict(request.headers)
            return _Resp()

        monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)

        tokens = list(engine.stream_response("what did I quote them?", SECRET))

        logged = [e for e in gate.log.entries(10) if e.body]
        assert logged, "nothing was logged"

        sent_body = posted["data"].decode("utf-8")
        assert sent_body == logged[0].body, (
            "the text that was logged and shown is not byte-identical to the "
            "text that was posted"
        )
        assert posted["url"] == logged[0].url
        # And the happy path still yields text, so this is not asserting
        # equality between two things that never happened.
        assert tokens == ["ok"]

    def test_the_key_is_sent_in_the_header_and_not_in_the_body(
        self, engine, gate, monkeypatch
    ):
        """Where the credential travels, asserted on the wire.

        The previous test guarantees the logged body equals the sent body. That
        guarantee is only safe *because* the key is not in the body — otherwise
        byte-identical logging would mean the secret is in the log by
        construction.
        """
        gate.policy.set(CLOUD_HOST, Mode.ALLOW)
        seen: dict = {}

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def __iter__(self):
                yield b"data: [DONE]\n"

        def fake_urlopen(request, **kwargs):
            seen["data"] = request.data
            seen["headers"] = {k.lower(): v for k, v in request.headers.items()}
            return _Resp()

        monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)

        list(engine.stream_response("q", SECRET))

        assert seen["headers"]["Authorization".lower()] == "Bearer sk-test-key-not-real"
        assert "sk-test-key-not-real" not in seen["data"].decode("utf-8")


class TestZaramNeverBuysInference:
    def test_no_key_is_a_refusal_at_construction(self):
        """Rule 1. A keyless cloud engine has nothing legitimate to fall back
        to, and failing at first use would put the discovery inside the user's
        first message instead of in setup."""
        with pytest.raises(MissingApiKey):
            OpenAICompatibleEngine(
                base_url=CLOUD_URL, api_key="", default_model="test-model"
            )

    def test_whitespace_is_not_a_key(self):
        with pytest.raises(MissingApiKey):
            OpenAICompatibleEngine(
                base_url=CLOUD_URL, api_key="   ", default_model="test-model"
            )


class TestTheEndpointIsBuiltPredictably:
    @pytest.mark.parametrize(
        "given",
        ["https://api.example.test", "https://api.example.test/", "https://api.example.test/v1"],
    )
    def test_both_conventions_reach_the_same_endpoint(self, given):
        """Providers print both in their own documentation, and a user pasting
        from a dashboard should not have to know which one we chose."""
        engine = OpenAICompatibleEngine(
            base_url=given, api_key="k", default_model="m"
        )

        assert engine.endpoint == "https://api.example.test/v1/chat/completions"

    def test_the_system_prompt_becomes_a_system_message(self):
        engine = OpenAICompatibleEngine(
            base_url=CLOUD_URL, api_key="k", default_model="m"
        )

        body = engine._body("the question", SECRET, None)

        assert body["messages"][0] == {"role": "system", "content": SECRET}
        assert body["messages"][1] == {"role": "user", "content": "the question"}
        assert body["stream"] is True

    def test_an_empty_system_prompt_sends_no_system_message(self):
        """A social turn the recall gate suppressed has nothing to carry, and
        an empty system message is a token cost with no content."""
        engine = OpenAICompatibleEngine(
            base_url=CLOUD_URL, api_key="k", default_model="m"
        )

        body = engine._body("hello", "", None)

        assert [m["role"] for m in body["messages"]] == ["user"]

    def test_json_is_valid_and_carries_the_model(self):
        engine = OpenAICompatibleEngine(
            base_url=CLOUD_URL, api_key="k", default_model="default-m"
        )

        assert json.loads(json.dumps(engine._body("q", "", "override-m")))["model"] == (
            "override-m"
        )
        assert engine._body("q", "", None)["model"] == "default-m"
