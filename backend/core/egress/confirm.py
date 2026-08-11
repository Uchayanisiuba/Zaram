"""Asking a person a question from inside a synchronous gate.

The gate's confirm hook is a plain callable that returns True or False, and
that shape is right: it is called from the middle of `check`, before anything
is logged or sent, and it must be impossible to fall through. But the person
who answers it is in a browser, several layers and one HTTP request away.

This is the bridge. `ask` blocks the calling thread on an event; the pending
request is visible to `/egress/pending`; a decision from the interface releases
it. The chat path already runs its generator in a worker thread, so blocking
there costs one thread and no responsiveness.

Three properties are deliberate.

**A timeout denies.** Not "allows after a while" — a dialog nobody answered is
a question nobody said yes to, and the whole point of confirm-before-send is
that silence is not consent. It also means a browser that closed mid-request
cannot leave a thread parked forever holding the user's documents in memory.

**The edit is written back onto the request.** `EgressRequest` is mutable and
the gate logs *after* the confirmation returns, so a body rewritten here is the
body that gets logged and the body that gets sent. Rule 4 is the reason this
has to be an edit rather than an all-or-nothing choice: the user can correct or
remove any stored fact, and a dialog that only offered "send everything or send
nothing" would make the useful case — *send this, but not my day rate* —
impossible to express.

**One decision per request, and it cannot be re-answered.** The entry is
removed as it is decided, so a duplicate POST from a double-click or a retry
finds nothing and says so, rather than approving a second send of text that has
already gone.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .gate import EgressRequest

#: How long a question waits before it is treated as unanswered. Long enough
#: for someone to read a paragraph of their own text and decide, short enough
#: that a closed tab does not park a thread for the life of the process.
DEFAULT_TIMEOUT = 120.0


@dataclass
class _Pending:
    id: str
    request: EgressRequest
    created_at: float
    event: threading.Event = field(default_factory=threading.Event)
    approved: bool = False
    #: The body the user approved, when they edited it. `None` means unchanged.
    edited_body: Optional[str] = None


class PendingConfirmations:
    """Holds questions waiting for an answer, and releases them when it comes."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout
        self._lock = threading.Lock()
        self._waiting: Dict[str, _Pending] = {}

    # ------------------------------------------------------------- gate side

    def ask(self, request: EgressRequest) -> bool:
        """The gate's confirm hook. **Blocks** until answered, or denies.

        Returns True only on an explicit approval. Every other outcome — a
        refusal, a timeout, a shutdown — is False, because this function
        answers "may this leave?" and the safe reading of every ambiguity is
        no.
        """
        pending = _Pending(
            id=uuid.uuid4().hex[:12], request=request, created_at=time.time()
        )
        with self._lock:
            self._waiting[pending.id] = pending

        answered = pending.event.wait(self._timeout)

        with self._lock:
            self._waiting.pop(pending.id, None)

        if not answered:
            return False
        if not pending.approved:
            return False

        if pending.edited_body is not None:
            # Written back onto the request the gate is holding, so the edited
            # text is what gets logged and what gets sent. The gate has not
            # recorded anything yet — this returns into the middle of `check`.
            request.body = pending.edited_body
        return True

    # -------------------------------------------------------- interface side

    def pending(self) -> List[Dict[str, Any]]:
        """Everything currently waiting, oldest first.

        A list rather than a single item because more than one thing can be in
        flight — a chat reply and a tool call, say — and a UI that assumed one
        would silently drop the second.
        """
        with self._lock:
            items = sorted(self._waiting.values(), key=lambda p: p.created_at)
            return [self._describe(p) for p in items]

    def get(self, confirmation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            found = self._waiting.get(confirmation_id)
            return self._describe(found) if found else None

    def decide(
        self,
        confirmation_id: str,
        *,
        approved: bool,
        body: Optional[str] = None,
    ) -> bool:
        """Answer a waiting question. False when there was nothing to answer.

        `body` is the edited outbound text, or `None` to send it unchanged.
        Ignored when `approved` is False: there is no such thing as editing
        something you are not sending, and honouring it would write a body to
        the log that no one ever agreed to send.
        """
        with self._lock:
            pending = self._waiting.get(confirmation_id)
            if pending is None:
                return False
            pending.approved = approved
            pending.edited_body = body if approved else None
            pending.event.set()
        return True

    def cancel_all(self) -> int:
        """Release every waiter as denied. Returns how many.

        For shutdown. A thread parked on an event nobody will ever set is a
        process that will not exit, and the correct answer to "may this leave?"
        while the machine is closing down is no.
        """
        with self._lock:
            waiting = list(self._waiting.values())
            for pending in waiting:
                pending.approved = False
                pending.event.set()
            self._waiting.clear()
        return len(waiting)

    @staticmethod
    def _describe(pending: _Pending) -> Dict[str, Any]:
        """What the dialog renders.

        The **literal text** is here rather than a summary, because that is the
        whole feature: the contract calls for showing what actually leaves, and
        a paraphrase is a claim about the text rather than the text.
        """
        request = pending.request
        return {
            "id": pending.id,
            "host": request.host,
            "method": request.method,
            "url": request.url,
            "body": request.body,
            "literal_text": request.literal_text,
            "byte_count": request.byte_count,
            "source": request.source,
            "created_at": pending.created_at,
        }
