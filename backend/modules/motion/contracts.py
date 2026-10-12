"""Contracts for the Code-to-Frame video generation pipeline.

This module defines the core data models for describing motion graphics
as composable layers with keyframe animations. It owns no implementations —
only the data shapes that the motion runtime depends on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class LayerType(str, Enum):
    """Rendering backend for a motion layer."""

    HTML = "html"
    SVG = "svg"
    CANVAS = "canvas"
    WEBGL = "webgl"


# Valid aspect ratio presets
ASPECT_RATIOS: Dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "4:3": (1440, 1080),
    "21:9": (2560, 1080),
}

DEFAULT_ASPECT_RATIO = "16:9"
MAX_DURATION = 60  # seconds, configurable via ZARAM_MOTION_MAX_DURATION


@dataclass(frozen=True)
class Keyframe:
    """A single keyframe in an animation timeline.

    Attributes:
        time: Timestamp in seconds from the start of the animation (>= 0).
        properties: CSS-style property map (e.g., {"opacity": "0.5", "transform": "translateX(100px)"}).
        easing: Easing function name (default: "linear").
    """

    time: float
    properties: Dict[str, Any]
    easing: str = "linear"

    def __post_init__(self) -> None:
        if self.time < 0:
            raise ValueError(f"keyframe time must be >= 0, got {self.time}")
        if not isinstance(self.properties, dict):
            raise ValueError("keyframe properties must be a dict")
        # Validate easing is a known CSS value or cubic-bezier
        valid_easings = {
            "linear", "ease", "ease-in", "ease-out", "ease-in-out",
            "step-start", "step-end"
        }
        if self.easing not in valid_easings and not self.easing.startswith("cubic-bezier("):
            # Allow custom cubic-bezier but warn for unknown named easings
            pass


@dataclass(frozen=True)
class MotionLayer:
    """A composable layer in a motion composition.

    Attributes:
        id: Unique identifier for the layer (non-empty).
        type: Rendering backend (HTML, SVG, CANVAS, WEBGL).
        content: Layer content — HTML markup, SVG source, Canvas drawing commands, or WebGL shader.
        keyframes: Ordered list of keyframes (at least one, sorted by time, unique times).
        z_index: Stacking order (default: 0).
        opacity: Layer opacity in [0, 1] (default: 1.0).
        transform_origin: CSS transform-origin (default: "center center").
    """

    id: str
    type: LayerType
    content: str
    keyframes: List[Keyframe]
    z_index: int = 0
    opacity: float = 1.0
    transform_origin: str = "center center"

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("layer id must be non-empty")
        if not self.content or not self.content.strip():
            raise ValueError("layer content must be non-empty")
        if not self.keyframes:
            raise ValueError("layer must have at least one keyframe")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError(f"opacity must be in [0, 1], got {self.opacity}")

        # Verify keyframes are sorted by time and times are unique
        times = [kf.time for kf in self.keyframes]
        if times != sorted(times):
            raise ValueError("keyframes must be sorted by time (ascending)")
        if len(times) != len(set(times)):
            raise ValueError("keyframe times must be unique")


@dataclass(frozen=True)
class MotionScript:
    """Complete motion composition script.

    Attributes:
        version: Script format version (default: "1.0").
        duration: Total duration in seconds (> 0, <= MAX_DURATION).
        fps: Frames per second (0 < fps <= 120).
        width: Canvas width in pixels (0 < width <= 7680).
        height: Canvas height in pixels (0 < height <= 7680).
        background: Background color or "transparent" (default: "transparent").
        layers: List of motion layers (at least one, unique IDs).
        metadata: Arbitrary metadata dictionary.
        aspect_ratio: Aspect ratio preset used (default: "16:9").
    """

    version: str = "1.0"
    duration: float = 10.0
    fps: int = 30
    width: int = 1920
    height: int = 1080
    background: str = "transparent"
    layers: List[MotionLayer] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    aspect_ratio: str = DEFAULT_ASPECT_RATIO

    def __post_init__(self) -> None:
        if self.duration <= 0:
            raise ValueError(f"duration must be > 0, got {self.duration}")
        if self.duration > MAX_DURATION:
            raise ValueError(f"duration must be <= {MAX_DURATION}s, got {self.duration}s")
        if not 0 < self.fps <= 120:
            raise ValueError(f"fps must be in (0, 120], got {self.fps}")
        if not 0 < self.width <= 7680:
            raise ValueError(f"width must be in (0, 7680], got {self.width}")
        if not 0 < self.height <= 7680:
            raise ValueError(f"height must be in (0, 7680], got {self.height}")
        if not self.layers:
            raise ValueError("script must have at least one layer")
        if self.aspect_ratio not in ASPECT_RATIOS:
            raise ValueError(f"aspect_ratio must be one of {list(ASPECT_RATIOS.keys())}, got {self.aspect_ratio}")

        # Verify unique layer IDs
        layer_ids = [layer.id for layer in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            raise ValueError("layer IDs must be unique")

        # Verify all keyframes are within duration
        for layer in self.layers:
            for kf in layer.keyframes:
                if kf.time > self.duration:
                    raise ValueError(
                        f"keyframe at t={kf.time}s exceeds script duration {self.duration}s "
                        f"(layer: {layer.id})"
                    )

        # Verify width/height match aspect ratio
        expected_w, expected_h = ASPECT_RATIOS[self.aspect_ratio]
        if self.width != expected_w or self.height != expected_h:
            raise ValueError(
                f"width/height ({self.width}x{self.height}) must match aspect_ratio "
                f"{self.aspect_ratio} ({expected_w}x{expected_h})"
            )


@dataclass(frozen=True)
class MotionAsset:
    """Rendered motion asset with its generating script and HTML timeline.

    Attributes:
        script: The MotionScript that generated this asset.
        html_timeline: Self-contained HTML document that plays the animation.
        duration_ms: Total duration in milliseconds (computed from script).
    """

    script: MotionScript
    html_timeline: str
    duration_ms: int

    def __post_init__(self) -> None:
        # Validate computed properties match script
        expected_duration_ms = int(self.script.duration * 1000)
        if self.duration_ms != expected_duration_ms:
            raise ValueError(
                f"duration_ms ({self.duration_ms}) must equal "
                f"script.duration * 1000 ({expected_duration_ms})"
            )

    @property
    def width(self) -> int:
        """Canvas width from the generating script."""
        return self.script.width

    @property
    def height(self) -> int:
        """Canvas height from the generating script."""
        return self.script.height

    @property
    def fps(self) -> int:
        """Frames per second from the generating script."""
        return self.script.fps

    @property
    def duration(self) -> float:
        """Total duration in seconds from the generating script."""
        return self.script.duration

    @property
    def layer_count(self) -> int:
        """Number of layers in the composition."""
        return len(self.script.layers)