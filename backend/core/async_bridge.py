"""Run coroutines from synchronous code, safely.

Several kernel components are synchronous generators that need to call async
runtime methods.  ``asyncio.run()`` cannot be used for this: when the caller is
already executing on a running event loop — which is always the case under
FastAPI — it raises::

    RuntimeError: asyncio.run() cannot be called from a running event loop

``run_sync`` handles both cases.  With no loop running it delegates to
``asyncio.run``.  With a loop already running it submits the coroutine to a
single long-lived background loop and blocks until it completes.

The background loop is created once and reused.  Creating a thread per call is
correct but far too slow when these helpers are hit in a loop, which they are
during retrieval and health checks.
"""
from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None
_loop_lock = threading.Lock()


def _background_loop() -> asyncio.AbstractEventLoop:
    """Return the shared background loop, starting it on first use."""
    global _loop
    if _loop is not None and not _loop.is_closed():
        return _loop
    with _loop_lock:
        if _loop is not None and not _loop.is_closed():
            return _loop
        loop = asyncio.new_event_loop()
        thread = threading.Thread(
            target=loop.run_forever,
            name="zaram-async-bridge",
            daemon=True,
        )
        thread.start()
        _loop = loop
        return _loop


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """Execute ``coro`` to completion and return its result.

    Safe to call whether or not an event loop is already running on this
    thread.  Propagates any exception raised inside the coroutine.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No loop on this thread — the simple path.
        return asyncio.run(coro)

    # A loop is already running here, so the coroutine has to go elsewhere.
    # Blocks the calling thread (the event loop thread) until it finishes,
    # which is acceptable for the short calls this is used for.
    #
    # **In the caller's context.** `run_coroutine_threadsafe` would create
    # the task inside the background loop's own context, so a `ContextVar`
    # set by the caller — which step of which reply is running, for the
    # egress log (`core/egress/step_context.py`) — would be invisible to the
    # coroutine. The task is created from a callback scheduled *with* the
    # caller's copied context, and a task copies the context it is created
    # in, so the coroutine sees what the caller saw.
    import concurrent.futures
    import contextvars

    loop = _background_loop()
    done: concurrent.futures.Future = concurrent.futures.Future()

    def _start() -> None:
        task = loop.create_task(coro)

        def _settle(t: "asyncio.Task[T]") -> None:
            if t.cancelled():
                done.cancel()
            elif t.exception() is not None:
                done.set_exception(t.exception())  # type: ignore[arg-type]
            else:
                done.set_result(t.result())

        task.add_done_callback(_settle)

    loop.call_soon_threadsafe(_start, context=contextvars.copy_context())
    return done.result()


def is_loop_running() -> bool:
    """True when the calling thread is inside a running event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def shutdown() -> None:
    """Stop the background loop. Intended for test teardown."""
    global _loop
    with _loop_lock:
        if _loop is not None and not _loop.is_closed():
            _loop.call_soon_threadsafe(_loop.stop)
        _loop = None
