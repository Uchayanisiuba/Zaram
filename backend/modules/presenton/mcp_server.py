"""MCP Server for Presenton — Exposes presentation generation to local LLMs via tools."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from .contracts import PresentationScript, PresentationMeta, PresentationSlide, PresentationElement, PresentationTheme
from .compiler import compile_presentation, CompilationError
from .renderer import render_to_pptx, render_to_pdf, RenderError, PresentonNotFoundError
from .preview import render_preview_html

mcp = FastMCP("Zaram-Presenton-Engine")

ARTIFACT_DIR = Path(".kilo/artifacts/presenton")
TEMPLATE_DIR = Path(".kilo/templates/presenton")

# Ensure directories exist on import
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)


@mcp.tool()
def create_presentation_artifact(
    artifact_name: str,
    title: str,
    slides_data: str,  # JSON string of slides array
    theme_data: str = "{}",  # JSON string of theme override
    template_id: str = "corporate_dark_v1",
) -> str:
    """
    Creates a Presenton presentation artifact (JSON) — the sacred source of truth.
    
    The LLM calls this with structured slide data. We validate, enrich with theme,
    and persist the artifact. The binary PPTX/PDF is NOT created yet.
    
    Args:
        artifact_name: Unique name for this artifact (e.g., "q3_board_deck")
        title: Presentation title
        slides_data: JSON array of slide objects with layout, elements, speaker_notes
        theme_data: Optional JSON theme override (colors, fonts, spacing)
        template_id: Template to use (must exist in .kilo/templates/presenton/)
    
    Returns:
        Path to the stored artifact JSON
    """
    # Parse and validate input
    try:
        slides = json.loads(slides_data)
    except json.JSONDecodeError as e:
        return f"Invalid slides_data JSON: {e}"
    
    try:
        theme_override = json.loads(theme_data)
    except json.JSONDecodeError as e:
        return f"Invalid theme_data JSON: {e}"
    
    # Build PresentationScript (validates structure)
    try:
        script = PresentationScript(
            meta=PresentationMeta(title=title, template_id=template_id),
            slides=[_parse_slide(s) for s in slides],
            theme=_merge_theme(theme_override),
        )
    except ValueError as e:
        return f"Invalid presentation structure: {e}"
    
    # Persist artifact (source of truth)
    artifact_path = ARTIFACT_DIR / f"{artifact_name}.json"
    with open(artifact_path, "w") as f:
        json.dump(script.to_dict(), f, indent=2)
    
    return f"Presentation artifact stored at {artifact_path}. Ready for compilation."


@mcp.tool()
def compile_presentation_artifact(
    artifact_name: str,
    export_format: str = "pptx",  # "pptx" | "pdf"
) -> str:
    """
    Compiles a stored Presenton artifact to PPTX or PDF using Presenton engine.
    
    This is the deterministic compilation step — no LLM involvement.
    The artifact JSON is never modified; only the binary output is produced.
    
    Args:
        artifact_name: Name of artifact (without .json extension)
        export_format: "pptx" or "pdf"
    
    Returns:
        Path to the rendered binary asset
    """
    artifact_path = ARTIFACT_DIR / f"{artifact_name}.json"
    output_path = ARTIFACT_DIR / f"{artifact_name}.{export_format}"
    
    if not artifact_path.exists():
        return f"Error: Artifact '{artifact_name}' not found at {artifact_path}"
    
    # Load and validate artifact
    try:
        with open(artifact_path) as f:
            script_data = json.load(f)
        script = PresentationScript.from_dict(script_data)
    except Exception as e:
        return f"Failed to load artifact: {e}"
    
    # Compile to Presenton intermediate representation
    try:
        ir = compile_presentation(script)
    except CompilationError as e:
        return f"Compilation failed: {e}"
    
    # Render to binary via Presenton CLI
    try:
        if export_format == "pptx":
            render_to_pptx(ir, output_path)
        elif export_format == "pdf":
            render_to_pdf(ir, output_path)
        else:
            return f"Unsupported format: {export_format}"
    except PresentonNotFoundError as e:
        return str(e)
    except RenderError as e:
        return f"Render failed: {e}"
    except subprocess.TimeoutExpired:
        return "Compilation timed out (120s limit)"
    
    return f"Successfully rendered {export_format.upper()} to: {output_path} (artifact preserved)"


@mcp.tool()
def list_presentation_templates() -> str:
    """Returns available Presenton templates with their layouts and theme specs."""
    templates = []
    for tpl in TEMPLATE_DIR.glob("*.json"):
        try:
            with open(tpl) as f:
                templates.append(json.load(f))
        except Exception:
            pass
    if not templates:
        # Return default template spec
        return json.dumps([{
            "id": "corporate_dark_v1",
            "name": "Corporate Dark",
            "description": "Dark theme with cyan accent, Inter font",
            "layouts": ["title", "content", "two_column", "metric_focus", "quote", "section"],
        }], indent=2)
    return json.dumps(templates, indent=2)


@mcp.tool()
def get_artifact_preview(artifact_name: str) -> str:
    """Returns HTML preview of the presentation for in-conversation display."""
    artifact_path = ARTIFACT_DIR / f"{artifact_name}.json"
    if not artifact_path.exists():
        return f"Artifact '{artifact_name}' not found"
    
    try:
        with open(artifact_path) as f:
            script = PresentationScript.from_dict(json.load(f))
        return render_preview_html(script)
    except Exception as e:
        return f"Preview failed: {e}"


@mcp.tool()
def validate_presentation_script(script_json: str) -> str:
    """Validates a PresentationScript JSON without persisting.
    
    Useful for LLM to check its output before calling create_presentation_artifact.
    """
    try:
        data = json.loads(script_json)
        script = PresentationScript.from_dict(data)
        # If we get here, structure is valid
        slide_count = len(script.slides)
        element_count = sum(len(s.elements) for s in script.slides)
        return f"Valid: {slide_count} slides, {element_count} elements"
    except Exception as e:
        return f"Invalid: {e}"


def _parse_slide(data: dict) -> PresentationSlide:
    return PresentationSlide(
        layout=data.get("layout", "content"),
        background=data.get("background", ""),
        elements=[_parse_element(e) for e in data.get("elements", [])],
        speaker_notes=data.get("speaker_notes", ""),
    )


def _parse_element(data: dict) -> PresentationElement:
    return PresentationElement(
        type=data["type"],
        content=data["content"],
        style=data.get("style", ""),
        position=data.get("position"),
    )


def _merge_theme(override: dict) -> PresentationTheme:
    base = {
        "colors": {"primary": "#1e293b", "secondary": "#334155", "accent": "#22d3ee",
                   "background": "#0f172a", "text": "#f8fafc", "muted": "#94a3b8"},
        "fonts": {"heading": "Inter", "body": "Inter", "mono": "JetBrains Mono"},
        "spacing": {"base": 24, "lg": 32, "xl": 48},
    }
    # Deep merge override
    import copy
    merged = copy.deepcopy(base)
    _deep_merge(merged, override)
    return PresentationTheme(**merged)


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v