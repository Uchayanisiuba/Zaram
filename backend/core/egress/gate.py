"""The egress gate — the one place a request can leave this machine.

Rules 3 and 5 of the project contract say that everything leaving is logged and
that nothing leaves without an explicit per-source policy. Those are claims about
what the software *cannot* do, and a claim of that shape cannot be kept by
convention. Before this module existed there were nine independent outbound call
sites across three HTTP libraries; each one was individually correct and
collectively they made Rule 3 unenforceable, because the tenth would have been
written by someone who had not read it.

So the gate is not a logging helper that call sites are asked to use. It is the
transport. Call sites no longer own an HTTP client; they own a reference to this,
and it decides whether their request happens at all.

Classification comes first
--------------------------
Not everything that opens a socket is egress. Ollama runs on ``localhost``, and
inference on your own machine is precisely the thing Zaram exists to make
possible — logging it as though it had left would make the log useless by
drowning the real events. The gate resolves the destination and treats loopback
as local: no policy, no log, straight through. Everything else is egress and
faces the full path.

That distinction is made here, once, from the URL — not asserted by the caller.
A caller that could declare its own request local could exempt itself from
Rule 3, which would put the invariant back in the realm of convention.

Order of operations
-------------------
For anything not loopback:

1. Ask the policy what should happen to this host. Unknown host → deny.
2. If the policy says *ask*, show the user the literal text about to leave and
   wait. The contract calls confirm-before-send the primary path, so it is the
   normal case rather than a strict mode.
3. Log the decision **before** the request is made, never after. A crash between
   sending and logging would otherwise produce exactly the silent egress the log
   exists to make impossible.
4. Only then perform the request.

A denied or cancelled attempt is logged too. An attempt is as worth seeing as a
success, and a log that only records what succeeded cannot show you what your
software tried to do.
"""

from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Callable

from .log import EgressLog
from .policy import EgressPolicy, Mode

#: Hostnames that never leave the machine. ``localhost`` and the reserved
#: ``.localhost`` TLD are loopback by RFC 6761.
_LOOPBACK_NAMES = {"localhost", ""}


def is_local(url: str) -> bool:
    """True when ``url`` cannot leave this machine.

    Addresses are parsed as addresses, never matched as strings. A prefix test
    like ``host.startswith("127.")`` looks equivalent and is not:
    ``127.0.0.1.evil.com`` passes it, which would let any attacker-registered
    domain declare itself loopback and skip the gate entirely. Whether something
    is an address is a question for the parser.

    Conservative in both directions — anything unparseable is treated as *not*
    local, so a malformed URL faces the policy rather than bypassing it.
    """
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except ValueError:
        return False

    if host in _LOOPBACK_NAMES or host.endswith(".localhost"):
        return True

    try:
        # Covers all of 127.0.0.0/8 and ::1, and nothing that merely looks like
        # them. A hostname that is not an IP literal raises here.
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class EgressDenied(Exception):
    """Raised when a request was not permitted to leave.

    Carries the logged entry id so the refusal can be traced to its record —
    a user who is told "that was blocked" should be able to find the entry.
    """

    def __init__(self, message: str, host: str, entry_id: str | None = None):
        super().__init__(message)
        self.host = host
        self.entry_id = entry_id


@dataclass
class EgressRequest:
    """What is about to leave, in the form the user will be shown."""

    host: str
    method: str
    url: str
    body: str | None
    source: str
    #: Why the confirm hook said no, when it did not say no on the user's behalf.
    #:
    #: The log's default wording for a refusal is "you chose not to send this",
    #: which is true when a person clicked the button and false in every other
    #: way a confirmation can fail. A hook that could not reach anyone sets this
    #: instead, so the record says what actually happened. An append-only,
    #: tamper-evident log that confidently attributes a decision to a user who
    #: never saw the question is worse than one that admits it does not know.
    refusal_reason: str | None = None

    @property
    def literal_text(self) -> str:
        """Exactly what goes on the wire, for the confirm dialog and the log."""
        return self.url if not self.body else f"{self.url}\n\n{self.body}"

    @property
    def byte_count(self) -> int:
        return len(self.url.encode("utf-8")) + (
            len(self.body.encode("utf-8")) if self.body else 0
        )


#: Called when policy says *ask*. Receives what is about to leave and returns
#: True to send. The default refuses: if nothing has been wired up to ask the
#: user, the honest interpretation of "ask the user" is that the answer is no.
ConfirmFn = Callable[[EgressRequest], bool]


def _refuse_by_default(_: EgressRequest) -> bool:
    return False


