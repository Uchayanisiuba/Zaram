"""VoiceManager: provider-agnostic orchestration and lifecycle.

Owns the provider registry and the active provider. It routes speech requests
to the selected provider and exposes health/lifecycle. It never imports a
concrete TTS engine, so application code stays decoupled from any provider.

A small :class:`VoiceRuntime` wrapper is provided for bootstrap integration
(async initialize/shutdown + logging) without adding a separate module.

4-Tier Voice Pipeline:
- Tier 1: Breeze TTS 2 (Cloud Premium)
- Tier 2: Chatterbox Turbo (VRAM-Efficient Local GPU)
- Tier 3: Qwen3-TTS / VoxCPM2 (CPU Lightweight)
- Tier 4: Kokoro 82M (Universal Fallback)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional, Union

from .cleanup import CleanupReport, cleanup_unused_voices
from .exceptions import ProviderNotFoundError, ProviderUnavailableError
from .providers.base import VoiceProvider
from .registry import VoiceRegistry
from .tier_router import VoiceTier, get_fallback_tier, get_tier_config, list_tier_status, select_tier, TierSelectionResult

logger = logging.getLogger(__name__)


@dataclass
class AutoTierConfig:
    """Configuration for automatic tier selection."""
    enabled: bool = True
    prefer_local: bool = True
    force_tier: Optional[VoiceTier] = None
    fallback_on_oom: bool = True


class VoiceManager:
    def __init__(
        self,
        audio_dir: str = "audio_cache",
        base_url: str = "http://127.0.0.1:8420",
        auto_tier_config: Optional[AutoTierConfig] = None,
    ) -> None:
        self.audio_dir = audio_dir
        self.base_url = base_url
        self.registry = VoiceRegistry()
        self._active: Optional[VoiceProvider] = None
        self._active_name: Optional[str] = None
        self._active_tier: Optional[VoiceTier] = None
        self._voice_mapping: Dict[str, str] = {}
        self._lock = threading.RLock()
        self.auto_tier_config = auto_tier_config or AutoTierConfig()

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

    def get_active_tier(self) -> Optional[VoiceTier]:
        """Return the currently active tier."""
        with self._lock:
            return self._active_tier

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

    # --- 4-Tier Pipeline: Auto tier selection ---
    async def auto_select_tier(self, force_refresh: bool = False) -> TierSelectionResult:
        """
        Automatically select the optimal TTS tier based on hardware profile.

        Registers and initializes the selected provider, shutting down the previous one.
        """
        if not self.auto_tier_config.enabled:
            return TierSelectionResult(
                selected_tier=VoiceTier.TIER_4_KOKORO,
                selected_config=[],
                reason="auto tier selection disabled",
            )

        result = select_tier(
            force_tier=self.auto_tier_config.force_tier,
            prefer_local=self.auto_tier_config.prefer_local,
        )

        logger.info(
            "Auto-selected tier: %s (reason: %s)",
            result.selected_tier.name,
            result.reason,
        )

        await self._switch_to_tier(result.selected_tier, result.selected_config.provider_name)
        return result

    async def _switch_to_tier(self, tier: VoiceTier, provider_name: str) -> None:
        """Switch active provider to the specified tier."""
        with self._lock:
            old_active = self._active
            old_name = self._active_name

        if old_active is not None:
            try:
                await old_active.shutdown()
                logger.info("Shut down previous provider '%s'", old_name)
            except Exception as exc:
                logger.warning("Error shutting down previous provider: %s", exc)

        # Register and initialize new provider
        if self.registry.is_registered(provider_name):
            new_provider = self.registry.get_instance(provider_name)
        else:
            # Provider not registered yet - need to bootstrap it
            new_provider = await self._bootstrap_provider(tier)
            self.registry.register(provider_name, new_provider)

        new_provider = self.registry.get_instance(provider_name)
        await new_provider.initialize()

        with self._lock:
            self._active = new_provider
            self._active_name = provider_name
            self._active_tier = tier

        logger.info("Switched to tier %s (provider: %s)", tier.name, provider_name)

    async def _bootstrap_provider(self, tier: VoiceTier) -> VoiceProvider:
        """Bootstrap a provider for the given tier."""
        if tier == VoiceTier.TIER_1_BREEZE:
            from voice.providers.breeze_tts import BreezeTTSProvider, bootstrap_breeze_tts
            from voice.config import BreezeTTSConfig
            config = BreezeTTSConfig.load()
            return BreezeTTSProvider(config=config)
        elif tier == VoiceTier.TIER_2_CHATTERBOX:
            from voice.providers.chatterbox_turbo import ChatterboxTurboProvider, bootstrap_chatterbox_turbo
            from voice.config import ChatterboxTurboConfig
            config = ChatterboxTurboConfig.load()
            return ChatterboxTurboProvider(config=config)
        elif tier == VoiceTier.TIER_3_QWEN3:
            from voice.providers.qwen3_tts import Qwen3TTSProvider, bootstrap_qwen3_tts
            from voice.config import Qwen3TTSConfig
            config = Qwen3TTSConfig.load()
            return Qwen3TTSProvider(config=config)
        elif tier == VoiceTier.TIER_4_KOKORO:
            from voice.providers.kokoro import KokoroProvider
            from voice.config import KokoroConfig
            config = KokoroConfig.load()
            return KokoroProvider(config=config)
        else:
            raise ValueError(f"Unknown tier: {tier}")

    async def set_tier_manually(self, tier: VoiceTier) -> TierSelectionResult:
        # Refused before anything is changed: a failed press must not leave the
        # manager forced onto a tier that cannot speak.
        if not get_tier_config(tier).implemented:
            raise ValueError(f"{tier.name} is not built yet")
        """Manually set the TTS tier, bypassing auto-selection."""
        self.auto_tier_config.force_tier = tier
        self.auto_tier_config.enabled = False
        return await self.auto_select_tier()

    async def re_enable_auto_tier(self) -> TierSelectionResult:
        """Re-enable automatic tier selection."""
        self.auto_tier_config.enabled = True
        self.auto_tier_config.force_tier = None
        return await self.auto_select_tier(force_refresh=True)

    # --- OOM Fallback ---
    async def handle_oom_fallback(self) -> Optional[VoiceTier]:
        """Handle OOM by falling back to the next available tier."""
        if not self.auto_tier_config.fallback_on_oom or self._active_tier is None:
            return None

        from .hardware_probe import get_hardware_profile
        profile = get_hardware_profile(force_refresh=True)
        fallback_tier = get_fallback_tier(self._active_tier, profile)

        if fallback_tier is not None:
            logger.warning(
                "OOM detected, falling back from %s to %s",
                self._active_tier.name,
                fallback_tier.name,
            )
            tier_config = list_tier_status(profile)[fallback_tier.name]
            await self._switch_to_tier(fallback_tier, tier_config["provider"])
            return fallback_tier

        logger.error("OOM detected but no fallback tier available")
        return None

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
        try:
            return await provider.generate_audio(text, voice=voice)
        except Exception as exc:
            # Check for OOM-like errors
            if self.auto_tier_config.fallback_on_oom and self._is_oom_error(exc):
                await self.handle_oom_fallback()
                # Retry with new provider
                provider = self.get_provider()
                return await provider.generate_audio(text, voice=voice)
            raise

    def _is_oom_error(self, exc: Exception) -> bool:
        """Check if an exception indicates OOM."""
        error_str = str(exc).lower()
        oom_indicators = [
            "out of memory",
            "oom",
            "cuda out of memory",
            "not enough memory",
            "allocation failed",
            "insufficient memory",
        ]
        return any(indicator in error_str for indicator in oom_indicators)

    # --- streaming routing ---
    async def stream_synthesis(
        self, text: str, *, voice: str = "", provider_name: Optional[str] = None
    ) -> AsyncIterator[Any]:
        """Stream a synthesized utterance as an ordered sequence of chunks.

        Provider-agnostic, async, non-blocking, failure-safe and cancellation-safe.
        On an unavailable provider or any synthesis error the generator simply
        closes cleanly (yields nothing) so callers never have to handle exceptions.
        Cancellation (``GeneratorExit`` / ``asyncio.CancelledError``) propagates
        out so the underlying synthesis can be aborted without hanging.
        """
        try:
            provider = self.get_provider(provider_name)
        except ProviderUnavailableError as exc:
            logger.warning("Streaming unavailable (no active provider): %s", exc)
            return

        try:
            async for chunk in provider.stream_audio(text, voice=voice):
                yield chunk
        except ProviderUnavailableError as exc:
            logger.warning("Streaming stopped (provider unavailable): %s", exc)
        except Exception as exc:
            if self.auto_tier_config.fallback_on_oom and self._is_oom_error(exc):
                await self.handle_oom_fallback()
            logger.error(
                "Streaming failed: %s",
                exc,
                extra={"voice": voice, "failure": type(exc).__name__},
            )

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
            active_tier = self._active_tier

        # Add tier status
        from .hardware_probe import get_hardware_profile
        profile = get_hardware_profile()
        tier_status = list_tier_status(profile)

        return {
            "runtime_id": "voice",
            "active_provider": active,
            "active_tier": active_tier.name if active_tier else None,
            "auto_tier_enabled": self.auto_tier_config.enabled,
            "prefer_local": self.auto_tier_config.prefer_local,
            "providers": providers,
            "tier_status": tier_status,
            "personalities_mapped": len(self._voice_mapping),
        }

    # --- cleanup ---
    async def cleanup_unused_voices(self, keep_voice: str = "am_michael") -> CleanupReport:
        """Purge all downloaded Kokoro voices except the active one."""
        return await cleanup_unused_voices(keep_voice=keep_voice)

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
        base_url: str = "http://127.0.0.1:8420",
        *,
        auto_register_kokoro: bool = False,
        kokoro_config: Any = None,
        auto_tier_config: Optional[AutoTierConfig] = None,
    ) -> None:
        self.manager = VoiceManager(audio_dir, base_url, auto_tier_config=auto_tier_config)
        self.auto_register_kokoro = auto_register_kokoro
        self.kokoro_config = kokoro_config

    async def initialize(self) -> None:
        logger.info("✓ Voice Runtime ready")
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
            # Auto-select tier if no provider registered
            if not self.manager.registry.list_providers():
                await self.manager.auto_select_tier()
            else:
                await self.manager.initialize()

    async def shutdown(self) -> None:
        await self.manager.shutdown()
        logger.info("Voice Runtime stopped")