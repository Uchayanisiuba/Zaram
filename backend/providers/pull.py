"""Fetching the model the first-run screen offered, and saying what it costs.

`core/readiness.py` names a model and its size; this is what happens when the
user presses the button. The two must agree, so **the model is resolved here
rather than sent by the caller**: the same manifest lookup, against the same
measured budget, produces the same answer, and a name arriving in a request
body could name something else entirely.

**The download is recorded before it starts, not after it succeeds.** Ollama is
on 127.0.0.1 and the request that reaches it carries a model name — but Ollama
then pulls gigabytes from the registry on the user's behalf, over a socket this
process does not own and `EgressGate` cannot see. Rule 3 says every byte that
leaves is logged, including bytes sent by tools rather than by chat, and a
transfer logged only on success is a log that misses every interrupted one. So
the entry goes in first, naming the destination and the expected size.

**It is recorded rather than gated, and that is rule 7j.** Pressing a button
that reads *"Download a model to start with — 4.7 GB download"* is the explicit
per-item decision rule 5 asks for; a confirmation dialog on top of it would ask
the same question twice, which reads as the product being broken. The log and
the Activity view carry it afterwards.

Nothing here decides *whether* to offer. That is `diagnose`'s job, and this
module is only reached by a person who has already chosen.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, Optional

from core.readiness import model_to_offer

logger = logging.getLogger(__name__)

__all__ = ["REGISTRY_HOST", "PullUnavailable", "stream_pull"]

#: Where Ollama fetches from. Named here rather than in the adapter because
#: `providers/discoverers/ollama.py` is exempt from the egress chokepoint on
#: the grounds that it only ever talks to this machine, and a remote host in it
#: would make that exemption a lie — `test_egress_chokepoint.py` asserts as
#: much, by scanning the module for exactly this.
REGISTRY_HOST = "registry.ollama.ai"

#: What the egress entry says happened. A download rather than a request: the
#: bytes come *in*, and `byte_count` on the entry counts what was sent, so the
#: expected size travels in `meta` where it cannot be mistaken for a
#: measurement of what left.
_REASON = (
    "the user chose to download a local model; Ollama fetches it from the "
    "registry on this machine's behalf"
)


class PullUnavailable(RuntimeError):
    """Ollama could not be asked. Raised before anything is logged."""


def stream_pull(
    *,
    budget_bytes: Optional[int],
    adapter: Any,
    log: Any = None,
    source: str = "first-run",
) -> Iterator[Dict[str, Any]]:
    """Pull the recommended model, yielding progress a screen can render.

    Events are plain: ``stage`` in a person's words, ``completed`` and
    ``total`` in bytes when the wire carries them, and exactly one terminal
    event — ``{"done": True}`` or ``{"error": "..."}``. **No model name is
    emitted**, for the same reason the offer's label does not carry one: the
    target user is not technical, and a progress line reading `qwen2.5:7b` is a
    filename they did not choose.

    ``log`` is the egress log, or ``None`` in a test that is not asserting
    about it. Passed in rather than reached for, so this stays decidable
    without a process-wide gate.
    """
    recommended = model_to_offer(budget_bytes)

    if log is not None:
        # Before the first byte. See the module docstring: a record written
        # after the fact is a record of the downloads that finished.
        log.append(
            host=REGISTRY_HOST,
            method="GET",
            url=f"https://{REGISTRY_HOST}",
            body=recommended.name,
            decision="allowed",
            reason=_REASON,
            source=source,
            meta={"expected_bytes": recommended.size_bytes, "direction": "download"},
        )

    try:
        events = adapter.pull_model(recommended.name)
    except Exception as exc:  # pragma: no cover - exercised through the route
        raise PullUnavailable(str(exc)) from exc

    # No `yield` in a `finally` here, deliberately: the browser can close this
    # stream at any moment, which throws `GeneratorExit` in, and a generator
    # that yields on the way out turns a user closing a tab into a RuntimeError
    # in the log.
    try:
        for event in events:
            error = event.get("error")
            if error:
                yield {"error": str(error)}
                return

            status = str(event.get("status") or "")
            if status.lower() == "success":
                # The terminal event is written once, below, so that a stream
                # which ends without one is still ended by this function.
                continue

            out: Dict[str, Any] = {"stage": _stage_for(status)}
            for field in ("completed", "total"):
                value = event.get(field)
                if isinstance(value, int):
                    out[field] = value
            yield out
    except Exception as exc:
        logger.warning("model pull failed: %s", exc)
        yield {"error": str(exc)}
        return

    yield {"done": True}


#: Ollama's own words, which are for a terminal: *"pulling 8934d96d3f08"* names
#: a digest, and a digest on a first-run screen is noise a person cannot act
#: on. Mapped rather than passed through, and anything unrecognised becomes the
#: honest general case rather than a raw status string.
_STAGES = (
    ("pulling manifest", "Looking it up"),
    ("pulling", "Downloading"),
    ("verifying", "Checking what arrived"),
    ("writing", "Saving it"),
    ("removing", "Tidying up"),
)


def _stage_for(status: str) -> str:
    lowered = status.lower()
    for prefix, phrase in _STAGES:
        if lowered.startswith(prefix):
            return phrase
    return "Working"
