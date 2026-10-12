"""TokenBudgetEnforcer - Inlet filter that enforces token budget on context."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..types import BaseInletFilter, FilterPriority, PipelineContext, FilterResult
from ...context_budget import ContextBudget, budget_for, estimate_tokens


class TokenBudgetEnforcer(BaseInletFilter):
    """Inlet filter that compacts context to fit within token budget."""
    
    priority = FilterPriority.CONTEXT
    
    def __init__(
        self,
        model: Optional[str] = None,
        reserve_tokens: int = 1000,
        context_budget: Optional[ContextBudget] = None,
    ):
        self.model = model
        self.reserve_tokens = reserve_tokens
        self.context_budget = context_budget
    
    async def process(self, request: Dict[str, Any], context: PipelineContext) -> FilterResult:
        """Enforce token budget on the request."""
        if self.context_budget is None and self.model is None:
            return FilterResult(metadata={"skipped": "no_budget_or_model"})
        
        try:
            # Get budget
            if self.context_budget:
                budget = self.context_budget
            else:
                budget = budget_for(self.model)
            
            # Calculate current token usage
            system_prompt = request.get("system_prompt", "") or ""
            user_prompt = request.get("text") or request.get("prompt") or ""
            
            system_tokens = estimate_tokens(system_prompt)
            user_tokens = estimate_tokens(user_prompt)
            
            # Account for recalled context (injected by SpineInjector)
            recalled_tokens = 0
            if "pipeline_inlet" in context.metadata:
                for filter_name, meta in context.metadata["pipeline_inlet"].items():
                    if "provenance" in meta:
                        for prov in meta["provenance"]:
                            recalled_tokens += estimate_tokens(prov.get("content", ""))
            
            total_input = system_tokens + user_tokens + recalled_tokens
            available = budget.input_tokens - self.reserve_tokens
            
            metadata = {
                "budget_input": budget.input_tokens,
                "reserve": self.reserve_tokens,
                "available": available,
                "system_tokens": system_tokens,
                "user_tokens": user_tokens,
                "recalled_tokens": recalled_tokens,
                "total_input": total_input,
            }
            
            if total_input <= available:
                metadata["within_budget"] = True
                return FilterResult(metadata=metadata)
            
            # Over budget - need to compact
            metadata["within_budget"] = False
            metadata["over_by"] = total_input - available
            
            # Compact the context (drop lowest importance facts first)
            compacted_request, dropped = await self._compact_context(
                request, context, available, system_tokens, user_tokens
            )
            
            metadata["dropped_facts"] = dropped
            metadata["final_tokens"] = total_input - sum(estimate_tokens(f.get("content", "")) for f in dropped)
            
            return FilterResult(
                modified_request=compacted_request,
                metadata=metadata,
            )
            
        except Exception as e:
            return FilterResult(
                metadata={"error": str(e)},
            )
    
    async def _compact_context(
        self,
        request: Dict[str, Any],
        context: PipelineContext,
        available: int,
        system_tokens: int,
        user_tokens: int,
    ) -> tuple[Dict[str, Any], List[Dict]]:
        """Compact context by dropping lowest-importance facts."""
        dropped = []
        compacted = dict(request)
        
        # Extract provenance from metadata
        provenance = []
        if "pipeline_inlet" in context.metadata:
            for filter_name, meta in context.metadata["pipeline_inlet"].items():
                if "provenance" in meta:
                    provenance.extend(meta["provenance"])
        
        # Sort by relevance (lowest first)
        provenance.sort(key=lambda p: p.get("relevance", 0))
        
        # Calculate how many tokens we need to drop
        current_total = system_tokens + user_tokens
        for prov in provenance:
            current_total += estimate_tokens(prov.get("content", ""))
        
        tokens_to_drop = current_total - available
        if tokens_to_drop <= 0:
            return compacted, dropped
        
        # Drop facts until under budget
        kept_provenance = []
        dropped_tokens = 0
        
        for prov in provenance:
            content = prov.get("content", "")
            content_tokens = estimate_tokens(content)
            
            # Never drop pinned facts
            if prov.get("pinned", False):
                kept_provenance.append(prov)
                continue
            
            if dropped_tokens + content_tokens <= tokens_to_drop:
                dropped.append(prov)
                dropped_tokens += content_tokens
            else:
                kept_provenance.append(prov)
        
        # Rebuild system prompt with kept facts
        if kept_provenance:
            context_block = self._build_context_block(kept_provenance)
            system_prompt = compacted.get("system_prompt", "")
            if system_prompt and "=== Relevant Context from Spine ===" in system_prompt:
                # Replace the context block
                parts = system_prompt.split("=== Relevant Context from Spine ===")
                compacted["system_prompt"] = parts[0] + "\n\n" + context_block
            elif system_prompt:
                compacted["system_prompt"] = system_prompt + "\n\n" + context_block
            else:
                compacted["system_prompt"] = context_block
        else:
            # Remove context block entirely
            system_prompt = compacted.get("system_prompt", "")
            if "=== Relevant Context from Spine ===" in system_prompt:
                parts = system_prompt.split("=== Relevant Context from Spine ===")
                compacted["system_prompt"] = parts[0].rstrip()
        
        return compacted, dropped
    
    def _build_context_block(self, facts: List[Dict]) -> str:
        """Build context block from provenance."""
        if not facts:
            return ""
        
        lines = ["=== Relevant Context from Spine ==="]
        
        for i, fact in enumerate(facts, 1):
            content = fact.get("content", "").strip()
            origin = fact.get("origin", "unknown")
            scope = fact.get("scope", "global")
            relevance = fact.get("relevance", 0)
            
            lines.append(f"[{i}] {content}")
            lines.append(f"    Source: {origin} | Scope: {scope} | Relevance: {relevance:.2f}")
        
        lines.append("=== End Context ===")
        return "\n".join(lines)


def create_token_budget_enforcer(
    model: Optional[str] = None,
    reserve_tokens: int = 1000,
    context_budget: Optional[ContextBudget] = None,
) -> TokenBudgetEnforcer:
    """Factory function to create a TokenBudgetEnforcer."""
    return TokenBudgetEnforcer(
        model=model,
        reserve_tokens=reserve_tokens,
        context_budget=context_budget,
    )