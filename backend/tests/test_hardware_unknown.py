"""Hardware detection returns unknown, never a wrong number.

`vram_bytes` was an `int` defaulting to 0, and the only implementation that could
fill it read `torch.cuda.get_device_properties`. So on Metal and DirectML the
profile said "GPU available, 0 bytes of VRAM" — a sentence describing a machine
that does not exist.

The cost is not cosmetic. VRAM-tiered recommendation compares model size against
that number, so a false zero tells a Mac user nothing fits, and the product looks
weak on precisely the hardware it runs best on. A recommendation built on a false
zero is worse than no recommendation, because the user has no way to know it is
wrong.

These tests fake each acceleration stack rather than depending on the host, so
they assert the same thing on a CUDA box and a Mac.
"""

from __future__ import annotations

import pytest

from providers.contracts import HardwareProfile
from providers.discoverers.hardware import HardwareProfiler


def _no_probe_succeeds(monkeypatch, profiler):
    """Every capacity probe comes back empty.

    Faked at the probe, not at `_cuda_available`. Those flags used to be
    independent readings of torch; now `_cuda_available` is *derived from* the
    probe result, so patching it says nothing about what `_vram_bytes` returns.
    A test that fakes the wrong side of a dependency asserts nothing — these
    three failed the moment the detection was rewritten, which is the only
    reason the inversion was noticed.
    """
    monkeypatch.setattr(profiler, "_probe_nvidia_smi", lambda: None)
    monkeypatch.setattr(profiler, "_probe_windows_registry", lambda: None)


class TestVramIsNeverAFalseZero:
    def test_unknown_is_none_not_zero(self, monkeypatch):
        """The whole rule, in one assertion."""
        profiler = HardwareProfiler()
        _no_probe_succeeds(monkeypatch, profiler)
        monkeypatch.setattr(profiler, "_metal_available", lambda: True)

        assert profiler._vram_bytes() is None, (
            "Metal has no separate VRAM figure. Returning 0 would be a "
            "measurement; this is the absence of one."
        )

    def test_directml_reports_unknown(self, monkeypatch):
        profiler = HardwareProfiler()
        _no_probe_succeeds(monkeypatch, profiler)
        monkeypatch.setattr(profiler, "_metal_available", lambda: False)
        monkeypatch.setattr(profiler, "_directml_available", lambda: True)

        assert profiler._vram_bytes() is None

    def test_no_accelerator_reports_unknown(self, monkeypatch):
        profiler = HardwareProfiler()
        _no_probe_succeeds(monkeypatch, profiler)
        monkeypatch.setattr(profiler, "_metal_available", lambda: False)
        monkeypatch.setattr(profiler, "_directml_available", lambda: False)

        assert profiler._vram_bytes() is None

    def test_a_probe_reporting_zero_is_rejected_not_believed(self, monkeypatch):
        """A driver that answers 0 is malfunctioning, not describing a card.

        Believing it would produce "GPU available, 0 bytes" — the exact
        sentence this module exists to never say.
        """
        profiler = HardwareProfiler()
        monkeypatch.setattr(
            profiler, "_run", staticmethod(lambda cmd: "0, NVIDIA GeForce RTX 3060")
        )
        monkeypatch.setattr(profiler, "_probe_windows_registry", lambda: None)

        assert profiler._vram_bytes() is None

    def test_the_default_is_unknown(self):
        """A profile nobody filled in must not claim a GPU with no memory."""
        assert HardwareProfile().vram_bytes is None
        assert HardwareProfile().vram_known is False


class TestGpuAvailableMeansPlannable:
    def test_not_available_when_capacity_is_unknown(self, monkeypatch):
        """`gpu_available` answers "can residency be planned", not "is there one"."""
        profiler = HardwareProfiler()
        monkeypatch.setattr(profiler, "_vram_bytes", lambda: None)

        assert profiler._gpu_available() is False

    def test_available_when_capacity_is_known(self, monkeypatch):
        profiler = HardwareProfiler()
        monkeypatch.setattr(profiler, "_vram_bytes", lambda: 12 * 1024**3)

        assert profiler._gpu_available() is True

    def test_metal_still_reports_an_accelerator(self):
        """Saying "no GPU" on a Mac would be its own wrong answer.

        The two questions are kept separate: `gpu_available` is whether we can
        plan against it, `accelerator_present` is whether one exists.
        """
        profile = HardwareProfile(
            gpu_available=False, vram_bytes=None, metal_available=True
        )
        assert profile.accelerator_present is True
        assert profile.vram_known is False


class TestSerialisation:
    def test_vram_serialises_as_null(self):
        """The UI must be able to render "unknown". 0 would render as a number."""
        payload = HardwareProfile(vram_bytes=None).to_dict()
        assert payload["vram_bytes"] is None
        assert payload["vram_known"] is False

    def test_a_real_measurement_survives(self):
        payload = HardwareProfile(vram_bytes=12 * 1024**3, gpu_available=True).to_dict()
        assert payload["vram_bytes"] == 12 * 1024**3
        assert payload["vram_known"] is True

    @pytest.mark.parametrize("value", [None, 0, 8 * 1024**3])
    def test_vram_known_matches_the_value(self, value):
        """0 is a legitimate measurement to serialise — it just is not the
        default, and it is not what unknown looks like."""
        assert HardwareProfile(vram_bytes=value).vram_known is (value is not None)
