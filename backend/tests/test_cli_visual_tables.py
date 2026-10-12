"""Tests for CLI Visual Engine - Comparison Tables."""

import pytest
from backend.cli.visual.tables import (
    ComparisonTableRenderer,
    FeatureRow,
    FeatureStatus,
    render_comparison,
    get_comparison_data,
    MEMORY_COMPARISON_FEATURES,
)


class TestComparisonTableRenderer:
    """Test the ComparisonTableRenderer class."""
    
    def test_render_feature_comparison_basic(self):
        """Test basic feature comparison rendering."""
        features = [
            FeatureRow("Feature A", {"System1": FeatureStatus.PRESENT, "System2": FeatureStatus.ABSENT}),
            FeatureRow("Feature B", {"System1": FeatureStatus.PARTIAL, "System2": FeatureStatus.PLANNED}),
        ]
        renderer = ComparisonTableRenderer()
        output = renderer.render_feature_comparison(features, title="Test Comparison")
        
        assert "Test Comparison" in output
        assert "Feature A" in output
        assert "Feature B" in output
        assert "System1" in output
        assert "System2" in output
    
    def test_render_feature_comparison_empty(self):
        """Test rendering empty feature list."""
        renderer = ComparisonTableRenderer()
        output = renderer.render_feature_comparison([])
        assert "No features to compare" in output
    
    def test_render_simple_comparison(self):
        """Test simple comparison from feature list and system dicts."""
        features = ["Feature A", "Feature B"]
        systems = {
            "System1": {"Feature A": FeatureStatus.PRESENT, "Feature B": FeatureStatus.ABSENT},
            "System2": {"Feature A": FeatureStatus.PARTIAL, "Feature B": FeatureStatus.PLANNED},
        }
        renderer = ComparisonTableRenderer()
        output = renderer.render_simple_comparison(features, systems, title="Simple Test")
        
        assert "Simple Test" in output
        assert "Feature A" in output
        assert "Feature B" in output


class TestComparisonData:
    """Test pre-defined comparison data."""
    
    def test_get_memory_comparison(self):
        """Test getting memory comparison data."""
        features = get_comparison_data("memory")
        assert len(features) > 0
        assert all(isinstance(f, FeatureRow) for f in features)
    
    def test_get_browser_comparison(self):
        """Test getting browser comparison data."""
        features = get_comparison_data("browser")
        assert len(features) > 0
    
    def test_get_search_comparison(self):
        """Test getting search comparison data."""
        features = get_comparison_data("search")
        assert len(features) > 0
    
    def test_get_pipeline_comparison(self):
        """Test getting pipeline comparison data."""
        features = get_comparison_data("pipeline")
        assert len(features) > 0
    
    def test_get_unknown_comparison(self):
        """Test getting unknown comparison returns empty."""
        features = get_comparison_data("unknown_topic")
        assert features == []
    
    def test_memory_comparison_features_structure(self):
        """Test memory comparison features have expected structure."""
        assert len(MEMORY_COMPARISON_FEATURES) > 5
        for feature in MEMORY_COMPARISON_FEATURES:
            assert isinstance(feature.feature, str)
            assert isinstance(feature.systems, dict)
            assert len(feature.systems) >= 2


class TestRenderComparison:
    """Test render_comparison function."""
    
    def test_render_memory_comparison(self):
        """Test rendering memory comparison."""
        output = render_comparison("memory")
        assert "Feature Comparison: Memory" in output
        assert "mem0" in output
        assert "Zaram Spine" in output
    
    def test_render_comparison_json(self):
        """Test rendering comparison as JSON."""
        output = render_comparison("memory", as_json=True)
        import json
        data = json.loads(output)
        assert data["topic"] == "memory"
        assert "features" in data
        assert len(data["features"]) > 0
    
    def test_render_unknown_comparison(self):
        """Test rendering unknown comparison."""
        output = render_comparison("unknown")
        assert "Unknown comparison topic" in output