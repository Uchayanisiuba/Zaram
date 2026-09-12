"""The graphics card, as the images runtime needs to see it.

Three questions and nothing else: how much is free *now*, what Zaram's own
servers are holding, and give it back. Each already had an answer somewhere in
the provider layer — `vram_free_bytes` (nvidia-smi), `ProviderManager.resident_now`
and `ProviderManager.release_resident` — and this is the seam that puts them in
front of the one caller that was loading 8.4 GB without asking any of them.

A protocol rather than the manager itself, so the runtime's tests can hand it
a card that reads whatever the test says and record the order it was asked in.
The order is the fix: read, release, read again, and only then load.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class Card(Protocol):
    def free_bytes(self) -> Optional[int]:
        """Free VRAM right now, or None when it cannot be read. Never a guess."""
        ...

    def resident(self) -> Optional[Dict[str, Optional[int]]]:
        """What Zaram's local servers hold: model name to bytes, or None."""
        ...

    def release(self) -> Dict[str, str]:
        """Unload what can be unloaded. Model name to outcome; a model that
        could not be released says so and why."""
        ...


class GpuCard:
    """The real one. `manager` is a `ProviderManager`; `free_probe` is
    `providers.discoverers.hardware.vram_free_bytes` unless a test says
    otherwise.

    Every method answers rather than raises: a probe that fails must cost the
    user a guard, never a picture — the same rule `_swap_preflight_event`
    keeps for chat.
    """

    def __init__(self, manager, free_probe: Callable[[], Optional[int]]) -> None:
        self._manager = manager
        self._free_probe = free_probe

    def free_bytes(self) -> Optional[int]:
        try:
            return self._free_probe()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Images: free-VRAM probe failed: %s", exc)
            return None

    def resident(self) -> Optional[Dict[str, Optional[int]]]:
        try:
            return self._manager.resident_now()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Images: residency probe failed: %s", exc)
            return None

    def release(self) -> Dict[str, str]:
        try:
            return dict(self._manager.release_resident())
        except Exception as exc:  # noqa: BLE001
            logger.debug("Images: release failed: %s", exc)
            return {}
