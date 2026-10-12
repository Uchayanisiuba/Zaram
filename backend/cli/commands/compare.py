"""zcode compare command - feature comparison tables."""

import typer
from typing import Optional, List

from ..visual import (
    render_comparison,
    render_comparison_list,
    get_comparison_data,
)


app = typer.Typer(
    name="compare",
    help="Compare features across systems",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def compare(
    topic: Optional[str] = typer.Argument(
        None,
        help="Topic to compare: memory, browser, search, pipeline",
    ),
    list_topics: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List available comparison topics",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Machine-readable JSON output",
    ),
) -> None:
    """Show feature comparison tables."""
    if list_topics:
        print(render_comparison_list())
        return
    
    if not topic:
        print(render_comparison_list())
        return
    
    result = render_comparison(topic, as_json=as_json)
    print(result)


if __name__ == "__main__":
    app()