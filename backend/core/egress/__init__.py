"""Egress — the single governed path off this machine.

Import the gate from here rather than reaching into the submodules, so that the
set of things a call site can do stays small and obvious.

    from core.egress import EgressGate, EgressDenied

Rules 3 and 5 of the project contract live in this package. See ``gate.py`` for
why the gate is the transport rather than a helper the call sites are asked to
remember.
"""

from .confirm import PendingConfirmations
from .gate import EgressDenied, EgressGate, EgressRequest, is_local
from .log import EgressEntry, EgressLog, TamperDetected
from .policy import DEFAULT_DECISION, Decision, EgressPolicy, Mode
from .runtime import (
    default_log_path,
    default_policy_path,
    get_gate,
    get_pending,
    set_gate,
    set_pending,
)

__all__ = [
    "EgressGate",
    "EgressDenied",
    "EgressRequest",
    "PendingConfirmations",
    "is_local",
    "EgressLog",
    "EgressEntry",
    "TamperDetected",
    "EgressPolicy",
    "Mode",
    "Decision",
    "DEFAULT_DECISION",
    "get_gate",
    "set_gate",
    "get_pending",
    "set_pending",
    "default_log_path",
    "default_policy_path",
]
