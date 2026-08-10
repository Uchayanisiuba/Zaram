"""Shutdown has to actually finish.

The speech runtime stored EventBus subscription tokens as ``_unsubscribe_*``
and called them, but ``subscribe`` returns an opaque string and there was no
``unsubscribe`` for it to be. Every kernel shutdown raised TypeError on the
first of those calls, so everything after it in ``shutdown()`` never ran.

That is not a voice bug even though it lives in the voice runtime. The Spine is
SQLite in WAL mode, and an unclean exit on every single run is not a thing to
leave in place while building on top of it.
"""

from __future__ import annotations

import pytest

from core.event_bus import EventBus, ZaramEvent


class TestUnsubscribe:
    def test_a_token_is_not_callable(self):
        """The shape that caused it, asserted so nobody re-derives the old idea."""
        bus = EventBus()
        token = bus.subscribe("x", lambda e: None)

        assert isinstance(token, str)
        assert not callable(token)

    def test_unsubscribe_stops_delivery(self):
        """The replacement works — not merely that the crash is gone."""
        bus = EventBus()
        seen = []
        token = bus.subscribe("ping", seen.append)

        bus.publish(ZaramEvent(event_type="ping"))
        assert len(seen) == 1

        assert bus.unsubscribe(token) is True
        bus.publish(ZaramEvent(event_type="ping"))
        assert len(seen) == 1, "callback still receiving after unsubscribe"

    def test_unsubscribe_is_idempotent(self):
        """Shutdown paths must not need to track whether they already ran."""
        bus = EventBus()
        token = bus.subscribe("ping", lambda e: None)

        assert bus.unsubscribe(token) is True
        assert bus.unsubscribe(token) is False
        assert bus.unsubscribe("sub_neverexisted") is False

    def test_unsubscribing_one_leaves_the_others(self):
        bus = EventBus()
        a, b = [], []
        token_a = bus.subscribe("ping", a.append)
        bus.subscribe("ping", b.append)

        bus.unsubscribe(token_a)
        bus.publish(ZaramEvent(event_type="ping"))

        assert a == []
        assert len(b) == 1


class TestSpeechRuntimeShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_completes_without_raising(self):
        """The regression itself, end to end."""
        from runtimes.speech.runtime import SpeechRuntime

        bus = EventBus()
        runtime = SpeechRuntime(bus)
        await runtime.initialize()

        await runtime.shutdown()  # raised TypeError before this fix

        assert runtime.get_state().value in {"stopped", "stopping"}

    @pytest.mark.asyncio
    async def test_shutdown_actually_detaches_from_the_bus(self):
        """Reaching the end of shutdown() is not the same as having unsubscribed."""
        from runtimes.speech.runtime import SpeechRuntime

        bus = EventBus()
        runtime = SpeechRuntime(bus)
        await runtime.initialize()
        subscribed = sum(len(v) for v in bus._subscribers.values())
        assert subscribed > 0, "nothing subscribed; test proves nothing"

        await runtime.shutdown()

        remaining = sum(len(v) for v in bus._subscribers.values())
        assert remaining < subscribed
