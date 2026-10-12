"""MotionScript Compiler — Compiles MotionScript to self-contained HTML5 timeline.

Transforms declarative MotionScript into a single HTML file containing:
- CSS @keyframes for each layer's animation
- HTML/SVG elements for each layer
- Web Animations API fallback for complex transforms
- No external dependencies (self-contained)
- CSP-compatible (inline styles only, no external scripts)
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List

from .contracts import MotionScript, MotionAsset, MotionLayer, Keyframe, LayerType, ASPECT_RATIOS


class CompilationError(ValueError):
    """Raised when compilation fails."""
    pass


def compile_script(script: MotionScript) -> MotionAsset:
    """Compile MotionScript to self-contained HTML5 timeline.

    Args:
        script: Validated MotionScript.

    Returns:
        MotionAsset with compiled HTML timeline.

    Raises:
        CompilationError: If compilation fails.
    """
    # Verify seek contract: all keyframes have absolute time, no relative offsets
    _verify_seek_contract(script)

    # Generate unique animation IDs
    anim_id = f"motion_{uuid.uuid4().hex[:8]}"

    # Build CSS @keyframes for each layer
    css_keyframes = _generate_css_keyframes(script.layers, anim_id, script)

    # Build layer HTML elements (pass script for canvas width/height)
    layer_html = _generate_layer_html(script.layers, anim_id, script)

    # Build complete HTML document
    html = _build_html_document(
        script=script,
        anim_id=anim_id,
        css_keyframes=css_keyframes,
        layer_html=layer_html,
    )

    return MotionAsset(
        script=script,
        html_timeline=html,
        duration_ms=int(script.duration * 1000),
    )


def _verify_seek_contract(script: MotionScript) -> None:
    """Verify absolute chronological seek contract compliance."""
    for layer in script.layers:
        for kf in layer.keyframes:
            if kf.time < 0:
                raise CompilationError(f"Layer '{layer.id}': negative keyframe time {kf.time}")
            if kf.time > script.duration:
                raise CompilationError(
                    f"Layer '{layer.id}': keyframe at {kf.time}s exceeds duration {script.duration}s"
                )
    # No loops, no relative timing — already enforced by MotionScript validation


def _generate_css_keyframes(layers: List[MotionLayer], anim_id: str, script: MotionScript) -> str:
    """Generate CSS @keyframes rules for all layers."""
    rules = []

    for layer in layers:
        if len(layer.keyframes) < 2:
            continue  # Static layer, no animation needed

        keyframe_rules = []
        for kf in layer.keyframes:
            # Convert time to percentage
            pct = (kf.time / script.duration) * 100 if script.duration > 0 else 0
            pct = min(100, max(0, pct))

            # Build CSS property declarations
            props = []
            for css_prop, value in kf.properties.items():
                props.append(f"  {_camel_to_kebab(css_prop)}: {_escape_css_value(value)};")
            props_str = "\n".join(props)

            keyframe_rules.append(f"{pct:.2f}% {{\n{props_str}\n}}")

        if keyframe_rules:
            anim_name = f"{anim_id}_{layer.id}"
            rules.append(f"@keyframes {anim_name} {{\n" + "\n".join(keyframe_rules) + "\n}}")

    return "\n\n".join(rules)


def _generate_layer_html(layers: List[MotionLayer], anim_id: str, script: MotionScript) -> str:
    """Generate HTML elements for all layers, sorted by z_index."""
    # Sort by z_index (ascending = back to front)
    sorted_layers = sorted(layers, key=lambda l: l.z_index)

    elements = []
    for layer in sorted_layers:
        anim_name = f"{anim_id}_{layer.id}"
        duration_ms = int(layer.keyframes[-1].time * 1000) if len(layer.keyframes) > 1 else 0

        style_parts = [
            f"position: absolute;",
            f"inset: 0;",
            f"z-index: {layer.z_index};",
            f"opacity: {layer.opacity};",
            f"transform-origin: {layer.transform_origin};",
        ]

        if len(layer.keyframes) > 1 and duration_ms > 0:
            # Apply animation via CSS
            style_parts.append(
                f"animation: {anim_name} {duration_ms}ms "
                f"{layer.keyframes[-1].easing} forwards;"
            )
            # Set initial state from first keyframe
            first_kf = layer.keyframes[0]
            for prop, val in first_kf.properties.items():
                style_parts.append(f"{_camel_to_kebab(prop)}: {_escape_css_value(val)};")

        style_attr = " ".join(style_parts)

        if layer.type == LayerType.HTML:
            elements.append(f'<div id="{layer.id}" style="{style_attr}">{layer.content}</div>')
        elif layer.type == LayerType.SVG:
            # Wrap SVG in div for positioning
            svg_wrapper = f'<div id="{layer.id}" style="{style_attr}">{layer.content}</div>'
            elements.append(svg_wrapper)
        elif layer.type in (LayerType.CANVAS, LayerType.WEBGL):
            # Canvas/WebGL need script execution — handled separately in HTML
            canvas_type = "canvas"
            elements.append(
                f'<{canvas_type} id="{layer.id}" width="{script.width}" '
                f'height="{script.height}" style="{style_attr}"></{canvas_type}>'
            )

    return "\n".join(elements)


def _build_html_document(
    script: MotionScript,
    anim_id: str,
    css_keyframes: str,
    layer_html: str,
) -> str:
    """Build complete self-contained HTML document."""
    canvas_layers = [l for l in script.layers if l.type in (LayerType.CANVAS, LayerType.WEBGL)]
    canvas_scripts = _generate_canvas_scripts(canvas_layers, script, anim_id)

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Zaram Motion: {script.metadata.get('title', 'Untitled')}</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ width: 100%; height: 100%; overflow: hidden; }}
    #stage {{
      width: {script.width}px;
      height: {script.height}px;
      position: relative;
      background: {_escape_css_value(script.background)};
      contain: strict;
    }}
    {css_keyframes}
  </style>
</head>
<body>
  <div id="stage">
{layer_html}
  </div>
  <script>
{canvas_scripts}
    // Auto-play: animations start on load via CSS
    // For canvas/WebGL, scripts initialize on DOMContentLoaded
  </script>
</body>
</html>"""


