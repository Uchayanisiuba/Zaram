"""Tests for the Presence Runtime shared contracts (v0.9.0).

The backend PresenceRuntime implementation has been removed in favor of the
desktop runtime as the single authoritative live-frame deliverer. This module
preserves contract coverage so the shared interface layer remains verified.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from runtime.presence.contracts import (
    AudioParams,
    EmbodimentHealth,
    EmbodimentStatus,
    EmotionParams,
    FrameMetadata,
    FrameState,
    IEmbodiment,
    SystemParams,
    VisualParams,
)


# ------------------------------------------------------------------
# Contract tests
# ------------------------------------------------------------------

class TestFrameState:
    def test_default_frame_state(self):
        fs = FrameState()
        assert fs.visual.presence == 0.5
        assert fs.system.state == "Idle"
        assert fs.sequence == 0

    def test_frame_state_to_dict_roundtrip(self):
        fs = FrameState(
            visual=VisualParams(presence=0.8, energy=0.6),
            audio=AudioParams(voice_level=0.9),
            emotion=EmotionParams(warmth=0.7),
            system=SystemParams(state="Thinking", cognitive_load=0.4),
            metadata=FrameMetadata(correlation_id="abc", version="2.0.0"),
            sequence=5,
        )
        data = fs.to_dict()
        assert data["visual"]["presence"] == 0.8
        assert data["audio"]["voiceLevel"] == 0.9
        assert data["emotion"]["warmth"] == 0.7
        assert data["system"]["state"] == "Thinking"
        assert data["metadata"]["correlationId"] == "abc"
        assert data["sequence"] == 5

        recovered = FrameState.from_dict(data)
        assert recovered.visual.presence == 0.8
        assert recovered.audio.voice_level == 0.9
        assert recovered.emotion.warmth == 0.7
        assert recovered.system.state == "Thinking"
        assert recovered.system.cognitive_load == 0.4
        assert recovered.metadata.correlation_id == "abc"
        assert recovered.metadata.version == "2.0.0"
        assert recovered.sequence == 5

    def test_frame_state_from_dict_defaults(self):
        fs = FrameState.from_dict({})
        assert fs.visual.presence == 0.5
        assert fs.system.state == "Idle"
        assert fs.sequence == 0


class TestEmbodimentStatus:
    def test_status_values(self):
        assert EmbodimentStatus.UNINITIALIZED.value == "uninitialized"
        assert EmbodimentStatus.RUNNING.value == "running"
        assert EmbodimentStatus.STOPPED.value == "stopped"


class TestEmbodimentHealth:
    def test_default_health(self):
        h = EmbodimentHealth()
        assert h.status == EmbodimentStatus.UNINITIALIZED
        assert h.frame_sequence == 0
        assert h.error is None

    def test_health_to_dict(self):
        h = EmbodimentHealth()
        h.frame_sequence = 3
        h.error = "boom"
        d = h.to_dict()
        assert d["frame_sequence"] == 3
        assert d["error"] == "boom"


class TestIEmbodimentProtocol:
    def test_protocol_exists(self):
        assert hasattr(IEmbodiment, "initialize")
        assert hasattr(IEmbodiment, "start")
        assert hasattr(IEmbodiment, "pause")
        assert hasattr(IEmbodiment, "resume")
        assert hasattr(IEmbodiment, "shutdown")
        assert hasattr(IEmbodiment, "set_frame_state")
        assert hasattr(IEmbodiment, "get_status")


# ------------------------------------------------------------------
# Renderer isolation tests (static analysis)
# ------------------------------------------------------------------

class TestRendererIsolation:
    def test_no_embodiment_imports_in_other_runtimes(self):
        """Verify no runtime module imports embodiment or renderer code."""
        import ast
        import os

        runtime_dirs = [
            Path(__file__).resolve().parent.parent.parent.parent / "voice",
            Path(__file__).resolve().parent.parent.parent.parent / "media",
            Path(__file__).resolve().parent.parent.parent.parent / "garage",
            Path(__file__).resolve().parent.parent.parent.parent / "runtimes",
            Path(__file__).resolve().parent.parent.parent.parent / "core",
        ]

        forbidden = ["runtime.presence", "OrbRenderer", "OrbEngine", "LivingOrb"]

        violations = []
        for root_dir in runtime_dirs:
            for dirpath, _, filenames in os.walk(root_dir):
                for fname in filenames:
                    if not fname.endswith(".py"):
                        continue
                    fpath = Path(dirpath) / fname
                    try:
                        text = fpath.read_text(encoding="utf-8")
                    except Exception:
                        continue
                    for token in forbidden:
                        if token in text:
                            if "runtime/presence" in str(fpath):
                                continue
                            violations.append(f"{fpath}: imports {token}")

        assert violations == [], f"Renderer isolation violated: {violations}"
