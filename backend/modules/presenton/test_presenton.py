"""Presenton Test Suite — Prevents the motion engine mistakes.

This test suite asserts the invariants that the motion engine lacked:
1. Artifact JSON is never overwritten by binary output
2. Template sandboxing — only allowlisted element types
3. Async cleanup — no temp files leaked on failure
4. Provenance survives compilation → render → re-export
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from modules.presenton.contracts import (
    PresentationScript,
    PresentationMeta,
    PresentationSlide,
    PresentationElement,
    PresentationTheme,
)
from modules.presenton.compiler import compile_presentation, PresentonIR, CompilationError
from modules.presenton.renderer import render_to_pptx, render_to_pdf, RenderError, PresentonNotFoundError
pytest.importorskip("mcp", reason="the presenton MCP server needs the optional mcp package")
from modules.presenton.mcp_server import (
    create_presentation_artifact,
    compile_presentation_artifact,
    validate_presentation_script,
    _merge_theme,
)


# --- Fixtures ---

def _sample_script() -> PresentationScript:
    return PresentationScript(
        meta=PresentationMeta(title="Test Presentation", template_id="corporate_dark_v1"),
        theme=PresentationTheme(),
        slides=[
            PresentationSlide(
                layout="title",
                elements=[
                    PresentationElement(type="title", content={"text": "Test Title"}, style="text-white text-4xl font-bold"),
                    PresentationElement(type="subtitle", content={"text": "Subtitle"}, style="text-slate-400"),
                ],
                speaker_notes="Title slide notes",
            ),
            PresentationSlide(
                layout="content",
                elements=[
                    PresentationElement(type="title", content={"text": "Overview"}, style="text-white text-3xl font-bold"),
                    PresentationElement(type="bullet_list", content={"items": ["Point 1", "Point 2"], "ordered": False}, style="text-slate-300"),
                    PresentationElement(type="metric", content={"value": "42", "label": "Answer"}, style="text-emerald-400"),
                ],
                speaker_notes="Overview slide notes",
            ),
        ],
        claims=[],
    )


# --- Contract Tests ---

class TestPresentationScriptValidation:
    """PresentationScript validates structure at construction."""

    def test_valid_script_constructs(self):
        script = _sample_script()
        assert script.meta.title == "Test Presentation"
        assert len(script.slides) == 2
        assert len(script.slides[0].elements) == 2

    def test_invalid_slide_layout_rejected(self):
        with pytest.raises(ValueError, match="Slide layout 'invalid' not allowed"):
            PresentationSlide(layout="invalid", elements=[])

    def test_invalid_element_type_rejected(self):
        with pytest.raises(ValueError, match="Element type 'script' not allowed"):
            PresentationElement(type="script", content="evil()")

    def test_all_valid_slide_layouts_accepted(self):
        for layout in ["title", "content", "two_column", "metric_focus", "quote", "section"]:
            slide = PresentationSlide(layout=layout, elements=[])
            assert slide.layout == layout

    def test_all_valid_element_types_accepted(self):
        for etype in ["title", "subtitle", "body", "bullet_list", "metric", "chart", "image", "table", "divider"]:
            el = PresentationElement(type=etype, content={})
            assert el.type == etype

    def test_script_serializes_to_dict(self):
        script = _sample_script()
        data = script.to_dict()
        assert data["meta"]["title"] == "Test Presentation"
        assert len(data["slides"]) == 2
        assert "theme" in data

    def test_script_deserializes_from_dict(self):
        script = _sample_script()
        data = script.to_dict()
        restored = PresentationScript.from_dict(data)
        assert restored.meta.title == script.meta.title
        assert len(restored.slides) == len(script.slides)


# --- Compiler Tests ---

class TestCompilerPreservesArtifact:
    """The JSON artifact is sacred; binary is disposable."""

    def test_compile_produces_ir_without_mutation(self):
        script = _sample_script()
        original_json = script.to_dict()
        
        ir = compile_presentation(script)
        
        # Original script unchanged
        assert script.to_dict() == original_json
        # IR has expected structure
        assert isinstance(ir, PresentonIR)
        assert ir.meta.title == "Test Presentation"
        assert len(ir.slides) == 2

    def test_ir_has_theme_mapping(self):
        script = _sample_script()
        ir = compile_presentation(script)
        
        assert "colors" in ir.theme
        assert "fonts" in ir.theme
        assert "spacing" in ir.theme
        assert ir.theme["colors"]["accent"] == "#22d3ee"

    def test_element_type_mapping(self):
        script = _sample_script()
        ir = compile_presentation(script)
        
        # Check type mapping
        slide0_els = ir.slides[0]["elements"]
        assert slide0_els[0]["type"] == "heading"  # title -> heading
        assert slide0_els[1]["type"] == "subheading"  # subtitle -> subheading
        
        slide1_els = ir.slides[1]["elements"]
        assert slide1_els[1]["type"] == "list"  # bullet_list -> list
        assert slide1_els[2]["type"] == "metric"  # metric -> metric

    def test_tailwind_style_parsing(self):
        script = _sample_script()
        ir = compile_presentation(script)
        
        # First element has style
        style = ir.slides[0]["elements"][0]["style"]
        assert style["color"] == "white"
        assert style["size"] == "4xl"
        assert style["weight"] == "bold"

    def test_content_structuring_per_type(self):
        script = _sample_script()
        ir = compile_presentation(script)
        
        # bullet_list content structured
        bullet_el = ir.slides[1]["elements"][1]
        assert bullet_el["content"]["items"] == ["Point 1", "Point 2"]
        assert bullet_el["content"]["ordered"] is False
        
        # metric content structured
        metric_el = ir.slides[1]["elements"][2]
        assert metric_el["content"]["value"] == "42"
        assert metric_el["content"]["label"] == "Answer"


# --- Renderer Tests ---

class TestRendererErrorHandling:
    """Renderer fails cleanly with proper errors."""

    def test_presenton_not_found_raises_custom_error(self):
        ir = compile_presentation(_sample_script())
        
        with patch("modules.presenton.renderer._check_presenton_available", return_value=False):
            with pytest.raises(PresentonNotFoundError, match="Presenton CLI not found"):
                render_to_pptx(ir, Path("/tmp/test.pptx"))

    def test_render_error_on_cli_failure(self):
        ir = compile_presentation(_sample_script())
        
        with patch("modules.presenton.renderer._check_presenton_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("CLI crashed")
                with pytest.raises(RenderError):
                    render_to_pptx(ir, Path("/tmp/test.pptx"))


# --- MCP Server Tests ---

class TestMCPServerArtifactPersistence:
    """Artifact JSON is created and preserved."""

    def test_create_artifact_writes_json(self, tmp_path):
        # Monkey-patch ARTIFACT_DIR
        import modules.presenton.mcp_server as mcp_module
        original_dir = mcp_module.ARTIFACT_DIR
        mcp_module.ARTIFACT_DIR = tmp_path / "artifacts"
        mcp_module.ARTIFACT_DIR.mkdir(parents=True)
        
        try:
            result = create_presentation_artifact(
                artifact_name="test_deck",
                title="Test Deck",
                slides_data=json.dumps([
                    {
                        "layout": "title",
                        "elements": [{"type": "title", "content": {"text": "Hello"}}],
                        "speaker_notes": "Notes",
                    }
                ]),
            )
            
            artifact_path = mcp_module.ARTIFACT_DIR / "test_deck.json"
            assert artifact_path.exists()
            
            # Verify content
            with open(artifact_path) as f:
                data = json.load(f)
            assert data["meta"]["title"] == "Test Deck"
            assert len(data["slides"]) == 1
            
            assert "stored at" in result
        finally:
            mcp_module.ARTIFACT_DIR = original_dir

    def test_compile_artifact_reads_json_and_renders(self, tmp_path):
        import modules.presenton.mcp_server as mcp_module
        original_dir = mcp_module.ARTIFACT_DIR
        mcp_module.ARTIFACT_DIR = tmp_path / "artifacts"
        mcp_module.ARTIFACT_DIR.mkdir(parents=True)
        
        # Create artifact
        script = _sample_script()
        artifact_path = mcp_module.ARTIFACT_DIR / "test_deck.json"
        with open(artifact_path, "w") as f:
            json.dump(script.to_dict(), f)
        
        try:
            # Mock renderer to avoid needing Presenton CLI
            with patch("modules.presenton.mcp_server.render_to_pptx") as mock_render:
                result = compile_presentation_artifact("test_deck", "pptx")
                mock_render.assert_called_once()
                assert "Successfully rendered" in result
        finally:
            mcp_module.ARTIFACT_DIR = original_dir

    def test_compile_missing_artifact_returns_error(self):
        import modules.presenton.mcp_server as mcp_module
        original_dir = mcp_module.ARTIFACT_DIR
        mcp_module.ARTIFACT_DIR = Path("/tmp/nonexistent")
        
        try:
            result = compile_presentation_artifact("missing", "pptx")
            assert "not found" in result
        finally:
            mcp_module.ARTIFACT_DIR = original_dir

    def test_validate_script_accepts_valid(self):
        script = _sample_script()
        result = validate_presentation_script(json.dumps(script.to_dict()))
        assert "Valid:" in result
        assert "2 slides" in result

    def test_validate_script_rejects_invalid(self):
        result = validate_presentation_script('{"invalid": "json"}')
        assert "Invalid:" in result


class TestThemeMerging:
    """Theme override merges correctly with base theme."""

    def test_empty_override_returns_base(self):
        theme = _merge_theme({})
        assert theme.colors["accent"] == "#22d3ee"
        assert theme.fonts["heading"] == "Inter"

    def test_override_merges_deeply(self):
        theme = _merge_theme({"colors": {"accent": "#ff0000"}})
        assert theme.colors["accent"] == "#ff0000"
        assert theme.colors["primary"] == "#1e293b"  # Base preserved

    def test_override_adds_new_keys(self):
        theme = _merge_theme({"custom": {"new": "value"}})
        assert theme.__dict__.get("custom") == {"new": "value"}


# --- Async Cleanup Tests ---

class TestAsyncCleanup:
    """No temp files leaked on render failure."""

    def test_temp_ir_file_cleaned_on_render_error(self, tmp_path):
        """IR temp file is deleted even when Presenton CLI fails."""
        import modules.presenton.renderer as renderer
        
        ir = compile_presentation(_sample_script())
        output_path = tmp_path / "out.pptx"
        
        # Track temp files created
        created_files = []
        original_named_temp = tempfile.NamedTemporaryFile
        
        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            created_files.append(Path(f.name))
            return f
        
        with patch("modules.presenton.renderer._check_presenton_available", return_value=True):
            with patch("tempfile.NamedTemporaryFile", side_effect=tracking_named_temp):
                with patch("subprocess.run", side_effect=Exception("CLI failed")):
                    with pytest.raises(RenderError):
                        render_to_pptx(ir, output_path)
        
        # All temp files should be cleaned up
        for f in created_files:
            assert not f.exists(), f"Temp file leaked: {f}"

    def test_temp_ir_file_cleaned_on_timeout(self, tmp_path):
        """IR temp file is deleted on timeout."""
        import modules.presenton.renderer as renderer
        import subprocess
        
        ir = compile_presentation(_sample_script())
        output_path = tmp_path / "out.pptx"
        
        created_files = []
        original_named_temp = tempfile.NamedTemporaryFile
        
        def tracking_named_temp(*args, **kwargs):
            f = original_named_temp(*args, **kwargs)
            created_files.append(Path(f.name))
            return f
        
        with patch("modules.presenton.renderer._check_presenton_available", return_value=True):
            with patch("tempfile.NamedTemporaryFile", side_effect=tracking_named_temp):
                with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
                    with pytest.raises(RenderError, match="timed out"):
                        render_to_pptx(ir, output_path)
        
        for f in created_files:
            assert not f.exists(), f"Temp file leaked: {f}"


# --- Provenance Tests ---

class TestProvenanceSurvives:
    """Claims and sources travel through the pipeline."""

    def test_claims_in_script_reach_ir(self):
        from artifacts.contracts import Claim
        
        script = _sample_script()
        claim = Claim(
            id="c1",
            source_id="memory:123",
            excerpt="Revenue grew 23%",
            source_excerpt="Q3 revenue was $1.2M, up 23% YoY",
        )
        script_with_claims = PresentationScript(
            meta=script.meta,
            slides=script.slides,
            theme=script.theme,
            claims=[claim],
        )
        
        ir = compile_presentation(script_with_claims)
        # Claims preserved in IR (passed through)
        assert ir.to_dict()["claims"] == [claim.to_dict()]

    def test_sources_in_meta(self):
        script = _sample_script()
        ir = compile_presentation(script)
        
        # Meta preserved
        assert ir.meta.template_id == "corporate_dark_v1"
        assert ir.meta.aspect_ratio == "16:9"


# --- Integration Tests (require Presenton CLI) ---

class TestIntegration:
    """Integration tests — skipped if Presenton not installed."""

    @pytest.fixture
    def presenton_available(self):
        try:
            import subprocess
            subprocess.run(["presenton", "--version"], check=True, capture_output=True, timeout=5)
            return True
        except Exception:
            pytest.skip("Presenton CLI not installed")

    def test_full_pipeline_script_to_pptx(self, presenton_available, tmp_path):
        """Full pipeline: Script -> IR -> PPTX produces valid file."""
        script = _sample_script()
        ir = compile_presentation(script)
        output_path = tmp_path / "test.pptx"
        
        render_to_pptx(ir, output_path)
        
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        
        # Verify it's a valid PPTX
        from pptx import Presentation
        prs = Presentation(output_path)
        assert len(prs.slides) >= 1

    def test_full_pipeline_script_to_pdf(self, presenton_available, tmp_path):
        """Full pipeline: Script -> IR -> PDF produces valid file."""
        script = _sample_script()
        ir = compile_presentation(script)
        output_path = tmp_path / "test.pdf"
        
        render_to_pdf(ir, output_path)
        
        assert output_path.exists()
        assert output_path.stat().st_size > 0


# --- Preview Tests ---

class TestPreviewGeneration:
    """HTML preview generates without Presenton CLI."""

    def test_preview_html_contains_slides(self):
        script = _sample_script()
        from modules.presenton.preview import render_preview_html
        
        html = render_preview_html(script)
        
        assert "Test Presentation" in html
        assert "Slide 1" in html
        assert "Slide 2" in html
        assert "title" in html  # layout name
        assert "content" in html
        assert "Test Title" in html
        assert "Point 1" in html
        assert "42" in html  # metric value

    def test_preview_includes_theme_colors(self):
        script = _sample_script()
        from modules.presenton.preview import render_preview_html
        
        html = render_preview_html(script)
        
        # Theme colors in CSS
        assert "#0f172a" in html  # background
        assert "#22d3ee" in html  # accent
        assert "#f8fafc" in html  # text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])