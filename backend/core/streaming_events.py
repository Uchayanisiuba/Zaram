# backend/core/streaming_events.py
"""Execution Tokens — structured streaming events for the kernel.

StreamEvent is the kernel's execution token format.  Each event
represents a discrete unit of output in the streaming response:
tokens, status changes, source attributions, errors, and completion.

The format is JSON-serializable for SSE transport and includes
sequence numbers for ordered reconstruction.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum

from core.contracts import ExecutionToken


class EventType(str, Enum):
    START = "start"
    TOKEN = "token"
    #: The model's working, not its answer.
    #:
    #: A separate event rather than a flag on TOKEN because the two have
    #: different destinations: TOKEN accumulates into `streamingText`, which is
    #: what gets committed to the transcript and what `pushSpeech` reads. Before
    #: this existed, a reasoning model's `<think>` block *was* the answer as far
    #: as this backend was concerned — rendered as the reply and read aloud by
    #: Kokoro. Keeping it off that channel is the fix; showing it is the feature.
    REASONING = "reasoning"
    STATUS = "status"
    SOURCE = "source"
    ERROR = "error"
    DONE = "done"
    STEP_START = "step_start"
    STEP_COMPLETE = "step_complete"
    PLAN_START = "plan_start"
    PLAN_COMPLETE = "plan_complete"
    RETRY = "retry"
    CANCEL = "cancel"
    #: A file Zaram made. Rendered as a card in the conversation and, from the
    #: same record, as a row in Work.
    ARTIFACT = "artifact"
    #: A model has to be loaded before this reply can start.
    #:
    #: Emitted *before* generation, not while it stalls. CLAUDE.md requires a
    #: route that forces a swap to be visible in the orb's state, and a
    #: indicator that appears once the machine has already gone quiet is not
    #: visibility — the user has spent the seconds and concluded the product
    #: hung. Distinct from STATUS because it carries what is being loaded and
    #: what it displaces, which is the evidence a user needs to go and change
    #: the assignment in Settings.
    MODEL_LOAD = "model_load"
    #: Something the user needs to know that is not part of the answer.
    #:
    #: Distinct from TOKEN because it must not be mistaken for the model
    #: speaking, and distinct from ERROR because nothing failed in this
    #: exchange. The first use is ingest: a file that gave nothing back has to
    #: be *mentioned in the conversation the first time it matters*, since
    #: Knowledge showing it only helps someone who opens Knowledge.
    NOTICE = "notice"
    #: Which model is about to answer, and where it runs.
    #:
    #: `CLAUDE.md`: "Every reply names the model that answered and why", and
    #: "Never hide the model" — the memory holding while the model changes
    #: underneath it is the product's best demonstration, and a reply that
    #: names nothing forfeits it. It is also the only way a user can tell a
    #: cloud answer from a local one: the maintainer connected OpenRouter and
    #: had no way to know whether anything ever reached it.
    #:
    #: Emitted *before* the first token, for the reason MODEL_LOAD is: an
    #: attribution that arrives after the answer is a footnote, and the
    #: question "where did this come from" is asked while reading, not after.
    ANSWERING = "answering"


@dataclass
class StreamEvent:
    """A single event in the streaming response.

    Events are JSON-serialized via ``to_ipc()`` for SSE transport.
    Each event carries a sequence number for ordered reconstruction
    and a timestamp for latency measurement.
    """
    type: EventType
    data: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    seq: int = 0
    correlation_id: str = ""

    def to_ipc(self) -> str:
        """Serialize to an SSE-compatible JSON line."""
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
            "ts": self.ts,
            "seq": self.seq,
            "correlation_id": self.correlation_id,
        })

    @staticmethod
    def token(content: str, seq: int = 0, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.TOKEN,
            data={"content": content},
            seq=seq,
            correlation_id=correlation_id,
        )

    @staticmethod
    def reasoning(content: str, seq: int = 0, correlation_id: str = "") -> StreamEvent:
        """One piece of the model's working, tags already removed."""
        return StreamEvent(
            type=EventType.REASONING,
            data={"content": content},
            seq=seq,
            correlation_id=correlation_id,
        )

    @staticmethod
    def status(state: str, capability_id: str | None = None, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.STATUS,
            data={
                "state": state,
                "capability_id": capability_id,
            },
            correlation_id=correlation_id,
        )

    @staticmethod
    def source(
        kind: str,
        url: str | None = None,
        title: str | None = None,
        *,
        excerpt: str | None = None,
        relevance: float | None = None,
        cited: bool = True,
        number: int | None = None,
        egress_id: str | None = None,
        bytes_sent: int | None = None,
        origin: str | None = None,
        record_id: str | None = None,
        correlation_id: str = "",
    ) -> StreamEvent:
        """One source behind an answer.

        `kind` is the distinction the whole citation UI rests on and no
        competitor has to make: `memory` and `document` stayed on the machine,
        `web` means bytes left and there is an egress log row for it. The
        frontend must never infer a kind — inventing one client-side would be
        the fabrication rule in a different file.

        Keyword-only past `title` on purpose. Five optional strings in a row is
        how `excerpt` ends up in the `url` slot at one call site and nowhere
        else, and a citation pointing at the wrong thing is worse than one that
        is missing.

        - `excerpt` — the passage that actually bore on the answer, which is
          what makes a citation checkable rather than decorative.
        - `relevance` — the similarity, never the ranking blend. Sent so the
          panel can show the gap between what was recalled and what was cited.
        - `cited` — whether it cleared `MIN_CITATION_SCORE`. False means
          recalled but not cited: it belongs in the panel's quieter section, not
          as an inline chip. Sent rather than dropped, so nothing is hidden.
        - `number` — the stable citation number. Assigned once, server-side, and
          shared by the inline chip and the panel card. Numbering client-side
          would drift the moment a chip is filtered from one view and not the
          other. `None` for uncited sources, which carry no number by design.
        - `egress_id` / `bytes_sent` — the egress log row this source came from.
          Present only for `web`, and the reason the citation and the egress log
          are the same object viewed twice.
        """
        return StreamEvent(
            type=EventType.SOURCE,
            data={
                "kind": kind,
                "url": url,
                "title": title,
                "excerpt": excerpt,
                "relevance": relevance,
                "cited": cited,
                "number": number,
                "egress_id": egress_id,
                "bytes_sent": bytes_sent,
                "origin": origin,
                "record_id": record_id,
            },
            correlation_id=correlation_id,
        )

    @staticmethod
    def model_load(
        kind: str,
        model: str,
        evicts: list[str] | None = None,
        correlation_id: str = "",
    ) -> StreamEvent:
        """A model must be loaded before this reply can begin.

        `kind` is `load` — a cold start with room to spare — or `swap`, where
        something resident has to be evicted first. They are separate words
        because the remedy differs: a cold start passes on its own, while a
        swap recurring every other message is a model-assignment problem the
        user can act on. Collapsing them would make `swapping` a synonym for
        "slow" and cost the distinction its meaning.

        Never emitted speculatively. The pre-flight returns `None` whenever it
        cannot tell, and no event is sent for that — announcing a swap that
        does not happen trains the user to ignore the indicator.
        """
        return StreamEvent(
            type=EventType.MODEL_LOAD,
            data={"kind": kind, "model": model, "evicts": list(evicts or [])},
            correlation_id=correlation_id,
        )

    @staticmethod
    def answering(
        model: str | None,
        locality: str | None,
        *,
        chosen_by: str | None = None,
        provider: str | None = None,
        correlation_id: str = "",
    ) -> StreamEvent:
        """Which model is answering, where it runs, and who picked it.

        **Three fields that must not be collapsed into one sentence here.** The
        backend reports; the interface phrases. A pre-composed string would put
        wording in the layer that cannot be styled, cannot be translated, and
        cannot show locality as anything but words — and locality is the field
        a user checks before trusting the rest.

        `locality` is three-valued and ``None`` is a real answer, carried from
        `ModelsRuntime.locality_of` rather than defaulted. Saying "on this
        machine" about a model whose record could not be resolved would be a
        confident false claim on the one thing the product asks to be trusted
        for; the interface renders nothing for a ``None`` instead.

        `chosen_by` is `request`, `settings`, `task` or `zaram` — the honest
        version of `CLAUDE.md`'s "routed to qwen2.5-coder — coding task".

        `task` is the one that was promised here and is now real: the message
        was classified against the intent exemplars, the intent named a model
        specialisation, and the provider layer had one installed. It is
        deliberately the narrowest of the four. Nobody having chosen is still
        `zaram`, because "Zaram picked its usual model" and "Zaram picked this
        model *for this question*" are different claims and only the second is
        a routing decision.
        """
        return StreamEvent(
            type=EventType.ANSWERING,
            data={
                "model": model,
                "locality": locality,
                "chosen_by": chosen_by,
                "provider": provider,
            },
            correlation_id=correlation_id,
        )

    @staticmethod
    def artifact(record: dict, correlation_id: str = "") -> StreamEvent:
        """A generated file, as a card in the conversation.

        Carries the whole artifact record rather than a URL, because the card
        shows what Work shows — filename, kind, sources, claims — and a card
        that had to fetch each of those would render empty first and then
        rearrange itself under the user.
        """
        return StreamEvent(
            type=EventType.ARTIFACT,
            data=record,
            correlation_id=correlation_id,
        )

    @staticmethod
    def notice(content: str, kind: str = "", action: str = "", correlation_id: str = "") -> StreamEvent:
        """Something the user should know, alongside the answer.

        `action` names where to go about it — "knowledge" — so the surface can
        offer a route rather than leaving the user to find it. Rendered
        distinctly from the reply: attributing this to the model would be
        putting words in its mouth.
        """
        return StreamEvent(
            type=EventType.NOTICE,
            data={"content": content, "kind": kind, "action": action},
            correlation_id=correlation_id,
        )

    @staticmethod
    def error(content: str, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.ERROR,
            data={"content": content},
            correlation_id=correlation_id,
        )

    @staticmethod
    def done(correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.DONE,
            data={},
            correlation_id=correlation_id,
        )

    @staticmethod
    def start(capability_id: str | None = None, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.START,
            data={"capability_id": capability_id},
            correlation_id=correlation_id,
        )

    @staticmethod
    def step_start(capability_id: str, step_index: int, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.STEP_START,
            data={"capability_id": capability_id, "step_index": step_index},
            correlation_id=correlation_id,
        )

    @staticmethod
    def step_complete(capability_id: str, step_index: int, success: bool = True, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.STEP_COMPLETE,
            data={"capability_id": capability_id, "step_index": step_index, "success": success},
            correlation_id=correlation_id,
        )

    @staticmethod
    def plan_start(correlation_id: str, step_count: int) -> StreamEvent:
        return StreamEvent(
            type=EventType.PLAN_START,
            data={"step_count": step_count},
            correlation_id=correlation_id,
        )

    @staticmethod
    def plan_complete(correlation_id: str, state: str) -> StreamEvent:
        return StreamEvent(
            type=EventType.PLAN_COMPLETE,
            data={"state": state},
            correlation_id=correlation_id,
        )

    @staticmethod
    def retry(capability_id: str, attempt: int, delay: float, correlation_id: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.RETRY,
            data={"capability_id": capability_id, "attempt": attempt, "delay": delay},
            correlation_id=correlation_id,
        )

    @staticmethod
    def cancel(correlation_id: str, reason: str = "") -> StreamEvent:
        return StreamEvent(
            type=EventType.CANCEL,
            data={"reason": reason},
            correlation_id=correlation_id,
        )

    def to_execution_token(self) -> ExecutionToken:
        """Convert to an ExecutionToken for internal use."""
        return ExecutionToken(
            token=self.data.get("content", ""),
            sequence=self.seq,
            final=self.type == EventType.DONE,
            metadata={
                "type": self.type.value,
                "ts": self.ts,
                "correlation_id": self.correlation_id,
            },
        )
