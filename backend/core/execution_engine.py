# backend/core/execution_engine.py
"""ExecutionEngine — the kernel's central orchestrator.

The ExecutionEngine ties together all kernel subsystems:

    User prompt
        ↓  IntentPlanner (Runtime_Intent)
    ExecutionPlan
        ↓  CapabilityRouter (Capability Resolution)
    Runtime
        ↓  ExecutionDispatcher (Runtime_Dispatcher)
    Streamed response

The engine supports two execution paths:

1. **Legacy synchronous path** (``execute``) — streams string tokens
   directly.  Used by the existing ChatRouter and tests.

2. **Task queue path** (``execute_async``) — schedules tasks onto the
   TaskQueue with priority, cancellation, and retry.  Used when the
   engine is running inside an async event loop with workers started.

No runtime directly calls another runtime.  All cross-runtime
communication flows through the EventBus.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import re
import time
from collections import OrderedDict
from collections.abc import Iterator
from typing import Any

from core.async_bridge import run_sync
from core.capability_router import CapabilityRouter
from core.contracts import (
    ExecutionPlan,
    ExecutionStep,
    PlanState,
    TaskPriority,
)
from core.dispatcher import ARTIFACT_MARKER, ExecutionDispatcher
from core.event_bus import EventBus, ZaramEvent
from core.execution_context import ExecutionContext
from core.planner import IntentClassification, IntentPlanner, IntentType
from core.streaming_events import StreamEvent
from core.registry import RuntimeRegistry
from core.scheduler import RuntimeScheduler
from core.task_queue import TaskQueue

logger = logging.getLogger(__name__)


def _scope_for(project_id: str | None) -> str | None:
    """The scope string for a project, or None when none is active.

    Rule 7i spells scopes `project:<id>` and that spelling lives in one place —
    `runtimes.memory.contracts.project_scope`. Imported lazily so `core/` keeps
    no import-time dependency on the memory runtime, which is the same seam
    `_memory_runtime` maintains.

    None is deliberate and is not the same as `global`. It means "no project
    filter", which lets recall see every scope — correct when the user is not
    working inside a project, and wrong as a *capture* value, which is why
    storage converts it separately.
    """
    if not (project_id or "").strip():
        return None
    from runtimes.memory.contracts import project_scope

    return project_scope(project_id)


def _relevance_of(result: Any) -> float:
    """How well a recalled memory bears on the question, 0..1.

    `MemoryResult` carries two numbers and only one of them answers this.
    `score` is the ranking blend used for ordering; `relevance` is the
    similarity retrieval produced. Falls back to `score` for any result type
    that has no `relevance` — several tests use plain stand-ins — so the
    tightening applies where the real field exists and changes nothing where
    it does not.
    """
    relevance = getattr(result, "relevance", None)
    if relevance is None:
        relevance = getattr(result, "score", 0.0)
    return float(relevance or 0.0)


class ExecutionEngine:
    """The operational core of Zaram. Orchestrates the lifecycle of a user request.

    The engine owns the IntentPlanner, CapabilityRouter, and
    ExecutionDispatcher.  It optionally integrates with the TaskQueue
    and Scheduler for advanced execution with priority, cancellation,
    and retry.
    """

    def __init__(
        self,
        registry: RuntimeRegistry,
        event_bus: EventBus,
        task_queue: TaskQueue | None = None,
        scheduler: RuntimeScheduler | None = None,
        semantic_router: Any | None = None,
    ) -> None:
        self._registry = registry
        self._event_bus = event_bus
        # None is the ordinary case in tests and any caller that has no
        # embedder; the planner falls back to keyword classification.
        self._planner = IntentPlanner(semantic_router=semantic_router)
        self._router = CapabilityRouter(registry)
        self._dispatcher = ExecutionDispatcher(self._router)
        self._task_queue = task_queue
        self._scheduler = scheduler
        self._active_plans: dict[str, ExecutionPlan] = {}
        #: Ephemeral session state, per rule 7d — never written to the Spine.
        #: session_id → recent (prompt, answer) pairs, LRU-capped at
        #: MAX_SESSIONS. Ordered because eviction order is the point.
        self._session_turns: OrderedDict[str, list[tuple[str, str]]] = OrderedDict()
        #: Returns one sentence to say in the transcript, or None. Injected so
        #: `core/` keeps no dependency on `ingest/`; `main.py` supplies it.
        self._notice_source: Any | None = None
        #: The provider layer, for the pre-flight residency check. Injected
        #: after boot — see `set_provider_manager`. None means no load or swap
        #: is ever announced, which is the correct degradation.
        self._provider_manager: Any | None = None

    def set_provider_manager(self, manager: Any | None) -> None:
        """Provide the provider layer, for the pre-flight residency check.

        Injected after construction rather than taken as a constructor argument
        because the providers runtime boots later than the engine. Absent, the
        engine simply never announces a load or a swap — the indicator is
        optional, the reply is not.
        """
        self._provider_manager = manager

    def set_notice_source(self, source: Any | None) -> None:
        """Provide a callable returning a one-off notice, or None.

        Ingest is the first caller: a file that gave nothing back must be
        mentioned in the conversation the first time it matters, because
        Knowledge showing it only helps someone who opens Knowledge.
        """
        self._notice_source = source

    def _pending_notice(self) -> str | None:
        if self._notice_source is None:
            return None
        try:
            return self._notice_source()
        except Exception:
            # A notice is never worth costing the user their answer.
            logger.warning("Engine: notice source failed", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Legacy synchronous execution (backward compatible)
    # ------------------------------------------------------------------

    def execute(
        self,
        prompt: str,
        model: str = "gemma3:latest",
        system_prompt: str = "",
        session_id: str = "default",
        project_id: str | None = None,
    ) -> Iterator[Any]:
        """End-to-end execution: Recall -> Plan -> Route -> Dispatch -> Stream.

        Yields plain strings for response tokens, and StreamEvent objects for
        structured output such as provenance. Callers that only understand
        strings continue to work unchanged.

        `project_id` is rule 7i's missing caller. M8 built the scope field, the
        recall filter, the migration and the promotion evidence, and then
        nothing ever told the engine which project was active — so every fact
        landed `global` and `promotion_candidates()` could only ever return an
        empty list. Recall narrows to this project plus global; capture writes
        this project's scope.

        None means no project is active, and that is a real answer rather than
        a missing one: a question asked outside any project is not about one.
        """
        logger.debug("Engine: execute prompt='%s...' model=%s", prompt[:50], model)

        # Before anything else, including recall: will this route force a model
        # out of VRAM? Asked first because the whole point is that the user
        # learns about the wait *before* they spend it. Recall itself takes
        # hundreds of milliseconds, so emitting this after it would already be
        # late.
        swap_event = self._swap_preflight_event(model)
        if swap_event is not None:
            yield swap_event

        # Provenance is emitted from two places — recall, and any search step.
        # Both can surface the same record, so dedupe across the whole request.
        seen_sources: set[str] = set()

        # Citation numbers are assigned here, at the single point every source
        # event passes through, rather than inside the two emitters.
        #
        # They have to be assigned *after* the dedupe above, or a source
        # surfaced by both recall and search consumes a number that no chip
        # ever shows — and the user sees a reply citing 1, 2 and 4. They also
        # have to be assigned server-side: the chips and the panel are two
        # renderings of one list, and a frontend numbering each of them
        # independently gets them out of step the first time one is filtered.
        citation_numbers = itertools.count(1)

        def _numbered(event):
            """Stamp a cited source with the next number. Uncited get none."""
            if event.data.get("cited"):
                event.data["number"] = next(citation_numbers)
            return event

        # --- Recall: what does the Spine already know that bears on this? ---
        recalled = self._recall(prompt, session_id, project_id)
        if recalled:
            system_prompt = self._augment_system_prompt(system_prompt, recalled)
            for event in self._provenance_events(recalled):
                key = event.data.get("url") or event.data.get("title", "")
                if key and key not in seen_sources:
                    seen_sources.add(key)
                    yield _numbered(event)

        # "Write that up as a proposal" is a *referential* request: the thing to
        # write up is the previous turn, and nothing in those five words is
        # semantically near it. Similarity recall therefore returns nothing
        # useful and the model fills the gap by inventing — one run produced a
        # confident document about a "Project Phoenix" that had never been
        # mentioned, with the real client's name and day rate nowhere in it.
        # That is the worst possible failure for a tool whose output the user
        # forwards to a client.
        #
        # So a document request carries the recent exchange explicitly. Recall
        # answers "what is relevant to these words"; this answers "what is
        # 'that'", and those are different questions.
        #
        # `context_resolved` is the honest half: it says whether there was
        # anything to resolve "that" against. The documents runtime refuses when
        # a referential request arrives without it (rule 9), so this flag must
        # be set from what actually happened rather than from having tried.
        context_resolved = False
        if self._is_document_request(prompt):
            system_prompt, context_resolved = self._augment_with_recent_turns(
                system_prompt, session_id
            )

        plan = self._planner.create_plan(prompt)
        plan = self._drop_unavailable_steps(plan)
        plan.state = PlanState.RUNNING
        logger.debug("Engine: plan created with %d steps", len(plan.steps))

        self._active_plans[plan.correlation_id] = plan
        self._publish("execution.plan_created", {
            "correlation_id": plan.correlation_id,
            "step_count": len(plan.steps),
        })

        step_results: dict[str, str] = {}
        failed_steps: list[dict[str, Any]] = []

        for i, step in enumerate(plan.steps):
            self._publish("execution.step_started", {
                "correlation_id": plan.correlation_id,
                "capability_id": step.capability_id,
                "step_index": i,
            })

            logger.debug("Engine: executing step %d/%d: %s", i + 1, len(plan.steps), step.capability_id)

            step_output = ""
            step_failed = False
            step_error: str | None = None
            # Internal steps gather context for later steps. Their raw output is
            # not user-facing and must not reach the stream.
            internal = step.capability_id in self.INTERNAL_CAPABILITIES

            # A document step writes up the answer the previous step produced.
            # The planner could not know that text, so it left a hole; filling
            # it here is what makes "write that up" mean *that*, rather than
            # re-answering the question into a file.
            if step.capability_id.startswith("document.") and not (
                step.input_data or {}
            ).get("answer"):
                step.input_data = dict(step.input_data or {})
                step.input_data["answer"] = step_results.get("reasoning.generate", "")
                step.input_data.setdefault("session_id", session_id)
                step.input_data["context_resolved"] = context_resolved

            try:
                for token in self._dispatcher.execute_step(step, model, system_prompt):
                    step_output += token
                    if internal:
                        continue
                    if token.startswith(ARTIFACT_MARKER):
                        # Becomes a card, never text. Reaching the user as a
                        # raw marker would be a visible bug, so a malformed
                        # payload is dropped with a log rather than printed.
                        try:
                            yield StreamEvent.artifact(
                                json.loads(token[len(ARTIFACT_MARKER):].strip())
                            )
                        except json.JSONDecodeError:
                            logger.exception(
                                "Document step emitted an unparseable artifact marker"
                            )
                    else:
                        yield token

                if step_output.strip().startswith("[FALLBACK]") or step_output.strip().startswith("[WARN]"):
                    step_failed = True
                    step_error = step_output.strip()
                    logger.warning("Engine: step %d (%s) returned fallback: %s", i + 1, step.capability_id, step_error[:100])
                elif step.capability_id == "knowledge.search":
                    try:
                        parsed = json.loads(step_output)
                        if parsed.get("fallback") or parsed.get("error"):
                            step_failed = True
                            step_error = parsed.get("error", "unknown error")
                            logger.warning("Engine: knowledge search returned fallback: %s", step_error)
                    except Exception:
                        pass

            except Exception as exc:
                step_failed = True
                step_error = str(exc)
                logger.error("Engine: step %d (%s) threw exception: %s: %s", i + 1, step.capability_id, type(exc).__name__, exc)

            if step_failed:
                failed_steps.append({"capability_id": step.capability_id, "error": step_error, "index": i})
                step.status = "failed"
            else:
                step.status = "completed"

            step_results[step.capability_id] = step_output

            # Fold a successful internal step's findings into the context the
            # next step sees, and surface its sources as provenance.
            if internal and not step_failed and step_output.strip():
                if step.capability_id == "knowledge.search":
                    sources = self._parse_search_results(step_output)
                    if sources:
                        system_prompt = self._augment_with_sources(system_prompt, sources)
                        for event in self._search_provenance_events(sources):
                            key = event.data.get("url") or event.data.get("title", "")
                            if key and key not in seen_sources:
                                seen_sources.add(key)
                                yield _numbered(event)

            self._publish("execution.step_completed" if not step_failed else "execution.step_failed", {
                "correlation_id": plan.correlation_id,
                "capability_id": step.capability_id,
                "step_index": i,
                "failed": step_failed,
                "error": step_error,
            })

        if failed_steps:
            if len(failed_steps) == len(plan.steps):
                plan.state = PlanState.FAILED
            else:
                plan.state = PlanState.DEGRADED
            logger.warning(
                "Engine: plan completed with %d/%d failed steps: %s",
                len(failed_steps),
                len(plan.steps),
                [f["capability_id"] for f in failed_steps],
            )
        else:
            plan.state = PlanState.COMPLETED
            logger.info("Engine: plan completed successfully")

        self._publish("execution.plan_completed", {
            "correlation_id": plan.correlation_id,
            "state": plan.state.value,
            "failed_steps": failed_steps,
        })

        # --- Remember: commit what the user told us to the Spine. ---
        answer = step_results.get("reasoning.generate", "")
        self._remember(prompt, answer, session_id, recalled, project_id)
        # Ephemeral, and separate from the Spine write above. This is what a
        # later "write that up" resolves against.
        self._record_exchange(session_id, prompt, answer)

        # --- Say what could not be read, once. ---
        #
        # After the answer, not before it: the user asked a question and the
        # answer is what they are waiting for. Interrupting with housekeeping
        # first is how a warning gets trained away. Once per scan, never per
        # reply, for the same reason.
        notice = self._pending_notice()
        if notice:
            yield StreamEvent.notice(notice, kind="ingest", action="knowledge")

        if plan.correlation_id in self._active_plans:
            del self._active_plans[plan.correlation_id]

    # ------------------------------------------------------------------
    # Recall — the memory loop
    # ------------------------------------------------------------------

    #: How many recalled facts reach the model.
    #:
    #: No longer also the citation count — `MIN_CITATION_SCORE` decides that
    #: separately, so raising this widens what the model can use without
    #: widening what the user is asked to check.
    #:
    #: 6, from measurement rather than taste: at 1,000 documents the deepest
    #: answerable target sat at rank 5 once selection was moved onto relevance,
    #: and a shortlist equal to the deepest observed rank has no headroom at all
    #: — one more near-identical invoice drops it. See
    #: `test_the_shortlist_covers_the_deepest_target`, which prints that
    #: headroom on every run precisely so this number can be revisited from
    #: evidence.
    MAX_RECALL = 6

    #: How many candidates to retrieve before the floor and the cut.
    #:
    #: **The rank-7 displacement this was written for no longer happens**, and
    #: the honest reason is that two separate defects were being read as one.
    #: The corpus was emitting filler that answered the eval question as well as
    #: the target did, and selection was cutting on the ranking blend rather
    #: than on relevance. With both fixed, every answerable target now returns
    #: at **rank 1 at 1,000 documents** — re-measured 11 August 2026, headroom
    #: 5 on a shortlist of 6.
    #:
    #: 25 is kept anyway, and on a weaker claim than the one it was chosen on:
    #: depth is nearly free — retrieval is a linear scan either way and the only
    #: cost is carrying twenty more rows a few milliseconds further — so this is
    #: cheap insurance against a real corpus that crowds harder than a synthetic
    #: one. It is no longer evidence of a displacement anybody has observed.
    #: Do not cite it as such.
    RECALL_CANDIDATES = 25

    #: How many turns of ephemeral session state to keep, per session.
    MAX_SESSION_TURNS = 8

    #: How many sessions to keep state for at once, evicted least-recently-used.
    #:
    #: The frontend mints a session id per page load, so without this the map
    #: grows for the life of the process and nothing is ever removed — each
    #: dead session pinning up to MAX_SESSION_TURNS prompt/answer pairs.
    #: 64 is generous for one person on one machine and still bounds the
    #: worst case at a few hundred KB.
    MAX_SESSIONS = 64

    #: Below this, a memory is not relevant enough to inject or to cite.
    #:
    #: Measured, not guessed. With bge-m3 embeddings and two facts in the Spine:
    #:
    #:     "When is the launch?"                      0.546, 0.515   related
    #:     "Where is the rehearsal being held?"       0.491, 0.436   related
    #:     "who won the 2026 world cup"               0.362, 0.355   unrelated
    #:     "What can you do"                          0.339, 0.327   unrelated
    #:     "write me a python function to sort a list" 0.332, 0.317  unrelated
    #:
    #: The old value of 0.25 sat below every one of those, so *every* question
    #: recalled *every* memory and cited it. That is worse than not citing at
    #: all: a citation the answer did not use is a false claim of provenance,
    #: and it teaches the user that the citations mean nothing. Rule 2 is about
    #: answers carrying their sources, which only works if the converse holds.
    #:
    #: bge-m3 puts any two English sentences around 0.3 even when they share no
    #: subject, so the usable signal starts well above zero. 0.42 sits in the
    #: gap measured above. Re-measure if the embedding model changes — this
    #: number is not transferable between models, which is why the backend can
    #: override it.
    MIN_RECALL_SCORE = float(os.getenv("ZARAM_MIN_RECALL_SCORE", "0.42"))

    #: Below this, a memory was worth giving the model but is not worth citing.
    #:
    #: A second, higher cut on the *same* `relevance` field, because "worth
    #: injecting" and "worth telling the user about" are different questions.
    #: Injecting six facts and citing the two that carried the answer is the
    #: correct behaviour, not a compromise.
    #:
    #: Measured: driving the interface produced a reply about a day rate citing
    #: five memories, all genuinely about day rates and payment terms, relevance
    #: 0.50–0.61 — and only the top one actually used. Nothing was wrong with
    #: retrieval; the gap is between *recalled* and *used*. An answer wearing
    #: five citations has taught the user that citations are decoration, and
    #: after that the real ones cannot help.
    #:
    #: 0.55 sits inside that observed band rather than above it, so the fact
    #: that carried the answer is still cited while the merely-adjacent ones
    #: move to the panel's "recalled, not cited" section. They are not hidden —
    #: `_provenance_events` emits them with `cited=False` — and the gap between
    #: the two thresholds is visible in the UI and therefore arguable.
    #:
    #: **Never applies to web sources.** Bytes leaving the machine are always
    #: cited regardless of relevance; that is an egress disclosure, not an
    #: attribution judgement, and thresholding it would hide the one thing this
    #: product exists to show.
    MIN_CITATION_SCORE = float(os.getenv("ZARAM_MIN_CITATION_SCORE", "0.55"))

    #: Capabilities whose output is context for later steps, never shown to the
    #: user. Their raw payloads (JSON search results, for example) would
    #: otherwise be streamed into the reply.
    INTERNAL_CAPABILITIES = frozenset({"knowledge.search"})

    # ------------------------------------------------------------------
    # Search results as context
    # ------------------------------------------------------------------

    def _drop_unavailable_steps(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Remove steps whose capability has no registered runtime.

        The classifier routes on keywords, so an ordinary question can be sent
        to a capability whose runtime is dormant — "what is my secret codeword?"
        matched the tool keywords and planned `tool.terminal`. Only four
        runtimes boot, so that produced a raw
        `[FALLBACK] tool.terminal unavailable: ...` in place of an answer.

        Planning against what is actually registered means a misroute degrades
        to a normal reply instead of showing the user an internal error.
        """
        available: list[ExecutionStep] = []
        for step in plan.steps:
            try:
                self._router.resolve(step.capability_id)
            except Exception:
                logger.info(
                    "Engine: dropping step %s — no runtime registered for it",
                    step.capability_id,
                )
                continue
            available.append(step)

        if not available:
            # Never return an empty plan: answering normally is always better
            # than answering not at all.
            logger.info("Engine: no planned capability was available; answering directly")
            available = [
                ExecutionStep(
                    capability_id="reasoning.generate",
                    input_data={"prompt": plan.original_prompt},
                    depends_on=[],
                )
            ]

        plan.steps = available
        return plan

    def _parse_search_results(self, raw: str) -> list[dict[str, Any]]:
        """Pull the result list out of a knowledge.search payload."""
        try:
            parsed = json.loads(raw)
        except Exception:
            return []
        if not isinstance(parsed, dict):
            return []
        results = parsed.get("results") or []
        return [r for r in results if isinstance(r, dict)]

    def _augment_with_sources(self, system_prompt: str, sources: list[dict[str, Any]]) -> str:
        """Fold search results into the system prompt with citation markers."""
        lines = [
            "",
            "=== SOURCES RETRIEVED FOR THIS QUESTION ===",
            "",
        ]
        for i, source in enumerate(sources, 1):
            title = (source.get("title") or "").strip()
            url = (source.get("url") or "").strip()
            snippet = (source.get("snippet") or "").strip()
            lines.append(f"[S{i}] {title}" if title else f"[S{i}]")
            if url:
                lines.append(f"     {url}")
            if snippet:
                lines.append(f"     {snippet}")
        lines += [
            "",
            "INSTRUCTIONS:",
            "- Answer from these sources where they are relevant, naming them in plain",
            "  words. Never print the [S1] markers themselves — they are internal",
            "  labels and mean nothing to the user.",
            "- Prefer them over your training data where they conflict.",
            "- If they do not answer the question, say so rather than inventing detail.",
            "=" * 43,
            "",
        ]
        return (system_prompt or "") + "\n".join(lines)

    def _search_provenance_events(self, sources: list[dict[str, Any]]) -> list[Any]:
        """One source event per search result. Always cited, never thresholded.

        Bytes left the machine to fetch these, so they are disclosed regardless
        of how central they were to the answer. `MIN_CITATION_SCORE` is an
        attribution judgement and this is not one — it is the egress log
        surfacing at the sentence level, and a relevance score is not a reason
        to stop telling someone what left their computer.

        `kind` is normalised to `web` rather than passed through as the
        provider name. The UI colours by egress, and a chip that said "brave"
        or "tavily" would make the user learn a vocabulary to answer the only
        question that matters: did this leave?
        """
        from core.streaming_events import StreamEvent

        events = []
        for source in sources:
            snippet = " ".join((source.get("snippet") or "").split())
            events.append(StreamEvent.source(
                kind="web",
                url=source.get("url"),
                title=(source.get("title") or "")[:120],
                excerpt=snippet[: self.EXCERPT_CHARS] or None,
                relevance=source.get("score"),
                cited=True,
                # The link that makes the citation and the egress log the same
                # object viewed twice. None when the search path did not report
                # one — shown as absent rather than faked, because a citation
                # claiming an egress row that does not exist is worse than one
                # admitting it cannot link.
                egress_id=source.get("egress_id"),
                bytes_sent=source.get("bytes_sent"),
                origin="web",
            ))
        return events

    def _swap_preflight_event(self, model: str) -> Any | None:
        """Announce a model load or swap before generation, or say nothing.

        Returns None in every uncertain case — no provider manager, no
        accelerator, unreadable VRAM, an unreachable Ollama, or a model the
        catalog does not know. The indicator is only worth having if it is
        right, so silence is the correct output whenever the answer is "cannot
        tell". This runs on the critical path of every reply, so it also
        swallows its own failures: a broken residency probe must cost the user
        an indicator, never an answer.
        """
        manager = getattr(self, "_provider_manager", None)
        if manager is None:
            return None
        try:
            plan = manager.swap_preflight(model)
        except Exception as exc:
            logger.debug("Engine: swap pre-flight failed: %s", exc)
            return None

        # `resident` is the common case and says nothing, deliberately: an
        # event on every reply would be noise the frontend has to filter, and
        # the orb already has a word for "working".
        if plan is None or plan.kind == "resident":
            return None

        logger.info(
            "Engine: %s required before reply — %s%s",
            plan.kind, plan.model,
            f", evicting {', '.join(plan.evicts)}" if plan.evicts else "",
        )
        return StreamEvent.model_load(
            kind=plan.kind, model=plan.model, evicts=plan.evicts,
        )

    def _memory_runtime(self) -> Any | None:
        """Resolve the memory runtime through the capability router.

        Returns None when no memory runtime is registered, so every call site
        degrades to the previous no-memory behaviour rather than failing.
        """
        try:
            return self._router.try_resolve("memory.retrieve")
        except Exception:
            return None

    def _recall_gate(self, runtime: Any) -> Any:
        """The gate, built once per memory runtime and kept.

        Keyed on the runtime rather than cached outright because tests swap the
        runtime under a live engine, and a gate holding the previous runtime's
        embedder would answer from the wrong model without saying so.
        """
        cached = getattr(self, "_recall_gate_cache", None)
        if cached is not None and cached[0] is runtime:
            return cached[1]

        from core.recall_gate import gate_from_memory_runtime

        gate = gate_from_memory_runtime(runtime)
        self._recall_gate_cache = (runtime, gate)
        return gate

    def _recall(
        self, prompt: str, session_id: str, project_id: str | None = None
    ) -> list[Any]:
        """Retrieve prior context relevant to this prompt.

        Retrieves `RECALL_CANDIDATES` and cuts to `MAX_RECALL` after the floor,
        rather than asking for five and hoping the right one is in them.

        Re-measured 11 August 2026 at 10, 100 and 1,000 documents: the floor
        holds at every size, with **zero false citations** and all five
        answerable targets returning at rank 1. The margin narrows as the corpus
        grows and then flattens — +0.131, +0.108, +0.106 — because `related_min`
        is a cosine between two fixed vectors and does not move, while
        `unrelated_max` is a maximum over the corpus and every document added is
        another draw.

        **The `+0.179` this docstring used to quote was never real.** It was
        inflated by the selection defect it was measuring: the document scoring
        0.517 was cut from the shortlist, so it never entered the sample the
        minimum was taken over. `docs/RERANKER.md` records +0.106 as the
        baseline and every earlier margin as read through a broken selector.

        That episode decided the reranker question, and not the way the numbers
        first suggested. Better similarities were never the binding constraint —
        the ones already available were being outvoted by importance, recency
        and access at roughly 4.5 to 1. See `test_recall_at_scale.py` and
        `docs/RERANKER.md`.
        """
        runtime = self._memory_runtime()
        if runtime is None or not prompt.strip():
            return []

        # Does this turn need the Spine at all? Asked before retrieving, not
        # after, because the floor provably cannot answer it: social turns and
        # vague referential ones *overlap* on corpus similarity — "good morning"
        # scores 0.493 against the user's files and "what did I quote them"
        # scores 0.463. Typing `Hi` pulled three documents, including day rates,
        # into the prompt. See `core/recall_gate.py` for the measurement.
        #
        # Fails open in every uncertain case, so this can cost milliseconds and
        # a line of UI but never an answer.
        if not self._recall_gate(runtime).should_recall(prompt):
            logger.debug("Engine: recall skipped, conversational turn: %r", prompt[:40])
            return []

        try:
            results = run_sync(runtime.retrieve(
                query=prompt,
                max_results=self.RECALL_CANDIDATES,
                session_id=None,
                # Rule 7i: this project plus global, and nothing else. A
                # question asked inside one project draws on that project and
                # on what is true about the user generally — never on another
                # client's terms. `None` means every scope, which is right when
                # no project is active and is what the Memory surface wants.
                scope=_scope_for(project_id),
            ))
        except Exception as exc:
            logger.warning("Engine: recall failed: %s: %s", type(exc).__name__, exc)
            return []

        # Thresholded on `relevance`, not `score`. `score` is the ranking
        # blend — importance, recency, access count, session membership — and
        # comparing it to a floor measured as a cosine similarity meant an
        # unrelated fact could be cited on recency alone. Ordering and
        # permission are different questions; this one is about relevance.
        # Floor on relevance, then cut on relevance. The cut used to take the
        # first five of whatever order retrieval returned, which is the ranking
        # blend — so the five facts the model was given were the five most
        # *recently touched* of those above the floor, not the five most
        # relevant. Both halves have to be the same number or the floor is
        # protecting a list that something else already chose.
        kept = sorted(
            (r for r in results if _relevance_of(r) >= self.MIN_RECALL_SCORE),
            key=_relevance_of,
            reverse=True,
        )[: self.MAX_RECALL]
        logger.info("Engine: recalled %d/%d memories above threshold", len(kept), len(results))
        self._publish("memory.recalled", {
            "query": prompt[:100],
            "candidates": len(results),
            "used": len(kept),
        })
        return kept

    def _is_document_request(self, prompt: str) -> bool:
        """Whether this plan will write a file.

        Asked of the classifier rather than pattern-matched here, so the
        embedding router and this stay in agreement — a second, cruder test
        would drift from the first the moment an exemplar changed.
        """
        try:
            return (
                self._planner.classify_intent(prompt).intent_type
                is IntentType.DOCUMENT
            )
        except Exception:
            return False

    def _record_exchange(self, session_id: str, prompt: str, answer: str) -> None:
        """Keep the last few turns of this session, in memory only.

        Rule 7d: conversation is ephemeral, and entering the Spine is a
        decision the system makes. Working state, clarifications and false
        starts stay in the session — so this is a bounded in-process buffer,
        not a write to the Spine, and it dies with the process.

        `_remember` deliberately stores the user's *words as a fact* and not
        the exchange, for reasons written out in its own docstring: storing the
        exchange made Zaram quote its own replies back. That is the right
        behaviour for long-term memory and it leaves nothing that can answer
        "what does 'that' refer to". This buffer answers exactly that and
        nothing else.
        """
        prompt, answer = (prompt or "").strip(), (answer or "").strip()
        if not prompt or not answer:
            return

        turns = self._session_turns.setdefault(session_id, [])
        turns.append((prompt, answer))
        # Bounded: a long conversation must not grow the process without limit,
        # and only the recent turns are what "that" can plausibly mean.
        del turns[:-self.MAX_SESSION_TURNS]

        # Bounded in the other direction too. Capping turns *per session* bounds
        # nothing on its own: the frontend mints a session id per page load, so
        # a day of reloads leaves a map of dead sessions, each holding up to
        # MAX_SESSION_TURNS prompt/answer pairs and none of them reachable
        # again. Least-recently-*used*, not least-recently-created: a long
        # conversation left open in one tab must not be evicted by a burst of
        # reloads in another.
        self._session_turns.move_to_end(session_id)
        while len(self._session_turns) > self.MAX_SESSIONS:
            evicted, _ = self._session_turns.popitem(last=False)
            logger.debug("Engine: evicted session state for %s", evicted)

    def _augment_with_recent_turns(
        self, system_prompt: str, session_id: str, limit: int = 3
    ) -> tuple[str, bool]:
        """Put the last few turns in front of the model, verbatim.

        Verbatim rather than summarised: a summary is another generation, and
        writing the document from a summary of the answer rather than the
        answer loses exactly the specifics — figures, names, terms — that make
        it worth having. The observed failure was a document about a "Project
        Phoenix" that was never mentioned, written confidently, with the real
        client's name and day rate nowhere in it.

        Silent when there is nothing: a first-turn document request has no
        "that" to resolve, and the model writing from the request alone is a
        weaker document rather than no document.
        """
        turns = self._session_turns.get(session_id, [])[-limit:]
        if not turns:
            # Returning False rather than quietly carrying on is the whole
            # point: the runtime refuses on this, and a flag set optimistically
            # would restore exactly the invented-client failure.
            logger.info("Engine: no prior turns to resolve a document request against")
            return system_prompt, False

        lines = ["", "The conversation so far. The document is about this:"]
        for prompt, answer in turns:
            lines.append(f"User: {prompt}")
            lines.append(f"You answered: {answer}")

        logger.info("Engine: gave the document step %d prior turns", len(turns))
        return system_prompt + "\n".join(lines), True

    def _augment_system_prompt(self, system_prompt: str, recalled: list[Any]) -> str:
        """Fold recalled memories into the system prompt, with citation markers.

        Each memory is numbered so the model can cite it, and the instruction
        block tells it to say when it is drawing on memory.
        """
        lines = [
            "",
            "=== WHAT YOU REMEMBER ABOUT THIS USER ===",
            "These are facts from earlier exchanges, retrieved from local memory.",
            "",
        ]
        for i, result in enumerate(recalled, 1):
            record = result.record
            when = time.strftime("%Y-%m-%d", time.localtime(record.created_at))
            lines.append(f"[M{i}] ({when}) {record.content}")
        lines += [
            "",
            "INSTRUCTIONS:",
            "- Use these memories when they are relevant to the question.",
            "- When you rely on one, refer to it in plain words, e.g. 'you mentioned",
            "  earlier that...'. Never print the [M1] markers themselves — they are",
            "  internal labels and mean nothing to the user.",
            "- If they do not bear on the question, ignore them silently.",
            "- Never invent a memory that is not listed above.",
            "=" * 42,
            "",
        ]
        return (system_prompt or "") + "\n".join(lines)

    #: How much of a passage to send as the excerpt.
    #:
    #: Longer than the 120-character title because they do different jobs: the
    #: title identifies the source in a chip, the excerpt is the evidence, and
    #: an excerpt truncated to a chip's length cannot be checked against the
    #: claim it supports.
    EXCERPT_CHARS = 400

    def _provenance_events(self, recalled: list[Any]) -> list[Any]:
        """One source event per recalled memory, cited or not.

        Emits everything recalled, including what fell below
        `MIN_CITATION_SCORE`. Those carry `cited=False` and belong in the
        panel's quieter "recalled but not cited" section — dropping them here
        would hide the gap between the two thresholds, and that gap is exactly
        what makes the citation cut arguable rather than magic.
        """
        from core.streaming_events import StreamEvent
        from runtimes.memory.contracts import Origin

        events = []
        for result in recalled:
            record = result.record
            # Stored exchanges span lines; collapse them so the title reads as a
            # single line in the UI.
            flat = " ".join(record.content.split())
            snippet = flat if len(flat) <= 120 else flat[:117] + "..."
            excerpt = flat if len(flat) <= self.EXCERPT_CHARS else (
                flat[: self.EXCERPT_CHARS - 3] + "..."
            )

            relevance = _relevance_of(result)
            origin = getattr(record, "origin", None)

            # A fact that came out of one of the user's own files is a
            # `document` to the citation UI, not a `memory`. The spec's three
            # kinds are about where a source came from, and "a passage from an
            # indexed file" is a different claim to the user — it has a
            # filename they recognise — than "something Zaram remembered".
            # Both stayed on the device, so both are cyan; the distinction is
            # the icon and the card, not the colour.
            metadata = record.metadata or {}
            filename = metadata.get("filename") or metadata.get("source_file")
            is_document = origin is Origin.USER_DOCUMENT or bool(filename)

            events.append(StreamEvent.source(
                kind="document" if is_document else "memory",
                url=f"memory:{record.id}",
                title=filename or snippet,
                excerpt=excerpt,
                relevance=relevance,
                # Recalled and cited are two different cuts on one number.
                cited=relevance >= self.MIN_CITATION_SCORE,
                origin=origin.value if origin is not None else None,
                record_id=record.id,
            ))
        return events

    #: Internal citation markers. The model is told not to print them but does
    #: anyway, so they are stripped rather than merely discouraged.
    _MARKER_RE = re.compile(r"\s*\[[MS]\d+\]")

    #: Openings that mark a message as a question rather than a statement.
    #: A question adds nothing to the Spine; a statement might.
    _QUESTION_OPENERS = (
        "what", "when", "where", "who", "why", "how", "which", "whose",
        "is ", "are ", "was ", "were ", "do ", "does ", "did ", "can ",
        "could ", "will ", "would ", "should ", "tell me", "show me",
        "list ", "explain",
    )

    #: Instructions. "Write any simple python code" is not a fact about the
    #: user, but it is not a question either, so the question test alone let it
    #: into the Spine — where it sat looking like something Zaram had learned.
    _INSTRUCTION_OPENERS = (
        "write ", "make ", "create ", "generate ", "draft ", "build ",
        "give me", "summarise", "summarize", "translate ", "rewrite ",
        "fix ", "debug ", "refactor ", "convert ", "help me", "find ",
        "search ", "look up", "open ", "run ", "add ", "remove ", "delete ",
        "compare ", "analyse ", "analyze ", "review ", "check ", "let's",
        "lets ", "please ",
    )

    #: Openers that mean "remember this", which override the instruction test —
    #: "remember: the launch is 9 September" begins like an instruction and is
    #: precisely the thing we most want to store.
    _MEMORY_OPENERS = ("remember", "note that", "keep in mind", "don't forget", "dont forget")

    #: Pleasantries. Short, contentless, and they accumulate.
    _PLEASANTRIES = {
        "hi", "hello", "hey", "yo", "thanks", "thank you", "ta", "cheers",
        "ok", "okay", "k", "sure", "yes", "no", "yep", "nope", "good morning",
        "good afternoon", "good evening", "goodbye", "bye", "night",
        "test", "testing", "ping",
    }

    def _carries_new_information(self, prompt: str) -> bool:
        """Whether a message tells us something, as opposed to asking for something.

        **This is a heuristic patching a structural problem, not a fix.**

        There is no session/memory split. Every accepted prompt lands in the one
        `memories` table as `MemoryType.CONVERSATION` — `SEMANTIC`, `EPISODIC`
        and `WORKING` are defined in the contracts and used nowhere. The data
        model anticipated the distinction; the engine collapsed it. So this
        function is a guess at the door about what deserves to be in a knowledge
        base, and every wrong guess is a permanent record until a human notices
        it in the Memory list and deletes it by hand.

        The structural fix is that conversation turns go somewhere ephemeral
        that recall never reads, and the Spine holds only facts — entered by an
        explicit "remember this" or extracted from a turn. Then a wrong guess
        costs a missing fact rather than a polluted Spine, and this function
        stops being load-bearing.

        Until then: the Spine holds what the user told Zaram, and everything
        else — questions, instructions, greetings — is traffic. Storing traffic
        has a specific visible cost: it comes back later as a citation, so Zaram
        appears to cite the user's own words as a source.

        Conservative in one direction only. A missed fact is recoverable — the
        user can say it again.
        """
        text = " ".join((prompt or "").strip().lower().split())
        if not text:
            return False

        # "Remember: ..." wins over everything below it.
        if text.startswith(self._MEMORY_OPENERS):
            return True

        if text.endswith("?"):
            return False
        if text.startswith(self._QUESTION_OPENERS):
            return False
        if text.startswith(self._INSTRUCTION_OPENERS):
            return False

        stripped = text.rstrip(".!,")
        if stripped in self._PLEASANTRIES:
            return False

        # Too short to be a fact worth keeping. Three words is enough for
        # "deadline is Friday" and excludes most stray input.
        return len(stripped.split()) >= 3

    def _already_known(self, runtime: Any, prompt: str) -> bool:
        """True when the Spine already holds this almost word for word.

        Cheap and deliberately conservative: only a near-exact match counts, so
        a genuinely new fact is never silently dropped.
        """
        try:
            results = run_sync(runtime.retrieve(query=prompt, max_results=3))
        except Exception:
            return False

        target = " ".join(prompt.lower().split())
        for result in results or []:
            existing = " ".join((result.record.content or "").lower().split())
            if existing == target:
                return True
        return False

    @classmethod
    def strip_markers(cls, text: str) -> str:
        """Remove [M1]/[S2] citation markers from user-facing text.

        They exist so the model can ground its answer in a specific chunk. They
        mean nothing to the user, and storing them would carry the noise into
        every future recall of this exchange.
        """
        return cls._MARKER_RE.sub("", text or "")

    def _remember(
        self,
        prompt: str,
        answer: str,
        session_id: str,
        recalled: list[Any] | None = None,
        project_id: str | None = None,
    ) -> None:
        """Store what the user told us, so a later question can recall it.

        Stores the user's own words, not the exchange. Storing
        "User asked: X / Zaram answered: Y" caused three visible problems:

        - Citations showed a transcript of how something was learned rather
          than the thing itself.
        - Every answer that used a memory got stored containing that memory, so
          Zaram ended up quoting its own previous replies back to the user.
        - Asking the same question twice produced two near-identical records,
          and both were then cited.

        A fact is what the user said. The answer is kept in metadata for
        context, but it is not the thing being remembered.
        """
        runtime = self._memory_runtime()
        if runtime is None:
            return
        answer = self.strip_markers(answer or "").strip()
        prompt = (prompt or "").strip()
        if not prompt or not answer or answer.startswith("[FALLBACK]"):
            return

        # Questions are not facts, and are never stored.
        #
        # This used to read `if recalled and not ...`, so the guard only ran
        # when something had been recalled. That held while the recall threshold
        # was loose enough that every prompt recalled something — and broke the
        # moment the threshold was tightened, because a question that now
        # correctly recalls nothing skipped the check and was stored as a fact.
        #
        # The visible symptom: asking "who won the 2026 world cup" stored the
        # question, and the next similar question cited it. Zaram was citing the
        # user's own words back at them as though they were a source.
        #
        # Whether a prompt is a question does not depend on what recall
        # returned, so neither does this.
        if not self._carries_new_information(prompt):
            logger.debug("Engine: not storing — the prompt is a question, not a fact")
            return

        # Imported lazily: core/ does not depend on a runtime at module load.
        from runtimes.memory.contracts import MemoryType

        # Do not store something the Spine already holds almost verbatim.
        if self._already_known(runtime, prompt):
            logger.debug("Engine: not storing — near-identical record exists")
            return

        try:
            run_sync(runtime.remember(
                content=prompt,
                memory_type=MemoryType.CONVERSATION,
                session_id=session_id,
                metadata={"prompt": prompt, "answer": answer},
                tags=["conversation"],
                # Rule 7i: default to the current project. A fact captured
                # while working on one is about that work, and it is the
                # `recalled_in` evidence gathered across several projects that
                # later argues for promoting it to global — never a question
                # asked at capture time, which would ask the user to predict
                # the future (rule 7e).
                #
                # `None` here means no project was active, and `remember`
                # stores `global` for it. That is the honest reading: a
                # question asked outside any project is not about one.
                scope=_scope_for(project_id),
            ))
            logger.info(
                "Engine: stored exchange in the Spine (session=%s, project=%s)",
                session_id, project_id or "none",
            )
        except Exception as exc:
            logger.warning("Engine: remember failed: %s: %s", type(exc).__name__, exc)

    # ------------------------------------------------------------------
    # Async execution with TaskQueue (new path)
    # ------------------------------------------------------------------

    async def execute_async(
        self,
        prompt: str,
        model: str = "gemma3:latest",
        system_prompt: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float | None = None,
    ) -> str:
        """Schedule a request onto the TaskQueue and return the correlation_id.

        This is the new async path that uses the TaskQueue and Scheduler
        for priority-based execution with cancellation and retry.

        The caller must start the TaskQueue workers before calling this
        method, and use ``wait_for_result`` to retrieve the output.
        """
        if self._task_queue is None or self._scheduler is None:
            raise RuntimeError("TaskQueue and Scheduler must be configured for async execution")

        plan = self._planner.create_plan(prompt)
        plan.state = PlanState.RUNNING
        plan.priority = priority.value
        self._active_plans[plan.correlation_id] = plan

        self._publish("execution.plan_created", {
            "correlation_id": plan.correlation_id,
            "step_count": len(plan.steps),
            "priority": priority.value,
        })

        correlation_id = await self._scheduler.schedule(plan, self._dispatch_step_async)
        return correlation_id

    async def _dispatch_step_async(self, step: ExecutionStep, context: ExecutionContext) -> Any:
        """Async step executor used by the scheduler."""
        return await self._dispatcher.dispatch(step, context)

    async def wait_for_result(
        self,
        correlation_id: str,
        timeout: float | None = None,
    ) -> list[Any]:
        """Wait for all tasks in a plan to complete and return results."""
        if self._scheduler is None:
            raise RuntimeError("Scheduler not configured")
        return await self._scheduler.wait_for_plan(correlation_id, timeout)

    def cancel_request(self, correlation_id: str, reason: str = "") -> int:
        """Cancel all tasks in a plan."""
        if self._scheduler is not None:
            return self._scheduler.cancel_plan(correlation_id, reason)
        if correlation_id in self._active_plans:
            del self._active_plans[correlation_id]
        return 0

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    def classify_intent(self, prompt: str) -> IntentClassification:
        """Classify a user prompt into an intent."""
        return self._planner.classify_intent(prompt)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def get_plan_status(self, correlation_id: str) -> dict[str, Any] | None:
        """Get the status of a plan."""
        plan = self._active_plans.get(correlation_id)
        if plan is None:
            return None
        return {
            "correlation_id": correlation_id,
            "state": plan.state.value,
            "priority": plan.priority,
            "steps": [
                {"capability_id": s.capability_id, "status": s.status}
                for s in plan.steps
            ],
        }

    def list_active_plans(self) -> list[str]:
        return list(self._active_plans.keys())

    def get_task_queue(self) -> TaskQueue | None:
        return self._task_queue

    def get_scheduler(self) -> RuntimeScheduler | None:
        return self._scheduler

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _publish(self, event_type: str, data: dict[str, Any]) -> None:
        self._event_bus.publish(ZaramEvent(
            source_runtime="execution_engine",
            event_type=event_type,
            data=data,
        ))
