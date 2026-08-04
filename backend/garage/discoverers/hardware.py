"""Hardware profiling for the AI Garage (v0.6.0).

Produces a provider-independent :class:`~garage.contracts.HardwareProfile`
of the host machine: CPU, RAM, GPU/VRAM, OS, storage, and the
availability of the major local-acceleration stacks (CUDA, Metal, DirectML).

All introspection is best-effort and dependency-tolerant: if a library is
missing or raises, the corresponding field degrades to ``False`` / ``0``
rather than crashing the Garage.
"""

from __future__ import annotations

import logging
import platform
from typing import Optional

import psutil

from ..contracts import HardwareProfile

logger = logging.getLogger(__name__)


class HardwareProfiler:
    """Gathers a point-in-time hardware profile of the host machine."""

    def profile(self) -> HardwareProfile:
        return HardwareProfile(
            cpu_model=self._cpu_model(),
            cpu_count=psutil.cpu_count(logical=True) or 0,
            total_ram_bytes=psutil.virtual_memory().total,
            gpu_available=self._gpu_available(),
            gpu_name=self._gpu_name(),
            vram_bytes=self._vram_bytes(),
            os_name=platform.system(),
            os_version=platform.release(),
            storage_total_bytes=self._storage_total(),
            storage_free_bytes=self._storage_free(),
            cuda_available=self._cuda_available(),
            metal_available=self._metal_available(),
            directml_available=self._directml_available(),
        )

    # --- CPU / RAM / storage ---
    def _cpu_model(self) -> str:
        try:
            return platform.processor() or "unknown"
        except Exception:
            return "unknown"

    def _storage_total(self) -> int:
        try:
            return psutil.disk_usage("/").total
        except Exception:
            return 0

    def _storage_free(self) -> int:
        try:
            return psutil.disk_usage("/").free
        except Exception:
            return 0

    # --- GPU acceleration (lazy imports, never fatal) ---
    def _cuda_available(self) -> bool:
        try:
            import torch  # type: ignore

            return bool(torch.cuda.is_available())
        except Exception:
            return False

    def _metal_available(self) -> bool:
        try:
            import torch  # type: ignore

            backends = getattr(torch, "backends", None)
            mps = getattr(backends, "mps", None)
            return bool(getattr(mps, "is_available", lambda: False)())
        except Exception:
            return False

    def _directml_available(self) -> bool:
        import importlib.util as util

        return util.find_spec("torch_directml") is not None

    def _gpu_available(self) -> bool:
        """An accelerator is present *and* we can size it.

        Not the same as "a GPU exists". This previously returned True whenever
        any acceleration stack was found, including Metal and DirectML — where
        `_vram_bytes` had no implementation and returned 0. The pair "GPU
        available, 0 bytes VRAM" then flowed into anything sizing a model, which
        is a false zero of exactly the kind that makes a recommendation worse
        than no recommendation.

        Callers wanting the other question — is there an accelerator at all —
        should use `HardwareProfile.accelerator_present`, which stays true on a
        Mac because saying "no GPU" there would be its own wrong answer.
        """
        return self._vram_bytes() is not None

    def _gpu_name(self) -> str:
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                return str(torch.cuda.get_device_name(0))
            backends = getattr(torch, "backends", None)
            mps = getattr(backends, "mps", None)
            if getattr(mps, "is_available", lambda: False)():
                # Apple does not expose a device name through torch, and the
                # unified memory pool has no separate VRAM figure to report.
                return "Apple Silicon (unified memory)"
        except Exception:
            pass
        if self._directml_available():
            return "DirectML device"
        return "unknown"

    def _vram_bytes(self) -> Optional[int]:
        """Total VRAM in bytes, or None when it cannot be determined.

        None on Metal — Apple Silicon shares one memory pool with the CPU, so
        there is no separate VRAM figure and reporting the system RAM would
        overstate what a model can actually claim. None on DirectML, which
        exposes no capacity through torch. None with no accelerator at all.

        Never 0. Zero is a measurement meaning "a GPU with no memory", which is
        not a machine that exists.
        """
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                return int(props.total_memory)
        except Exception:
            pass
        return None
