# backend/core/pipeline/__init__.py
"""Phase 1 Pipeline Infrastructure - Inlet/Outlet filters for context injection, egress enforcement, and privacy policy interception."""

from .types import (
    FilterPhase,
    FilterPriority,
    PipelineContext,
    FilterResult,
    InletFilter,
    OutletFilter,
)
from .registry import FilterRegistry
from .pipeline import Pipeline
from .builtins import (
    SpineInjector,
    EgressGuard,
    PIIScrubber,
    TokenBudgetEnforcer,
)

__all__ = [
    "FilterPhase",
    "FilterPriority",
    "PipelineContext",
    "FilterResult",
    "InletFilter",
    "OutletFilter",
    "FilterRegistry",
    "Pipeline",
    "SpineInjector",
    "EgressGuard",
    "PIIScrubber",
    "TokenBudgetEnforcer",
]