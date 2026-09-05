from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class DecayConfig:
    """Configuration for memory decay rules."""

    forget_threshold: float = 0.1
    low_importance_threshold: float = 0.3
    half_life_days: float = 90.0
    access_boost: float = 0.05
    max_importance: float = 1.0
    min_importance: float = 0.0


@dataclass
class DecayResult:
    """Result of a decay pass."""

    decayed: int = 0
    forgotten: int = 0
    boosted: int = 0
    #: Records the pass did not touch because the user pinned them. Counted
    #: rather than merely skipped, so "nothing decayed" can be told apart from
    #: "everything was exempt" when reading a pass in `/memory/maintenance`.
    pinned: int = 0
    total_records: int = 0
    config: DecayConfig = field(default_factory=DecayConfig)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decayed": self.decayed,
            "forgotten": self.forgotten,
            "boosted": self.boosted,
            "pinned": self.pinned,
            "total_records": self.total_records,
            "config": {
                "forget_threshold": self.config.forget_threshold,
                "low_importance_threshold": self.config.low_importance_threshold,
                "half_life_days": self.config.half_life_days,
            },
            "timestamp": self.timestamp,
        }


class MemoryDecayEngine:
    """Applies decay rules to memories based on age, importance, and access patterns.

    Decay rules:
    - Memories below forget_threshold are removed
    - Memories below low_importance_threshold decay (importance reduced)
    - Recently accessed memories get a boost
    - Decay follows a half-life model
    """

    def __init__(self, config: DecayConfig | None = None):
        self._config = config or DecayConfig()
        self._stats = {
            "total_decay_passes": 0,
            "total_decayed": 0,
            "total_forgotten": 0,
            "total_boosted": 0,
            "total_latency_ms": 0.0,
        }

    @property
    def config(self) -> DecayConfig:
        return self._config

    def calculate_decay_factor(self, age_days: float) -> float:
        """Calculate decay factor using half-life model.

        Returns a value between 0 and 1 where 1 means no decay.
        """
        if age_days <= 0:
            return 1.0
        return 0.5 ** (age_days / self._config.half_life_days)

    def calculate_importance(
        self,
        base_importance: float,
        age_days: float,
        access_count: int,
        last_accessed: float,
    ) -> float:
        """Calculate adjusted importance considering decay and access patterns."""
        decay_factor = self.calculate_decay_factor(age_days)

        access_recency = time.time() - last_accessed
        access_recency_days = access_recency / 86400
        recency_boost = 0.0
        if access_recency_days < 1:
            recency_boost = 0.1
        elif access_recency_days < 7:
            recency_boost = 0.05

        access_boost = min(access_count * self._config.access_boost, 0.2)

        adjusted = base_importance * decay_factor + access_boost + recency_boost
        return min(max(adjusted, self._config.min_importance), self._config.max_importance)

    def should_forget(
        self,
        importance: float,
        age_days: float,
        access_count: int,
    ) -> bool:
        """Determine if a memory should be forgotten."""
        if importance < self._config.forget_threshold:
            return True
        if importance < self._config.low_importance_threshold:
            if age_days > self._config.half_life_days * 2:
                return True
            if access_count == 0 and age_days > 30:
                return True
        return False

    def should_decay(self, importance: float, age_days: float) -> bool:
        """Determine if a memory should have its importance decayed."""
        if importance < self._config.forget_threshold:
            return False
        if importance < self._config.low_importance_threshold:
            return age_days > 7
        return age_days > self._config.half_life_days

    def calculate_decayed_importance(
        self,
        current_importance: float,
        age_days: float,
    ) -> float:
        """Calculate the new importance after decay."""
        decay_factor = self.calculate_decay_factor(age_days)
        decayed = current_importance * decay_factor * 0.95
        return max(decayed, self._config.forget_threshold)

    async def apply_decay(
        self,
        store,
        graph=None,
        config: DecayConfig | None = None,
    ) -> DecayResult:
        """Apply decay rules to all memories in the store.

        Args:
            store: Memory store with _records dict
            graph: Optional MemoryGraph for relationship-aware decay
            config: Optional override for decay configuration

        Returns:
            DecayResult with statistics
        """
        cfg = config or self._config
        start = time.time()
        result = DecayResult(config=cfg)

        # Enumerated through the contract, not through `store._records`.
        #
        # That private dict exists only on `InMemoryMemoryStore`. On the SQLite
        # store the product actually runs, `hasattr` was simply false, the id
        # list came out empty, and the pass reported a clean run over zero
        # records — no error, no warning, nothing decayed, ever. It is the same
        # defect as the `access_count` one: two implementations of one contract,
        # and the tests exercised the one nobody ships.
        #
        # Superseded records are excluded. A correction keeps the old value
        # visible as struck-through history, and decay deleting it would erase
        # the evidence that the user corrected anything.
        records = await store.all_records(include_superseded=False)

        now = time.time()

        for record in records:
            rid = record.id
            age_days = (now - record.created_at) / 86400

            # **A pinned fact is exempt, and it was not.**
            #
            # Measured 3 September 2026: a pinned record, 200 days old, never
            # recalled, importance 0.2 — deleted by this pass. Pinning is the
            # user saying *keep this*, the Memory surface tells them in as many
            # words that it changes how recall treats the fact, and the curator
            # was quietly undoing it a month later.
            #
            # It is rule 4 read from the other end. That rule gives the user
            # power over their own facts; a maintenance pass that overrules an
            # explicit instruction has taken it back, and silently — the fact
            # is simply gone, with nothing saying why.
            #
            # Skipped entirely rather than merely spared deletion. Decaying a
            # pinned record's importance would demote it in ranking, one pass
            # at a time, while the interface still claimed recall prefers it —
            # the same promise broken slowly instead of all at once.
            if getattr(record, "pinned", False):
                result.pinned += 1
                continue

            if self.should_forget(record.importance, age_days, record.access_count):
                await store.delete(rid)
                if graph:
                    graph.remove_node(rid)
                result.forgotten += 1
            elif self.should_decay(record.importance, age_days):
                new_importance = self.calculate_decayed_importance(record.importance, age_days)
                if new_importance < cfg.forget_threshold:
                    await store.delete(rid)
                    if graph:
                        graph.remove_node(rid)
                    result.forgotten += 1
                else:
                    updated = type(record)(
                        **{**record.__dict__, "importance": new_importance, "updated_at": now}
                    )
                    await store.put(updated)
                    result.decayed += 1
            else:
                adjusted = self.calculate_importance(
                    record.importance,
                    age_days,
                    record.access_count,
                    record.last_accessed,
                )
                if adjusted > record.importance + 0.01:
                    updated = type(record)(
                        **{**record.__dict__, "importance": adjusted, "updated_at": now}
                    )
                    await store.put(updated)
                    result.boosted += 1

        result.total_records = len(records) - result.forgotten
        result.timestamp = time.time()

        latency = (time.time() - start) * 1000
        self._stats["total_decay_passes"] += 1
        self._stats["total_decayed"] += result.decayed
        self._stats["total_forgotten"] += result.forgotten
        self._stats["total_boosted"] += result.boosted
        self._stats["total_latency_ms"] += latency

        return result

    def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "config": {
                "forget_threshold": self._config.forget_threshold,
                "low_importance_threshold": self._config.low_importance_threshold,
                "half_life_days": self._config.half_life_days,
            },
            "stats": self._stats,
            "avg_latency_ms": self._stats["total_latency_ms"] / max(self._stats["total_decay_passes"], 1),
        }


def create_decay_engine(config: DecayConfig | None = None) -> MemoryDecayEngine:
    """Factory for creating a memory decay engine."""
    return MemoryDecayEngine(config)
