"""Generic internal model catalog for the AI Garage (v0.6.0).

:class:`GarageModelCatalog` is the single in-memory store of every model
discovered across all providers. It is modality-agnostic and knows nothing
about Ollama, LM Studio, or any cloud API — it only stores
:class:`~garage.contracts.ModelInfo` records.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional

from .contracts import (
    CapabilityLocality,
    ModelCategory,
    ModelInfo,
)

logger = logging.getLogger(__name__)


class GarageModelCatalog:
    """Stores and queries discovered :class:`ModelInfo` records by id."""

    def __init__(self) -> None:
        # model id -> ModelInfo
        self._models: Dict[str, ModelInfo] = {}

    # --- writes ---
    def upsert(self, model: ModelInfo) -> None:
        """Insert or replace a model record (keyed by ``id``)."""
        self._models[model.id] = model

    def upsert_all(self, models: Iterable[ModelInfo]) -> int:
        """Bulk insert/replace. Returns the number of records stored."""
        count = 0
        for model in models:
            self.upsert(model)
            count += 1
        return count

    def remove(self, model_id: str) -> bool:
        return self._models.pop(model_id, None) is not None

    def clear(self) -> None:
        self._models.clear()

    # --- reads ---
    def get(self, model_id: str) -> Optional[ModelInfo]:
        return self._models.get(model_id)

    def count(self) -> int:
        return len(self._models)

    def all(self) -> List[ModelInfo]:
        return list(self._models.values())

    def available_count(self) -> int:
        return sum(1 for m in self._models.values() if m.available)

    # --- filtering (provider-agnostic) ---
    def filter(
        self,
        *,
        category: Optional[ModelCategory] = None,
        capability: Optional[str] = None,
        locality: Optional[CapabilityLocality] = None,
        available_only: bool = False,
        provider: Optional[str] = None,
    ) -> List[ModelInfo]:
        """Return models matching all supplied criteria (empty criteria = no filter)."""
        results: List[ModelInfo] = []
        for model in self._models.values():
            if category is not None and model.category != category:
                continue
            if capability is not None and capability not in model.capabilities:
                continue
            if locality is not None and model.locality != locality:
                continue
            if provider is not None and model.provider != provider:
                continue
            if available_only and not model.available:
                continue
            results.append(model)
        return results

    def by_category(self) -> Dict[str, int]:
        """Counts of models per category value (for capability dashboards)."""
        counts: Dict[str, int] = {}
        for model in self._models.values():
            key = model.category.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def to_dicts(self) -> List[Dict[str, object]]:
        return [m.to_dict() for m in self._models.values()]
