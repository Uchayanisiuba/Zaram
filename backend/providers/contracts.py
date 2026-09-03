"""Shared contracts for the Zaram provider layer (v0.6.0).

The provider layer is Zaram's control center for AI resources. It discovers and
tracks *every* AI capability available to the system — local LLMs, local AI
servers, installed voices, installed personalities, active runtimes, and
(future) skills and plugins.

This module defines only the generic, provider-independent data shapes. No
concrete engine (Ollama, LM Studio, Kokoro, ...) is referenced here; those
live exclusively inside their own discoverers. The provider layer never hardcodes a
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


class DataPolicy(Enum):
    """What happens to a prompt sent to this model.

    Three values, and no fourth — see CLAUDE.md. This is the one fact a user
    must see *before* choosing a model rather than after: size and speed are
    recoverable mistakes, sending a confidential document to a provider that
    trains on it is not.

    Unknown is deliberately *not* a member here. A model whose policy nobody
    established is represented by ``ModelInfo.data_policy is None``, which is
    the absence of an answer rather than a fourth kind of answer. The
    distinction matters: an enum member would eventually get a label in a
    picker and start looking like a choice.
    """

    #: Local inference. Nothing is sent.
    NEVER_LEAVES_DEVICE = "never_leaves_device"
    #: The provider logs prompts and may train on them. Every free tier is this.
    LOGGED_AND_TRAINED_ON = "logged_and_trained_on"
    #: The user's own key, and the provider's terms exclude training on API data.
    YOUR_KEY_NO_TRAINING = "your_key_no_training"

    @classmethod
    def from_value(cls, value: Optional[str]) -> Optional["DataPolicy"]:
        """Coerce a string, or ``None`` when there is nothing to coerce.

        Note what this deliberately does *not* do: fall back to a member. Every
        other ``from_value`` in this module picks a safe-looking default, which
        is right for a category or a health status and wrong here — an
        unparseable policy string is an unanswered question, and answering it
        with ``NEVER_LEAVES_DEVICE`` would state a guarantee no one verified.
        """
        if not value:
            return None
        try:
            return cls(str(value).lower())
        except ValueError:
            return None


#: Name fragments that mark a model as tuned for one job rather than for talking.
#:
#: Matched against the model's name, which is the only signal any provider
#: exposes for this — Ollama's ``/api/show`` reports capabilities and families,
#: neither of which distinguishes a coding fine-tune from its base model.
#:
#: These are task markers, not model identities. The provider layer still never
#: hardcodes a model name: "coder" matches qwen2.5-coder, deepseek-coder and
#: whatever ships next year without any of them being listed. Add markers here,
#: never model names.
TASK_MARKERS: Dict[str, tuple[str, ...]] = {
    "code": ("coder", "code"),
    "math": ("math",),
    "moderation": ("guard", "shield", "moderation"),
}


def specialisation_from_name(name: str) -> Optional[str]:
    """The task a model is tuned for, or ``None`` when it is general-purpose.

    Deliberately conservative: an unrecognised name is general, because the
    cost of the two mistakes is asymmetric. Calling a general model specialised
    removes a good default for no reason; calling a specialised model general
    is how a coding fine-tune ends up answering everything.
    """
    lowered = name.lower()
    for task, markers in TASK_MARKERS.items():
        if any(marker in lowered for marker in markers):
            return task
    return None


class HealthStatus(Enum):
    """Aggregated health of a provider layer component."""

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
    in the provider layer — adapters populate these from provider responses.
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
    #: What the provider does with prompts, or ``None`` when unestablished.
    #:
    #: There is no default policy on purpose. ``NEVER_LEAVES_DEVICE`` would be
    #: the comfortable choice and it is the dangerous one: every adapter that
    #: forgot to set the field would ship a privacy guarantee nobody checked,
    #: which is the same failure as ``vram_bytes`` defaulting to 0 — a value
    #: standing in for the absence of one, except the damage here is a leaked
    #: document rather than a bad recommendation. Defaulting the other way
    #: (``LOGGED_AND_TRAINED_ON``) is safe but false for local models, and
    #: would make Ollama unselectable by the rule below.
    #:
    #: So: unknown, until an adapter says otherwise, and unknown is not
    #: offered by default.
    data_policy: Optional["DataPolicy"] = None
    #: The task this model is tuned for ("code", "math", ...), or ``None`` for a
    #: general-purpose model. Set by the adapter at discovery time.
    specialisation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_general_purpose(self) -> bool:
        """Whether this model is a reasonable answer to an arbitrary question.

        A coding fine-tune is not a worse model than its base — it is a
        different one, and picking it for general chat is a category error that
        shows up as oddly-shaped answers rather than as an obvious failure.
        """
        return self.specialisation is None

    @property
    def emits_image(self) -> bool:
        """Whether this model can **draw** a picture, as opposed to read one.

        A property rather than a stored field, deliberately, and derived from
        what discovery already recorded rather than from a new flag nothing
        sets — a field that every adapter has to remember is a field most of
        them forget, which is precisely how ``supports_vision`` came to be read
        by a gate while nothing populated it.

        Two sources, and both are already written by the OpenRouter
        discoverer: ``output_modalities`` in metadata, which is the direct
        statement, and ``ModelCategory.IMAGE``, which that discoverer sets for
        a model that emits images and no text.

        **This is a precondition, never a score.** "Can this model draw"
        answers yes or no; it does not answer "how well". `CLAUDE.md` names
        merging the two as this codebase's most expensive recurring error, and
        its modality form is the worst of them: a text model asked to draw
        answers with confident prose about a picture it never made, which is
        rule 9's failure wearing a new medium.

        A local Ollama chat model returns False, and that is the correct
        answer. Nothing served through Ollama emits images, so a machine with
        only local models must be told images cannot be drawn by a *model* —
        which is not the same as saying they cannot be drawn, because the
        local SDXL pipeline is not a model in this registry at all.
        """
        emits = self.metadata.get("output_modalities")
        if isinstance(emits, (list, tuple, set)) and "image" in emits:
            return True
        return self.category is ModelCategory.IMAGE

    @property
    def data_policy_known(self) -> bool:
        """Whether anyone has established what this provider does with prompts."""
        return self.data_policy is not None

    @property
    def selectable_by_default(self) -> bool:
        """Whether Zaram may route to this model without the user choosing it.

        Two ways to fail. ``LOGGED_AND_TRAINED_ON`` may only ever be picked
        deliberately by someone who has seen the label — free is not a good
        enough reason to make that choice on a user's behalf. And an
        unestablished policy is not a quiet yes: if we cannot say what happens
        to the prompt, we do not send it anywhere on our own initiative.
        """
        return self.data_policy in (
            DataPolicy.NEVER_LEAVES_DEVICE,
            DataPolicy.YOUR_KEY_NO_TRAINING,
        )

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
            # Reading and drawing, side by side and never one number. The
            # picker shows them as two separate things for the same reason the
            # gate treats them as two separate questions.
            "emits_image": self.emits_image,
            "supports_embedding": self.supports_embedding,
            "supports_tools": self.supports_tools,
            "recommended_use": self.recommended_use,
            "memory_requirement_bytes": self.memory_requirement_bytes,
            "locality": self.locality.value,
            "available": self.available,
            "health_status": self.health_status.value,
            "endpoint": self.endpoint,
            # Serialises as null, never as a policy. The UI must render this as
            # "unknown" and must not offer the model as a default.
            "data_policy": self.data_policy.value if self.data_policy else None,
            "data_policy_known": self.data_policy_known,
            "selectable_by_default": self.selectable_by_default,
            "specialisation": self.specialisation,
            "is_general_purpose": self.is_general_purpose,
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
            data_policy=DataPolicy.from_value(data.get("data_policy")),
            specialisation=data.get("specialisation"),
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
    """A point-in-time snapshot of the host machine's AI-relevant hardware.

    Unknown is a value here, not a zero. ``vram_bytes`` was an ``int`` defaulting
    to ``0``, and the only implementation that could fill it read
    ``torch.cuda.get_device_properties`` — so every Mac and every AMD card
    reported "GPU available, 0 bytes of VRAM". A recommendation built on that
    false zero is worse than no recommendation: it tells the user a model will
    not fit when it would, and makes the product look weak on exactly the
    hardware that runs it best.
    """

    cpu_model: str = "unknown"
    cpu_count: int = 0
    total_ram_bytes: int = 0
    #: True only when an accelerator is present *and* its capacity is known, so
    #: that residency can actually be planned against it. An accelerator we
    #: cannot measure is reported through ``metal_available`` /
    #: ``directml_available`` below rather than as a capacity we do not have.
    gpu_available: bool = False
    gpu_name: str = "unknown"
    #: Bytes of VRAM, or ``None`` when it cannot be determined. Never 0 as a
    #: stand-in for unknown — 0 is a measurement, and this is the absence of one.
    vram_bytes: Optional[int] = None
    os_name: str = "unknown"
    os_version: str = "unknown"
    storage_total_bytes: int = 0
    storage_free_bytes: int = 0
    cuda_available: bool = False
    metal_available: bool = False
    directml_available: bool = False
    timestamp: float = field(default_factory=time.time)

    @property
    def vram_known(self) -> bool:
        """Whether residency can be planned at all.

        Anything sizing a model against this machine must check here first. A
        caller that treats ``vram_bytes or 0`` as a number has reintroduced the
        bug this field exists to prevent.
        """
        return self.vram_bytes is not None

    @property
    def accelerator_present(self) -> bool:
        """An accelerator exists, whether or not we can measure it.

        Distinct from ``gpu_available``: a Mac has a real GPU that Zaram cannot
        size. Saying "no GPU" there would be its own false statement, so the two
        questions are kept separate — is there one, and can we plan against it.
        """
        return self.cuda_available or self.metal_available or self.directml_available

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cpu_model": self.cpu_model,
            "cpu_count": self.cpu_count,
            "total_ram_bytes": self.total_ram_bytes,
            "gpu_available": self.gpu_available,
            "accelerator_present": self.accelerator_present,
            "gpu_name": self.gpu_name,
            # Serialises as null, never 0. The UI must render this as "unknown".
            "vram_bytes": self.vram_bytes,
            "vram_known": self.vram_known,
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
    The provider layer provides its own conversion here.
    """
    if not value:
        return CapabilityLocality.LOCAL
    try:
        return CapabilityLocality(str(value).lower())
    except ValueError:
        return CapabilityLocality.LOCAL


def new_id(prefix: str = "provider") -> str:
    """Generate a prefixed unique identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now() -> float:
    """Current epoch timestamp (single source of truth for 'created_at')."""
    return time.time()
