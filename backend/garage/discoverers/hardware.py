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
from typing import Any, Dict, Optional

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
        return self._cuda_available() or self._metal_available() or self._directml_available()

    def _gpu_name(self) -> str:
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                return str(torch.cuda.get_device_name(0))
        except Exception:
            pass
        return "unknown"

    def _vram_bytes(self) -> int:
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                return int(props.total_memory)
        except Exception:
            pass
        return 0
