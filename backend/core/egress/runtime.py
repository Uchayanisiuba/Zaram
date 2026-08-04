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

from .gate import EgressGate
from .log import EgressLog
from .policy import EgressPolicy

_lock = threading.Lock()
_gate: EgressGate | None = None


def default_log_path() -> str:
    """Beside the Spine, but a separate file. See ``log.py`` for why."""
    return os.environ.get(
        "ZARAM_EGRESS_LOG",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "egress.db"),
    )


def default_policy_path() -> str:
    return os.environ.get(
        "ZARAM_EGRESS_POLICY",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "egress-policy.json"),
    )


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
