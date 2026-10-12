"""Presenton Renderer — Renders Presenton IR to PPTX/PDF via Presenton CLI."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class RenderError(Exception):
    """Raised when Presenton rendering fails."""
    pass


class PresentonNotFoundError(RenderError):
    """Raised when Presenton CLI is not installed."""
    pass


def _check_presenton_available() -> bool:
    """Check if Presenton CLI is available."""
    try:
        subprocess.run(
            ["presenton", "--version"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _render_via_cli(ir: Any, output_path: Path, format: str) -> None:
    """Invoke Presenton CLI with IR as stdin, binary as stdout."""
    if not _check_presenton_available():
        raise PresentonNotFoundError(
            "Presenton CLI not found. Install with: pip install presenton"
        )
    
    # Write IR to temp file for CLI consumption
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(ir.to_dict(), f)
        ir_path = Path(f.name)
    
    try:
        # Presenton CLI invocation pattern
        cmd = [
            "presenton", "render",
            "--input", str(ir_path),
            "--output", str(output_path),
            "--format", format,
        ]
        
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,  # Longer timeout for complex presentations
        )
    except subprocess.CalledProcessError as e:
        raise RenderError(f"Presenton CLI failed (exit {e.returncode}): {e.stderr}")
    except subprocess.TimeoutExpired:
        raise RenderError("Presenton render timed out after 120s")
    finally:
        ir_path.unlink(missing_ok=True)


def render_to_pptx(ir: Any, output_path: Path) -> None:
    """Render Presenton IR to PPTX using Presenton CLI."""
    _render_via_cli(ir, output_path, "pptx")


def render_to_pdf(ir: Any, output_path: Path) -> None:
    """Render Presenton IR to PDF using Presenton CLI."""
    _render_via_cli(ir, output_path, "pdf")