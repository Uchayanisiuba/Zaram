"""AI Garage discoverers package (v0.6.0)."""

from __future__ import annotations

from .base import (
    HardwareProfiler,
    ModelProviderAdapter,
    PersonalitySourceAdapter,
    RuntimeSourceAdapter,
    VoiceSourceAdapter,
)
from .hardware import HardwareProfiler as HardwareProfilerImpl
from .ollama import OllamaAdapter
from .openai_compat import LMStudioAdapter, OpenAICompatibleAdapter
from .personalities import PersonalitiesFileAdapter, StaticPersonalitySource
from .runtimes import RegistryRuntimeSource
from .voices import StaticVoiceSource, VoiceRegistryAdapter

__all__ = [
    "ModelProviderAdapter",
    "VoiceSourceAdapter",
    "RuntimeSourceAdapter",
    "PersonalitySourceAdapter",
    "HardwareProfiler",
    "HardwareProfilerImpl",
    "OllamaAdapter",
    "OpenAICompatibleAdapter",
    "LMStudioAdapter",
    "PersonalitiesFileAdapter",
    "StaticPersonalitySource",
    "RegistryRuntimeSource",
    "VoiceRegistryAdapter",
    "StaticVoiceSource",
]
