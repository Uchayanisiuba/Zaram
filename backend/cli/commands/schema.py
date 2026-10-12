"""zcode schema command - application schemas and flowcharts."""

import typer
from typing import Optional

from ..visual import (
    render_schema,
    render_schema_list,
    render_memory_schema,
    render_egress_schema,
    render_pipeline_schema,
    render_browser_schema,
    render_project_schema,
    SCHEMAS,
)


app = typer.Typer(
    name="schema",
    help="Show application schemas and flowcharts",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def schema(
    name: Optional[str] = typer.Argument(
        None,
        help="Schema name: memory, egress, pipeline, browser, project <project_id>",
    ),
    project_id: Optional[str] = typer.Option(
        None,
        "--project",
        "-p",
        help="Project ID for project-scoped schema",
    ),
    list_schemas: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List available schemas",
    ),
    graph_easy: bool = typer.Option(
        False,
        "--graph-easy",
        help="Output in Graph-Easy format",
    ),
) -> None:
    """Show ASCII flowcharts for system architectures."""
    if list_schemas:
        print(render_schema_list())
        return
    
    if not name:
        print(render_schema_list())
        return
    
    # Handle project schema with optional project_id
    if name.lower() == "project":
        result = render_project_schema(project_id=project_id, as_graph_easy=graph_easy)
    else:
        result = render_schema(name, as_graph_easy=graph_easy)
    
    print(result)


if __name__ == "__main__":
    app()