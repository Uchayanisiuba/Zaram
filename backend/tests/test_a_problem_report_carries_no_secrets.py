"""The problem report: what a person pastes to say something went wrong.

Zaram sends nothing on its own (rule 7g) and has no thumbs (rule 7f), so
feedback travels with the person. The report must be useful to a
maintainer and safe to paste anywhere: it names versions, hardware, models,
routing and the last egress *decisions* — and never a key, a body, a
document name or a remembered fact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.contracts import CapabilityLocality
from core.report import build_report


@dataclass
class _Model:
    id: str
    locality: CapabilityLocality
    context_length: Optional[int] = None
    available: bool = True


class _Catalog:
    def __init__(self, *models):
        self._m = list(models)

    def all(self):
        return self._m


@dataclass
class _Hw:
    cpu_model: str = "Ryzen 7"
    total_ram_bytes: int = 32_000_000_000
    gpu_name: str = "RTX 3060"
    vram_bytes: Optional[int] = 12_000_000_000


class _Manager:
    catalog = _Catalog(
        _Model("nvidia_nim:z-ai/glm-5.3-flash", CapabilityLocality.CLOUD, 131072),
        _Model("qwen3-14b-16k:latest", CapabilityLocality.LOCAL),
    )

    def hardware_profile(self):
        return _Hw()


@dataclass
class _Entry:
    at: float
    host: str
    decision: str
    reason: str
    body: Optional[str]
    data_class: str = "prompt"


class _Conn:
    provider_id = "nvidia_nim"
    api_key = "nvapi-SECRET-DO-NOT-SHOW"


class _Settings:
    class routing_preference:
        value = "auto"

    default_model = None
    task_models = {"document": "nvidia_nim:moonshotai/kimi-k2-instruct"}

    class image_locality:
        value = "cloud"


def test_the_report_names_what_a_maintainer_needs():
    text = build_report(
        manager=_Manager(),
        settings=_Settings(),
        connections=[_Conn()],
        egress_entries=[_Entry(1_800_000_000.0, "ai.api.nvidia.com", "allowed", "you confirmed the first image", "a lighthouse", "image")],
        images={"answers": "flux-schnell · NVIDIA NIM", "local_ok": False},
    )
    assert "Zaram 0.1.0" in text
    assert "RTX 3060" in text and "12.0 GB" in text
    assert "nvidia_nim:z-ai/glm-5.3-flash · cloud · window 131,072" in text
    assert "qwen3-14b-16k:latest · local" in text
    assert "document=nvidia_nim:moonshotai/kimi-k2-instruct" in text
    assert "Pictures: prefer cloud" in text
    assert "Can draw: yes — flux-schnell · NVIDIA NIM" in text
    assert "Connected providers: nvidia_nim" in text
    assert "ai.api.nvidia.com · image · allowed — you confirmed the first image" in text


def test_the_report_carries_no_key_and_no_body():
    text = build_report(
        manager=_Manager(),
        settings=_Settings(),
        connections=[_Conn()],
        egress_entries=[_Entry(1.0, "h", "allowed", "ok", "the client's day rate is £400")],
    )
    assert "nvapi-SECRET" not in text
    assert "day rate" not in text
    assert "Contains no conversation text" in text


def test_everything_unreadable_is_still_a_report():
    text = build_report()
    assert "Hardware: unknown" in text
    assert "none, or the catalogue could not be read" in text
    assert "settings could not be read" in text
    assert "Connected providers: none" in text
