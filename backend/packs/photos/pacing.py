"""Staying under a source's rate limit instead of meeting it.

Openverse's anonymous tier allows about 20 requests a minute, and one page can
need more than that: eight descriptions, each a search or three and a download
or five. Without pacing the first 20 go through and everything after the 429 is
reported as "rate limited", on a page that would have finished a minute later.

This module is the "wait a little" half. The finder asks `RequestPacer.acquire`
before every request -- searches **and** downloads, since the source counts
both -- and either gets a go-ahead (after a short sleep if needed) or a refusal
that says the wait would be too long, which the finder turns into a plain
reason on the photos it could not get.

A sliding window, not a refilling bucket
----------------------------------------
The usual token bucket starts full and refills steadily, which lets a burst of
its capacity through and then a trickle -- so in a single minute it can pass
the capacity *plus* a minute's refill, more than the limit it was meant to
respect. This keeps the last ``per_minute`` request times and allows a new one
only when the oldest of them is a full minute old, so **no 60-second window ever
holds more than ``per_minute``**. The cost is that a burst is followed by a
real pause rather than a trickle, which is the honest shape of the source's own
limit.

Time is injected (``clock`` and ``sleep``) so tests drive it with a fake clock
and never really wait. State is per process and keyed by source, so two pages at
once share one allowance, and a 429 (`penalise`) holds the source back for
everything that follows, not only the page that met it.

Nothing here is stored: the allowance lives in memory and is gone when Zaram
closes.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

WINDOW = 60.0


class RequestPacer:
    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] | None = None,
    ):
        self._clock = clock
        # Looked up at call time, so a test that patches `time.sleep` still works.
        self._sleep = sleep or (lambda seconds: time.sleep(seconds))
        self._lock = threading.Lock()
        self._slots: dict[str, deque[float]] = {}
        self._held_until: dict[str, float] = {}

    def now(self) -> float:
        return self._clock()

    def wait_needed(self, key: str, per_minute: int) -> float:
        """Seconds until a request could go, without reserving anything."""
        with self._lock:
            return self._slot(key, per_minute, self._clock()) - self._clock()

    def acquire(self, key: str, per_minute: int, *, max_wait: float) -> float | None:
        """Reserve the next slot and sleep until it. Returns the seconds slept.

        ``None`` means the wait would exceed ``max_wait``: nothing was reserved
        and nothing was slept, and the caller should give up on this source for
        now rather than hold the page.
        """
        with self._lock:
            now = self._clock()
            slot = self._slot(key, per_minute, now)
            wait = max(0.0, slot - now)
            if wait > max_wait:
                return None
            self._slots.setdefault(key, deque()).append(slot)
        if wait > 0:
            self._sleep(wait)
        return wait

    def penalise(self, key: str, seconds: float) -> None:
        """The source said "too many": ask nothing of it for ``seconds``."""
        with self._lock:
            until = self._clock() + max(0.0, seconds)
            self._held_until[key] = max(self._held_until.get(key, 0.0), until)

    def reset(self) -> None:
        with self._lock:
            self._slots.clear()
            self._held_until.clear()

    # ------------------------------------------------------------ internals

    def _slot(self, key: str, per_minute: int, now: float) -> float:
        """The earliest time the next request may go. Caller holds the lock."""
        per_minute = max(1, int(per_minute))
        slots = self._slots.setdefault(key, deque())
        while slots and slots[0] <= now - WINDOW:
            slots.popleft()
        slot = now
        if len(slots) >= per_minute:
            slot = slots[-per_minute] + WINDOW
        if slots:
            slot = max(slot, slots[-1])  # keep the reservations in order
        return max(slot, self._held_until.get(key, 0.0), now)


_PACER = RequestPacer()


def default_pacer() -> RequestPacer:
    """The process-wide pacer: one allowance per source however many pages ask."""
    return _PACER
