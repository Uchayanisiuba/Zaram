"""Core types for the pipeline infrastructure."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Protocol, Callable, Awaitable


class FilterPhase(Enum):
    """When a filter runs in the pipeline."""
    INLET = "inlet"      # Before LLM call
    OUTLET = "outlet"    # After LLM response


class FilterPriority(IntEnum):
    """Filter execution order: lower runs first."""
    SECURITY = 10        # PII, egress guard
    CONTEXT = 20         # Spine injection, token budget
    TRANSFORM = 30       # Format normalization
    LOGGING = 90         # Audit, metrics


@dataclass
class PipelineContext:
    """Context passed through the pipeline."""
    request: Dict[str, Any]                    # Original request
    response: Optional[Dict[str, Any]] = None  # Response (outlet only)
    session_id: str = "default"
    user_id: str = "user"
    project_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FilterResult:
    """Result of a filter execution."""
    modified_request: Optional[Dict[str, Any]] = None
    modified_response: Optional[Dict[str, Any]] = None
    blocked: bool = False
    block_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_modifications(self) -> bool:
        return self.modified_request is not None or self.modified_response is not None


class InletFilter(Protocol):
    """Protocol for inlet filters (pre-LLM)."""
    priority: FilterPriority
    
    async def process(self, request: Dict[str, Any], context: PipelineContext) -> FilterResult:
        """Process the request before it goes to the LLM."""
        ...


class OutletFilter(Protocol):
    """Protocol for outlet filters (post-LLM)."""
    priority: FilterPriority
    
    async def process(self, response: Dict[str, Any], context: PipelineContext) -> FilterResult:
        """Process the response after it comes from the LLM."""
        ...


# Base classes for easier implementation
class BaseInletFilter:
    """Base class for inlet filters."""
    priority: FilterPriority = FilterPriority.CONTEXT
    
    async def process(self, request: Dict[str, Any], context: PipelineContext) -> FilterResult:
        raise NotImplementedError


class BaseOutletFilter:
    """Base class for outlet filters."""
    priority: FilterPriority = FilterPriority.LOGGING
    
    async def process(self, response: Dict[str, Any], context: PipelineContext) -> FilterResult:
        raise NotImplementedError


# Type aliases for filter collections
InletFilterType = Callable[[Dict[str, Any], PipelineContext], Awaitable[FilterResult]]
OutletFilterType = Callable[[Dict[str, Any], PipelineContext], Awaitable[FilterResult]]