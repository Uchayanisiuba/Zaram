"""Voice provider package.

Concrete providers are registered via :class:`~voice.registry.VoiceRegistry`.
Tier 1: Breeze TTS 2 (Cloud Premium)
Tier 2: Chatterbox Turbo (VRAM-Efficient Local GPU)
Tier 3: Qwen3-TTS / VoxCPM2 (CPU Lightweight GGUF)
Tier 4: Kokoro 82M (Universal Fallback)
"""

from __future__ import annotations

from .base import VoiceProvider
from .breeze_tts import BreezeTTSProvider, bootstrap_breeze_tts
from .chatterbox_turbo import ChatterboxTurboProvider, bootstrap_chatterbox_turbo
from .kokoro import KokoroProvider, bootstrap_kokoro
from .qwen3_tts import Qwen3TTSProvider, bootstrap_qwen3_tts

__all__ = [
    "VoiceProvider",
    "KokoroProvider",
    "bootstrap_kokoro",
    "BreezeTTSProvider",
    "bootstrap_breeze_tts",
    "ChatterboxTurboProvider",
    "bootstrap_chatterbox_turbo",
    "Qwen3TTSProvider",
    "bootstrap_qwen3_tts",
]
