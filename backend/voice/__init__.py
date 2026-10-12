"""Zaram Voice Runtime — 4-Tier Voice Pipeline (v0.6.0).

A modular voice subsystem that sits independently from the Kernel. The
application depends only on :class:`VoiceManager` / :class:`VoiceRegistry`
and the provider interface — never on a concrete TTS engine.

Tiers:
- Tier 1: Breeze TTS 2 (Cloud Premium)
- Tier 2: Chatterbox Turbo (VRAM-Efficient Local GPU)
- Tier 3: Qwen3-TTS / VoxCPM2 (CPU Lightweight GGUF)
- Tier 4: Kokoro 82M (Universal Fallback)
"""

from __future__ import annotations

from .cleanup import CleanupReport, cleanup_unused_voices, cleanup_unused_voices_async, get_cache_status
from .config import (
    KokoroConfig,
    BreezeTTSConfig,
    ChatterboxTurboConfig,
    Qwen3TTSConfig,
)
from .events import ALL_VOICE_EVENTS, create_voice_event
from .exceptions import (
    DuplicateProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    VoiceRuntimeError,
)
from .audio_events import (
    audio_event_from_chunk,
    audio_event_from_result,
    to_audio_event,
)
from .hardware_probe import HardwareProfile, get_hardware_profile, probe_hardware
from .health import AudioCache
from .providers.kokoro import AudioChunk, AudioResult, KokoroProvider, bootstrap_kokoro
from .providers.breeze_tts import BreezeTTSProvider, bootstrap_breeze_tts
from .providers.chatterbox_turbo import ChatterboxTurboProvider, bootstrap_chatterbox_turbo
from .providers.qwen3_tts import Qwen3TTSProvider, bootstrap_qwen3_tts
from .registry import VoiceRegistry
from .tier_router import VoiceTier, TierSelectionResult, select_tier, list_tier_status, get_fallback_tier
from .voice_manager import VoiceManager, VoiceRuntime, AutoTierConfig

__all__ = [
    # Core
    "VoiceManager",
    "VoiceRuntime",
    "VoiceRegistry",
    "AutoTierConfig",
    # Configs
    "KokoroConfig",
    "BreezeTTSConfig",
    "ChatterboxTurboConfig",
    "Qwen3TTSConfig",
    # Providers
    "KokoroProvider",
    "BreezeTTSProvider",
    "ChatterboxTurboProvider",
    "Qwen3TTSProvider",
    "bootstrap_kokoro",
    "bootstrap_breeze_tts",
    "bootstrap_chatterbox_turbo",
    "bootstrap_qwen3_tts",
    # Audio
    "AudioCache",
    "AudioResult",
    "AudioChunk",
    "to_audio_event",
    "audio_event_from_result",
    "audio_event_from_chunk",
    # Tier routing
    "VoiceTier",
    "TierSelectionResult",
    "select_tier",
    "list_tier_status",
    "get_fallback_tier",
    # Hardware detection
    "HardwareProfile",
    "get_hardware_profile",
    "probe_hardware",
    # Cleanup
    "CleanupReport",
    "cleanup_unused_voices",
    "cleanup_unused_voices_async",
    "get_cache_status",
    # Exceptions
    "VoiceRuntimeError",
    "ProviderNotFoundError",
    "DuplicateProviderError",
    "ProviderUnavailableError",
    # Events
    "create_voice_event",
    "ALL_VOICE_EVENTS",
]
