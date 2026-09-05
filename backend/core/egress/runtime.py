"""The process's egress gate.

Call sites need a gate, and threading one through every provider constructor
would mean touching call chains that have nothing to do with egress — which is
how a migration like this stalls half-finished, leaving some paths governed and
others not. A single process-wide gate is the pragmatic shape, for the same
reason logging uses one.

The accessor is deliberately not a bare module global:

- :func:`set_gate` lets the bootstrapper install a gate configured with the
  user's real log path, policy and confirm handler.
- Tests install their own and tear it down, so nothing leaks between them.
- Until something installs one, :func:`get_gate` builds a gate with an **empty
  policy**, which denies everything. An unconfigured Zaram refuses to talk to
  the network rather than defaulting to open — the safe direction, and the one
  Rule 5 requires.
"""

from __future__ import annotations

import os
import threading

from .confirm import PendingConfirmations
from .gate import EgressGate
from .log import EgressLog
from .policy import EgressPolicy

_lock = threading.Lock()
_gate: EgressGate | None = None
_pending: PendingConfirmations | None = None


def default_log_path() -> str:
    """Beside the Spine, but a separate file. See ``log.py`` for why."""
    from core.paths import in_data_dir

    return in_data_dir("egress.db", "ZARAM_EGRESS_LOG")


def default_policy_path() -> str:
    from core.paths import in_data_dir

    return in_data_dir("egress-policy.json", "ZARAM_EGRESS_POLICY")


def get_gate() -> EgressGate:
    """The gate this process sends through. Never ``None``."""
    global _gate
    with _lock:
        if _gate is None:
            _gate = EgressGate(
                EgressLog(default_log_path()),
                EgressPolicy(default_policy_path()),
            )
        return _gate


def set_gate(gate: EgressGate | None) -> None:
    """Install the process gate. ``None`` resets to the default-deny gate."""
    global _gate
    with _lock:
        _gate = gate


def get_pending() -> PendingConfirmations:
    """The questions this process is waiting on an answer for.

    One store, for the same reason there is one gate: the thread that blocks
    inside :meth:`EgressGate.check` and the HTTP handler that releases it are in
    different call stacks and must be looking at the same dictionary. A second
    instance anywhere means a dialog that answers a question nobody asked, while
    the real one times out and denies.

    Building it on first use rather than at import keeps it out of processes
    that never send anything — a test suite, a one-shot script — where a
    120-second timeout on a thread nothing will answer is a hang with no cause
    the reader can see.
    """
    global _pending
    with _lock:
        if _pending is None:
            _pending = PendingConfirmations()
        return _pending


def set_pending(pending: PendingConfirmations | None) -> None:
    """Install the process confirmation store. ``None`` resets it.

    Tests install one with a short timeout; without this they would inherit the
    two-minute default and a single unanswered question would stall the suite.
    """
    global _pending
    with _lock:
        _pending = pending
