# backend/tests/test_confirm_does_not_freeze.py
"""The confirmation has to be answerable, which means the server has to answer.

Everything about confirm-before-send was in place and tested — the gate blocked,
the question appeared in `/egress/pending`, an approval released the thread, an
edit reached the wire. Run against the real backend, the feature could not work
at all.

`ChatRouter._kernel_stream` was an `async def` generator driving the engine's
*synchronous* generator with a plain `for`. Every blocking step therefore ran on
the event loop thread. When the gate reached its confirm hook, the loop stopped:
`/egress/pending` could not be served, so the dialog could never appear, so no
answer could arrive, so the only reachable outcome was the two-minute timeout —
with `/health` unresponsive throughout. The log then recorded that timeout as
"you chose not to send this", attributing to the user a decision they were never
shown.

Three defects, one cause, and none of them visible from a unit test of any
single component. So this file grades the property that connects them: **a
blocking engine step must not stop the loop, and a refusal nobody made must not
be recorded as one.**
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from core.chat_router import ChatRouter
from core.egress import EgressGate, EgressLog, EgressPolicy, Mode
from core.egress.confirm import PendingConfirmations
from core.egress.gate import EgressDenied, EgressRequest

HOST = "api.example-cloud.test"
URL = f"https://{HOST}/v1/chat/completions"

class _Engine:
    """An engine that parks mid-stream, the way waiting for an answer does."""

    def __init__(self, started: threading.Event | None = None,
                 release: threading.Event | None = None):
        self._started = started
        self._release = release
        self.ran_on: list[int] = []

    def execute(self, *args, **kwargs):
        yield "first"
        self.ran_on.append(threading.get_ident())
        if self._started is not None:
            self._started.set()
        if self._release is not None:
            # Bounded, so a regression fails the test instead of hanging it.
            self._release.wait(5.0)
        yield "second"


async def drain(agen) -> list:
    return [chunk async for chunk in agen]


@pytest.mark.asyncio
async def test_the_loop_keeps_serving_while_the_engine_blocks(monkeypatch):
    """The property the whole feature rests on.

    While a chat stream sits inside a blocking step — which is exactly what
    waiting for a confirmation is — the loop must still be running other work.
    If it is not, `/egress/pending` cannot be served, the dialog never appears,
    and the question can only time out.

    **Asked from another thread, deliberately.** The first version of this test
    measured from inside the loop, which cannot work: code on a blocked loop
    does not run, so the measurement happened before the block began and the
    test passed against the very bug it was written for. A watcher thread waits
    until the engine is parked, then asks the loop to do one trivial thing and
    times how long that takes. A blocked loop cannot answer; a free one answers
    at once.
    """
    monkeypatch.setattr("core.chat_router.USE_NEW_KERNEL", True)
    loop = asyncio.get_running_loop()

    started, release = threading.Event(), threading.Event()
    ticked = threading.Event()
    responsive: list[bool] = []

    def watch():
        if not started.wait(5.0):
            release.set()
            return
        # The engine is parked right now. Can the loop still do anything?
        loop.call_soon_threadsafe(ticked.set)
        responsive.append(ticked.wait(1.5))
        release.set()

    engine = _Engine(started, release)
    router = ChatRouter(engine, event_bus=None, legacy_generator_func=lambda *a: iter(()))
    threading.Thread(target=watch, daemon=True).start()

    chunks = await asyncio.wait_for(drain(router.route("hello", "m")), timeout=15)

    assert responsive == [True], (
        "the event loop could not run a callback while the engine was blocked — "
        "nothing could answer /egress/pending, so no confirmation could arrive"
    )
    assert any("first" in c for c in chunks)
    assert any("second" in c for c in chunks)


@pytest.mark.asyncio
async def test_the_engine_runs_off_the_loop_thread(monkeypatch):
    """Stated directly, so the reason survives a refactor of the timing test."""
    monkeypatch.setattr("core.chat_router.USE_NEW_KERNEL", True)
    engine = _Engine()
    router = ChatRouter(engine, event_bus=None, legacy_generator_func=lambda *a: iter(()))

    await drain(router.route("hello", "m"))

    assert engine.ran_on and engine.ran_on[0] != threading.get_ident(), (
        "the engine ran on the event loop thread"
    )


@pytest.mark.asyncio
async def test_the_legacy_path_does_not_block_either(monkeypatch):
    """Both chat paths, or the freeze just moves to whichever is in use."""
    monkeypatch.setattr("core.chat_router.USE_NEW_KERNEL", False)
    seen: list[int] = []

    def legacy(*args, **kwargs):
        seen.append(threading.get_ident())
        yield "token"

    router = ChatRouter(None, event_bus=None, legacy_generator_func=legacy)
    await drain(router.route("hello", "m"))

    assert seen and seen[0] != threading.get_ident()


class TestTheLogSaysWhatActuallyHappened:
    """A refusal nobody made must not be recorded as one.

    The log is append-only and tamper-evident. An entry claiming the user
    declined something they were never shown is not a cosmetic wording problem:
    it is a permanent, verifiable record of a decision that did not happen, and
    it is exactly the entry someone would go looking for to understand why a
    request failed.
    """

    @pytest.fixture
    def gate(self, tmp_path):
        gate = EgressGate(
            log=EgressLog(str(tmp_path / "egress.db")),
            policy=EgressPolicy(str(tmp_path / "policy.json")),
        )
        gate.policy.set(HOST, Mode.ASK)
        return gate

    def _refused_entry(self, gate):
        entries = [e for e in gate.log.entries(10) if e.decision == "cancelled"]
        assert entries, "the refusal was not recorded at all"
        return entries[0]

    def test_a_timeout_is_not_recorded_as_the_user_refusing(self, gate):
        gate.set_confirm(PendingConfirmations(timeout=0.2).ask)

        with pytest.raises(EgressDenied):
            gate.check(URL, method="POST", body="b", source="chat")

        reason = self._refused_entry(gate).reason
        assert "nobody answered" in reason
        assert "you chose" not in reason

    def test_shutdown_is_not_recorded_as_the_user_refusing(self, gate):
        pending = PendingConfirmations(timeout=5)
        gate.set_confirm(pending.ask)

        thread = threading.Thread(
            target=lambda: _swallow(lambda: gate.check(URL, method="POST", body="b")),
            daemon=True,
        )
        thread.start()
        _wait_for(pending, count=1)
        pending.cancel_all()
        thread.join(timeout=5)

        assert "shutting down" in self._refused_entry(gate).reason

    def test_an_actual_refusal_still_says_the_user_refused(self, gate):
        pending = PendingConfirmations(timeout=5)
        gate.set_confirm(pending.ask)

        thread = threading.Thread(
            target=lambda: _swallow(lambda: gate.check(URL, method="POST", body="b")),
            daemon=True,
        )
        thread.start()
        waiting = _wait_for(pending, count=1)[0]
        pending.decide(waiting["id"], approved=False)
        thread.join(timeout=5)

        assert self._refused_entry(gate).reason == "you chose not to send this"


class TestAskingFromTheEventLoopRefusesInstead:
    """The guard, not the fix.

    The call site was corrected, and this is what stops the next one costing
    two minutes of a frozen product. Asked from the event loop thread, the hook
    cannot deliver its question to anyone, so it refuses at once and records
    why rather than blocking the server that would have answered it.
    """

    @pytest.mark.asyncio
    async def test_it_refuses_at_once_rather_than_blocking(self):
        pending = PendingConfirmations(timeout=30)
        request = EgressRequest(HOST, "POST", URL, "b", "chat")

        started = time.monotonic()
        answer = pending.ask(request)
        took = time.monotonic() - started

        assert answer is False
        assert took < 1.0, f"blocked for {took:.1f}s on the event loop"
        assert pending.pending() == [], "left a question nobody could ever answer"
        assert "would have frozen" in (request.refusal_reason or "")

    def test_off_the_loop_it_still_blocks_and_waits(self):
        """The guard must not have turned every confirmation into a refusal."""
        pending = PendingConfirmations(timeout=5)
        request = EgressRequest(HOST, "POST", URL, "b", "chat")
        results: list[bool] = []

        thread = threading.Thread(
            target=lambda: results.append(pending.ask(request)), daemon=True
        )
        thread.start()
        waiting = _wait_for(pending, count=1)[0]
        pending.decide(waiting["id"], approved=True)
        thread.join(timeout=5)

        assert results == [True]


def _swallow(fn):
    try:
        fn()
    except EgressDenied:
        pass


def _wait_for(pending, *, count: int, tries: int = 300):
    for _ in range(tries):
        items = pending.pending()
        if len(items) >= count:
            return items
        threading.Event().wait(0.01)
    raise AssertionError(f"expected {count} pending, saw {pending.pending()}")
