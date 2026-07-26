# backend/knowledge/temporal.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from .protocol import KnowledgeObject, TemporalVersion


@dataclass
class TemporalEngine:
    """Manages temporal knowledge and versioning."""

    default_ttl: float = 365 * 24 * 3600

    def create_version(self, valid_from: float | None = None, ttl: float | None = None) -> TemporalVersion:
        now = valid_from or time.time()
        return TemporalVersion(
            valid_from=now,
            valid_until=now + (ttl or self.default_ttl),
            created=now,
            indexed=now,
            last_updated=now,
            version=1,
            is_current=True,
        )

    def update_version(self, current: TemporalVersion, now: float | None = None) -> TemporalVersion:
        now = now or time.time()
        current.last_updated = now
        current.version += 1
        return current

    def create_new_version(self, previous: TemporalVersion, now: float | None = None) -> TemporalVersion:
        now = now or time.time()
        previous.is_current = False
        previous.valid_until = now
        new_version = TemporalVersion(
            valid_from=now,
            valid_until=now + self.default_ttl,
            created=previous.created,
            indexed=previous.indexed,
            last_updated=now,
            version=previous.version + 1,
            is_current=True,
        )
        return new_version

    def is_valid(self, version: TemporalVersion, now: float | None = None) -> bool:
        now = now or time.time()
        if not version.is_current:
            return False
        if version.valid_until > 0 and now >= version.valid_until:
            return False
        return True

    def apply_to_object(self, obj: KnowledgeObject, ttl: float | None = None) -> None:
        if obj.temporal is None:
            obj.temporal = self.create_version(ttl=ttl)
        else:
            obj.temporal = self.update_version(obj.temporal)
