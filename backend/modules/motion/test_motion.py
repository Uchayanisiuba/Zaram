"""Unit tests for the Motion module."""

import pytest
import tempfile
from pathlib import Path

from .contracts import (
    MotionScript, MotionLayer, Keyframe, LayerType, 
    ASPECT_RATIOS, MAX_DURATION, DEFAULT_ASPECT_RATIO
)
from .compiler import compile_script, CompilationError
from .generator import (
    parse_response, validate_script,
    MotionScriptParseError, MotionScriptValidationError
)
from .renderer import check_playwright_available, render_to_video, RenderError


class TestMotionContracts:
    """Test MotionScript data contracts."""

    def test_valid_motion_script(self):
        """Test creating a valid MotionScript."""
        layer = MotionLayer(
            id="test_layer",
            type=LayerType.HTML,
            content="<div>Test</div>",
            keyframes=[
                Keyframe(time=0.0, properties={"opacity": "0"}, easing="ease-out"),
                Keyframe(time=1.0, properties={"opacity": "1"}, easing="ease-out"),
            ],
        )
        script = MotionScript(
            duration=2.0,
            fps=30,
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            layers=[layer],
        )
        assert script.duration == 2.0
        assert len(script.layers) == 1

    def test_invalid_duration_too_long(self):
        """Test that duration exceeding MAX_DURATION raises error."""
        layer = MotionLayer(
            id="test",
            type=LayerType.HTML,
            content="<div>Test</div>",
            keyframes=[Keyframe(time=0.0, properties={})],
        )
        with pytest.raises(ValueError, match="duration must be <="):
            MotionScript(
                duration=MAX_DURATION + 1,
                fps=30,
                width=1920,
                height=1080,
                aspect_ratio="16:9",
                layers=[layer],
            )

    def test_aspect_ratio_mismatch(self):
        """Test that width/height must match aspect_ratio."""
        layer = MotionLayer(
            id="test",
            type=LayerType.HTML,
            content="<div>Test</div>",
            keyframes=[Keyframe(time=0.0, properties={})],
        )
        with pytest.raises(ValueError, match="must match aspect_ratio"):
            MotionScript(
                duration=2.0,
                fps=30,
                width=1920,
                height=1080,
                aspect_ratio="1:1",  # Mismatch: 1920x1080 != 1:1
                layers=[layer],
            )

    def test_keyframe_time_ordering(self):
        """Test that keyframes must be sorted by time."""
        with pytest.raises(ValueError, match="sorted by time"):
            MotionLayer(
                id="test",
                type=LayerType.HTML,
                content="<div>Test</div>",
                keyframes=[
                    Keyframe(time=1.0, properties={}),
                    Keyframe(time=0.0, properties={}),  # Out of order
                ],
            )

    def test_keyframe_unique_times(self):
        """Test that keyframe times must be unique."""
        with pytest.raises(ValueError, match="unique"):
            MotionLayer(
                id="test",
                type=LayerType.HTML,
                content="<div>Test</div>",
                keyframes=[
                    Keyframe(time=1.0, properties={}),
                    Keyframe(time=1.0, properties={}),  # Duplicate time
                ],
            )


