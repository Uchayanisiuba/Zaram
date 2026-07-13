"""VoiceManager: provider-agnostic orchestration and lifecycle.

Owns the provider registry and the active provider. It routes speech requests
to the selected provider and exposes health/lifecycle. It never imports a
concrete TTS engine, so application code stays decoupled from any provider.

A small :class:`VoiceRuntime` wrapper is provided for bootstrap integration
(async initialize/shutdown + logging) without adding a separate module.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional, Union

from .exceptions import ProviderNotFoundError, ProviderUnavailableError
from .providers.base import VoiceProvider
from .registry import VoiceRegistry

logger = logging.getLogger(__name__)


class VoiceManager:
    def __init__(self, audio_dir: str = "audio_cache", base_url: str = "http://127.0.0.1:8000") -> None:
        self.audio_dir = audio_dir
        self.base_url = base_url
        self.registry = VoiceRegistry()
        self._active: Optional[VoiceProvider] = None
        self._active_name: Optional[str] = None
        self._voice_mapping: Dict[str, str] = {}
        self._lock = threading.RLock()

    # --- provider registration / selection ---
    async def register_provider(
        self, name: str, provider: Union[type[VoiceProvider], VoiceProvider], set_active: bool = True
    ) -> None:
        self.registry.register(name, provider)
        if set_active:
            self._active = self.registry.get_instance(name)
            self._active_name = name
            logger.info("Voice provider '%s' registered and set active", name)

    def get_provider(self, name: Optional[str] = None) -> VoiceProvider:
        """Return the active provider, or a named one. Raises if unavailable."""
        with self._lock:
            if name is not None:
                if not self.registry.is_registered(name):
                    raise ProviderNotFoundError(f"Provider '{name}' is not registered")
                return self.registry.get_instance(name)
            if self._active is None:
                raise ProviderUnavailableError("No active voice provider is configured")
            return self._active

    # --- lifecycle ---
    async def initialize(self) -> None:
        """Initialize the active provider if one is configured.

        Safe to call with no provider registered (foundation milestone does not
        initialize a TTS engine yet).
        """
        with self._lock:
            active = self._active
        if active is not None:
            await active.initialize()
            logger.info("Voice provider '%s' initialized", self._active_name)
        else:
            logger.info("VoiceManager initialized (no TTS provider configured)")

    async def shutdown(self) -> None:
        with self._lock:
            active = self._active
        if active is not None:
            try:
                await active.shutdown()
            except Exception as exc:  # shutdown must never raise
                logger.warning("Error during voice provider shutdown: %s", exc)
            logger.info("Voice provider '%s' shut down", self._active_name)

    # --- voice discovery ---
    async def available_voices(self) -> Dict[str, Any]:
        """Return the active provider's discovered voices (structured metadata)."""
        provider = self.get_provider()
        return await provider.available_voices()

    # --- request routing ---
    async def synthesize(
        self, text: str, *, voice: str = "", provider_name: Optional[str] = None
    ) -> Any:
        """Route a speech request to the selected provider.

        Raises :class:`ProviderUnavailableError` when no provider can serve it.
        """
        provider = self.get_provider(provider_name)
        return await provider.generate_audio(text, voice=voice)

    # --- health ---
    async def health(self) -> Dict[str, Any]:
        providers: Dict[str, Any] = {}
        for name in self.registry.list_providers():
            try:
                providers[name] = await self.registry.get_instance(name).health_check()
            except Exception as exc:  # pragma: no cover - defensive
                providers[name] = {"available": False, "error": str(exc)}
        with self._lock:
            active = self._active_name
        return {
            "runtime_id": "voice",
            "active_provider": active,
            "providers": providers,
            "personalities_mapped": len(self._voice_mapping),
        }

    # --- future: personality voice selection (config-driven hook) ---
    def set_voice_mapping(self, mapping: Dict[str, str]) -> None:
        with self._lock:
            self._voice_mapping = dict(mapping)

    def resolve_voice(self, personality_id: str) -> Optional[str]:
        """Return the configured voice id for a personality (future use)."""
        with self._lock:
            return self._voice_mapping.get(personality_id)


class VoiceRuntime:
    """Bootstrap-friendly wrapper around :class:`VoiceManager`.

    Provides the async lifecycle used by the application startup without
    coupling the runtime to the Kernel registry.
    """

    def __init__(
        self,
        audio_dir: str = "audio_cache",
        base_url: str = "http://127.0.0.1:8000",
        *,
        auto_register_kokoro: bool = False,
        kokoro_config: Any = None,
    ) -> None:
        self.manager = VoiceManager(audio_dir, base_url)
        self.auto_register_kokoro = auto_register_kokoro
        self.kokoro_config = kokoro_config

    async def initialize(self) -> None:
        logger.info("✓ Voice Runtime initialized")
        if self.auto_register_kokoro:
            try:
                from voice.providers.kokoro import bootstrap_kokoro

                await bootstrap_kokoro(self.manager, self.kokoro_config)
            except Exception as exc:  # registration must never break chat
                logger.error(
                    "Kokoro provider registration failed (chat remains operational): %s",
                    exc,
                )
        else:
            await self.manager.initialize()

    async def shutdown(self) -> None:
        await self.manager.shutdown()
        logger.info("Voice Runtime stopped")
