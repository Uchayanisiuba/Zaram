"""Which step of which reply is running, so an egress entry can say so.

`docs/PLAN.md` C2, 19 September 2026. The working pane opens from a row and
shows what that step sent off the machine — which needs the log to know
which step wrote each entry. Threading an id through every gate call site
would touch a dozen modules; a `ContextVar` set by the engine around each
step and each tool call, and read at the one place an entry is recorded,
touches two. An entry written outside any step (a search the person ran from
Knowledge, a model listing at boot) carries nothing, and the pane shows
nothing for it rather than guessing.

The value is a plain string — ``"<correlation_id>:<index>"`` for a plan step,
``"<correlation_id>:call:<n>"`` for the n-th tool call of a reply — and it is
stamped into ``meta["step_id"]``, which the hash already covers, so it is as
tamper-evident as the rest of the record.

**The mark has to survive a `yield`, and a `ContextVar` alone does not.**
Found on screen, 20 September 2026, on the first reply after this shipped:
the reply was empty and the text on it was `Token ... was created in a
different Context`. `ChatRouter` drives the engine's generator with
Starlette's `iterate_in_threadpool`, which runs *each* `next()` in a pooled
thread under a fresh copy of the request's context. So a value set before a
`yield` is gone after it, and `reset(token)` on the far side of one raises.
The fakes in the suite iterate in one context and could not see it.

So the id lives on a `StepHolder` that belongs to the reply — a plain object
the generator's frame keeps hold of across yields — and `carried()` wraps the
engine's generator to re-apply the holder's value to the `ContextVar` at the
start of every `next()`. Inside one `next()` the var is what the gate reads;
between two of them the holder is what remembers.
"""

from __future__ import annotations

import functools
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator, Optional

_STEP: ContextVar[Optional[str]] = ContextVar("zaram_egress_step", default=None)


class StepHolder:
    """The reply's own memory of which step is running. One per generator,
    created by `carried`; never shared between replies."""

    __slots__ = ("step_id",)

    def __init__(self) -> None:
        self.step_id: Optional[str] = None


_HOLDER: ContextVar[Optional[StepHolder]] = ContextVar("zaram_egress_step_holder", default=None)


def current_step() -> Optional[str]:
    """The step running in this context, or ``None``."""
    return _STEP.get()


@contextmanager
def running_step(step_id: str) -> Iterator[None]:
    """Mark everything inside as belonging to `step_id`. Restored on exit,
    including on an exception, so a failed step cannot leave its id on the
    next one's entries.

    Restores by *setting the previous value*, never by `reset(token)`: the
    exit may run in a different context copy from the entry (see the module
    docstring), and a token from another context is refused."""
    holder = _HOLDER.get()
    previous = holder.step_id if holder is not None else _STEP.get()
    value = step_id or None
    if holder is not None:
        holder.step_id = value
    _STEP.set(value)
    try:
        yield
    finally:
        if holder is not None:
            holder.step_id = previous
        _STEP.set(previous)


def carried(events: Iterator[Any]) -> Iterator[Any]:
    """Drive `events` so that its step mark survives however it is iterated.

    Each `next()` re-applies the holder's current id to the context it runs
    in, then hands over. Closing the wrapper closes the inner generator, so an
    aborted stream still runs the engine's own tidy-up."""
    holder = StepHolder()
    try:
        while True:
            holder_token = _HOLDER.set(holder)
            step_token = _STEP.set(holder.step_id)
            try:
                item = next(events)
            except StopIteration:
                return
            finally:
                # Same context as the two `set`s above, so `reset` is safe here.
                _STEP.reset(step_token)
                _HOLDER.reset(holder_token)
            yield item
    finally:
        close = getattr(events, "close", None)
        if close is not None:
            close()


def carries_step(fn: Callable[..., Iterator[Any]]) -> Callable[..., Iterator[Any]]:
    """Decorator form of `carried`, for the engine's generator methods."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Iterator[Any]:
        return carried(fn(*args, **kwargs))

    return wrapper
