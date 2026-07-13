"""Zaram Voice Runtime foundation (v0.5.1).

A modular voice subsystem that sits independently from the Kernel. The
application depends only on :class:`VoiceManager` / :class:`VoiceRegistry`
and the provider interface — never on a concrete TTS engine.

Later milestones plug in providers (Kokoro, XTTS, cloud, Unreal) and wire
speech requests through the event bus. This milestone delivers the
architecture layer only.
"""

from __future__ import annotations

from .events import ALL_VOICE_EVENTS, create_voice_event
from .exceptions import (
    DuplicateProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    VoiceRuntimeError,
)
from .config import KokoroConfig
from .health import AudioCache
from .providers.kokoro import KokoroProvider, bootstrap_kokoro
from .registry import VoiceRegistry
from .voice_manager import VoiceManager, VoiceRuntime

__all__ = [
    "VoiceManager",
    "VoiceRuntime",
    "VoiceRegistry",
    "KokoroProvider",
    "KokoroConfig",
    "AudioCache",
    "bootstrap_kokoro",
    "VoiceRuntimeError",
    "ProviderNotFoundError",
    "DuplicateProviderError",
    "ProviderUnavailableError",
    "create_voice_event",
    "ALL_VOICE_EVENTS",
]
