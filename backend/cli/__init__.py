# backend/cli/__init__.py
"""CLI package for Zaram command-line interface."""

from .main import (
    _credential,
    _token_path,
    PROGRAM,
    app,
    _fail,
    pair,
    recall,
    remember,
    correct,
    show,
    projects,
    main,
)

from zaram_mcp import Spine, DEFAULT_API

# Provide _client as a function that dynamically imports from main (allows mocking)
def _client():
    from .main import _client_factory
    return _client_factory()

# Factory function for Spine client - can be replaced for mocking
def _client_factory() -> Spine:
    from .main import _credential
    import os
    return Spine(_credential(), os.environ.get("ZARAM_API") or DEFAULT_API)

from .visual import (
    render_comparison,
    render_comparison_list,
    render_schema,
    render_schema_list,
    render_analytics_chart,
    render_analytics_list,
    render_dashboard,
)

__all__ = [
    "_client",
    "_client_factory",
    "_credential",
    "_token_path",
    "PROGRAM",
    "app",
    "_fail",
    "pair",
    "recall",
    "remember",
    "correct",
    "show",
    "projects",
    "main",
    "render_comparison",
    "render_comparison_list",
    "render_schema",
    "render_schema_list",
    "render_analytics_chart",
    "render_analytics_list",
    "render_dashboard",
]