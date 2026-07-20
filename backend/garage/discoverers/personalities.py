"""Personality source adapter for the AI Garage (v0.6.0).

Personalities are installed profiles (identity, voice mapping, ...). The
Garage reads them from an injected source — by default a JSON file such as
``characters.json`` — and never couples to a specific file layout.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PersonalitiesFileAdapter:
    """Reads installed personalities from a JSON file.

    The file is expected to be a mapping of ``personality_id -> profile``
    (matching ``characters.json``). Each profile is returned with its ``id``
    injected so the Garage can key on it.
    """

    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def list_personalities(self) -> List[Dict[str, Any]]:
        if not self._path.is_file():
            logger.warning("Personalities file not found: %s", self._path)
            return []
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:
            logger.warning("Failed to read personalities %s: %s", self._path, exc)
            return []

        if not isinstance(data, dict):
            return []

        result: List[Dict[str, Any]] = []
        for personality_id, profile in data.items():
            if not isinstance(profile, dict):
                continue
            entry = dict(profile)
            entry.setdefault("id", personality_id)
            result.append(entry)
        return result


class StaticPersonalitySource:
    """A fixed set of personalities (tests / embedded default)."""

    def __init__(self, personalities: List[Dict[str, Any]]) -> None:
        self._personalities = list(personalities or [])

    def list_personalities(self) -> List[Dict[str, Any]]:
        return list(self._personalities)
