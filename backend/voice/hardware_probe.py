"""Hardware detection for 4-Tier Voice Pipeline routing.

Detects VRAM, System RAM, Cloud LLM status, and local LLM VRAM footprint
to determine the optimal TTS tier.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HardwareProfile:
    """Complete hardware profile for tier routing decisions."""

    # GPU / VRAM
    gpu_vendor: str = "unknown"  # nvidia, amd, intel, apple, unknown
    gpu_name: str = "unknown"
    total_vram_gb: Optional[float] = None
    free_vram_gb: Optional[float] = None

    # System RAM
    total_system_ram_gb: Optional[float] = None
    free_system_ram_gb: Optional[float] = None

    # Cloud / Local LLM status
    cloud_llm_active: bool = False
    cloud_llm_provider: Optional[str] = None  # openrouter, anthropic, etc.

    local_llm_active: bool = False
    local_llm_model_id: Optional[str] = None
    local_llm_vram_footprint_gb: Optional[float] = None

    # Platform
    os_name: str = field(default_factory=lambda: platform.system().lower())
    arch: str = field(default_factory=lambda: platform.machine().lower())

    # Raw data for debugging
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gpu_vendor": self.gpu_vendor,
            "gpu_name": self.gpu_name,
            "total_vram_gb": self.total_vram_gb,
            "free_vram_gb": self.free_vram_gb,
            "total_system_ram_gb": self.total_system_ram_gb,
            "free_system_ram_gb": self.free_system_ram_gb,
            "cloud_llm_active": self.cloud_llm_active,
            "cloud_llm_provider": self.cloud_llm_provider,
            "local_llm_active": self.local_llm_active,
            "local_llm_model_id": self.local_llm_model_id,
            "local_llm_vram_footprint_gb": self.local_llm_vram_footprint_gb,
            "os_name": self.os_name,
            "arch": self.arch,
        }


def _run_cmd(cmd: List[str], timeout: float = 5.0) -> Optional[str]:
    """Run a command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _parse_nvidia_smi() -> Dict[str, Any]:
    """Parse nvidia-smi for VRAM info."""
    out = _run_cmd(["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"])
    if not out:
        return {}

    gpus = []
    for line in out.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 3:
            try:
                gpus.append({
                    "name": parts[0],
                    "total_mb": int(parts[1]),
                    "free_mb": int(parts[2]),
                })
            except ValueError:
                pass

    if not gpus:
        return {}

    # Use the GPU with most free VRAM
    best = max(gpus, key=lambda g: g["free_mb"])
    return {
        "gpu_vendor": "nvidia",
        "gpu_name": best["name"],
        "total_vram_gb": round(best["total_mb"] / 1024, 2),
        "free_vram_gb": round(best["free_mb"] / 1024, 2),
    }


def _parse_rocm_smi() -> Dict[str, Any]:
    """Parse rocm-smi for AMD VRAM info."""
    out = _run_cmd(["rocm-smi", "--showmeminfo", "vram", "--csv"])
    if not out:
        return {}

    lines = out.strip().split("\n")
    if len(lines) < 2:
        return {}

    # Header + data rows
    headers = [h.strip() for h in lines[0].split(",")]
    best = {"free_mb": 0, "total_mb": 0, "name": "AMD GPU"}

    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(headers):
            continue
        try:
            row = dict(zip(headers, parts))
            free_mb = int(row.get("VRAM Free Memory (MB)", 0))
            total_mb = int(row.get("VRAM Total Memory (MB)", 0))
            if free_mb > best["free_mb"]:
                best = {"free_mb": free_mb, "total_mb": total_mb, "name": row.get("Card series", "AMD GPU")}
        except Exception:
            pass

    if best["total_mb"] == 0:
        return {}

    return {
        "gpu_vendor": "amd",
        "gpu_name": best["name"],
        "total_vram_gb": round(best["total_mb"] / 1024, 2),
        "free_vram_gb": round(best["free_mb"] / 1024, 2),
    }


