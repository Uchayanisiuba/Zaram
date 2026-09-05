# backend/tests/test_confirm_api.py
"""M10 — the question reaching a browser, and the answer reaching the thread.

`test_confirm_before_send.py` grades the machinery: that a blocked gate becomes
a visible question, that silence denies, and that an edit is what gets logged
*and* what gets sent. Every one of those tests calls `PendingConfirmations`
directly, which is the right level for those claims and is exactly why none of
them could see that nothing in the running product ever constructed one.

That is the shape of the deck bug repeated — an exporter with green tests behind
a route that read a field its model did not have. A capability reachable only
from Python is not a capability the product has. So this file grades the seam
and nothing the other file already covers:

* the routes exist, and the literal text survives the trip through JSON
* a decision posted over HTTP releases a thread parked inside the gate
* a question already answered cannot be answered a second time
* the gate the bootstrapper builds asks *this process's* store, not one that
  was replaced afterwards

The last one is the wiring, and it is the half that was missing. `set_confirm`
appeared in five test files and no shipped module.
"""

from __future__ import annotations

import json
import threading

import pytest
from fastapi.testclient import TestClient

from core.egress import (
    EgressGate,
    EgressLog,
    EgressPolicy,
    Mode,
    PendingConfirmations,
    set_gate,
    set_pending,
)

HOST = "api.example-cloud.test"
URL = f"https://{HOST}/v1/chat/completions"

#: Stands in for a recalled fact in the system prompt — what a user would
#: plausibly strike out before letting the request go.
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
def client(tmp_path):
    """The real routes over a gate and a store this test owns.

    No kernel boot: these endpoints touch the egress package and nothing else,
    and booting runtimes to reach them would grade the bootstrapper's speed
    rather than the routes. The wiring the boot path is responsible for is
    asserted separately, at the bottom of this file.
    """
    import main as main_module

    gate = EgressGate(
        log=EgressLog(str(tmp_path / "egress.db")),
        policy=EgressPolicy(str(tmp_path / "policy.json")),
    )
    gate.policy.set(HOST, Mode.ASK)

    # Short, so a test that deliberately leaves a question unanswered costs
    # half a second rather than two minutes.
    pending = PendingConfirmations(timeout=0.4)
    gate.set_confirm(pending.ask)

    set_gate(gate)
    set_pending(pending)
    try:
        yield TestClient(main_module.app), gate, pending
    finally:
        pending.cancel_all()
        set_gate(None)
        set_pending(None)


