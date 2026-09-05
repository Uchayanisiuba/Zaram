# backend/tests/test_confirm_before_send.py
"""M10 — confirm before send, and the edit that makes it useful.

The gate has always had a confirm hook, and it has always been answered by
`_refuse_by_default`. This is the machinery that lets a person answer it: the
hook blocks a worker thread, the question becomes visible to the interface, and
a decision releases it.

**The edit is the half that is easy to get wrong and easy to skip.** An
all-or-nothing dialog can only express "send everything" or "send nothing",
and the case that actually arises is neither — *send this question, but not my
day rate*. Rule 4 says the user can remove any stored fact and see the effect;
a confirmation that cannot honour a removal is offering a choice the product
has already promised is finer-grained than that.

The dangerous version of the same feature is one where the text shown, the text
logged and the text sent are not the same three bytes. That is worse than not
asking at all, because it looks like consent. Most of this file is that.
"""

from __future__ import annotations

import json
import threading

import pytest

from core.egress import EgressGate, EgressLog, EgressPolicy, Mode
from core.egress.confirm import PendingConfirmations

HOST = "api.example-cloud.test"
URL = f"https://{HOST}/v1/chat/completions"

#: Stands in for a recalled fact in the system prompt — the thing a user would
#: plausibly strike out before sending.
DAY_RATE = "their day rate is 450,000 naira"


def body_with_secret() -> str:
    return json.dumps(
        {
            "model": "m",
            "messages": [
                {"role": "system", "content": f"Recalled: {DAY_RATE}"},
                {"role": "user", "content": "draft the follow-up"},
            ],
        }
    )


@pytest.fixture
def gate(tmp_path):
    gate = EgressGate(
        log=EgressLog(str(tmp_path / "egress.db")),
        policy=EgressPolicy(str(tmp_path / "policy.json")),
    )
    gate.policy.set(HOST, Mode.ASK)
    return gate


@pytest.fixture
def pending():
    # Short timeout: the timeout tests should not add two minutes to the suite.
    return PendingConfirmations(timeout=0.4)


def ask_in_background(gate, body, *, sent):
    """Run a gated request on a thread, as the chat path does.

    `sent` collects what actually reached the transport, so every assertion
    below can compare shown, logged and sent rather than trusting any one.
    """

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def __iter__(self):
            yield b"data: [DONE]\n"

    def run():
        try:
            list(
                gate.stream_lines(
                    URL, method="POST", body=body, source="chat", timeout=5
                )
            )
        except Exception as exc:  # EgressDenied on refusal — expected in some tests
            sent.append(("denied", str(exc)))

    return run, _Resp


class TestTheQuestionReachesTheInterface:
    def test_a_waiting_request_is_visible_with_its_literal_text(self, gate, pending, monkeypatch):
        """The dialog renders this. It must be the text, not a summary —
        a paraphrase is a claim *about* what leaves rather than what leaves."""
        gate.set_confirm(pending.ask)
        sent: list = []
        run, resp = ask_in_background(gate, body_with_secret(), sent=sent)
        monkeypatch.setattr(
            "core.egress.gate.urllib.request.urlopen", lambda r, **kw: resp()
        )

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        waiting = _wait_for_one(pending)
        assert waiting["host"] == HOST
        assert DAY_RATE in waiting["literal_text"]
        assert waiting["byte_count"] > 0

        pending.decide(waiting["id"], approved=False)
        thread.join(timeout=5)

    def test_more_than_one_can_wait_at_once(self, pending):
        """A chat reply and a tool call can be in flight together, and a UI
        built on the assumption of one would silently drop the second."""
        from core.egress.gate import EgressRequest

        for i in range(2):
            threading.Thread(
                target=pending.ask,
                args=(EgressRequest(HOST, "POST", URL, f"body {i}", "chat"),),
                daemon=True,
            ).start()

        items = _wait_for(pending, count=2)
        assert len({i["id"] for i in items}) == 2