def _parse_system_profiler() -> Dict[str, Any]:
    """Parse macOS system_profiler for Apple Silicon VRAM (unified memory)."""
    if platform.system() != "Darwin":
        return {}

    out = _run_cmd(["system_profiler", "SPDisplaysDataType", "-json"])
    if not out:
        return {}

    try:
        import json
        data = json.loads(out)
        for display in data.get("SPDisplaysDataType", []):
            if "VRAM" in str(display):
                # Apple Silicon uses unified memory; VRAM == System RAM effectively
                vram_str = display.get("sppci_vram", "0 GB")
                # Format: "8 GB"
                vram_gb = float(vram_str.split()[0]) if vram_str else 0
                return {
                    "gpu_vendor": "apple",
                    "gpu_name": display.get("sppci_model", "Apple GPU"),
                    "total_vram_gb": vram_gb,
                    "free_vram_gb": None,  # Unified memory - no separate free VRAM
                }
    except Exception:
        pass
    return {}


def _get_windows_vram() -> Dict[str, Any]:
    """Get VRAM on Windows via WMI (fallback)."""
    if platform.system() != "Windows":
        return {}

    out = _run_cmd([
        "powershell", "-Command",
        "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json"
    ])
    if not out:
        return {}

    try:
        import json
        data = json.loads(out)
        gpus = data if isinstance(data, list) else [data]
        best = {"free_mb": 0, "total_mb": 0, "name": "Unknown GPU"}
        for gpu in gpus:
            name = gpu.get("Name", "Unknown")
            adapter_ram = gpu.get("AdapterRAM")
            if adapter_ram:
                total_mb = int(adapter_ram) // (1024 * 1024)
                # Win32_VideoController.AdapterRAM is often capped at 4GB (uint32)
                # and doesn't report free VRAM. Use as last resort.
                if total_mb > best["total_mb"]:
                    best = {"free_mb": None, "total_mb": total_mb, "name": name}
        if best["total_mb"] > 0:
            vendor = "nvidia" if "nvidia" in best["name"].lower() else \
                     "amd" if "amd" in best["name"].lower() or "radeon" in best["name"].lower() else \
                     "intel" if "intel" in best["name"].lower() else "unknown"
            return {
                "gpu_vendor": vendor,
                "gpu_name": best["name"],
                "total_vram_gb": round(best["total_mb"] / 1024, 2),
                "free_vram_gb": round(best["free_mb"] / 1024, 2) if best["free_mb"] else None,
            }
    except Exception:
        pass
    return {}


