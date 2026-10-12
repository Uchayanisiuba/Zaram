"""SpineInjector - Inlet filter that injects relevant Spine facts into the request."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..types import BaseInletFilter, FilterPriority, PipelineContext, FilterResult
from ...contracts import ExecutionPlan


class SpineInjector(BaseInletFilter):
    """Inlet filter that retrieves relevant facts from the Spine and injects them as context."""
    
    priority = FilterPriority.CONTEXT
    
    def __init__(
        self,
        memory_runtime: Any,
        max_facts: int = 6,
        min_relevance: float = 0.3,
    ):
        self.memory_runtime = memory_runtime
        self.max_facts = max_facts
        self.min_relevance = min_relevance
    
    async def process(self, request: Dict[str, Any], context: PipelineContext) -> FilterResult:
        """Retrieve relevant facts and inject into system prompt."""
        if self.memory_runtime is None:
            return FilterResult(metadata={"skipped": "no_memory_runtime"})
        
        # Get the user's query from the request
        query = request.get("text") or request.get("prompt") or ""
        if not query:
            return FilterResult(metadata={"skipped": "no_query"})
        
        try:
            # Build scope from project_id
            scope = context.project_id
            if scope:
                from runtimes.memory.contracts import project_scope
                scope = project_scope(scope)
            
            # Retrieve from Spine
            recalled = await self.memory_runtime.retrieve(
                query=query,
                max_results=self.max_facts,
                scope=scope,
                session_id=context.session_id,
                user_id=context.user_id,
            )
            
            # Filter by relevance
            relevant_facts = [
                r for r in recalled
                if (r.relevance or r.score or 0) >= self.min_relevance
            ]
            
            if not relevant_facts:
                return FilterResult(metadata={"recalled": 0, "injected": 0})
            
            # Build context block
            context_block = self._build_context_block(relevant_facts)
            
            # Inject into system prompt
            modified_request = dict(request)
            system_prompt = modified_request.get("system_prompt", "")
            
            if context_block:
                if system_prompt:
                    modified_request["system_prompt"] = f"{system_prompt}\n\n{context_block}"
                else:
                    modified_request["system_prompt"] = context_block
            
            # Store provenance for citations
            provenance = []
            for fact in relevant_facts:
                record = getattr(fact, "record", None)
                if record:
                    provenance.append({
                        "id": record.id,
                        "content": record.content[:200],
                        "origin": record.origin.value if hasattr(record.origin, "value") else str(record.origin),
                        "scope": record.scope,
                        "relevance": fact.relevance or fact.score,
                    })
            
            return FilterResult(
                modified_request=modified_request,
                metadata={
                    "recalled": len(recalled),
                    "injected": len(relevant_facts),
                    "provenance": provenance,
                },
            )
            
        except Exception as e:
            return FilterResult(
                metadata={"error": str(e)},
            )
    
    def _build_context_block(self, facts: List[Any]) -> str:
        """Build the context block from recalled facts."""
        if not facts:
            return ""
        
        lines = ["=== Relevant Context from Spine ==="]
        
        for i, fact in enumerate(facts, 1):
            record = getattr(fact, "record", None)
            if not record:
                continue
            
            content = record.content.strip()
            origin = record.origin.value if hasattr(record.origin, "value") else str(record.origin)
            scope = record.scope
            relevance = fact.relevance or fact.score or 0
            
            lines.append(f"[{i}] {content}")
            lines.append(f"    Source: {origin} | Scope: {scope} | Relevance: {relevance:.2f}")
        
        lines.append("=== End Context ===")
        return "\n".join(lines)


def create_spine_injector(
    memory_runtime: Any,
    max_facts: int = 6,
    min_relevance: float = 0.3,
) -> SpineInjector:
    """Factory function to create a SpineInjector."""
    return SpineInjector(
        memory_runtime=memory_runtime,
        max_facts=max_facts,
        min_relevance=min_relevance,
    )