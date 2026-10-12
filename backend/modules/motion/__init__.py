"""Motion Generation Module — Code-to-Frame video generation engine.

This module implements an offline video/motion graphics generation engine using
the "Code-to-Frame" architecture pattern. A local LLM writes declarative,
time-stamped animation script models (MotionScript), which are compiled to
HTML5 timelines (CSS Animations / Web Animations API) and rendered locally
using a headless browser context (Playwright).

The pipeline:
    User Request → MotionScript (JSON) → HTML5 Timeline → WebM/MP4 Video → Artifact

Key constraints from CLAUDE.md:
- Absolute chronological seek contract — no unrestricted loops
- Declarative, time-stamped keyframes only
- Standard CSS animations or Web Animations API
- Lightweight rendering blocks
- Generative tier: creates new artifacts, changes nothing existing
"""

from .contracts import (
    Keyframe,
    MotionLayer,
    MotionScript,
    MotionAsset,
    LayerType,
    ASPECT_RATIOS,
    MAX_DURATION,
    DEFAULT_ASPECT_RATIO,
)

from .generator import (
    build_system_prompt,
    build_user_prompt,
    parse_response,
    validate_script,
    MotionScriptParseError,
    MotionScriptValidationError,
)

from .compiler import compile_script, CompilationError
from .renderer import render_to_video, RenderError, check_playwright_available
from .runtime import MotionRuntime, GENERATE

__all__ = [
    # Contracts
    "Keyframe",
    "MotionLayer",
    "MotionScript",
    "MotionAsset",
    "LayerType",
    "ASPECT_RATIOS",
    "MAX_DURATION",
    "DEFAULT_ASPECT_RATIO",
    # Generator
    "build_system_prompt",
    "build_user_prompt",
    "parse_response",
    "validate_script",
    "MotionScriptParseError",
    "MotionScriptValidationError",
    # Compiler
    "compile_script",
    "CompilationError",
    # Renderer
    "render_to_video",
    "RenderError",
    "check_playwright_available",
    # Runtime
    "MotionRuntime",
    "GENERATE",
]