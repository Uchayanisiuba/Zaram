"""Voice source adapter for the AI Garage (v0.6.0).

The Garage discovers installed voices through an injected source, never by
importing the Voice Runtime. In production the Voice Runtime's manager (which
exposes ``available_voices()``) is injected; tests use the static source.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..contracts import VoiceInfo

logger = logging.getLogger(__name__)


class VoiceRegistryAdapter:
    """Adapts any object exposing ``available_voices() -> Dict[id, meta]``."""

    def __init__(self, source: Any) -> None:
        self._source = source

    async def list_voices(self) -> Dict[str, Any]:
        try:
            source = self._source
            if hasattr(source, "available_voices"):
                result = source.available_voices()
            elif hasattr(source, "list_voices"):
                result = source.list_voices()
            else:
                return {}
            if hasattr(result, "__await__"):
                result = await result
            return dict(result or {})
        except Exception as exc:
            logger.warning("Voice discovery failed: %s", exc)
            return {}

    def to_voice_infos(self, voices: Dict[str, Any]) -> List[VoiceInfo]:
        infos: List[VoiceInfo] = []
        for voice_id, meta in (voices or {}).items():
            meta = meta or {}
            infos.append(
                VoiceInfo(
                    id=voice_id,
                    display_name=meta.get("display_name", meta.get("name", voice_id)),
                    provider=meta.get("provider", "unknown"),
                    language=meta.get("language", meta.get("language_code", "unknown")),
                    gender=meta.get("gender", "unknown"),
                    metadata=dict(meta),
                )
            )
        return infos


class StaticVoiceSource:
    """A fixed set of voices (used for tests and offline configuration)."""

    def __init__(self, voices: Dict[str, Any]) -> None:
        self._voices = dict(voices or {})

    async def list_voices(self) -> Dict[str, Any]:
        return dict(self._voices)