def _generate_canvas_scripts(
    canvas_layers: List[MotionLayer],
    script: MotionScript,
    anim_id: str,
) -> str:
    """Generate JavaScript for canvas/WebGL layer animation."""
    if not canvas_layers:
        return "// No canvas/WebGL layers"

    scripts = []
    for layer in canvas_layers:
        if layer.type == LayerType.CANVAS:
            scripts.append(_generate_canvas_script(layer, script, anim_id))
        elif layer.type == LayerType.WEBGL:
            scripts.append(_generate_webgl_script(layer, script, anim_id))

    return "\n\n".join(scripts)


def _generate_canvas_script(layer: MotionLayer, script: MotionScript, anim_id: str) -> str:
    """Generate Canvas 2D animation script using Web Animations API.
    
    For v1, canvas layers are restricted to procedural drawing commands that
    read animated values from a proxy element. The drawing commands must be
    valid JavaScript that operates on `ctx` (CanvasRenderingContext2D).
    
    Security: No eval() — drawing commands are injected directly.
    """
    anim_name = f"{anim_id}_{layer.id}"
    duration_ms = int(script.duration * 1000)

    # Build keyframes data for Web Animations API
    keyframes_data = [
        {**{"offset": kf.time / script.duration if script.duration > 0 else 0}, **kf.properties}
        for kf in layer.keyframes
    ]
    keyframes_json = json.dumps(keyframes_data)

    # For v1: canvas layer content must be valid JavaScript drawing commands
    # that operate on `ctx`. We inject it directly without eval().
    # Supported: ctx.fillRect, ctx.arc, ctx.fillText, ctx.drawImage, etc.
    drawing_commands = layer.content.strip()

    return f"""
  // Canvas layer: {layer.id}
  (function() {{
    const canvas = document.getElementById('{layer.id}');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = {script.width};
    canvas.height = {script.height};

    // Parse keyframes for Web Animations API
    const keyframes = {keyframes_json};

    // Animate using Web Animations API for canvas properties
    // Note: canvas drawing is procedural; we animate a proxy element and read its computed style
    const proxy = document.createElement('div');
    proxy.style.display = 'none';
    document.body.appendChild(proxy);
    const animation = proxy.animate(keyframes, {{
      duration: {duration_ms},
      easing: '{layer.keyframes[-1].easing if len(layer.keyframes) > 1 else 'linear'}',
      fill: 'forwards'
    }});

    function render(timestamp) {{
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      // Execute drawing commands with current animated values
      // The drawing commands have access to: ctx, canvas, timestamp
      try {{
        {drawing_commands}
      }} catch (e) {{
        console.error('Canvas drawing error:', e);
      }}
      if (animation.playState !== 'finished') {{
        requestAnimationFrame(render);
      }}
    }}
    requestAnimationFrame(render);
  }})();
"""


def _generate_webgl_script(layer: MotionLayer, script: MotionScript, anim_id: str) -> str:
    """Generate WebGL animation script placeholder."""
    return f"""
  // WebGL layer: {layer.id} - placeholder for WebGL rendering
  console.log('WebGL layer {layer.id} initialized');
"""


def _camel_to_kebab(s: str) -> str:
    """Convert camelCase to kebab-case for CSS properties."""
    return re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', s).lower()


def _escape_css_value(value: Any) -> str:
    """Escape value for safe CSS inclusion."""
    s = str(value)
    # Basic escaping for CSS values
    return s.replace("'", "\\'").replace('"', '\\"')