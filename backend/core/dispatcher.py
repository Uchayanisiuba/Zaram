# backend/core/dispatcher.py
"""Runtime_Dispatcher — dispatches capability execution to runtimes.

The dispatcher resolves a capability_id to a runtime via the
CapabilityRouter, then invokes the appropriate service method on that
runtime.  It handles both streaming (Iterator) and async execution
patterns, with graceful fallback on failure.

No runtime directly calls another runtime.  All cross-runtime
communication flows through the EventBus.
"""
from __future__ import annotations

import asyncio
import json
import logging
import traceback
from collections.abc import Iterator
from typing import Any

from core.async_bridge import run_sync
from core.capability_router import CapabilityRouter
from core.contracts import ExecutionStep
from core.execution_context import ExecutionContext

#: Prefix for the one marker line a document step emits. Defined here and
#: imported by the engine so the producer and the consumer cannot drift — a
#: marker that only one side knows about is a marker rendered to the user.
ARTIFACT_MARKER = "[ARTIFACT]"

#: Prefix for one denoising step's worth of progress. Same shape and the same
#: reason as `ARTIFACT_MARKER`: this generator is typed as yielding strings and
#: several callers rely on that, so a structured payload travels as one marked
#: line and the engine converts it before anything user-facing.
PROGRESS_MARKER = "[IMAGE_PROGRESS]"

logger = logging.getLogger(__name__)


