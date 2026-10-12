"""ASCII line charts using asciichart for analytics visualization."""

from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

try:
    import asciichart
except ImportError:
    asciichart = None


class ChartPreset(Enum):
    """Pre-defined chart configurations."""
    TOKEN_SPEED = "token_speed"
    LATENCY = "latency"
    MEMORY_DECAY = "memory_decay"
    EGRESS_BYTES = "egress_bytes"


@dataclass
class ChartConfig:
    """Configuration for a chart."""
    height: int = 15
    width: int = 80
    colors: List[str] = None
    title: Optional[str] = None
    x_label: Optional[str] = None
    y_label: Optional[str] = None
    
    def __post_init__(self):
        if self.colors is None:
            # ANSI color codes: green, blue, red, yellow, magenta, cyan
            self.colors = ["\033[32m", "\033[34m", "\033[31m", "\033[33m", "\033[35m", "\033[36m"]


class ChartRenderer:
    """Renders ASCII line charts using asciichart."""
    
    PRESET_CONFIGS = {
        ChartPreset.TOKEN_SPEED: ChartConfig(
            title="Token Generation Speed (tokens/sec)",
            y_label="tokens/s",
            colors=["\033[32m", "\033[34m"],
        ),
        ChartPreset.LATENCY: ChartConfig(
            title="Inference Latency (ms)",
            y_label="ms",
            colors=["\033[31m", "\033[33m", "\033[32m"],
        ),
        ChartPreset.MEMORY_DECAY: ChartConfig(
            title="Memory Importance Decay",
            y_label="importance",
            colors=["\033[35m", "\033[36m"],
        ),
        ChartPreset.EGRESS_BYTES: ChartConfig(
            title="Egress Bytes Over Time",
            y_label="bytes",
            colors=["\033[31m", "\033[33m", "\033[32m", "\033[34m"],
        ),
    }
    
    def __init__(self, config: Optional[ChartConfig] = None, use_fallback: bool = None):
        if asciichart is None:
            raise ImportError("asciichart not installed. Run: pip install asciichart")
        self.config = config or ChartConfig()
        # Use fallback on Windows to avoid encoding issues
        import sys
        self.use_fallback = use_fallback if use_fallback is not None else (sys.platform == "win32")
    
    def render_line_chart(
        self,
        data: List[float],
        label: str = "",
        config: Optional[ChartConfig] = None,
    ) -> str:
        """Render a single line chart."""
        if not data:
            return "No data to chart."
        
        cfg = config or self.config
        
        if self.use_fallback:
            return self._fallback_chart(data, label, cfg)
        
        # Prepare series with colors
        colored_data = []
        for i, val in enumerate(data):
            color = cfg.colors[i % len(cfg.colors)]
            colored_data.append([val])
        
        # Configure asciichart
        chart_config = {
            "height": cfg.height,
            "width": cfg.width,
            "colors": cfg.colors[:len(data)] if len(data) <= len(cfg.colors) else cfg.colors,
        }
        
        try:
            chart = asciichart.plot(colored_data, chart_config)
        except Exception:
            # Fallback: simple text representation
            return self._fallback_chart(data, label, cfg)
        
        lines = []
        if cfg.title:
            lines.append(f"\n{cfg.title}")
            lines.append("=" * len(cfg.title))
        
        if label:
            lines.append(f"Series: {label}")
        
        lines.append(chart)
        
        if cfg.x_label or cfg.y_label:
            axis_info = []
            if cfg.x_label:
                axis_info.append(f"X: {cfg.x_label}")
            if cfg.y_label:
                axis_info.append(f"Y: {cfg.y_label}")
            lines.append(" | ".join(axis_info))
        
        return "\n".join(lines)
    
    def render_multi_series(
        self,
        series: Dict[str, List[float]],
        config: Optional[ChartConfig] = None,
    ) -> str:
        """Render multiple series on the same chart."""
        if not series:
            return "No data to chart."
        
        cfg = config or self.config
        
        if self.use_fallback:
            return self._fallback_multi(series, cfg)
        
        # Find max length
        max_len = max(len(v) for v in series.values())
        
        # Pad shorter series with None
        padded_series = []
        labels = []
        for label, data in series.items():
            labels.append(label)
            if len(data) < max_len:
                padded = data + [None] * (max_len - len(data))
            else:
                padded = data[:max_len]
            padded_series.append(padded)
        
        # Prepare chart config with colors
        chart_colors = cfg.colors[:len(padded_series)]
        chart_config = {
            "height": cfg.height,
            "width": cfg.width,
            "colors": chart_colors,
        }
        
        try:
            chart = asciichart.plot(padded_series, chart_config)
        except Exception:
            return self._fallback_multi(series, cfg)
        
        lines = []
        if cfg.title:
            lines.append(f"\n{cfg.title}")
            lines.append("=" * len(cfg.title))
        
        lines.append("Series: " + ", ".join(f"{c}{l}\033[0m" for c, l in zip(chart_colors, labels)))
        lines.append(chart)
        
        if cfg.x_label or cfg.y_label:
            axis_info = []
            if cfg.x_label:
                axis_info.append(f"X: {cfg.x_label}")
            if cfg.y_label:
                axis_info.append(f"Y: {cfg.y_label}")
            lines.append(" | ".join(axis_info))
        
        return "\n".join(lines)
    
    def render_preset(
        self,
        preset: ChartPreset,
        data: Union[List[float], Dict[str, List[float]]],
    ) -> str:
        """Render using a pre-defined preset."""
        cfg = self.PRESET_CONFIGS.get(preset, self.config)
        
        if isinstance(data, dict):
            return self.render_multi_series(data, cfg)
        else:
            return self.render_line_chart(data, preset.value, cfg)
    
    def _fallback_chart(self, data: List[float], label: str, config: Optional[ChartConfig] = None) -> str:
        """Simple text fallback when asciichart fails."""
        if not data:
            return "No data"
        
        max_val = max(data)
        min_val = min(data)
        range_val = max_val - min_val if max_val != min_val else 1
        
        cfg = config or ChartConfig()
        title = cfg.title or ""
        
        lines = []
        if title:
            lines.append(f"\n{title}")
            lines.append("=" * len(title))
        
        lines.append(f"{label}: {len(data)} points, range [{min_val:.2f}, {max_val:.2f}]")
        
        # Simple ASCII sparkline
        width = 60
        step = max(1, len(data) // width)
        spark = ""
        for i in range(0, len(data), step):
            val = data[i]
            normalized = (val - min_val) / range_val
            bar_height = int(normalized * 8)
            spark += " .:-=+*#%@"[bar_height]
        
        lines.append(spark)
        
        if cfg.x_label or cfg.y_label:
            axis_info = []
            if cfg.x_label:
                axis_info.append(f"X: {cfg.x_label}")
            if cfg.y_label:
                axis_info.append(f"Y: {cfg.y_label}")
            lines.append(" | ".join(axis_info))
        
        return "\n".join(lines)
    
    def _fallback_multi(self, series: Dict[str, List[float]], config: Optional[ChartConfig] = None) -> str:
        """Multi-series fallback."""
        cfg = config or ChartConfig()
        
        lines = []
        if cfg.title:
            lines.append(f"\n{cfg.title}")
            lines.append("=" * len(cfg.title))
        
        for label, data in series.items():
            if data:
                max_val = max(data)
                min_val = min(data)
                lines.append(f"  {label}: {len(data)} points, range [{min_val:.2f}, {max_val:.2f}]")
        
        if cfg.x_label or cfg.y_label:
            axis_info = []
            if cfg.x_label:
                axis_info.append(f"X: {cfg.x_label}")
            if cfg.y_label:
                axis_info.append(f"Y: {cfg.y_label}")
            lines.append(" | ".join(axis_info))
        
        return "\n".join(lines)


# Data source functions (to be implemented with actual backend integration)
def get_token_speed_data(hours: int = 24) -> List[float]:
    """Get token speed data from the last N hours."""
    # Placeholder - would query actual metrics
    import random
    return [random.uniform(20, 80) for _ in range(min(hours * 4, 96))]


def get_latency_data(hours: int = 24) -> Dict[str, List[float]]:
    """Get latency data by model/provider."""
    import random
    return {
        "local": [random.uniform(50, 200) for _ in range(min(hours * 4, 96))],
        "cloud": [random.uniform(200, 1000) for _ in range(min(hours * 4, 96))],
    }


def get_memory_decay_data(hours: int = 24) -> Dict[str, List[float]]:
    """Get memory decay data."""
    import random
    return {
        "importance": [max(0.1, 1.0 - i * 0.01) for i in range(min(hours * 4, 96))],
        "access_count": [random.randint(0, 10) for _ in range(min(hours * 4, 96))],
    }


def get_egress_bytes_data(hours: int = 24) -> Dict[str, List[float]]:
    """Get egress bytes by data class."""
    import random
    return {
        "prompt": [random.uniform(100, 5000) for _ in range(min(hours * 4, 96))],
        "image": [random.uniform(10000, 5000000) for _ in range(min(hours * 4, 96))],
        "spine": [random.uniform(500, 10000) for _ in range(min(hours * 4, 96))],
    }


def render_analytics(
    metric: str,
    hours: int = 24,
    as_json: bool = False,
) -> str:
    """Render analytics chart for a metric."""
    metric = metric.lower()
    
    data_map = {
        "tokens": (ChartPreset.TOKEN_SPEED, get_token_speed_data(hours)),
        "token_speed": (ChartPreset.TOKEN_SPEED, get_token_speed_data(hours)),
        "latency": (ChartPreset.LATENCY, get_latency_data(hours)),
        "decay": (ChartPreset.MEMORY_DECAY, get_memory_decay_data(hours)),
        "memory_decay": (ChartPreset.MEMORY_DECAY, get_memory_decay_data(hours)),
        "egress": (ChartPreset.EGRESS_BYTES, get_egress_bytes_data(hours)),
        "egress_bytes": (ChartPreset.EGRESS_BYTES, get_egress_bytes_data(hours)),
    }
    
    if metric not in data_map:
        available = ", ".join(data_map.keys())
        return f"Unknown metric: {metric}. Available: {available}"
    
    preset, data = data_map[metric]
    
    if as_json:
        import json
        if isinstance(data, dict):
            return json.dumps({k: v for k, v in data.items()}, indent=2)
        else:
            return json.dumps({"metric": metric, "hours": hours, "data": data}, indent=2)
    
    renderer = ChartRenderer()
    return renderer.render_preset(preset, data)