"""Hardware profiling for the provider layer (v0.6.0).

Produces a provider-independent :class:`~providers.contracts.HardwareProfile`
of the host machine: CPU, RAM, GPU/VRAM, OS, storage, and the
availability of the major local-acceleration stacks (CUDA, Metal, DirectML).

All introspection is best-effort and dependency-tolerant: if a library is
missing or raises, the corresponding field degrades to ``False`` / ``0``
rather than crashing the provider layer.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional

import psutil

from ..contracts import HardwareProfile

logger = logging.getLogger(__name__)

#: Long enough for a cold nvidia-smi on a loaded machine, short enough that a
#: wedged driver cannot stall boot. Hardware detection is on the startup path.
_PROBE_TIMEOUT_S = 4.0

#: The occupancy probe runs before every reply, not once at boot, so it gets a
#: much tighter budget than capacity detection. A slow answer here is worse than
#: no answer: the fallback is to say nothing about a swap, which is correct and
#: costs the user an indicator, while waiting costs them the reply. Same
#: reasoning as the one-second timeout on Ollama's residency probe.
_OCCUPANCY_TIMEOUT_S = 1.0

#: Where Windows records adapter memory as a 64-bit value. The obvious source,
#: Win32_VideoController.AdapterRAM, is a uint32 and saturates at 4 GB — it
#: reports 4294967295 for a 12 GB card, which is precisely the kind of confident
#: wrong number this module exists to avoid.
_WIN_GPU_REG_PATH = (
    r"HKLM:\SYSTEM\CurrentControlSet\Control\Class"
    r"\{4d36e968-e325-11ce-bfc1-08002be10318}\0*"
)


@dataclass(frozen=True)
class _GpuReading:
    """One probe of the GPU, or the absence of one.

    ``vram_bytes`` is None whenever capacity could not be established. It is
    never 0 — zero is a measurement meaning "a GPU with no memory", which is not
    a machine that exists.
    """

    name: Optional[str] = None
    vram_bytes: Optional[int] = None
    #: Which probe produced this, for the log line that explains a refusal.
    source: str = "none"


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

    # --- GPU acceleration ---
    #
    # None of this goes through torch any more. Reading VRAM through
    # `torch.cuda.get_device_properties` made a 528 MB deep-learning framework
    # the only thing standing between the product and knowing how much memory
    # the card has — and it did not even work: torch is not installed in a
    # packaged build, so `_vram_bytes` returned None on every user's machine and
    # the residency fit gate never engaged. The unit tests passed against a
    # pinned profile the whole time.
    #
    # nvidia-smi ships with the driver, so any machine that can run CUDA
    # inference already has it. Windows records adapter memory in the registry
    # as a 64-bit value, which covers AMD and Intel. Everything else reports
    # unknown, which is a true statement rather than a convenient one.

    def _gpu_reading(self) -> _GpuReading:
        """Probe the GPU once and reuse the answer.

        Cached per instance because `profile()` asks four separate questions
        that all resolve to the same reading, and shelling out four times on the
        startup path to learn the same fact is waste the user pays for.
        """
        cached = getattr(self, "_cached_reading", None)
        if cached is None:
            cached = self._probe_gpu()
            self._cached_reading = cached
            logger.debug(
                "Hardware: GPU probe via %s — name=%s vram=%s",
                cached.source,
                cached.name,
                cached.vram_bytes,
            )
        return cached

    def _probe_gpu(self) -> _GpuReading:
        for probe in (self._probe_nvidia_smi, self._probe_windows_registry):
            try:
                reading = probe()
            except Exception as exc:
                logger.debug("Hardware: %s failed: %s", probe.__name__, exc)
                continue
            if reading is not None:
                return reading
        return _GpuReading()

    def _probe_nvidia_smi(self) -> Optional[_GpuReading]:
        """Total VRAM and adapter name from the NVIDIA driver.

        Reports the card's total memory, not what is free. The residency
        calculation subtracts the models it intends to hold; subtracting
        whatever happened to be resident during boot would make the answer
        depend on when the probe ran.
        """
        out = self._run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total,name",
                "--format=csv,noheader,nounits",
            ]
        )
        if not out:
            return None

        # One line per GPU. Take the first: multi-GPU residency planning is a
        # separate problem, and picking the largest would imply we can place a
        # model on a specific device, which nothing here can do yet.
        first = out.splitlines()[0]
        mib_text, _, name = first.partition(",")
        mib = int(mib_text.strip())
        if mib <= 0:
            return None
        return _GpuReading(
            name=name.strip() or None,
            vram_bytes=mib * 1024 * 1024,
            source="nvidia-smi",
        )

    def _probe_windows_registry(self) -> Optional[_GpuReading]:
        """Adapter memory for non-NVIDIA cards on Windows."""
        if platform.system() != "Windows":
            return None

        out = self._run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "$a = Get-ItemProperty -Path '"
                + _WIN_GPU_REG_PATH
                + "' -ErrorAction SilentlyContinue | "
                "Where-Object { $_.'HardwareInformation.qwMemorySize' } | "
                "Select-Object -First 1; "
                "if ($a) { "
                "  \"$($a.'HardwareInformation.qwMemorySize')|$($a.DriverDesc)\" }",
            ]
        )
        if not out:
            return None

        size_text, _, name = out.splitlines()[0].partition("|")
        size = int(size_text.strip())
        if size <= 0:
            return None
        return _GpuReading(
            name=name.strip() or None,
            vram_bytes=size,
            source="windows-registry",
        )

    @staticmethod
    def _run(cmd: list[str], *, timeout: float = _PROBE_TIMEOUT_S) -> Optional[str]:
        """Run a probe, or return None. Never raises, never blocks for long."""
        kwargs = {}
        if platform.system() == "Windows":
            # Without this every probe flashes a console window, which on the
            # startup path means the app appears to blink on launch.
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            **kwargs,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def _cuda_available(self) -> bool:
        return self._gpu_reading().source == "nvidia-smi"

    def _metal_available(self) -> bool:
        """Metal is present on every Mac this product could run on.

        Determined from the platform rather than by asking a framework, which
        is both faster and correct in a packaged build where torch is absent.
        Note that this says an accelerator exists, not that it can be sized —
        `_vram_bytes` still reports None, because Apple shares one memory pool
        with the CPU and there is no separate VRAM figure to report.
        """
        return platform.system() == "Darwin"

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
        named = self._gpu_reading().name
        if named:
            return named
        if self._metal_available():
            return "Apple Silicon (unified memory)"
        if self._directml_available():
            return "DirectML device"
        return "unknown"

    def _vram_bytes(self) -> Optional[int]:
        """Total VRAM in bytes, or None when it cannot be determined.

        None on Metal — Apple Silicon shares one memory pool with the CPU, so
        there is no separate VRAM figure, and reporting system RAM would
        overstate what a model can actually claim. None where no probe could
        establish a capacity.

        Never 0. Zero is a measurement meaning "a GPU with no memory", which is
        not a machine that exists, and anything sizing a model against it would
        conclude that nothing fits.
        """
        return self._gpu_reading().vram_bytes

    def vram_used_bytes(self) -> Optional[int]:
        """VRAM occupied on the card *right now*, or None.

        Deliberately outside `profile()` and deliberately not cached. Capacity
        is a property of the machine and is asked once at boot; occupancy
        changes between one reply and the next, so a cached answer here would
        be a stale number wearing a measurement's authority.

        It exists because occupancy cannot always be reached by adding up what
        Zaram knows about. `swap_preflight` sums the sizes each local server
        reports for what it holds, and a server that names the model without
        sizing it leaves that sum unanswerable — TabbyAPI is exactly that
        shape, because no OpenAI-compatible route carries a memory figure. The
        driver can answer regardless, because it measures the card rather than
        asking its tenants.

        None whenever it cannot be established: no NVIDIA driver, a Mac (Apple
        shares one memory pool and there is no separate figure to report), or a
        probe that failed. **Zero, unlike in `_vram_bytes`, is a real reading
        here** — an idle card genuinely holds nothing, whereas a card with no
        memory is not a machine that exists. Same discipline, opposite
        conclusion, because it is a different quantity.
        """
        if self._gpu_reading().source != "nvidia-smi":
            return None
        try:
            out = self._run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used",
                    "--format=csv,noheader,nounits",
                ],
                timeout=_OCCUPANCY_TIMEOUT_S,
            )
        except Exception as exc:
            logger.debug("Hardware: VRAM occupancy probe failed: %s", exc)
            return None
        if not out:
            return None
        # The first line, to stay consistent with `_probe_nvidia_smi`: it takes
        # the first card because placing a model on a specific device is not
        # something anything here can do, and reading occupancy off a different
        # card than capacity would be worse than reading neither.
        try:
            mib = int(out.splitlines()[0].strip())
        except ValueError:
            return None
        return mib * 1024 * 1024 if mib >= 0 else None
