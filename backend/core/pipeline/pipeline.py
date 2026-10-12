"""Pipeline orchestrator - runs inlet filters, LLM, then outlet filters."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Callable, Awaitable

from .types import PipelineContext, FilterResult
from .registry import FilterRegistry


class Pipeline:
    """Main pipeline orchestrator."""
    
    def __init__(
        self,
        registry: FilterRegistry,
        egress_gate: Any = None,
        spine: Any = None,
        llm_call: Optional[Callable[[Dict[str, Any], PipelineContext], Awaitable[Dict[str, Any]]]] = None,
    ):
        self.registry = registry
        self.egress_gate = egress_gate
        self.spine = spine
        self._llm_call = llm_call
        self._enabled = os.getenv("ZARAM_PIPELINE_ENABLED", "false").lower() == "true"
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    def enable(self) -> None:
        self._enabled = True
    
    def disable(self) -> None:
        self._enabled = False
    
    async def process_inlet(self, request: Dict[str, Any], context: PipelineContext) -> Dict[str, Any]:
        """Run all inlet filters in priority order."""
        if not self._enabled:
            return request
        
        current_request = request
        inlet_filters = self.registry.get_inlet_filters()
        
        for filter in inlet_filters:
            try:
                result = await filter.process(current_request, context)
                
                if result.blocked:
                    raise PipelineBlockedError(
                        f"Inlet filter '{filter.__class__.__name__}' blocked request: {result.block_reason}"
                    )
                
                if result.modified_request:
                    current_request = result.modified_request
                
                # Merge metadata
                context.metadata.setdefault("pipeline_inlet", {})[filter.__class__.__name__] = result.metadata
                
            except PipelineBlockedError:
                raise
            except Exception as e:
                # Log but don't block on filter errors
                context.metadata.setdefault("pipeline_errors", []).append({
                    "filter": filter.__class__.__name__,
                    "phase": "inlet",
                    "error": str(e),
                })
        
        return current_request
    
    async def process_outlet(self, response: Dict[str, Any], context: PipelineContext) -> Dict[str, Any]:
        """Run all outlet filters in priority order."""
        if not self._enabled:
            return response
        
        current_response = response
        context.response = response
        outlet_filters = self.registry.get_outlet_filters()
        
        for filter in outlet_filters:
            try:
                result = await filter.process(current_response, context)
                
                if result.blocked:
                    raise PipelineBlockedError(
                        f"Outlet filter '{filter.__class__.__name__}' blocked response: {result.block_reason}"
                    )
                
                if result.modified_response:
                    current_response = result.modified_response
                
                # Merge metadata
                context.metadata.setdefault("pipeline_outlet", {})[filter.__class__.__name__] = result.metadata
                
            except PipelineBlockedError:
                raise
            except Exception as e:
                # Log but don't block on filter errors
                context.metadata.setdefault("pipeline_errors", []).append({
                    "filter": filter.__class__.__name__,
                    "phase": "outlet",
                    "error": str(e),
                })
        
        return current_response
    
    async def run(
        self,
        request: Dict[str, Any],
        context: PipelineContext,
    ) -> Dict[str, Any]:
        """Full pipeline: inlet -> LLM -> outlet."""
        # Process inlet filters
        processed_request = await self.process_inlet(request, context)
        
        # Call LLM if available
        if self._llm_call:
            context.request = processed_request
            response = await self._llm_call(processed_request, context)
        else:
            # No LLM call - return request as response (for testing)
            response = {"text": "", "model": "none", "pipeline_only": True}
        
        # Process outlet filters
        final_response = await self.process_outlet(response, context)
        
        return final_response
    
    def get_status(self) -> Dict[str, Any]:
        """Get pipeline status."""
        return {
            "enabled": self._enabled,
            "filters": self.registry.list_filters(),
        }


class PipelineBlockedError(Exception):
    """Raised when a filter blocks the pipeline."""
    pass


# Global pipeline instance (set by bootstrapper)
_pipeline: Optional[Pipeline] = None


def get_pipeline() -> Optional[Pipeline]:
    """Get the global pipeline instance."""
    return _pipeline


def set_pipeline(pipeline: Pipeline) -> None:
    """Set the global pipeline instance."""
    global _pipeline
    _pipeline = pipeline


async def run_pipeline(
    request: Dict[str, Any],
    session_id: str = "default",
    user_id: str = "user",
    project_id: Optional[str] = None,
    llm_call: Optional[Callable[[Dict[str, Any], PipelineContext], Awaitable[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Convenience function to run the pipeline."""
    pipeline = get_pipeline()
    if pipeline is None:
        # Pipeline not initialized - return request as-is
        return request if llm_call is None else await llm_call(request, PipelineContext(
            request=request,
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
        ))
    
    context = PipelineContext(
        request=request,
        session_id=session_id,
        user_id=user_id,
        project_id=project_id,
    )
    
    return await pipeline.run(request, context)