class TestCompiler:
    """Test MotionScript compiler."""

    def test_compile_simple_html_layer(self):
        """Test compiling a simple HTML layer animation."""
        layer = MotionLayer(
            id="box",
            type=LayerType.HTML,
            content="<div style='width:100px;height:100px;background:red;'></div>",
            keyframes=[
                Keyframe(time=0.0, properties={"opacity": "0", "transform": "translateX(-100px)"}),
                Keyframe(time=1.0, properties={"opacity": "1", "transform": "translateX(0)"}),
            ],
        )
        script = MotionScript(
            duration=1.0,
            fps=30,
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            layers=[layer],
        )
        asset = compile_script(script)
        
        assert asset.html_timeline is not None
        assert "<div id=\"box\"" in asset.html_timeline
        assert "@keyframes" in asset.html_timeline
        assert asset.duration_ms == 1000

    def test_compile_svg_layer(self):
        """Test compiling an SVG layer."""
        layer = MotionLayer(
            id="circle",
            type=LayerType.SVG,
            content="<svg><circle cx='50' cy='50' r='40' fill='blue'/></svg>",
            keyframes=[
                Keyframe(time=0.0, properties={"opacity": "0"}),
                Keyframe(time=1.0, properties={"opacity": "1"}),
            ],
        )
        script = MotionScript(
            duration=1.0,
            fps=30,
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            layers=[layer],
        )
        asset = compile_script(script)
        
        assert "<svg>" in asset.html_timeline
        assert "circle" in asset.html_timeline

    def test_compile_canvas_layer_uses_script_dimensions(self):
        """Test that canvas layer uses script width/height (Task 1 fix)."""
        layer = MotionLayer(
            id="canvas1",
            type=LayerType.CANVAS,
            content="ctx.fillRect(0, 0, 100, 100);",
            keyframes=[
                Keyframe(time=0.0, properties={"opacity": "0"}),
                Keyframe(time=1.0, properties={"opacity": "1"}),
            ],
        )
        script = MotionScript(
            duration=1.0,
            fps=30,
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            layers=[layer],
        )
        asset = compile_script(script)
        
        # Canvas element should have script's width/height
        assert 'width="1920"' in asset.html_timeline
        assert 'height="1080"' in asset.html_timeline
        # Canvas script should use script dimensions
        assert "canvas.width = 1920" in asset.html_timeline
        assert "canvas.height = 1080" in asset.html_timeline

    def test_compile_no_eval_in_output(self):
        """Test that compiled output contains no eval() (Task 7)."""
        layer = MotionLayer(
            id="canvas1",
            type=LayerType.CANVAS,
            content="ctx.fillRect(0, 0, 100, 100);",
            keyframes=[
                Keyframe(time=0.0, properties={"opacity": "0"}),
                Keyframe(time=1.0, properties={"opacity": "1"}),
            ],
        )
        script = MotionScript(
            duration=1.0,
            fps=30,
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            layers=[layer],
        )
        asset = compile_script(script)
        
        # Should not contain eval() - security fix
        assert "eval(" not in asset.html_timeline
        # Should contain drawing commands directly
        assert "ctx.fillRect(0, 0, 100, 100);" in asset.html_timeline

    def test_compile_keyframe_exceeds_duration(self):
        """Test that keyframe exceeding duration raises error."""
        layer = MotionLayer(
            id="test",
            type=LayerType.HTML,
            content="<div>Test</div>",
            keyframes=[
                Keyframe(time=0.0, properties={"opacity": "0"}),
                Keyframe(time=5.0, properties={"opacity": "1"}),  # Exceeds 2s duration
            ],
        )
        # Validation happens at MotionScript creation time
        with pytest.raises(ValueError, match="exceeds script duration"):
            MotionScript(
                duration=2.0,
                fps=30,
                width=1920,
                height=1080,
                aspect_ratio="16:9",
                layers=[layer],
            )


class TestGenerator:
    """Test MotionScript generator parsing and validation."""

    def test_parse_valid_json(self):
        """Test parsing valid MotionScript JSON."""
        json_str = '''
        {
            "version": "1.0",
            "duration": 2.0,
            "fps": 30,
            "width": 1920,
            "height": 1080,
            "aspect_ratio": "16:9",
            "background": "transparent",
            "layers": [
                {
                    "id": "layer1",
                    "type": "html",
                    "content": "<div>Test</div>",
                    "keyframes": [
                        {"time": 0.0, "properties": {"opacity": "0"}, "easing": "ease-out"},
                        {"time": 1.0, "properties": {"opacity": "1"}, "easing": "ease-out"}
                    ]
                }
            ],
            "metadata": {}
        }
        '''
        script = parse_response(json_str)
        assert isinstance(script, MotionScript)
        assert script.duration == 2.0
        assert len(script.layers) == 1

    def test_parse_json_with_code_fences(self):
        """Test parsing JSON wrapped in markdown code fences."""
        json_str = '''
        ```json
        {
            "version": "1.0",
            "duration": 1.0,
            "fps": 30,
            "width": 1920,
            "height": 1080,
            "aspect_ratio": "16:9",
            "background": "transparent",
            "layers": [
                {
                    "id": "test",
                    "type": "html",
                    "content": "<div>Test</div>",
                    "keyframes": [
                        {"time": 0.0, "properties": {"opacity": "0"}},
                        {"time": 1.0, "properties": {"opacity": "1"}}
                    ]
                }
            ],
            "metadata": {}
        }
        ```
        '''
        script = parse_response(json_str)
        assert isinstance(script, MotionScript)

    def test_parse_invalid_json(self):
        """Test that invalid JSON raises parse error."""
        with pytest.raises(MotionScriptParseError):
            parse_response("not valid json")

    def test_parse_missing_required_fields(self):
        """Test that missing required fields raises validation error."""
        json_str = '{"duration": 1.0}'  # Missing layers, width, height, etc.
        with pytest.raises(MotionScriptValidationError):
            parse_response(json_str)

    def test_validate_script_warnings(self):
        """Test that validate_script returns warnings for short duration."""
        layer = MotionLayer(
            id="test",
            type=LayerType.HTML,
            content="<div>Test</div>",
            keyframes=[Keyframe(time=0.0, properties={"opacity": "1"})],  # Single keyframe = static
        )
        script = MotionScript(
            duration=0.1,  # Very short
            fps=30,
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            layers=[layer],
        )
        warnings = validate_script(script)
        assert any("very short" in w for w in warnings)
        assert any("static" in w for w in warnings)


class TestRenderer:
    """Test renderer availability check."""

    def test_check_playwright_available(self):
        """Test that check_playwright_available returns boolean."""
        result = check_playwright_available()
        assert isinstance(result, bool)


# Integration test would require Playwright and a running backend
# class TestIntegration:
#     @pytest.mark.asyncio
#     async def test_render_to_video(self):
#         pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])