class _Resp:
    """A streaming response that records nothing and ends immediately."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        yield b"data: [DONE]\n"


def send_in_background(gate, body, posted, monkeypatch):
    """Run a gated request on a thread, as the chat path does.

    `posted` collects what actually reached the transport, so the assertions
    can compare shown, logged and sent rather than trusting any one of them.
    """

    def fake_urlopen(request, **kwargs):
        posted["data"] = request.data
        return _Resp()

    monkeypatch.setattr("core.egress.gate.urllib.request.urlopen", fake_urlopen)

    def run():
        try:
            list(gate.stream_lines(URL, method="POST", body=body, source="chat", timeout=5))
        except Exception as exc:  # EgressDenied — expected where a test refuses
            posted["denied"] = str(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


class TestTheQuestionIsVisibleOverHTTP:
    def test_a_waiting_request_is_listed_with_its_literal_text(
        self, client, monkeypatch
    ):
        """What the dialog renders, arriving the way the dialog gets it.

        The literal text rather than a summary: the contract calls for showing
        what actually leaves, and a paraphrase is a claim *about* the text.
        """
        http, gate, pending = client
        posted: dict = {}
        thread = send_in_background(gate, body_with_secret(), posted, monkeypatch)

        waiting = _wait_for_listing(http, count=1)[0]
        assert waiting["host"] == HOST
        assert DAY_RATE in waiting["literal_text"]
        assert waiting["byte_count"] > 0
        assert waiting["source"] == "chat"

        http.post(f"/egress/pending/{waiting['id']}", json={"approved": False})
        thread.join(timeout=5)

    def test_one_waiting_request_can_be_fetched_by_id(self, client, monkeypatch):
        """A dialog that reopened needs its subject back."""
        http, gate, pending = client
        posted: dict = {}
        thread = send_in_background(gate, body_with_secret(), posted, monkeypatch)

        listed = _wait_for_listing(http, count=1)[0]
        one = http.get(f"/egress/pending/{listed['id']}")

        assert one.status_code == 200
        assert one.json()["literal_text"] == listed["literal_text"]

        http.post(f"/egress/pending/{listed['id']}", json={"approved": False})
        thread.join(timeout=5)

    def test_nothing_waiting_is_an_empty_list_not_an_error(self, client):
        http, _, _ = client
        body = http.get("/egress/pending").json()
        assert body == {"pending": [], "count": 0}


class TestTheAnswerReachesTheThread:
    def test_approving_over_http_sends_the_request(self, client, monkeypatch):
        http, gate, pending = client
        body = body_with_secret()
        posted: dict = {}
        thread = send_in_background(gate, body, posted, monkeypatch)

        waiting = _wait_for_listing(http, count=1)[0]
        answer = http.post(f"/egress/pending/{waiting['id']}", json={"approved": True})
        thread.join(timeout=5)

        assert answer.status_code == 200
        assert answer.json() == {"id": waiting["id"], "approved": True, "edited": False}
        assert posted["data"].decode("utf-8") == body

    def test_refusing_over_http_blocks_it_and_records_the_attempt(
        self, client, monkeypatch
    ):
        """A refusal is logged too. A log that only records what succeeded
        cannot show what the software tried to do."""
        http, gate, pending = client
        posted: dict = {}
        thread = send_in_background(gate, body_with_secret(), posted, monkeypatch)

        waiting = _wait_for_listing(http, count=1)[0]
        http.post(f"/egress/pending/{waiting['id']}", json={"approved": False})
        thread.join(timeout=5)

        assert "data" not in posted, "a refused request reached the transport"
        assert "denied" in posted
        cancelled = [e for e in gate.log.entries(10) if e.decision == "cancelled"]
        assert cancelled, "a refusal left no record"

    def test_an_edit_posted_over_http_is_what_is_sent_and_logged(
        self, client, monkeypatch
    ):
        """The whole feature, through the wire that carries it.

        The user strikes the day rate in the dialog. Three things must agree
        afterwards: the bytes on the wire, the body in the append-only log, and
        the absence of the fact they removed. If the wire kept the original the
        dialog would be theatre — and worse than no dialog, because the user
        believes the removal happened.
        """
        http, gate, pending = client
        original = body_with_secret()
        redacted = original.replace(DAY_RATE, "[removed]")
        posted: dict = {}
        thread = send_in_background(gate, original, posted, monkeypatch)

        waiting = _wait_for_listing(http, count=1)[0]
        answer = http.post(
            f"/egress/pending/{waiting['id']}",
            json={"approved": True, "body": redacted},
        )
        thread.join(timeout=5)

        on_the_wire = posted["data"].decode("utf-8")
        logged = [e for e in gate.log.entries(10) if e.body][0].body

        assert answer.json()["edited"] is True
        assert DAY_RATE not in on_the_wire, "the removed fact was sent anyway"
        assert DAY_RATE not in logged, "the log records text the user did not approve"
        assert on_the_wire == redacted == logged

    def test_answering_twice_is_refused(self, client, monkeypatch):
        """A double-click, or a retry against a question that already timed
        out. Neither may approve a second send of text that has already gone."""
        http, gate, pending = client
        posted: dict = {}
        thread = send_in_background(gate, body_with_secret(), posted, monkeypatch)

        waiting = _wait_for_listing(http, count=1)[0]
        first = http.post(f"/egress/pending/{waiting['id']}", json={"approved": True})
        second = http.post(f"/egress/pending/{waiting['id']}", json={"approved": True})
        thread.join(timeout=5)

        assert first.status_code == 200
        assert second.status_code == 404
        assert "no longer waiting" in second.json()["detail"]

    def test_deciding_an_unknown_id_is_a_404(self, client):
        assert http_404(client, "/egress/pending/no-such-id")

    def test_fetching_an_unknown_id_is_a_404(self, client):
        http, _, _ = client
        assert http.get("/egress/pending/no-such-id").status_code == 404


class TestTheGateTheProductActuallyBuilds:
    """The half that was missing, and the reason it stayed missing.

    `set_confirm` existed, was correct, and appeared in nothing but tests. The
    resting state that produced — every `ask` host refused — is the *right*
    default and is indistinguishable from this being wired, right up until
    someone tries to send something.
    """

    def test_the_booted_gate_asks_this_processs_store(self, tmp_path, monkeypatch):
        from core.bootstrapper import KernelBootstrapper
        from core.egress import get_gate, get_pending

        monkeypatch.setenv("ZARAM_EGRESS_LOG", str(tmp_path / "egress.db"))
        monkeypatch.setenv("ZARAM_EGRESS_POLICY", str(tmp_path / "policy.json"))
        monkeypatch.setenv("ZARAM_EGRESS_RETENTION_DAYS", "0")

        set_gate(None)
        set_pending(PendingConfirmations(timeout=0.4))
        try:
            KernelBootstrapper()._init_egress_gate()
            gate = get_gate()
            gate.policy.set(HOST, Mode.ASK)

            decided: list[bool] = []
            thread = threading.Thread(
                target=lambda: decided.append(_check_quietly(gate)), daemon=True
            )
            thread.start()

            # Visible in the store the endpoints read. Before this wiring the
            # question was never asked at all — `_refuse_by_default` answered
            # it, and nothing was ever pending.
            waiting = _wait_for_store(get_pending(), count=1)[0]
            assert waiting["host"] == HOST

            get_pending().decide(waiting["id"], approved=False)
            thread.join(timeout=5)
            assert decided == [False]
        finally:
            get_pending().cancel_all()
            set_gate(None)
            set_pending(None)

    def test_a_replaced_store_is_the_one_that_gets_asked(self, tmp_path, monkeypatch):
        """The hook resolves the store per call rather than binding it at boot.

        Bound once, a later `set_pending` would leave the gate asking an
        instance no interface is watching: the question invisible, and the only
        possible outcome a two-minute timeout that reads as a hang.
        """
        from core.bootstrapper import KernelBootstrapper
        from core.egress import get_gate, get_pending

        monkeypatch.setenv("ZARAM_EGRESS_LOG", str(tmp_path / "egress.db"))
        monkeypatch.setenv("ZARAM_EGRESS_POLICY", str(tmp_path / "policy.json"))
        monkeypatch.setenv("ZARAM_EGRESS_RETENTION_DAYS", "0")

        set_gate(None)
        set_pending(PendingConfirmations(timeout=0.4))
        try:
            KernelBootstrapper()._init_egress_gate()
            gate = get_gate()
            gate.policy.set(HOST, Mode.ASK)

            replacement = PendingConfirmations(timeout=0.4)
            set_pending(replacement)

            thread = threading.Thread(target=lambda: _check_quietly(gate), daemon=True)
            thread.start()

            waiting = _wait_for_store(replacement, count=1)[0]
            replacement.decide(waiting["id"], approved=False)
            thread.join(timeout=5)
        finally:
            get_pending().cancel_all()
            set_gate(None)
            set_pending(None)


def _check_quietly(gate) -> bool:
    """Run the gate's decision and report it, swallowing the refusal."""
    from core.egress import EgressDenied

    try:
        gate.check(URL, method="POST", body="b", source="chat")
        return True
    except EgressDenied:
        return False


def _wait_for_listing(http, *, count: int, tries: int = 300):
    for _ in range(tries):
        body = http.get("/egress/pending").json()
        if body["count"] >= count:
            return body["pending"]
        threading.Event().wait(0.01)
    raise AssertionError(f"expected {count} pending over HTTP, saw {http.get('/egress/pending').json()}")


def _wait_for_store(pending, *, count: int, tries: int = 300):
    for _ in range(tries):
        items = pending.pending()
        if len(items) >= count:
            return items
        threading.Event().wait(0.01)
    raise AssertionError(f"expected {count} pending, saw {pending.pending()}")


def http_404(client, path: str) -> bool:
    http, _, _ = client
    return http.post(path, json={"approved": True}).status_code == 404
