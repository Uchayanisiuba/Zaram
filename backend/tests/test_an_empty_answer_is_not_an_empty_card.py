"""What "nothing is loaded" is evidence of, and what it is not.

`_resident_models` asks every local server what it holds. When they all answer
*nothing*, that is evidence about **Zaram's own tenants** and about nothing
else — and `_headroom_bytes` treated it as a measurement of the card, because
`all()` of an empty mapping is vacuously true. The sum path was taken with a
sum of zero and returned the entire budget.

Measured 6 September 2026 on the 12 GB card, and it is not hypothetical. An
`ollama app.exe` stopped without its child left `llama-server.exe` orphaned and
holding **8.34 GB** — parent dead, `/api/ps` reporting no models, the driver
reporting 911 MiB free. Zaram would have graded a 10 GB model as fitting onto
900 MB.

This is the same defect the method's own docstring records being fixed on
28 August, when Ollama answered an empty map while TabbyAPI held 9.5 GB. That
fix merged the servers' answers; it did not stop an empty merge from being read
as an empty card.
"""

from __future__ import annotations

import pytest

from providers.contracts import HardwareProfile


class _Profiler:
    """A driver that can see the whole card, orphans included."""

    def __init__(self, total: int, used: int) -> None:
        self._total, self._used = total, used

    def vram_used_bytes(self) -> int:
        return self._used


GB = 1_000_000_000
CARD = 12 * GB


@pytest.fixture
def manager():
    from providers.manager import ProviderManager

    return ProviderManager()


def _measured(manager, *, used: int, embedder: int = 0) -> None:
    """Point the manager at a card with ``used`` bytes already spoken for."""
    manager._hardware = HardwareProfile(
        gpu_available=True, gpu_name="RTX 3060", vram_bytes=CARD
    )
    manager.registry.set_hardware_profiler(_Profiler(CARD, used))
    manager.embedding_footprint_bytes = lambda: embedder  # type: ignore[method-assign]


class TestAnEmptyAnswerIsNotAnEmptyCard:
    def test_an_orphan_holding_the_card_is_not_headroom(self, manager):
        """The measured case. Every server says nothing; the card says 8.34 GB."""
        _measured(manager, used=8_340_000_000)

        headroom = manager._headroom_bytes({})

        assert headroom is not None
        assert headroom < 4 * GB, (
            f"reported {headroom / GB:.2f} GB of headroom on a card with "
            "0.9 GB free"
        )

    def test_a_genuinely_empty_card_still_reports_room(self, manager):
        """The fix must not turn every cold start into a refusal."""
        _measured(manager, used=500_000_000)

        headroom = manager._headroom_bytes({})

        assert headroom is not None
        assert headroom > 10 * GB

    def test_room_is_left_for_the_embedder_when_it_is_not_loaded(self, manager):
        """Recall runs on every exchange, so it is not an optional tenant."""
        _measured(manager, used=500_000_000, embedder=1_160_000_000)

        headroom = manager._headroom_bytes({})

        assert headroom < CARD - 500_000_000 - GB

    def test_with_no_driver_to_ask_the_budget_is_the_fallback(self, manager):
        """The fix must not make Apple, DirectML and every machine without a
        VRAM probe answer "cannot tell" on a cold start.

        With nothing resident *and* no driver reading there is no measurement
        to prefer, so this falls back to the same assumption
        `resident_budget_bytes` already makes by counting from total capacity.
        An orphan is invisible here — unavoidably, since nothing on the machine
        can see it."""
        manager._hardware = HardwareProfile(
            gpu_available=True, gpu_name="RTX 3060", vram_bytes=CARD
        )
        manager.registry.set_hardware_profiler(object())  # no `vram_used_bytes`
        manager.embedding_footprint_bytes = lambda: 0  # type: ignore[method-assign]

        assert manager._headroom_bytes({}) == CARD

    def test_an_unsized_tenant_with_no_driver_stays_unknown(self, manager):
        """Different case, and it must stay three-valued: something *is* on the
        card and nothing can say how much."""
        manager._hardware = HardwareProfile(
            gpu_available=True, gpu_name="RTX 3060", vram_bytes=CARD
        )
        manager.registry.set_hardware_profiler(object())
        manager.embedding_footprint_bytes = lambda: 0  # type: ignore[method-assign]

        assert manager._headroom_bytes({"Qwen3.8-27B-exl3": None}) is None


class TestTheSumPathStillWorksWhenItHasSomethingToSum:
    def test_a_sized_tenant_is_counted_against_the_budget(self, manager):
        """Preferred when available because it is attributable: it counts
        Zaram's own tenants and does not move when an unrelated program takes a
        slice of the card."""
        _measured(manager, used=11_000_000_000)

        headroom = manager._headroom_bytes({"qwen3:14b": 9 * GB})

        # The sum path, not the driver: budget (12) - 9 = 3, rather than the
        # 1 GB the driver would report.
        assert headroom == pytest.approx(3 * GB, abs=GB // 2)

    def test_an_unsized_tenant_falls_through_to_the_driver(self, manager):
        """TabbyAPI names its model without sizing it, and an unanswerable sum
        is how 9.5 GB came to be invisible once already."""
        _measured(manager, used=9_500_000_000)

        headroom = manager._headroom_bytes({"Qwen3.8-27B-exl3": None})

        assert headroom is not None
        assert headroom < 3 * GB