class ExecutionDispatcher:
    """Executes individual steps by dispatching to the correct Runtime Service.

    The dispatcher is the kernel's Runtime_Dispatcher component.  It is
    the final hop before a runtime service is invoked.
    """

    def __init__(self, router: CapabilityRouter) -> None:
        self._router = router

    # ------------------------------------------------------------------
    # Synchronous streaming dispatch (backward compatible)
    # ------------------------------------------------------------------

    def execute_step(
        self,
        step: ExecutionStep,
        model: str | None = None,
        system_prompt: str = "",
    ) -> Iterator[str]:
        """Resolves the capability and executes the service with graceful error handling.

        This is the legacy synchronous interface used by the existing
        ExecutionEngine.  It yields string tokens.
        """
        logger.debug(
            "Dispatcher: execute_step capability=%s model=%s",
            step.capability_id,
            model,
        )
        try:
            runtime = self._router.resolve(step.capability_id)
            logger.debug(
                "Dispatcher: resolved runtime=%s",
                runtime.get_runtime_id() if hasattr(runtime, "get_runtime_id") else type(runtime).__name__,
            )

            if hasattr(runtime, "execute"):
                if step.capability_id.startswith("image."):
                    # Drawing takes tens of seconds, so this one cannot use
                    # `run_sync`: that blocks the calling thread until the
                    # coroutine finishes, which would mean no progress could be
                    # reported *and* nothing else could be yielded for the
                    # whole wait. The picture would land with the bar still at
                    # zero, which is the state this branch exists to fix.
                    #
                    # So the generation is started, and this generator turns
                    # into the thing that reports it: it drains a queue the
                    # provider fills from the sampling thread, one marker line
                    # per denoising step.
                    yield from self._execute_image_step(runtime, step)
                    return

                # run_sync, not asyncio.run: this generator is consumed on the
                # FastAPI event loop thread, where asyncio.run() raises.
                result = run_sync(runtime.execute(step.capability_id, step.input_data or {}))

                if step.capability_id.startswith("speech."):
                    if isinstance(result, dict):
                        if "stream" in result:
                            yield f"[AUDIO_STREAM]{result['request_id']}{result}\n"
                        elif "audio_url" in result:
                            yield f"[AUDIO]{result['audio_url']}\n"
                        elif result.get("success") is False:
                            yield f"[FALLBACK] {step.capability_id} failed: {result.get('error', 'unknown')}\n"
                        else:
                            yield f"[OK] {step.capability_id} completed\n"
                    else:
                        yield f"[OK] {step.capability_id} completed\n"
                elif step.capability_id.startswith("document."):
                    # The artifact record travels as one marker line, which the
                    # engine turns into a StreamEvent. Same shape as `[AUDIO]`
                    # above, and for the same reason: this generator is typed
                    # as yielding strings and several callers rely on that.
                    #
                    # The engine converts it before anything user-facing, so
                    # the marker never reaches a screen. If it ever does, that
                    # is a missing branch in the engine, not cosmetic.
                    if isinstance(result, dict) and result.get("success") and result.get("artifact"):
                        yield ARTIFACT_MARKER + json.dumps(result["artifact"]) + "\n"
                    else:
                        error = (
                            result.get("error", "unknown")
                            if isinstance(result, dict)
                            else "unknown"
                        )
                        yield f"[FALLBACK] {step.capability_id} failed: {error}\n"
                elif step.capability_id.startswith("mcp."):
                    # The payload *is* the point, so it is carried whole rather
                    # than summarised into a status line. Same shape as
                    # `knowledge.search`, which the engine already parses with
                    # `json.loads`, and for the same reason: both are internal
                    # steps whose output becomes context for the next one.
                    #
                    # Without this branch the generic `[OK] ... completed` below
                    # caught it, and the tool list — the whole reason the step
                    # ran — was discarded between the runtime returning it and
                    # the engine looking for it. That is the shape of failure
                    # this repository keeps finding: every layer reports
                    # success and the payload never arrives.
                    #
                    # A refusal and a confirmation request are *answers*, not
                    # failures, so they travel this path too. The engine decides
                    # what to show; the dispatcher does not editorialise.
                    yield json.dumps(result if isinstance(result, dict) else {"success": False})
                elif isinstance(result, dict) and "error" in result:
                    yield f"[FALLBACK] {step.capability_id} failed: {result['error']}\n"
                else:
                    yield f"[OK] {step.capability_id} completed\n"

            elif hasattr(runtime, "get_service"):
                service = runtime.get_service()
                logger.debug(
                    "Dispatcher: capability=%s input_keys=%s",
                    step.capability_id,
                    list((step.input_data or {}).keys()),
                )
                if step.capability_id.startswith("vision."):
                    # **A vision step that reaches here has no image, always.**
                    # `IntentPlanner.create_plan` sends an attached image down
                    # the ordinary generation path — that is what carries it to
                    # whichever model was routed, through the residency and
                    # consent gates and into the egress log — so the only way a
                    # `vision.*` step survives is a keyword match on a prompt
                    # with nothing attached to it.
                    #
                    # It used to reach `analyze_image` and from there
                    # `stream_vision_response`, which posted to a hardcoded
                    # `qwen2.5vl:7b` past routing and past the gate. That is
                    # deleted, and this must not become a fall-through to
                    # `generate_response` instead: asked to describe a picture
                    # that was never supplied, a model writes a confident
                    # description of nothing, which is rule 9 exactly. Refusing
                    # is the whole point.
                    logger.debug(
                        "Dispatcher: refusing %s — no image was attached",
                        step.capability_id,
                    )
                    yield (
                        "[ERROR] There is no image attached, so there is "
                        "nothing to look at. Zaram will not describe a picture "
                        "it has not been given — attach it with the paperclip "
                        "and ask again."
                    )
                elif step.capability_id == "knowledge.search" and hasattr(service, "search_knowledge"):
                    query = step.input_data.get("query", "") or step.input_data.get("prompt", "")
                    persona = step.input_data.get("persona", "zaram_prime") or "zaram_prime"
                    logger.debug("Dispatcher: calling search_knowledge query='%s...' persona=%s", query[:50], persona)
                    yield from self._execute_with_fallback(
                        lambda: service.search_knowledge(query, persona),
                        step.capability_id,
                        query,
                        "knowledge search",
                    )
                elif hasattr(service, "generate_response"):
                    prompt = step.input_data.get("prompt", "")
                    # Carried on `input_data` rather than as a new argument to
                    # `execute_step`, because that is what `input_data` is for
                    # and every other per-request value already travels there.
                    images = step.input_data.get("images") or None
                    logger.debug(
                        "Dispatcher: calling generate_response prompt='%s...' model=%s images=%s",
                        prompt[:50], model, bool(images),
                    )
                    # `model` was logged here and then not passed, so every
                    # request answered with the engine default whatever it asked
                    # for. The log made it look plumbed.
                    # **Passed only when there are some.** `generate_response`
                    # is implemented by every model service and by a dozen test
                    # doubles, and handing all of them a fourth argument broke
                    # thirteen tests — including the provenance and outbound-
                    # query invariants, which are the two this repository can
                    # least afford to have red for an unrelated reason.
                    #
                    # An implementation that cannot take images still fails
                    # loudly when one is actually attached: the `TypeError`
                    # surfaces through the fallback path and is reported. What
                    # it no longer does is fail when no image is involved.
                    yield from self._execute_with_fallback(
                        lambda: (
                            service.generate_response(prompt, system_prompt, model, images)
                            if images
                            else service.generate_response(prompt, system_prompt, model)
                        ),
                        step.capability_id,
                        prompt[:100] if prompt else "empty",
                        "response generation",
                    )
                else:
                    yield f"[WARN] Service for {step.capability_id} does not support generate_response."
            else:
                yield f"[WARN] Runtime {runtime.get_runtime_id()} does not expose a service or execute method."
        except Exception as e:
            logger.error(
                "Dispatcher: CRITICAL ERROR for %s: %s: %s",
                step.capability_id,
                type(e).__name__,
                e,
            )
            traceback.print_exc()
            yield self._fallback_response(step.capability_id, str(e))

    # ------------------------------------------------------------------
    # Drawing, which is the one step that reports itself while it runs
    # ------------------------------------------------------------------

    def _execute_image_step(self, runtime: Any, step: ExecutionStep) -> Iterator[str]:
        """Run an image step, reporting each denoising step as it lands.

        Why this is not `run_sync` like every other capability: that blocks the
        calling thread until the coroutine returns, and drawing runs for tens
        of seconds. Everything reportable would arrive at the end, which is the
        same as reporting nothing — the wait is the whole problem being solved.

        With code you watch it being written and the delay explains itself. An
        image is silent for its entire duration unless something says
        otherwise, and a diffusion pipeline emits a callback per step, so what
        is reported here is **measured**. There is no time remaining in this
        method and none in the payload: seconds-left is a guess until several
        steps have run, and a confident wrong number is worse than no number.
        """
        import queue
        import time

        from core.async_bridge import _background_loop

        updates: "queue.Queue[dict]" = queue.Queue()

        payload = dict(step.input_data or {})
        # Filled from the sampling thread; `Queue.put` is what makes that safe.
        payload["progress_sink"] = updates.put

        future = asyncio.run_coroutine_threadsafe(
            runtime.execute(step.capability_id, payload), _background_loop()
        )

        def drain() -> Iterator[str]:
            while True:
                try:
                    yield PROGRESS_MARKER + json.dumps(updates.get_nowait()) + "\n"
                except queue.Empty:
                    return

        while not future.done():
            yield from drain()
            # Long enough not to spin a core, short enough that a step lands
            # within one tick of finishing: SDXL steps take ~0.3s on the card
            # this was measured on, and a bar that updates four times a second
            # reads as continuous.
            time.sleep(0.05)
        yield from drain()

        try:
            result = future.result()
        except Exception as error:  # pragma: no cover - defended, not expected
            logger.exception("Image step raised")
            yield f"[FALLBACK] {step.capability_id} failed: {error}\n"
            return

        if isinstance(result, dict) and result.get("success"):
            # One marker line per picture, because each is its own artifact
            # with its own record, path and download. The conversation draws a
            # *batch* as one card with a grid in it, and that grouping is a
            # rendering decision — making it a second artifact shape here would
            # be something Work then has to understand too.
            cards = result.get("artifacts") or (
                [result["artifact"]] if result.get("artifact") else []
            )
            for card in cards:
                yield ARTIFACT_MARKER + json.dumps(card) + "\n"
            if not cards:
                yield f"[FALLBACK] {step.capability_id} produced no image\n"
            return

        error = result.get("error", "unknown") if isinstance(result, dict) else "unknown"
        remedy = result.get("remedy", "") if isinstance(result, dict) else ""
        # `[ERROR]`, not `[FALLBACK]`, when nothing on the machine can draw.
        # A fallback invites the engine to answer some other way, and the only
        # other way available is a text model writing about a picture it never
        # made — the exact failure this capability exists to prevent.
        marker = (
            "[ERROR]" if isinstance(result, dict) and result.get("unavailable")
            else "[FALLBACK]"
        )
        yield f"{marker} {error}{(' ' + remedy) if remedy else ''}\n"

    # ------------------------------------------------------------------
    # Async dispatch with ExecutionContext (new interface)
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        step: ExecutionStep,
        context: ExecutionContext,
        model: str | None = None,
        system_prompt: str = "",
    ) -> Any:
        """Dispatch a step asynchronously using an ExecutionContext.

        This is the new async interface that supports cancellation,
        retry, and tracing via the ExecutionContext.
        """
        context.check_cancellation()

        runtime = self._router.resolve(step.capability_id)
        logger.debug(
            "Dispatcher: dispatch capability=%s runtime=%s correlation=%s",
            step.capability_id,
            runtime.get_runtime_id(),
            context.correlation_id,
        )

        if hasattr(runtime, "execute"):
            result = await runtime.execute(step.capability_id, step.input_data or {})
            return result

        if hasattr(runtime, "get_service"):
            service = runtime.get_service()
            if step.capability_id == "knowledge.search" and hasattr(service, "search_knowledge"):
                query = step.input_data.get("query", "") or step.input_data.get("prompt", "")
                persona = step.input_data.get("persona", "zaram_prime") or "zaram_prime"
                return list(service.search_knowledge(query, persona))
            elif hasattr(service, "generate_response"):
                prompt = step.input_data.get("prompt", "")
                return list(service.generate_response(prompt, system_prompt, model))

        return {"error": f"No handler for capability {step.capability_id}"}

    async def dispatch_stream(
        self,
        step: ExecutionStep,
        context: ExecutionContext,
        model: str | None = None,
        system_prompt: str = "",
    ) -> Iterator[str]:
        """Dispatch a step with streaming output using an ExecutionContext."""
        context.check_cancellation()

        runtime = self._router.resolve(step.capability_id)

        if hasattr(runtime, "get_service"):
            service = runtime.get_service()
            if hasattr(service, "generate_response"):
                prompt = step.input_data.get("prompt", "")
                for token in service.generate_response(prompt, system_prompt, model):
                    context.check_cancellation()
                    yield token
                return

        # Fall back to non-streaming
        result = await self.dispatch(step, context, model, system_prompt)
        if isinstance(result, str):
            yield result
        elif isinstance(result, dict):
            yield json.dumps(result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _execute_with_fallback(
        self,
        func: Any,
        capability_id: str,
        input_desc: str,
        operation: str,
    ) -> Iterator[str]:
        """Execute a function with graceful fallback on failure."""
        try:
            yield from func()
        except Exception as e:
            logger.warning(
                "Dispatcher: %s (%s) failed: %s: %s",
                capability_id,
                operation,
                type(e).__name__,
                e,
            )
            yield self._fallback_response(capability_id, f"{operation} failed: {e}")

    def _fallback_response(self, capability_id: str, error: str) -> str:
        """Generate a fallback JSON response for failed capabilities."""
        if capability_id == "knowledge.search":
            return json.dumps({
                "results": [],
                "total_results": 0,
                "providers_consulted": [],
                "provider_status": {},
                "latency_ms": 0,
                "error": error,
                "fallback": True,
            })
        return f"[FALLBACK] {capability_id} unavailable: {error}"