class EgressGate:
    """The chokepoint. Hold one of these; do not open sockets anywhere else."""

    def __init__(
        self,
        log: EgressLog,
        policy: EgressPolicy,
        confirm: ConfirmFn | None = None,
        *,
        user_agent: str = "Zaram/1.0",
    ):
        self._log = log
        self._policy = policy
        self._confirm = confirm or _refuse_by_default
        self._user_agent = user_agent

    @property
    def log(self) -> EgressLog:
        return self._log

    @property
    def policy(self) -> EgressPolicy:
        return self._policy

    def set_confirm(self, confirm: ConfirmFn) -> None:
        """Wire the confirm dialog once the UI transport exists."""
        self._confirm = confirm

    # ----------------------------------------------------------------- check

    def check(self, url: str, *, method: str = "GET", body: str | None = None,
              source: str = "unknown") -> EgressRequest | None:
        """Decide and log, without performing the request.

        Returns the approved :class:`EgressRequest`, or ``None`` when the
        destination is loopback and no decision was needed. Raises
        :class:`EgressDenied` if it may not go.

        Separated from :meth:`request` so async call sites can get a verdict
        here and then use their own client to send. The verdict is still made
        and logged in one place, which is the property that matters.
        """
        if is_local(url):
            return None

        host = (urllib.parse.urlparse(url).hostname or "").lower()
        req = EgressRequest(host=host, method=method.upper(), url=url,
                            body=body, source=source)
        decision = self._policy.decide(host)

        if decision.mode is Mode.DENY:
            entry = self._record(req, "denied", decision.reason)
            raise EgressDenied(
                f"Zaram blocked a request to {host}: {decision.reason}.",
                host=host,
                entry_id=entry.id,
            )

        if decision.mode is Mode.ASK:
            if not self._confirm(req):
                entry = self._record(
                    req,
                    "cancelled",
                    req.refusal_reason or "you chose not to send this",
                )
                raise EgressDenied(
                    f"The request to {host} was cancelled.",
                    host=host,
                    entry_id=entry.id,
                )
            # Logged before the send, never after.
            self._record(req, "allowed", "you confirmed this request")
            return req

        self._record(req, "allowed", decision.reason)
        return req

    def resolve(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        method: str = "GET",
        body: str | None = None,
        source: str = "unknown",
    ) -> str:
        """Fold ``params`` into the URL, check it, and return the final URL.

        For async call sites, which have their own client and only need the
        verdict. They must then send *this* URL rather than passing ``params``
        separately — otherwise the client assembles a different URL from the one
        that was checked and logged, and the log would record a request that
        never happened alongside one that did.

        Raises :class:`EgressDenied` if it may not go. Returns the URL unchanged
        for loopback destinations, which need no decision.
        """
        final = url
        if params:
            encoded = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            final = f"{url}{'&' if urllib.parse.urlparse(url).query else '?'}{encoded}"
        self.check(final, method=method, body=body, source=source)
        return final

    def _record(self, req: EgressRequest, decision: str, reason: str):
        return self._log.append(
            host=req.host,
            method=req.method,
            url=req.url,
            body=req.body,
            decision=decision,
            reason=reason,
            source=req.source,
        )

    # --------------------------------------------------------------- perform

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        body: bytes | str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        source: str = "unknown",
    ) -> bytes:
        """Check, log, and send. Returns the response body.

        The synchronous path, used by every urllib and requests call site.
        """
        body_text: str | None = None
        if body is not None:
            body_text = body.decode("utf-8", "replace") if isinstance(body, bytes) else body

        # Same reasoning as `stream_lines`: the confirmation may have rewritten
        # the body, and what is sent has to be what was logged and agreed to.
        approved = self.check(url, method=method, body=body_text, source=source)
        edited = approved is not None and approved.body != body_text

        if edited:
            payload = approved.body.encode("utf-8") if approved.body else None
        else:
            # Unedited bodies keep their original bytes. Re-encoding from the
            # logged text would round-trip a binary payload through a lossy
            # `decode(..., "replace")` and corrupt it — the log is allowed to
            # hold a best-effort rendering of bytes; the wire is not.
            payload = body if isinstance(body, bytes) else (
                body.encode("utf-8") if body else None
            )
        req = urllib.request.Request(
            url,
            data=payload,
            method=method.upper(),
            headers={"User-Agent": self._user_agent, **(headers or {})},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    def get_json(self, url: str, *, timeout: float = 10.0, source: str = "unknown",
                 headers: dict[str, str] | None = None) -> Any:
        """The shape almost every existing call site actually wanted."""
        return json.loads(self.request(url, timeout=timeout, source=source,
                                       headers=headers))

    def stream_lines(
        self,
        url: str,
        *,
        method: str = "POST",
        body: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 120.0,
        source: str = "unknown",
    ) -> Iterator[bytes]:
        """Check, log, and stream the response one line at a time.

        Added for cloud generation, which is the first outbound call whose
        response must be consumed *as it arrives* — a chat reply that only
        appears once the model has finished is a worse product than a local one,
        and buffering it here would undo the reason for going to the cloud.

        It exists on the gate rather than in the engine because of what
        `test_egress_chokepoint.py` enforces: no shipped module opens its own
        outbound connection. The engine could have called `check` and then used
        its own client — `check` is deliberately separable and async call sites
        do exactly that — but doing so in a *synchronous* path that had no such
        constraint would have traded the invariant for convenience, and the
        chokepoint scan is right to refuse it. The gate is the transport; this
        is the transport growing the one shape it was missing.

        **Headers are sent and not logged.** That asymmetry is deliberate and
        is what makes this usable for an authenticated API: the log is
        append-only and tamper-evident, so writing a bearer token into it would
        create a credential the user cannot delete and therefore cannot rotate
        away from. What the log records is the destination and the body — what
        left and where it went, which is the question it exists to answer.

        Raises :class:`EgressDenied` before opening a socket if policy or the
        user says no, and lets `urllib.error.HTTPError` through so the caller
        can read the status and explain it. An `HTTPError` is itself a readable
        response, which is what makes a provider's "no credit left" reachable
        rather than becoming a bare 402.
        """
        # Checked first, and the body read back *afterwards*. A confirmation
        # may rewrite it — M10's dialog lets the user remove a recalled fact
        # before sending — and the gate logs the edited text, so encoding
        # before the check would send bytes that differ from the ones logged
        # and approved. That gap is worse than not asking, because it looks
        # like consent.
        approved = self.check(url, method=method, body=body, source=source)
        final_body = approved.body if approved is not None else body
        body_bytes = final_body.encode("utf-8") if final_body is not None else None

        req = urllib.request.Request(
            url,
            data=body_bytes,
            method=method.upper(),
            headers={"User-Agent": self._user_agent, **(headers or {})},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for line in resp:
                yield line
