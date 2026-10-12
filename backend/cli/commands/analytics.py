"""zcode analytics command - data visualization charts."""

import typer
from typing import Optional

from ..visual import (
    render_analytics_chart,
    render_analytics_list,
    render_dashboard,
)


app = typer.Typer(
    name="analytics",
    help="Show analytics charts and metrics",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def analytics(
    metric: Optional[str] = typer.Argument(
        None,
        help="Metric to chart: tokens, latency, decay, egress",
    ),
    hours: int = typer.Option(
        24,
        "--hours",
        "-h",
        min=1,
        max=168,
        help="Hours of data to show (1-168)",
    ),
    list_metrics: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List available metrics",
    ),
    dashboard: bool = typer.Option(
        False,
        "--dashboard",
        "-d",
        help="Show full dashboard",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Machine-readable JSON output",
    ),
) -> None:
    """Show analytics charts."""
    if list_metrics:
        print(render_analytics_list())
        return
    
    if dashboard:
        print(render_dashboard())
        return
    
    if not metric:
        print(render_analytics_list())
        return
    
    result = render_analytics_chart(metric, hours=hours, as_json=as_json)
    print(result)


if __name__ == "__main__":
    app()