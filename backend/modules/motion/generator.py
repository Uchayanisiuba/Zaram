"""Code Generation Blueprint — System instruction framework for MotionScript generation.

This module constructs the system instruction framework that forces local coding
models to produce valid MotionScript JSON. It enforces:
- Output ONLY valid JSON matching MotionScript schema
- No loops, no setTimeout, no requestAnimationFrame in generated code
- All animations via CSS @keyframes or Web Animations API
- Absolute timestamps (seconds) on every keyframe
- Duration declared upfront, all keyframes within [0, duration]
- Layers use only permitted types: html, svg, canvas, webgl
- Duration capped at MAX_DURATION (default 60s)
- aspect_ratio field must be one of the valid presets
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .contracts import MotionScript, MotionLayer, Keyframe, LayerType, ASPECT_RATIOS, MAX_DURATION, DEFAULT_ASPECT_RATIO


class MotionScriptParseError(ValueError):
    """Raised when the model's response cannot be parsed as MotionScript."""
    pass


class MotionScriptValidationError(ValueError):
    """Raised when parsed MotionScript fails validation."""
    pass


# --------------------------------------------------------------------------- #
# System Prompt
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = f"""You are a motion graphics code generator. Output ONLY valid JSON matching the MotionScript schema below. No prose, no markdown, no explanations.

SCHEMA:
{{
  "version": "1.0",
  "duration": <float, seconds, > 0, <= {MAX_DURATION}>,
  "fps": <int, 1-120>,
  "width": <int, 1-7680>,
  "height": <int, 1-7680>,
  "background": "<CSS color or 'transparent'>",
  "aspect_ratio": "<one of {list(ASPECT_RATIOS.keys())}>",
  "layers": [
    {{
      "id": "<unique string>",
      "type": "<html|svg|canvas|webgl>",
      "content": "<string: HTML markup, SVG source, or drawing commands>",
      "keyframes": [
        {{"time": <float, >=0>, "properties": {{"<css-prop>": "<value>"}}, "easing": "<css-easing>"}}
      ],
      "z_index": <int, default 0>,
      "opacity": <float 0-1, default 1.0>,
      "transform_origin": "<css transform-origin, default 'center center'>"
    }}
  ],
  "metadata": {{}}
}}

HARD CONSTRAINTS (VIOLATION = INVALID OUTPUT):
1. Output ONLY the JSON object. No ```json fences, no comments, no extra keys.
2. ALL keyframes MUST use absolute time in seconds from animation start (0.0 to duration).
3. NO loops, NO setTimeout, NO setInterval, NO requestAnimationFrame, NO while, NO for loops in content.
4. Animations ONLY via CSS @keyframes or Web Animations API — the compiler handles this.
5. Layer "type" MUST be one of: "html", "svg", "canvas", "webgl".
6. Every layer MUST have at least one keyframe.
7. Keyframe times within a layer MUST be sorted ascending and unique.
8. All keyframe times MUST be <= duration.
9. Layer IDs MUST be unique.
10. Duration > 0, <= {MAX_DURATION}, fps in 1..120, width/height in 1..7680.
11. Opacity in [0, 1].
12. Easing must be valid CSS: linear, ease, ease-in, ease-out, ease-in-out, step-start, step-end, or cubic-bezier(...).
13. aspect_ratio must be one of: {list(ASPECT_RATIOS.keys())}.
14. width/height MUST match the aspect_ratio preset dimensions.

CONTENT GUIDELINES BY LAYER TYPE:
- html: Valid HTML fragment (div, span, etc.). CSS properties animated via properties keyframes.
- svg: Valid SVG source. Use transform, opacity, fill, stroke properties.
- canvas: JavaScript drawing commands as string. Will be executed in CanvasRenderingContext2D.
- webgl: JavaScript WebGL commands as string. Will be executed in WebGLRenderingContext.

EXAMPLE (simple fade-in box):
{{
  "version": "1.0",
  "duration": 3.0,
  "fps": 30,
  "width": 1920,
  "height": 1080,
  "background": "transparent",
  "aspect_ratio": "16:9",
  "layers": [
    {{
      "id": "box",
      "type": "html",
      "content": "<div style='width:200px;height:200px;background:#22d3ee;border-radius:12px;'></div>",
      "keyframes": [
        {{"time": 0.0, "properties": {{"opacity": "0", "transform": "translateY(50px)"}}, "easing": "ease-out"}},
        {{"time": 1.5, "properties": {{"opacity": "1", "transform": "translateY(0)"}}, "easing": "ease-out"}}
      ],
      "z_index": 0
    }}
  ],
  "metadata": {{}}
}}"""


def build_system_prompt() -> str:
    """Return the system instruction for MotionScript generation."""
    return _SYSTEM_PROMPT


# --------------------------------------------------------------------------- #
# User Prompt Builder
# --------------------------------------------------------------------------- #

