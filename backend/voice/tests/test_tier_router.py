"""Tests for tier_router.py - tier selection logic for 4-Tier Voice Pipeline."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from voice.hardware_probe import HardwareProfile
from voice.tier_router import (
    VoiceTier,
    TierConfig,
    TierSelectionResult,
    select_tier,
    get_fallback_tier,
    get_tier_config,
    list_tier_status,
    _check_tier_conditions,
    TIER_CONFIGS,
)


# These tests are about the router's *rules* -- cloud needs a cloud model, a GPU tier
# needs a GPU, and so on. Three of the four providers are still stubs, so the shipped
# configs refuse them (`implemented=False`; see test_a_stub_tier_is_never_chosen.py).
# Here the tiers are taken as if every provider were built, so the rules can be
# tested; the day they are built, the flag flips and this indirection can go.
import dataclasses

from voice import tier_router as _router

TIER_CONFIGS = [dataclasses.replace(c, implemented=True) for c in _router.TIER_CONFIGS]


@pytest.fixture(autouse=True)
def _as_if_the_providers_were_built(monkeypatch):
    monkeypatch.setattr(_router, "TIER_CONFIGS", TIER_CONFIGS)


class TestTierConfigs:
    """Tests for tier configuration constants."""

    def test_four_tiers_defined(self):
        tiers = [c.tier for c in TIER_CONFIGS]
        assert tiers == [
            VoiceTier.TIER_1_BREEZE,
            VoiceTier.TIER_2_CHATTERBOX,
            VoiceTier.TIER_3_QWEN3,
            VoiceTier.TIER_4_KOKORO,
        ]

    def test_tier_configs_have_required_fields(self):
        for config in TIER_CONFIGS:
            assert isinstance(config.tier, VoiceTier)
            assert config.provider_name
            assert config.provider_class
            assert config.config_class
            assert isinstance(config.description, str)
            assert config.description != ""

    def test_tier_priority_order(self):
        # Tier 1 has highest priority (lowest enum value)
        assert VoiceTier.TIER_1_BREEZE.value == 1
        assert VoiceTier.TIER_2_CHATTERBOX.value == 2
        assert VoiceTier.TIER_3_QWEN3.value == 3
        assert VoiceTier.TIER_4_KOKORO.value == 4


class TestCheckTierConditions:
    """Tests for _check_tier_conditions."""

    def make_profile(self, **kwargs):
        defaults = {
            "gpu_vendor": "unknown",
            "gpu_name": "unknown",
            "total_vram_gb": None,
            "free_vram_gb": None,
            "total_system_ram_gb": None,
            "free_system_ram_gb": None,
            "cloud_llm_active": False,
            "cloud_llm_provider": None,
            "local_llm_active": False,
            "local_llm_model_id": None,
            "local_llm_vram_footprint_gb": None,
        }
        defaults.update(kwargs)
        return HardwareProfile(**defaults)

    def test_tier_4_always_eligible(self):
        profile = self.make_profile()
        config = get_tier_config(VoiceTier.TIER_4_KOKORO)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is True
        assert reason == "all conditions met"

    def test_tier_1_requires_cloud_llm(self):
        profile = self.make_profile(cloud_llm_active=False)
        config = get_tier_config(VoiceTier.TIER_1_BREEZE)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is False
        assert "requires cloud LLM" in reason

    def test_tier_1_eligible_with_cloud_llm(self):
        profile = self.make_profile(cloud_llm_active=True, cloud_llm_provider="openrouter")
        config = get_tier_config(VoiceTier.TIER_1_BREEZE)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is True

    def test_tier_1_eligible_with_free_vram(self):
        profile = self.make_profile(
            cloud_llm_active=False,
            gpu_vendor="nvidia",
            total_vram_gb=12.0,
            free_vram_gb=5.0,
        )
        config = get_tier_config(VoiceTier.TIER_1_BREEZE)
        eligible, reason = _check_tier_conditions(config, profile)
        # Tier 1 is cloud-only - requires cloud LLM, not just VRAM
        assert eligible is False
        assert "requires cloud LLM" in reason

    def test_tier_1_not_eligible_insufficient_vram(self):
        profile = self.make_profile(
            cloud_llm_active=False,
            gpu_vendor="nvidia",
            total_vram_gb=8.0,
            free_vram_gb=2.0,
        )
        config = get_tier_config(VoiceTier.TIER_1_BREEZE)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is False
        assert "requires cloud LLM" in reason

    def test_tier_2_requires_gpu(self):
        profile = self.make_profile()
        config = get_tier_config(VoiceTier.TIER_2_CHATTERBOX)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is False
        assert "requires GPU" in reason

    def test_tier_2_eligible_with_gpu(self):
        profile = self.make_profile(
            gpu_vendor="nvidia",
            total_vram_gb=12.0,
            free_vram_gb=3.0,
            total_system_ram_gb=32.0,
        )
        config = get_tier_config(VoiceTier.TIER_2_CHATTERBOX)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is True

    def test_tier_2_insufficient_free_vram(self):
        profile = self.make_profile(
            gpu_vendor="nvidia",
            total_vram_gb=12.0,
            free_vram_gb=1.0,
            total_system_ram_gb=32.0,
        )
        config = get_tier_config(VoiceTier.TIER_2_CHATTERBOX)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is False
        assert "free VRAM" in reason

    def test_tier_2_insufficient_system_ram(self):
        profile = self.make_profile(
            gpu_vendor="nvidia",
            total_vram_gb=12.0,
            free_vram_gb=3.0,
            total_system_ram_gb=16.0,
        )
        config = get_tier_config(VoiceTier.TIER_2_CHATTERBOX)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is False
        assert "system RAM" in reason

    def test_tier_2_local_llm_vram_limit(self):
        profile = self.make_profile(
            gpu_vendor="nvidia",
            total_vram_gb=12.0,
            free_vram_gb=3.0,
            total_system_ram_gb=32.0,
            local_llm_active=True,
            local_llm_vram_footprint_gb=11.0,  # Exceeds 10.5GB limit
        )
        config = get_tier_config(VoiceTier.TIER_2_CHATTERBOX)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is False
        assert "local LLM VRAM" in reason

    def test_tier_3_requires_system_ram(self):
        profile = self.make_profile(total_system_ram_gb=8.0)
        config = get_tier_config(VoiceTier.TIER_3_QWEN3)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is False
        assert "system RAM" in reason

    def test_tier_3_eligible_with_ram(self):
        profile = self.make_profile(total_system_ram_gb=16.0)
        config = get_tier_config(VoiceTier.TIER_3_QWEN3)
        eligible, reason = _check_tier_conditions(config, profile)
        assert eligible is True


class TestSelectTier:
    """Tests for select_tier function."""

    def make_profile(self, **kwargs):
        defaults = {
            "gpu_vendor": "unknown",
            "gpu_name": "unknown",
            "total_vram_gb": None,
            "free_vram_gb": None,
            "total_system_ram_gb": None,
            "free_system_ram_gb": None,
            "cloud_llm_active": False,
            "cloud_llm_provider": None,
            "local_llm_active": False,
            "local_llm_model_id": None,
            "local_llm_vram_footprint_gb": None,
        }
        defaults.update(kwargs)
        return HardwareProfile(**defaults)

    def test_force_tier_override(self):
        profile = self.make_profile()
        result = select_tier(profile=profile, force_tier=VoiceTier.TIER_2_CHATTERBOX)
        assert result.selected_tier == VoiceTier.TIER_2_CHATTERBOX
        assert "manually forced" in result.reason

    def test_force_invalid_tier_raises(self):
        profile = self.make_profile()
        with pytest.raises(ValueError, match="Unknown tier"):
            select_tier(profile=profile, force_tier="INVALID")

    def test_tier_1_selected_with_cloud_llm(self):
        profile = self.make_profile(cloud_llm_active=True, cloud_llm_provider="openrouter")
        result = select_tier(profile=profile, prefer_local=False)
        assert result.selected_tier == VoiceTier.TIER_1_BREEZE

    def test_tier_1_selected_with_free_vram(self):
        profile = self.make_profile(
            cloud_llm_active=False,
            gpu_vendor="nvidia",
            total_vram_gb=16.0,
            free_vram_gb=5.0,
        )
        result = select_tier(profile=profile, prefer_local=False)
        # No cloud LLM, so Tier 1 not eligible even with VRAM
        # Falls through to Tier 4 (Kokoro) as no GPU tier is eligible without local LLM
        assert result.selected_tier == VoiceTier.TIER_4_KOKORO

    def test_prefer_local_skips_tier_1(self):
        profile = self.make_profile(
            cloud_llm_active=True,
            cloud_llm_provider="openrouter",
            gpu_vendor="nvidia",
            total_vram_gb=12.0,
            free_vram_gb=3.0,
            total_system_ram_gb=32.0,
        )
        result = select_tier(profile=profile, prefer_local=True)
        # Should prefer Tier 2 (local) over Tier 1 (cloud)
        assert result.selected_tier == VoiceTier.TIER_2_CHATTERBOX
        assert result.fallback_tier == VoiceTier.TIER_1_BREEZE

    def test_tier_2_selected_when_tier_1_not_eligible(self):
        profile = self.make_profile(
            cloud_llm_active=False,
            gpu_vendor="nvidia",
            total_vram_gb=12.0,
            free_vram_gb=3.0,
            total_system_ram_gb=32.0,
        )
        result = select_tier(profile=profile)
        assert result.selected_tier == VoiceTier.TIER_2_CHATTERBOX

    def test_tier_3_selected_cpu_only(self):
        profile = self.make_profile(total_system_ram_gb=32.0)
        result = select_tier(profile=profile)
        assert result.selected_tier == VoiceTier.TIER_3_QWEN3

    def test_tier_4_fallback_low_spec(self):
        profile = self.make_profile(total_system_ram_gb=8.0)
        result = select_tier(profile=profile)
        assert result.selected_tier == VoiceTier.TIER_4_KOKORO

    def test_tier_4_fallback_no_ram_info(self):
        profile = self.make_profile()
        result = select_tier(profile=profile)
        assert result.selected_tier == VoiceTier.TIER_4_KOKORO


class TestGetFallbackTier:
    """Tests for get_fallback_tier function."""

    def make_profile(self, **kwargs):
        defaults = {
            "gpu_vendor": "unknown",
            "gpu_name": "unknown",
            "total_vram_gb": None,
            "free_vram_gb": None,
            "total_system_ram_gb": None,
            "free_system_ram_gb": None,
            "cloud_llm_active": False,
            "cloud_llm_provider": None,
            "local_llm_active": False,
            "local_llm_model_id": None,
            "local_llm_vram_footprint_gb": None,
        }
        defaults.update(kwargs)
        return HardwareProfile(**defaults)

    def test_fallback_from_tier_1(self):
        profile = self.make_profile(
            cloud_llm_active=False,
            gpu_vendor="nvidia",
            total_vram_gb=12.0,
            free_vram_gb=3.0,
            total_system_ram_gb=32.0,
        )
        fallback = get_fallback_tier(VoiceTier.TIER_1_BREEZE, profile)
        assert fallback == VoiceTier.TIER_2_CHATTERBOX

    def test_fallback_from_tier_2(self):
        profile = self.make_profile(total_system_ram_gb=32.0)
        fallback = get_fallback_tier(VoiceTier.TIER_2_CHATTERBOX, profile)
        assert fallback == VoiceTier.TIER_3_QWEN3

    def test_fallback_from_tier_3(self):
        profile = self.make_profile(total_system_ram_gb=8.0)
        fallback = get_fallback_tier(VoiceTier.TIER_3_QWEN3, profile)
        assert fallback == VoiceTier.TIER_4_KOKORO

    def test_fallback_from_tier_4_none(self):
        profile = self.make_profile()
        fallback = get_fallback_tier(VoiceTier.TIER_4_KOKORO, profile)
        assert fallback is None

    def test_no_fallback_when_not_eligible(self):
        profile = self.make_profile(total_system_ram_gb=8.0)
        fallback = get_fallback_tier(VoiceTier.TIER_2_CHATTERBOX, profile)
        assert fallback == VoiceTier.TIER_4_KOKORO  # Tier 3 not eligible (needs 16GB), Tier 4 is next


class TestGetTierConfig:
    """Tests for get_tier_config function."""

    def test_all_tiers_return_config(self):
        for tier in VoiceTier:
            config = get_tier_config(tier)
            assert config.tier == tier
            assert isinstance(config, TierConfig)

    def test_invalid_tier_raises(self):
        with pytest.raises(ValueError, match="Unknown tier"):
            get_tier_config("INVALID_TIER")


class TestListTierStatus:
    """Tests for list_tier_status function."""

    def make_profile(self, **kwargs):
        defaults = {
            "gpu_vendor": "unknown",
            "gpu_name": "unknown",
            "total_vram_gb": None,
            "free_vram_gb": None,
            "total_system_ram_gb": None,
            "free_system_ram_gb": None,
            "cloud_llm_active": False,
            "cloud_llm_provider": None,
            "local_llm_active": False,
            "local_llm_model_id": None,
            "local_llm_vram_footprint_gb": None,
        }
        defaults.update(kwargs)
        return HardwareProfile(**defaults)

    def test_returns_all_tiers(self):
        profile = self.make_profile()
        status = list_tier_status(profile)
        assert set(status.keys()) == {t.name for t in VoiceTier}

    def test_status_has_required_fields(self):
        profile = self.make_profile()
        status = list_tier_status(profile)
        for tier_name, info in status.items():
            assert "provider" in info
            assert "eligible" in info
            assert "reason" in info
            assert "description" in info
            assert "requires_cloud" in info
            assert "requires_gpu" in info

    def test_tier_4_always_eligible(self):
        profile = self.make_profile()
        status = list_tier_status(profile)
        assert status["TIER_4_KOKORO"]["eligible"] is True

    def test_tier_1_eligible_with_cloud(self):
        profile = self.make_profile(cloud_llm_active=True, cloud_llm_provider="openrouter")
        status = list_tier_status(profile)
        assert status["TIER_1_BREEZE"]["eligible"] is True

    def test_tier_1_not_eligible_without_cloud_or_vram(self):
        profile = self.make_profile()
        status = list_tier_status(profile)
        assert status["TIER_1_BREEZE"]["eligible"] is False