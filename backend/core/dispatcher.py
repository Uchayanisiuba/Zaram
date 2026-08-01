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

from core.capability_router import CapabilityRouter
from core.contracts import ExecutionStep
from core.execution_context import ExecutionContext

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
        model: str = "gemma3:latest",
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
                result = asyncio.run(runtime.execute(step.capability_id, step.input_data or {}))

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
                if step.capability_id.startswith("vision.") and hasattr(service, "analyze_image"):
                    prompt = step.input_data.get("prompt", "")
                    image = step.input_data.get("image", "")
                    logger.debug("Dispatcher: calling analyze_image prompt='%s...'", prompt[:50])
                    yield from service.analyze_image(prompt, image, system_prompt)
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
                    logger.debug("Dispatcher: calling generate_response prompt='%s...' model=%s", prompt[:50], model)
                    yield from self._execute_with_fallback(
                        lambda: service.generate_response(prompt, system_prompt),
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
    # Async dispatch with ExecutionContext (new interface)
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        step: ExecutionStep,
        context: ExecutionContext,
        model: str = "gemma3:latest",
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
                return list(service.generate_response(prompt, system_prompt))

        return {"error": f"No handler for capability {step.capability_id}"}

    async def dispatch_stream(
        self,
        step: ExecutionStep,
        context: ExecutionContext,
        model: str = "gemma3:latest",
        system_prompt: str = "",
    ) -> Iterator[str]:
        """Dispatch a step with streaming output using an ExecutionContext."""
        context.check_cancellation()

        runtime = self._router.resolve(step.capability_id)

        if hasattr(runtime, "get_service"):
            service = runtime.get_service()
            if hasattr(service, "generate_response"):
                prompt = step.input_data.get("prompt", "")
                for token in service.generate_response(prompt, system_prompt):
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
