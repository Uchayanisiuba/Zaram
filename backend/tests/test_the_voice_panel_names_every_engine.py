"""The Voices panel names every speech engine, and which one is speaking.

10 October 2026. `/voice/tier` read `tier_status` out of the speech runtime's health
report, and that report has never carried one -- the four-tier router was not wired
into the runtime that speaks -- so a live backend answered with an empty list and no
active engine. The panel's engine chips rendered nothing, and the maintainer asked
twice where the other voice options were. These tests use the route's real tier table
and a fake runtime that reports what the live one reported.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest


@pytest.fixture
def tier_status(monkeypatch):
    import main
    from voice import tier_router
    from voice.hardware_probe import HardwareProfile

    # A machine with nothing special, so the answer does not depend on this one.
    monkeypatch.setattr(tier_router, "get_hardware_profile", lambda: HardwareProfile())

    def run(connector="kokoro"):
        runtime = SimpleNamespace(health_check=lambda: {"active_connector": connector, "connectors": {}})
        monkeypatch.setattr(main, "kernel", SimpleNamespace(speech_runtime=runtime))
        return asyncio.run(main.voice_tier_status())

    return run


def test_every_engine_in_the_table_is_listed(tier_status):
    from voice.tier_router import TIER_CONFIGS

    answer = tier_status()
    assert set(answer["tier_status"]) == {c.tier.name for c in TIER_CONFIGS}


def test_the_speaking_engine_is_named(tier_status):
    answer = tier_status()
    assert answer["active_tier"] == "TIER_4_KOKORO" and answer["active_provider"] == "kokoro"


def test_the_unbuilt_engines_say_so(tier_status):
    tiers = tier_status()["tier_status"]
    for name in ("TIER_1_BREEZE", "TIER_2_CHATTERBOX", "TIER_3_QWEN3"):
        assert tiers[name]["implemented"] is False and tiers[name]["eligible"] is False
        assert "not built yet" in tiers[name]["reason"]
    assert tiers["TIER_4_KOKORO"]["implemented"] is True


def test_it_does_not_claim_an_automatic_choice_that_is_not_running(tier_status):
    assert tier_status()["auto_tier_enabled"] is False