class TestSilenceIsNotConsent:
    def test_an_unanswered_question_denies(self, pending):
        """Not "allows after a while". A dialog nobody answered is a question
        nobody said yes to, and a closed tab must not park a thread holding the
        user's documents."""
        from core.egress.gate import EgressRequest

        request = EgressRequest(HOST, "POST", URL, body_with_secret(), "chat")

        assert pending.ask(request) is False

    def test_shutdown_releases_waiters_as_denied(self, pending):
        """A thread parked on an event nobody will set is a process that will
        not exit, and the right answer while closing down is no."""
        from core.egress.gate import EgressRequest

        results: list[bool] = []
        thread = threading.Thread(
            target=lambda: results.append(
                pending.ask(EgressRequest(HOST, "POST", URL, "b", "chat"))
            ),
            daemon=True,
        )
        thread.start()
        _wait_for_one(pending)

        assert pending.cancel_all() == 1
        thread.join(timeout=5)
        assert results == [False]

    def test_deciding_something_that_is_not_waiting_says_so(self, pending):
        """A double-click or a retry must not approve a second send of text
        that has already gone."""
        assert pending.decide("no-such-id", approved=True) is False


class TestWhatIsShownIsWhatIsLoggedAndSent:
    def test_approving_unchanged_sends_the_original(self, gate, pending, monkeypatch):
        gate.set_confirm(pending.ask)
        body = body_with_secret()
        posted: dict = {}

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def __iter__(self):
                yield b"data: [DONE]\n"

        def fake_urlopen(request, **kwargs):
            posted["data"] = request.data
            return _Resp()

        monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)

        thread = threading.Thread(
            target=lambda: list(
                gate.stream_lines(URL, method="POST", body=body, source="chat", timeout=5)
            ),
            daemon=True,
        )
        thread.start()

        waiting = _wait_for_one(pending)
        pending.decide(waiting["id"], approved=True)
        thread.join(timeout=5)

        logged = [e for e in gate.log.entries(10) if e.body]
        assert logged[0].body == body
        assert posted["data"].decode("utf-8") == body

    def test_an_edit_is_what_gets_logged_and_what_gets_sent(
        self, gate, pending, monkeypatch
    ):
        """The whole feature, and the one place it can silently lie.

        The user strikes the day rate. Three things must now agree: the text on
        the wire, the text in the append-only log, and the absence of the fact
        they removed. If the wire kept the original, the dialog would be
        theatre — and worse than no dialog, because the user believes they
        removed it.
        """
        gate.set_confirm(pending.ask)
        original = body_with_secret()
        redacted = original.replace(DAY_RATE, "[removed]")
        posted: dict = {}

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def __iter__(self):
                yield b"data: [DONE]\n"

        def fake_urlopen(request, **kwargs):
            posted["data"] = request.data
            return _Resp()

        monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)

        thread = threading.Thread(
            target=lambda: list(
                gate.stream_lines(URL, method="POST", body=original, source="chat", timeout=5)
            ),
            daemon=True,
        )
        thread.start()

        waiting = _wait_for_one(pending)
        pending.decide(waiting["id"], approved=True, body=redacted)
        thread.join(timeout=5)

        on_the_wire = posted["data"].decode("utf-8")
        logged = [e for e in gate.log.entries(10) if e.body][0].body

        assert DAY_RATE not in on_the_wire, "the removed fact was sent anyway"
        assert DAY_RATE not in logged, "the log records text the user did not approve"
        assert on_the_wire == redacted
        assert logged == redacted

    def test_an_edit_on_a_refusal_is_ignored(self, pending):
        """There is no such thing as editing something you are not sending.

        Honouring it would write a body to the append-only log that nobody ever
        agreed to send — a permanent record of a fiction.
        """
        from core.egress.gate import EgressRequest

        request = EgressRequest(HOST, "POST", URL, "original", "chat")
        results: list[bool] = []
        thread = threading.Thread(
            target=lambda: results.append(pending.ask(request)), daemon=True
        )
        thread.start()

        waiting = _wait_for_one(pending)
        pending.decide(waiting["id"], approved=False, body="edited anyway")
        thread.join(timeout=5)

        assert results == [False]
        assert request.body == "original"


def _wait_for(pending, *, count: int, tries: int = 200):
    for _ in range(tries):
        items = pending.pending()
        if len(items) >= count:
            return items
        threading.Event().wait(0.01)
    raise AssertionError(f"expected {count} pending confirmation(s), saw {pending.pending()}")


def _wait_for_one(pending):
    return _wait_for(pending, count=1)[0]
