"""A voice tier whose provider is a stub is never the one chosen.

10 October 2026, found auditing a batch of changes. Breeze, Chatterbox Turbo and
Qwen3-TTS each declare in their own docstring that they are stubs, and each answers
a synthesis request with "not yet implemented". The router ranked them above Kokoro,
the only engine that speaks, so on a machine with 16 GB of RAM it chose the Qwen3
stub automatically, and a press in Settings could force any of them. A reply that
should speak would have come back with an error where the voice should be.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from voice.hardware_probe import HardwareProfile
from voice.tier_router import (
    TIER_CONFIGS,
    VoiceTier,
    list_tier_status,
    select_tier,
)
from voice.voice_manager import VoiceManager

BACKEND = Path(__file__).resolve().parents[2]

#: A machine on which every unbuilt tier would otherwise be eligible: a cloud model,
#: a roomy GPU and plenty of memory.
RICH = HardwareProfile(
    gpu_vendor="nvidia",
    gpu_name="test card",
    total_vram_gb=24.0,
    free_vram_gb=20.0,
    total_system_ram_gb=64.0,
    free_system_ram_gb=48.0,
    cloud_llm_active=True,
    cloud_llm_provider="some-cloud",
    local_llm_active=False,
    local_llm_model_id=None,
    local_llm_vram_footprint_gb=None,
)

STUBS = [VoiceTier.TIER_1_BREEZE, VoiceTier.TIER_2_CHATTERBOX, VoiceTier.TIER_3_QWEN3]


def test_the_three_stub_tiers_are_marked_unbuilt_and_kokoro_is_not():
    built = {c.tier: c.implemented for c in TIER_CONFIGS}
    assert [t for t, ok in built.items() if not ok] == STUBS
    assert built[VoiceTier.TIER_4_KOKORO] is True


@pytest.mark.parametrize("prefer_local", [True, False])
def test_even_on_a_machine_that_could_run_them_automatic_selection_picks_kokoro(prefer_local):
    chosen = select_tier(profile=RICH, prefer_local=prefer_local)
    assert chosen.selected_tier is VoiceTier.TIER_4_KOKORO


@pytest.mark.parametrize("tier", STUBS)
def test_forcing_a_stub_is_refused(tier):
    with pytest.raises(ValueError, match="not built yet"):
        select_tier(profile=RICH, force_tier=tier)


def test_the_status_says_why_a_tier_is_unavailable():
    status = list_tier_status(RICH)
    for tier in STUBS:
        assert status[tier.name]["eligible"] is False
        assert status[tier.name]["implemented"] is False
        assert "not built yet" in status[tier.name]["reason"]
    assert status[VoiceTier.TIER_4_KOKORO.name]["eligible"] is True


@pytest.mark.parametrize("tier", STUBS)
def test_a_refused_press_leaves_the_manager_as_it_was(tier, tmp_path):
    manager = VoiceManager(str(tmp_path), "http://127.0.0.1:8420")
    before = (manager.auto_tier_config.enabled, manager.auto_tier_config.force_tier)
    import asyncio

    with pytest.raises(ValueError, match="not built yet"):
        asyncio.run(manager.set_tier_manually(tier))
    assert (manager.auto_tier_config.enabled, manager.auto_tier_config.force_tier) == before


def test_a_tier_may_only_be_marked_built_when_its_provider_no_longer_says_it_is_a_stub():
    # The flag and the docstring have to agree. Flipping the flag without writing the
    # provider is the failure this file exists for, so it is checked from both sides.
    for config in TIER_CONFIGS:
        module = config.provider_class.rsplit(".", 1)[0].replace(".", "/") + ".py"
        source = (BACKEND / module).read_text(encoding="utf-8")
        says_stub = bool(re.search(r"This is a stub|not yet implemented", source))
        assert says_stub is (not config.implemented), (
            f"{config.tier.name}: implemented={config.implemented} but its provider "
            f"{'still says it is a stub' if says_stub else 'no longer says it is a stub'}"
        )