def build_user_prompt(
    user_request: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Build the user prompt with request and optional context.

    Args:
        user_request: The user's natural language request (e.g., "animate a logo fading in")
        context: Optional context dict with keys like:
            - conversation_summary: Recent conversation context
            - project_style: Style preferences from project
            - brand_colors: Brand color palette
            - aspect_ratio: "16:9", "9:16", "1:1", etc.
            - duration: Duration in seconds

    Returns:
        Formatted user prompt string.
    """
    parts = [f"Create a motion graphics animation for: {user_request}"]

    if context:
        if context.get("conversation_summary"):
            parts.append(f"\nConversation context: {context['conversation_summary']}")
        if context.get("project_style"):
            parts.append(f"\nProject style: {context['project_style']}")
        if context.get("brand_colors"):
            colors = context["brand_colors"]
            if isinstance(colors, dict):
                parts.append(f"\nBrand colors: {json.dumps(colors)}")
        if context.get("aspect_ratio"):
            ar = context["aspect_ratio"]
            w, h = ASPECT_RATIOS.get(ar, (1920, 1080))
            parts.append(f"\nAspect ratio: {ar} → width={w}, height={h}")
        if context.get("duration"):
            parts.append(f"\nDuration: {context['duration']} seconds")

    parts.append("\nReturn ONLY the MotionScript JSON.")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Response Parser & Validator
# --------------------------------------------------------------------------- #

def parse_response(raw: str) -> MotionScript:
    """Parse model response into MotionScript.

    Extracts JSON from response (handles ```json fences), validates structure,
    and returns typed MotionScript object.

    Args:
        raw: Raw model response string.

    Returns:
        Validated MotionScript object.

    Raises:
        MotionScriptParseError: If JSON extraction or parsing fails.
        MotionScriptValidationError: If parsed object fails MotionScript validation.
    """
    # Extract JSON from response (handle code fences)
    json_str = _extract_json(raw)
    if not json_str:
        raise MotionScriptParseError("No JSON found in response")

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise MotionScriptParseError(f"Invalid JSON: {e}") from e

    # Convert to MotionScript (triggers __post_init__ validation)
    try:
        return _dict_to_motion_script(data)
    except (ValueError, TypeError, KeyError) as e:
        raise MotionScriptValidationError(f"MotionScript validation failed: {e}") from e


def _extract_json(text: str) -> Optional[str]:
    """Extract JSON object from text, handling ```json fences."""
    # Try ```json ... ``` first
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Try bare { ... }
    brace_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if brace_match:
        return brace_match.group(1).strip()

    return None


def _dict_to_motion_script(data: Dict[str, Any]) -> MotionScript:
    """Convert parsed dict to MotionScript with nested object construction."""
    # Convert layers
    layers = []
    for layer_data in data.get("layers", []):
        keyframes = [
            Keyframe(
                time=kf["time"],
                properties=kf["properties"],
                easing=kf.get("easing", "linear")
            )
            for kf in layer_data.get("keyframes", [])
        ]
        layer = MotionLayer(
            id=layer_data["id"],
            type=LayerType(layer_data["type"]),
            content=layer_data["content"],
            keyframes=keyframes,
            z_index=layer_data.get("z_index", 0),
            opacity=layer_data.get("opacity", 1.0),
            transform_origin=layer_data.get("transform_origin", "center center"),
        )
        layers.append(layer)

    return MotionScript(
        version=data.get("version", "1.0"),
        duration=data["duration"],
        fps=data.get("fps", 30),
        width=data.get("width", 1920),
        height=data.get("height", 1080),
        background=data.get("background", "transparent"),
        aspect_ratio=data.get("aspect_ratio", DEFAULT_ASPECT_RATIO),
        layers=layers,
        metadata=data.get("metadata", {}),
    )


def validate_script(script: MotionScript) -> List[str]:
    """Additional validation beyond MotionScript.__post_init__.

    Returns list of warnings (non-fatal issues). Raises MotionScriptValidationError
    for fatal issues that would break rendering.

    Args:
        script: MotionScript to validate.

    Returns:
        List of warning strings (empty if none).
    """
    warnings = []

    # Check for very short durations that may not render well
    if script.duration < 0.5:
        warnings.append(f"Duration {script.duration}s is very short; consider >= 0.5s for smooth rendering")

    # Check for layers with only 1 keyframe (static)
    for layer in script.layers:
        if len(layer.keyframes) == 1:
            warnings.append(f"Layer '{layer.id}' has only 1 keyframe — will be static")

        # Check for large jumps in keyframe times
        for i in range(1, len(layer.keyframes)):
            gap = layer.keyframes[i].time - layer.keyframes[i-1].time
            if gap > script.duration * 0.5:
                warnings.append(
                    f"Layer '{layer.id}' has large keyframe gap ({gap:.1f}s) — "
                    "consider adding intermediate keyframes"
                )

    # Check for unsupported CSS properties in keyframes
    supported_props = {
        "opacity", "transform", "translate", "rotate", "scale",
        "width", "height", "left", "top", "right", "bottom",
        "background", "background-color", "color", "fill", "stroke",
        "stroke-width", "stroke-opacity", "fill-opacity",
        "filter", "backdrop-filter", "clip-path"
    }
    for layer in script.layers:
        for kf in layer.keyframes:
            for prop in kf.properties:
                base_prop = prop.split("-")[0] if "-" in prop else prop
                if base_prop not in supported_props:
                    warnings.append(
                        f"Layer '{layer.id}' keyframe at {kf.time}s uses "
                        f"potentially unsupported property: {prop}"
                    )

    return warnings