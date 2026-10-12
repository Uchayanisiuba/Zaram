"""High-level render functions combining tables, graphs, and charts."""

from typing import Optional
from .tables import (
    ComparisonTableRenderer,
    FeatureRow,
    FeatureStatus,
    render_comparison,
    get_comparison_data,
    MEMORY_COMPARISON_FEATURES,
    BROWSER_COMPARISON_FEATURES,
    SEARCH_COMPARISON_FEATURES,
    PIPELINE_COMPARISON_FEATURES,
)
from .graphs import (
    GraphRenderer,
    Node,
    Edge,
    NodeType,
    EdgeType,
    render_schema,
    create_memory_schema,
    create_egress_schema,
    create_pipeline_schema,
    create_browser_schema,
    create_project_memory_schema,
    SCHEMAS,
)
from .charts import (
    ChartRenderer,
    ChartConfig,
    ChartPreset,
    render_analytics,
    get_token_speed_data,
    get_latency_data,
    get_memory_decay_data,
    get_egress_bytes_data,
)


def render_memory_comparison(as_json: bool = False) -> str:
    """Render the memory systems feature comparison."""
    return render_comparison("memory", as_json=as_json)


def render_browser_comparison(as_json: bool = False) -> str:
    """Render the browser automation comparison."""
    return render_comparison("browser", as_json=as_json)


def render_search_comparison(as_json: bool = False) -> str:
    """Render the web search comparison."""
    return render_comparison("search", as_json=as_json)


def render_pipeline_comparison(as_json: bool = False) -> str:
    """Render the pipeline architecture comparison."""
    return render_comparison("pipeline", as_json=as_json)


def render_pipeline_schema(as_graph_easy: bool = False) -> str:
    """Render the pipeline architecture schema."""
    return render_schema("pipeline", as_graph_easy=as_graph_easy)


def render_memory_schema(as_graph_easy: bool = False) -> str:
    """Render the memory architecture schema."""
    return render_schema("memory", as_graph_easy=as_graph_easy)


def render_egress_schema(as_graph_easy: bool = False) -> str:
    """Render the egress pipeline schema."""
    return render_schema("egress", as_graph_easy=as_graph_easy)


def render_browser_schema(as_graph_easy: bool = False) -> str:
    """Render the browser automation schema."""
    return render_schema("browser", as_graph_easy=as_graph_easy)


def render_project_schema(project_id: Optional[str] = None, as_graph_easy: bool = False) -> str:
    """Render the project-scoped memory schema."""
    # For now, project_id doesn't change the schema but could in future
    return render_schema("project", as_graph_easy=as_graph_easy)


def render_analytics_chart(
    metric: str,
    hours: int = 24,
    as_json: bool = False,
) -> str:
    """Render an analytics chart."""
    return render_analytics(metric, hours=hours, as_json=as_json)


def render_dashboard() -> str:
    """Render a full dashboard with key metrics."""
    sections = []
    
    sections.append("=" * 60)
    sections.append("ZARAM SYSTEM DASHBOARD")
    sections.append("=" * 60)
    
    # Memory comparison summary
    sections.append("\n[bold]MEMORY SYSTEMS COMPARISON[/bold]")
    sections.append(render_memory_comparison())
    
    # Pipeline schema
    sections.append("\n[bold]PIPELINE ARCHITECTURE[/bold]")
    sections.append(render_pipeline_schema())
    
    # Token speed chart
    sections.append("\n[bold]TOKEN GENERATION SPEED (24h)[/bold]")
    sections.append(render_analytics_chart("tokens", hours=24))
    
    # Latency chart
    sections.append("\n[bold]INFERENCE LATENCY (24h)[/bold]")
    sections.append(render_analytics_chart("latency", hours=24))
    
    # Egress chart
    sections.append("\n[bold]EGRESS BYTES (24h)[/bold]")
    sections.append(render_analytics_chart("egress", hours=24))
    
    return "\n".join(sections)


def render_schema_list() -> str:
    """List all available schemas."""
    lines = ["Available Schemas:", "=" * 30]
    for name, func in SCHEMAS.items():
        graph = func()
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)
        lines.append(f"  {name:12} - {node_count} nodes, {edge_count} edges")
    return "\n".join(lines)


def render_comparison_list() -> str:
    """List all available comparisons."""
    lines = ["Available Comparisons:", "=" * 30]
    lines.append("  memory       - Memory systems (mem0, Zaram Spine, browser-use, Open WebUI)")
    lines.append("  browser      - Browser automation tools")
    lines.append("  search       - Web search providers")
    lines.append("  pipeline     - Pipeline architectures")
    return "\n".join(lines)


def render_analytics_list() -> str:
    """List all available analytics metrics."""
    lines = ["Available Analytics Metrics:", "=" * 30]
    lines.append("  tokens       - Token generation speed (tokens/sec)")
    lines.append("  latency      - Inference latency by provider (ms)")
    lines.append("  decay        - Memory importance decay over time")
    lines.append("  egress       - Egress bytes by data class")
    return "\n".join(lines)


__all__ = [
    # Tables
    "ComparisonTableRenderer",
    "FeatureRow",
    "FeatureStatus",
    "render_comparison",
    "get_comparison_data",
    "MEMORY_COMPARISON_FEATURES",
    "BROWSER_COMPARISON_FEATURES",
    "SEARCH_COMPARISON_FEATURES",
    "PIPELINE_COMPARISON_FEATURES",
    # Graphs
    "GraphRenderer",
    "Node",
    "Edge",
    "NodeType",
    "EdgeType",
    "render_schema",
    "create_memory_schema",
    "create_egress_schema",
    "create_pipeline_schema",
    "create_browser_schema",
    "create_project_memory_schema",
    "SCHEMAS",
    # Charts
    "ChartRenderer",
    "ChartConfig",
    "ChartPreset",
    "render_analytics",
    "get_token_speed_data",
    "get_latency_data",
    "get_memory_decay_data",
    "get_egress_bytes_data",
    # High-level
    "render_memory_comparison",
    "render_browser_comparison",
    "render_search_comparison",
    "render_pipeline_comparison",
    "render_pipeline_schema",
    "render_memory_schema",
    "render_egress_schema",
    "render_browser_schema",
    "render_project_schema",
    "render_analytics_chart",
    "render_dashboard",
    "render_schema_list",
    "render_comparison_list",
    "render_analytics_list",
]