"""Tier selection logic for 4-Tier Voice Pipeline.

Routes TTS workload to optimal tier based on hardware profile and runtime state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from .hardware_probe import HardwareProfile, get_hardware_profile

logger = logging.getLogger(__name__)


class VoiceTier(Enum):
    """TTS engine tiers in priority order (1 = highest)."""
    TIER_1_BREEZE = 1       # Breeze TTS 2 - Cloud, premium
    TIER_2_CHATTERBOX = 2   # Chatterbox Turbo - Local GPU, VRAM-efficient
    TIER_3_QWEN3 = 3        # Qwen3-TTS / VoxCPM2 - CPU-only, lightweight
    TIER_4_KOKORO = 4       # Kokoro 82M - Universal fallback


@dataclass(frozen=True)
class TierConfig:
    """Configuration for a specific tier."""
    tier: VoiceTier
    provider_name: str
    provider_class: str  # Fully qualified class name for dynamic import
    config_class: str    # Fully qualified config class name
    requires_cloud: bool = False
    requires_gpu: bool = False
    min_free_vram_gb: float = 0.0
    min_system_ram_gb: float = 0.0
    max_local_llm_vram_gb: float = float('inf')
    description: str = ""
    #: False while the provider behind the tier is a stub that answers "not yet
    #: implemented". A tier nobody can speak through must never be the one
    #: chosen -- automatically or by a press -- so the router refuses it and the
    #: status says why. Flip it when the provider really synthesises.
    implemented: bool = True


# Tier configurations in priority order
TIER_CONFIGS = [
    TierConfig(
        tier=VoiceTier.TIER_1_BREEZE,
        provider_name="breeze_tts",
        provider_class="voice.providers.breeze_tts.BreezeTTSProvider",
        config_class="voice.config.BreezeTTSConfig",
        requires_cloud=True,
        requires_gpu=False,  # Cloud API - no local GPU needed
        min_free_vram_gb=4.0,  # For local fallback consideration
        description="Breeze TTS 2 - Cloud premium, full GPU acceleration, max expressive prosody",
        implemented=False,  # stub provider
    ),
    TierConfig(
        tier=VoiceTier.TIER_2_CHATTERBOX,
        provider_name="chatterbox_turbo",
        provider_class="voice.providers.chatterbox_turbo.ChatterboxTurboProvider",
        config_class="voice.config.ChatterboxTurboConfig",
        requires_cloud=False,
        requires_gpu=True,
        min_free_vram_gb=1.5,
        min_system_ram_gb=32.0,
        max_local_llm_vram_gb=10.5,  # Leaves ~1.5GB for Chatterbox on 12GB card
        description="Chatterbox Turbo - VRAM-efficient, zero-shot cloning, 1.5-2GB footprint",
        implemented=False,  # stub provider
    ),
    TierConfig(
        tier=VoiceTier.TIER_3_QWEN3,
        provider_name="qwen3_tts",
        provider_class="voice.providers.qwen3_tts.Qwen3TTSProvider",
        config_class="voice.config.Qwen3TTSConfig",
        requires_cloud=False,
        requires_gpu=False,
        min_system_ram_gb=16.0,
        description="Qwen3-TTS / VoxCPM2 - CPU-only, multi-threaded, high-quality localized",
        implemented=False,  # stub provider
    ),
    TierConfig(
        tier=VoiceTier.TIER_4_KOKORO,
        provider_name="kokoro",
        provider_class="voice.providers.kokoro.KokoroProvider",
        config_class="voice.config.KokoroConfig",
        requires_cloud=False,
        requires_gpu=False,
        description="Kokoro 82M - Universal fallback, 340MB, instant on low-spec",
    ),
]


@dataclass
class TierSelectionResult:
    """Result of tier selection."""
    selected_tier: VoiceTier
    selected_config: TierConfig
    reason: str
    fallback_tier: Optional[VoiceTier] = None
    fallback_reason: Optional[str] = None


def _check_tier_conditions(config: TierConfig, profile: HardwareProfile) -> tuple[bool, str]:
    """Check if hardware profile meets tier requirements. Returns (eligible, reason)."""
    if not config.implemented:
        return False, "not built yet: this tier's provider is a stub"

    # Cloud requirement
    if config.requires_cloud and not profile.cloud_llm_active:
        return False, f"requires cloud LLM (active: {profile.cloud_llm_active})"

    # GPU requirement
    if config.requires_gpu:
        if profile.gpu_vendor == "unknown" or profile.total_vram_gb is None:
            return False, "requires GPU but none detected"
        if profile.free_vram_gb is not None and profile.free_vram_gb < config.min_free_vram_gb:
            return False, f"free VRAM {profile.free_vram_gb:.1f}GB < required {config.min_free_vram_gb:.1f}GB"

    # System RAM requirement
    if config.min_system_ram_gb > 0:
        if profile.total_system_ram_gb is None or profile.total_system_ram_gb < config.min_system_ram_gb:
            return False, f"system RAM {profile.total_system_ram_gb}GB < required {config.min_system_ram_gb}GB"

    # Local LLM VRAM footprint check (for Tier 2)
    if config.max_local_llm_vram_gb < float('inf'):
        if profile.local_llm_active and profile.local_llm_vram_footprint_gb is not None:
            if profile.local_llm_vram_footprint_gb > config.max_local_llm_vram_gb:
                return False, f"local LLM VRAM {profile.local_llm_vram_footprint_gb:.1f}GB > max {config.max_local_llm_vram_gb:.1f}GB"

    # VRAM check for non-GPU tiers (e.g., Tier 1 cloud fallback consideration)
    # Only applies if cloud is not active and we're evaluating local capability
    if config.min_free_vram_gb > 0 and not config.requires_gpu:
        # This is a cloud provider being evaluated for local fallback
        # It's eligible for cloud use regardless of VRAM
        # But if we're checking local fallback, require VRAM
        pass  # Cloud providers don't need local VRAM for their primary operation

    return True, "all conditions met"


def select_tier(
    profile: Optional[HardwareProfile] = None,
    force_tier: Optional[VoiceTier] = None,
    prefer_local: bool = True,
) -> TierSelectionResult:
    """
    Select the optimal TTS tier based on hardware profile.

    Args:
        profile: Hardware profile (auto-detected if None)
        force_tier: Override automatic selection
        prefer_local: If True, prefer local tiers over cloud when both eligible

    Returns:
        TierSelectionResult with selected tier and reasoning
    """
    if profile is None:
        profile = get_hardware_profile()

    if force_tier:
        for cfg in TIER_CONFIGS:
            if cfg.tier == force_tier:
                if not cfg.implemented:
                    raise ValueError(f"{force_tier.name} is not built yet")
                return TierSelectionResult(
                    selected_tier=force_tier,
                    selected_config=cfg,
                    reason=f"manually forced to {force_tier.name}",
                )
        raise ValueError(f"Unknown tier: {force_tier}")

    # Check tiers in priority order
    for i, config in enumerate(TIER_CONFIGS):
        eligible, reason = _check_tier_conditions(config, profile)
        if eligible:
            # For Tier 1 (cloud), check prefer_local
            if config.tier == VoiceTier.TIER_1_BREEZE and prefer_local:
                # Check if a local tier would also work
                for local_config in TIER_CONFIGS[i+1:]:
                    local_eligible, _ = _check_tier_conditions(local_config, profile)
                    if local_eligible and not local_config.requires_cloud:
                        return TierSelectionResult(
                            selected_tier=local_config.tier,
                            selected_config=local_config,
                            reason=f"prefer_local=True, {local_config.tier.name} eligible",
                            fallback_tier=config.tier,
                            fallback_reason=f"cloud tier available but local preferred",
                        )

            return TierSelectionResult(
                selected_tier=config.tier,
                selected_config=config,
                reason=reason,
            )

    # Should never reach here - Tier 4 has no requirements
    return TierSelectionResult(
        selected_tier=VoiceTier.TIER_4_KOKORO,
        selected_config=TIER_CONFIGS[-1],
        reason="fallback: no other tier eligible",
    )


def get_fallback_tier(current_tier: VoiceTier, profile: Optional[HardwareProfile] = None) -> Optional[VoiceTier]:
    """Get the next best tier if current tier fails (e.g., OOM)."""
    if profile is None:
        profile = get_hardware_profile()

    current_idx = next(i for i, c in enumerate(TIER_CONFIGS) if c.tier == current_tier)
    for config in TIER_CONFIGS[current_idx + 1:]:
        eligible, _ = _check_tier_conditions(config, profile)
        if eligible:
            return config.tier
    return None


def get_tier_config(tier: VoiceTier) -> TierConfig:
    """Get TierConfig for a specific tier."""
    for config in TIER_CONFIGS:
        if config.tier == tier:
            return config
    raise ValueError(f"Unknown tier: {tier}")


def list_tier_status(profile: Optional[HardwareProfile] = None) -> Dict[str, Any]:
    """Get eligibility status for all tiers."""
    if profile is None:
        profile = get_hardware_profile()

    result = {}
    for config in TIER_CONFIGS:
        eligible, reason = _check_tier_conditions(config, profile)
        result[config.tier.name] = {
            "provider": config.provider_name,
            "eligible": eligible,
            "reason": reason,
            "description": config.description,
            "requires_cloud": config.requires_cloud,
            "requires_gpu": config.requires_gpu,
            "implemented": config.implemented,
        }
    return result