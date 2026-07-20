"""Shared contracts for the Zaram AI Garage (v0.6.0).

The AI Garage is Zaram's control center for AI resources. It discovers and
tracks *every* AI capability available to the system — local LLMs, local AI
servers, installed voices, installed personalities, active runtimes, and
(future) skills and plugins.

This module defines only the generic, provider-independent data shapes. No
concrete engine (Ollama, LM Studio, Kokoro, ...) is referenced here; those
live exclusively inside their own discoverers. The Garage never hardcodes a
model name — every field is learned at discovery time.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from core.contracts import CapabilityLocality


class ModelCategory(Enum):
    """What kind of intelligence a model provides."""

    LLM = "llm"
    EMBEDDING = "embedding"
    VISION = "vision"
    TTS = "tts"
    STT = "stt"
    IMAGE = "image"
    VIDEO = "video"
    OTHER = "other"

    @classmethod
    def from_value(cls, value: Optional[str]) -> "ModelCategory":
        if not value:
            return cls.OTHER
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.OTHER


class ProviderKind(Enum):
    """Where a model *source* actually lives."""

    LOCAL_LLM = "local_llm"
    LOCAL_AI_SERVER = "local_ai_server"
    CLOUD_API = "cloud_api"
    EMBEDDED = "embedded"

    @classmethod
    def from_value(cls, value: Optional[str]) -> "ProviderKind":
        if not value:
            return cls.LOCAL_LLM
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.LOCAL_LLM


class HealthStatus(Enum):
    """Aggregated health of a Garage component."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

    @classmethod
    def from_value(cls, value: Optional[str]) -> "HealthStatus":
        if not value:
            return cls.UNKNOWN
        try:
            return cls(str(value).lower())
        except ValueError:
            return cls.UNKNOWN


@dataclass
class ModelInfo:
    """The generic internal representation of one discovered model.

    Every field is optional or inferred. No model name is hardcoded anywhere
    in the Garage — adapters populate these from provider responses.
    """

    id: str
    display_name: str
    provider: str
    provider_kind: ProviderKind = ProviderKind.LOCAL_LLM
    category: ModelCategory = ModelCategory.LLM
    version: str = ""
    size_bytes: Optional[int] = None
    context_length: Optional[int] = None
    quantization: Optional[str] = None
    capabilities: set[str] = field(default_factory=set)
    supports_vision: bool = False
    supports_embedding: bool = False
    supports_tools: bool = False
    recommended_use: str = ""
    memory_requirement_bytes: Optional[int] = None
    locality: CapabilityLocality = CapabilityLocality.LOCAL
    available: bool = False
    health_status: HealthStatus = HealthStatus.UNKNOWN
    endpoint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "provider": self.provider,
            "provider_kind": self.provider_kind.value,
            "category": self.category.value,
            "version": self.version,
            "size_bytes": self.size_bytes,
            "context_length": self.context_length,
            "quantization": self.quantization,
            "capabilities": sorted(self.capabilities),
            "supports_vision": self.supports_vision,
            "supports_embedding": self.supports_embedding,
            "supports_tools": self.supports_tools,
            "recommended_use": self.recommended_use,
            "memory_requirement_bytes": self.memory_requirement_bytes,
            "locality": self.locality.value,
            "available": self.available,
            "health_status": self.health_status.value,
            "endpoint": self.endpoint,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        return cls(
            id=data.get("id", new_id("model")),
            display_name=data.get("display_name", data.get("id", "unknown")),
            provider=data.get("provider", "unknown"),
            provider_kind=ProviderKind.from_value(data.get("provider_kind")),
            category=ModelCategory.from_value(data.get("category", "llm")),
            version=data.get("version", ""),
            size_bytes=data.get("size_bytes"),
            context_length=data.get("context_length"),
            quantization=data.get("quantization"),
            capabilities=set(data.get("capabilities", [])),
            supports_vision=bool(data.get("supports_vision", False)),
            supports_embedding=bool(data.get("supports_embedding", False)),
            supports_tools=bool(data.get("supports_tools", False)),
            recommended_use=data.get("recommended_use", ""),
            memory_requirement_bytes=data.get("memory_requirement_bytes"),
            locality=locality_from_value(data.get("locality", "local")),
            available=bool(data.get("available", False)),
            health_status=HealthStatus.from_value(data.get("health_status")),
            endpoint=data.get("endpoint"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class VoiceInfo:
    """A discovered voice identity (provider-agnostic)."""

    id: str
    display_name: str
    provider: str
    language: str = "unknown"
    gender: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "provider": self.provider,
            "language": self.language,
            "gender": self.gender,
            "metadata": dict(self.metadata),
        }


@dataclass
class RuntimeInfo:
    """A discovered Zaram runtime (read from the Kernel registry)."""

    runtime_id: str
    version: str = ""
    state: str = "unknown"
    healthy: bool = False
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "version": self.version,
            "state": self.state,
            "healthy": self.healthy,
            "capabilities": list(self.capabilities),
            "metadata": dict(self.metadata),
        }


@dataclass
class HardwareProfile:
    """A point-in-time snapshot of the host machine's AI-relevant hardware."""

    cpu_model: str = "unknown"
    cpu_count: int = 0
    total_ram_bytes: int = 0
    gpu_available: bool = False
    gpu_name: str = "unknown"
    vram_bytes: int = 0
    os_name: str = "unknown"
    os_version: str = "unknown"
    storage_total_bytes: int = 0
    storage_free_bytes: int = 0
    cuda_available: bool = False
    metal_available: bool = False
    directml_available: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_model": self.cpu_model,
            "cpu_count": self.cpu_count,
            "total_ram_bytes": self.total_ram_bytes,
            "gpu_available": self.gpu_available,
            "gpu_name": self.gpu_name,
            "vram_bytes": self.vram_bytes,
            "os_name": self.os_name,
            "os_version": self.os_version,
            "storage_total_bytes": self.storage_total_bytes,
            "storage_free_bytes": self.storage_free_bytes,
            "cuda_available": self.cuda_available,
            "metal_available": self.metal_available,
            "directml_available": self.directml_available,
            "timestamp": self.timestamp,
        }


@dataclass
class ProviderSummary:
    """A serializable description of a registered model provider."""

    id: str
    kind: ProviderKind
    endpoint: Optional[str] = None
    available: bool = False
    model_count: int = 0
    health_status: HealthStatus = HealthStatus.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "endpoint": self.endpoint,
            "available": self.available,
            "model_count": self.model_count,
            "health_status": self.health_status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProviderSummary":
        return cls(
            id=data.get("id", ""),
            kind=ProviderKind.from_value(data.get("kind")),
            endpoint=data.get("endpoint"),
            health_status=HealthStatus.from_value(data.get("health_status")),
        )


def locality_from_value(value: Optional[str]) -> CapabilityLocality:
    """Coerce a string to :class:`CapabilityLocality` (falls back to LOCAL).

    The core enum intentionally exposes no ``from_value`` helper, so the
    Garage provides its own conversion here.
    """
    if not value:
        return CapabilityLocality.LOCAL
    try:
        return CapabilityLocality(str(value).lower())
    except ValueError:
        return CapabilityLocality.LOCAL


def new_id(prefix: str = "garage") -> str:
    """Generate a prefixed unique identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> float:
    """Current epoch timestamp (single source of truth for 'created_at')."""
    return time.time()
