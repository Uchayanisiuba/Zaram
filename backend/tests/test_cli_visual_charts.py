"""Tests for CLI Visual Engine - Charts."""

import pytest
from backend.cli.visual.charts import (
    ChartRenderer,
    ChartConfig,
    ChartPreset,
    render_analytics,
    get_token_speed_data,
    get_latency_data,
    get_memory_decay_data,
    get_egress_bytes_data,
)


class TestChartConfig:
    """Test ChartConfig dataclass."""
    
    def test_default_config(self):
        """Test default chart config."""
        config = ChartConfig()
        assert config.height == 15
        assert config.width == 80
        assert config.colors is not None
        assert len(config.colors) == 6
    
    def test_custom_config(self):
        """Test custom chart config."""
        config = ChartConfig(height=20, width=100, title="Custom", colors=["red", "blue"])
        assert config.height == 20
        assert config.width == 100
        assert config.title == "Custom"
        assert config.colors == ["red", "blue"]


class TestChartRenderer:
    """Test ChartRenderer class."""
    
    def test_render_line_chart_basic(self):
        """Test basic line chart rendering."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        renderer = ChartRenderer()
        output = renderer.render_line_chart(data, "Test Series")
        
        assert "Test Series" in output
        assert "5 points" in output
    
    def test_render_line_chart_empty(self):
        """Test rendering empty data."""
        renderer = ChartRenderer()
        output = renderer.render_line_chart([])
        assert "No data to chart" in output
    
    def test_render_multi_series(self):
        """Test rendering multiple series."""
        series = {
            "series1": [1.0, 2.0, 3.0],
            "series2": [2.0, 3.0, 4.0],
        }
        renderer = ChartRenderer()
        output = renderer.render_multi_series(series)
        
        assert "series1" in output
        assert "series2" in output
    
    def test_render_multi_series_empty(self):
        """Test rendering empty series."""
        renderer = ChartRenderer()
        output = renderer.render_multi_series({})
        assert "No data to chart" in output
    
    def test_render_preset(self):
        """Test rendering with preset."""
        data = [10.0, 20.0, 30.0]
        renderer = ChartRenderer()
        output = renderer.render_preset(ChartPreset.TOKEN_SPEED, data)
        
        assert "Token Generation Speed" in output
    
    def test_fallback_chart(self):
        """Test fallback chart rendering."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        renderer = ChartRenderer()
        output = renderer._fallback_chart(data, "Test", ChartConfig())
        
        assert "Test" in output
        assert "5 points" in output
    
    def test_fallback_multi(self):
        """Test fallback multi-series rendering."""
        series = {"a": [1.0, 2.0], "b": [3.0, 4.0]}
        renderer = ChartRenderer()
        output = renderer._fallback_multi(series, ChartConfig())
        
        assert "a" in output
        assert "b" in output


class TestDataSources:
    """Test data source functions."""
    
    def test_get_token_speed_data(self):
        """Test token speed data generation."""
        data = get_token_speed_data(24)
        assert len(data) == 96  # 24 * 4
        assert all(isinstance(x, float) for x in data)
        assert all(20 <= x <= 80 for x in data)
    
    def test_get_latency_data(self):
        """Test latency data generation."""
        data = get_latency_data(12)
        assert "local" in data
        assert "cloud" in data
        assert len(data["local"]) == 48
        assert len(data["cloud"]) == 48
    
    def test_get_memory_decay_data(self):
        """Test memory decay data generation."""
        data = get_memory_decay_data(6)
        assert "importance" in data
        assert "access_count" in data
        assert len(data["importance"]) == 24
    
    def test_get_egress_bytes_data(self):
        """Test egress bytes data generation."""
        data = get_egress_bytes_data(3)
        assert "prompt" in data
        assert "image" in data
        assert "spine" in data


class TestRenderAnalytics:
    """Test render_analytics function."""
    
    def test_render_tokens(self):
        """Test rendering tokens metric."""
        output = render_analytics("tokens", hours=12)
        assert "Token Generation Speed" in output
    
    def test_render_latency(self):
        """Test rendering latency metric."""
        output = render_analytics("latency", hours=6)
        assert "Inference Latency" in output
    
    def test_render_decay(self):
        """Test rendering decay metric."""
        output = render_analytics("decay", hours=3)
        assert "Memory Importance Decay" in output
    
    def test_render_egress(self):
        """Test rendering egress metric."""
        output = render_analytics("egress", hours=1)
        assert "Egress Bytes" in output
    
    def test_render_unknown_metric(self):
        """Test rendering unknown metric."""
        output = render_analytics("unknown")
        assert "Unknown metric" in output
    
    def test_render_json(self):
        """Test rendering as JSON."""
        output = render_analytics("tokens", hours=2, as_json=True)
        import json
        data = json.loads(output)
        assert data["metric"] == "tokens"
        assert data["hours"] == 2
        assert "data" in data