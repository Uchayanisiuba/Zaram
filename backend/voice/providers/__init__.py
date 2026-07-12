"""Voice provider package.

Only the abstract interface lives here for now. Concrete providers
(Kokoro, XTTS, ElevenLabs, OpenAI, Unreal, custom) are added in later
milestones and registered via :class:`~voice.registry.VoiceRegistry`.
"""

from __future__ import annotations

from .base import VoiceProvider

__all__ = ["VoiceProvider"]