def _get_system_ram() -> Dict[str, Optional[float]]:
    """Get system RAM using psutil if available, else platform fallback."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_system_ram_gb": round(mem.total / (1024**3), 2),
            "free_system_ram_gb": round(mem.available / (1024**3), 2),
        }
    except ImportError:
        # Fallback: rough estimates
        if platform.system() == "Linux":
            out = _run_cmd(["grep", "MemTotal", "/proc/meminfo"])
            if out:
                kb = int(out.split()[1])
                return {"total_system_ram_gb": round(kb / (1024**2), 2), "free_system_ram_gb": None}
        elif platform.system() == "Darwin":
            out = _run_cmd(["sysctl", "-n", "hw.memsize"])
            if out:
                bytes_ = int(out.strip())
                return {"total_system_ram_gb": round(bytes_ / (1024**3), 2), "free_system_ram_gb": None}
        elif platform.system() == "Windows":
            out = _run_cmd(["wmic", "OS", "get", "TotalVisibleMemorySize", "/value"])
            if out:
                for line in out.split("\n"):
                    if "TotalVisibleMemorySize" in line:
                        kb = int(line.split("=")[1])
                        return {"total_system_ram_gb": round(kb / (1024**2), 2), "free_system_ram_gb": None}
    return {"total_system_ram_gb": None, "free_system_ram_gb": None}


def _detect_cloud_llm() -> Dict[str, Any]:
    """Detect if a cloud LLM is configured/active via environment or config."""
    # Check common env vars for cloud LLM keys
    cloud_indicators = {
        "openrouter": ["OPENROUTER_API_KEY", "OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "together": ["TOGETHER_API_KEY"],
        "fireworks": ["FIREWORKS_API_KEY"],
    }

    for provider, env_vars in cloud_indicators.items():
        for var in env_vars:
            if os.getenv(var):
                return {"cloud_llm_active": True, "cloud_llm_provider": provider}

    # Could also check Zaram's model registry / config for active cloud model
    return {"cloud_llm_active": False, "cloud_llm_provider": None}


def _detect_local_llm() -> Dict[str, Any]:
    """Detect local LLM (Ollama, TabbyAPI, etc.) and estimate VRAM footprint."""
    # Check if Ollama is running and has models loaded
    try:
        import requests
        resp = requests.get("http://127.0.0.1:11434/api/ps", timeout=2)
        if resp.ok:
            data = resp.json()
            models = data.get("models", [])
            if models:
                # Estimate VRAM from model size
                model = models[0]
                model_name = model.get("name", "")
                size_bytes = model.get("size", 0)
                size_gb = size_bytes / (1024**3) if size_bytes else None
                return {
                    "local_llm_active": True,
                    "local_llm_model_id": model_name,
                    "local_llm_vram_footprint_gb": size_gb,
                }
    except Exception:
        pass

    # Check TabbyAPI
    try:
        import requests
        resp = requests.get("http://127.0.0.1:1234/v1/models", timeout=2)
        if resp.ok:
            data = resp.json()
            models = data.get("data", [])
            if models:
                model_id = models[0].get("id", "")
                # Rough estimate based on model name
                vram_est = _estimate_model_vram(model_id)
                return {
                    "local_llm_active": True,
                    "local_llm_model_id": model_id,
                    "local_llm_vram_footprint_gb": vram_est,
                }
    except Exception:
        pass

    return {"local_llm_active": False, "local_llm_model_id": None, "local_llm_vram_footprint_gb": None}


def _estimate_model_vram(model_id: str) -> Optional[float]:
    """Rough VRAM estimate for common local models."""
    model_id = model_id.lower()
    # Parameter count estimates (billions) -> VRAM at 4-bit quant (~0.5 GB/B)
    if any(x in model_id for x in ["70b", "72b"]):
        return 40.0
    if any(x in model_id for x in ["30b", "32b", "34b"]):
        return 20.0
    if any(x in model_id for x in ["27b"]):
        return 18.0
    if any(x in model_id for x in ["14b", "13b"]):
        return 10.0
    if any(x in model_id for x in ["8b", "7b", "9b"]):
        return 6.0
    if any(x in model_id for x in ["3b", "4b", "1b", "2b", "0.5b"]):
        return 3.0
    return None


def probe_hardware() -> HardwareProfile:
    """Run all hardware probes and return a complete HardwareProfile."""
    profile_data: Dict[str, Any] = {}

    # GPU / VRAM detection (try multiple methods in order of reliability)
    for probe in [_parse_nvidia_smi, _parse_rocm_smi, _parse_system_profiler, _get_windows_vram]:
        result = probe()
        if result:
            profile_data.update(result)
            break

    # System RAM
    profile_data.update(_get_system_ram())

    # Cloud LLM
    profile_data.update(_detect_cloud_llm())

    # Local LLM
    profile_data.update(_detect_local_llm())

    # Build profile
    return HardwareProfile(
        gpu_vendor=profile_data.get("gpu_vendor", "unknown"),
        gpu_name=profile_data.get("gpu_name", "unknown"),
        total_vram_gb=profile_data.get("total_vram_gb"),
        free_vram_gb=profile_data.get("free_vram_gb"),
        total_system_ram_gb=profile_data.get("total_system_ram_gb"),
        free_system_ram_gb=profile_data.get("free_system_ram_gb"),
        cloud_llm_active=profile_data.get("cloud_llm_active", False),
        cloud_llm_provider=profile_data.get("cloud_llm_provider"),
        local_llm_active=profile_data.get("local_llm_active", False),
        local_llm_model_id=profile_data.get("local_llm_model_id"),
        local_llm_vram_footprint_gb=profile_data.get("local_llm_vram_footprint_gb"),
        raw=profile_data,
    )


# Module-level cache for single-probe-per-session
_cached_profile: Optional[HardwareProfile] = None


def get_hardware_profile(force_refresh: bool = False) -> HardwareProfile:
    """Get cached hardware profile, probing if needed."""
    global _cached_profile
    if _cached_profile is None or force_refresh:
        _cached_profile = probe_hardware()
        logger.info("Hardware profile detected: %s", _cached_profile.to_dict())
    return _cached_profile