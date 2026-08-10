"""The thing that makes rule 7e happen.

Rule 7e says facts *"enter provisionally, become durable through use, and decay
if never recalled"*. The rules for that were written, tested and correct, and
nothing in the running product ever called them. A decay engine nobody invokes
and no decay engine at all are the same Spine: one that grows forever and
promotes nothing.

**Why daily, and why also at startup.**

Every threshold in `DecayConfig` is expressed in whole days — a 90-day half
life, `age_days > 30`, `age_days > 7`. A pass running more often than once a
day therefore cannot change a single outcome; it can only rewrite rows and
compete with the user's question for the disk. So daily is not a guess at a
reasonable interval, it is the finest granularity the rules can actually
distinguish.

Daily alone would not be enough, though, because Zaram is a desktop application
and not a server. Someone who opens it for an hour each morning would never
reach a 24-hour timer, and their Spine would decay exactly never — the same
inert outcome, arrived at more slowly. The startup pass is what makes the
behaviour real for how the product is actually used.

**Promotion proposes and never promotes.** `promotion_candidates()` is called
on the same pass because it needs the same full scan, but its output is an
offer. Promotion moves a fact from project scope to global, which changes what
is shareable, and rule 6 is that autonomy is granted by the user rather than
assumed.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

#: One pass a day. See the module docstring — this is the finest interval the
#: decay rules can distinguish, not a tuning knob.
#:
#: Overridable by environment for the same reason `MIN_RECALL_SCORE` is: a
#: schedule measured in days cannot otherwise be watched happening. Nothing in
#: the product sets it.
DEFAULT_INTERVAL_SECONDS = float(
    os.getenv("ZARAM_SPINE_MAINTENANCE_INTERVAL", str(24 * 60 * 60))
)

#: How long after boot the first pass runs.
#:
#: Not zero. A full scan of the Spine at the moment the kernel comes up would
#: compete with the user's first question, which is the single worst moment in
#: the product to be slow — it is the one people judge it on. A minute is long
#: enough to be clear of that and short enough that a five-minute session still
#: gets a pass.
DEFAULT_INITIAL_DELAY_SECONDS = float(
    os.getenv("ZARAM_SPINE_MAINTENANCE_DELAY", "60")
)


class SpineMaintenance:
    """Runs the decay pass and collects promotion candidates, on a timer.

    Owns no policy of its own. Both halves live in the memory runtime; this
    decides only *when*, and makes sure a failure in either one cannot take the
    backend down with it.
    """

    def __init__(
        self,
        memory_runtime: Any,
        event_bus: Any | None = None,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        initial_delay_seconds: float = DEFAULT_INITIAL_DELAY_SECONDS,
    ) -> None:
        self._memory = memory_runtime
        self._event_bus = event_bus
        self._interval = interval_seconds
        self._initial_delay = initial_delay_seconds
        self._task: asyncio.Task | None = None
        self._last_result: dict[str, Any] | None = None

    @property
    def last_result(self) -> dict[str, Any] | None:
        """What the most recent pass did, or None if none has run.

        None means "has not run", which is a different claim from "ran and
        changed nothing" — and the distinction is the whole point of this
        module, so it is not collapsed into an empty dict.
        """
        return self._last_result

    async def run_once(self) -> dict[str, Any]:
        """One pass. Safe to call directly, which is what makes it testable.

        Returns what it did rather than logging and discarding it, so a caller —
        a test, an endpoint, a future Settings panel — can show the user what
        the system decided on their behalf.
        """
        started = time.time()
        decay: dict[str, Any] = {}
        candidates: list[str] = []

        try:
            decay = await self._memory.apply_decay()
        except Exception as exc:
            # A failed decay pass must not stop promotion from being offered,
            # and neither may take the process with it. This runs unattended on
            # a background task; an exception here would be swallowed by the
            # event loop and the maintenance would silently stop forever.
            logger.warning("Spine maintenance: decay failed: %s: %s", type(exc).__name__, exc)
            decay = {"error": f"{type(exc).__name__}: {exc}"}

        try:
            records = await self._memory.promotion_candidates()
            candidates = [r.id for r in records]
        except Exception as exc:
            logger.warning(
                "Spine maintenance: promotion scan failed: %s: %s", type(exc).__name__, exc
            )

        result = {
            "ran_at": started,
            "duration_ms": (time.time() - started) * 1000,
            "decay": decay,
            "promotion_candidates": candidates,
        }
        self._last_result = result

        logger.info(
            "Spine maintenance: forgot %s, decayed %s, boosted %s; "
            "%d fact(s) now eligible for promotion",
            decay.get("forgotten", "?"), decay.get("decayed", "?"),
            decay.get("boosted", "?"), len(candidates),
        )

        if self._event_bus is not None:
            try:
                from core.event_bus import ZaramEvent

                self._event_bus.publish(ZaramEvent(
                    source_runtime="memory",
                    event_type="memory.maintenance",
                    priority="background",
                    data=result,
                ))
            except Exception as exc:  # pragma: no cover - bus shape varies
                logger.debug("Spine maintenance: could not publish: %s", exc)

        return result

    async def _loop(self) -> None:
        await asyncio.sleep(self._initial_delay)
        while True:
            await self.run_once()
            await asyncio.sleep(self._interval)

    def start(self) -> None:
        """Begin the timer. Idempotent — a second call is ignored."""
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "Spine maintenance: first pass in %.0fs, then every %.1fh",
            self._initial_delay, self._interval / 3600,
        )

    async def stop(self) -> None:
        """Cancel the timer and wait for it to actually stop.

        Awaited rather than fire-and-forget: a cancelled task that nobody
        collects logs "Task exception was never retrieved" on shutdown, which
        reads as a crash in a product whose console the user may well be
        watching.
        """
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
