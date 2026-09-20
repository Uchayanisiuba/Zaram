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
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

_STEP: ContextVar[Optional[str]] = ContextVar("zaram_egress_step", default=None)


def current_step() -> Optional[str]:
    """The step running in this context, or ``None``."""
    return _STEP.get()


@contextmanager
def running_step(step_id: str) -> Iterator[None]:
    """Mark everything inside as belonging to `step_id`. Restored on exit,
    including on an exception, so a failed step cannot leave its id on the
    next one's entries."""
    token = _STEP.set(step_id or None)
    try:
        yield
    finally:
        _STEP.reset(token)
