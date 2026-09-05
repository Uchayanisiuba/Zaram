"""Which model to suggest for this machine, from a dated file rather than a guess.

`CLAUDE.md`: *"Model recommendations ship as a dated local manifest — JSON in
the bundle, grouped by VRAM tier, with a visible `generated` date. Never fail
closed: a missing or corrupt manifest falls back to whatever is installed.
Detection (hardware, installed models) is separate from recommendation (names,
sizes) — the first never goes stale."*

That separation is the whole design here. This module answers *"what would suit
a machine with this much room"* and knows nothing about what the machine
actually has; the caller measures that. So a stale manifest recommends an older
model and never misreports the hardware, which is the failure that would
matter.

**Every number here is approximate and says so.** The size is what the download
is expected to be, rounded, and it is quoted so a person on a metered
connection can decide before it starts. The *true* total arrives from the pull
itself and is what the progress counts against — a manifest figure presented as
a measurement would be a value nobody measured, which this product treats as
worse than no figure at all.

**Never fail closed.** Every failure path returns no recommendation rather than
raising: a missing file, a corrupt file, a tier list that is not a list. A
first run that cannot suggest a model is a smaller problem than a first run
that will not start.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.manifest.json")

#: One gigabyte, as the manifest counts them. Decimal rather than binary
#: because that is how download sizes are quoted everywhere a user will
#: compare them — a provider's page, a data plan, a disk.
GB = 1_000_000_000


@dataclass(frozen=True)
class Recommendation:
    """One model worth pulling, and what it costs.

    ``fits`` is not on here on purpose. Whether it fits is a fact about the
    machine, measured by the caller; this record is the manifest's half.
    """

    name: str
    size_bytes: int
    why: str
    #: The manifest's date, carried on every recommendation so a surface can
    #: show it without reaching back for the file. `CLAUDE.md` asks for it to
    #: be visible: a recommendation is only as current as the list it came from.
    generated: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "why": self.why,
            "generated": self.generated,
        }


def _load(path: str = MANIFEST_PATH) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        # Logged rather than raised. A packaging mistake must cost a
        # recommendation, never the launch.
        logger.warning("model manifest unreadable at %s: %s", path, error)
        return None
    return data if isinstance(data, dict) else None


def recommend_for(budget_bytes: Optional[int], *, path: str = MANIFEST_PATH) -> List[Recommendation]:
    """What suits a machine with ``budget_bytes`` of room for a chat model.

    ``budget_bytes`` is `ProviderManager.resident_budget_bytes` — VRAM less
    the embedder and the KV reserve — and **`None` is a real answer**, meaning
    the machine could not be measured. Apple and DirectML report nothing, and
    `hardware.py` returns `None` rather than zero for exactly this reason.

    On `None` the smallest tier is returned. That is the conservative choice
    and the honest one: a recommendation the machine cannot run is worse than a
    thin one it certainly can, and `CLAUDE.md`'s first-run rule — *"start with
    the smallest capable model and fetch better in the background"* — points
    the same way.
    """
    data = _load(path)
    if not data:
        return []

    generated = str(data.get("generated") or "")
    tiers = data.get("tiers")
    if not isinstance(tiers, list):
        logger.warning("model manifest has no tier list")
        return []

    budget_gb = None if budget_bytes is None else budget_bytes / GB

    for tier in tiers:
        if not isinstance(tier, dict):
            continue
        ceiling = tier.get("max_budget_gb")
        # `null` is the top tier and matches anything that got this far. An
        # unmeasurable machine never gets here: it takes the first tier.
        if budget_gb is None or ceiling is None or budget_gb <= float(ceiling):
            return _models_in(tier, generated)

    return []


def _models_in(tier: Dict[str, Any], generated: str) -> List[Recommendation]:
    out: List[Recommendation] = []
    for entry in tier.get("models") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        size = entry.get("size_bytes")
        if not name or not isinstance(size, int):
            # A recommendation with no size cannot state its cost, and an
            # offer whose cost is unstated is the one thing this must not be.
            continue
        out.append(
            Recommendation(
                name=name,
                size_bytes=size,
                why=str(entry.get("why") or ""),
                generated=generated,
            )
        )
    return out


def smaller_than(
    size_bytes: Optional[int],
    budget_bytes: Optional[int],
    *,
    installed: Sequence[str] = (),
    path: str = MANIFEST_PATH,
) -> Optional[Recommendation]:
    """A model that would fit, for someone whose current one does not.

    The remedy half of the *"too large for this machine"* warning. Returns
    `None` when there is nothing better to offer — the machine is unmeasured,
    the manifest is gone, or the suggestion is already installed, in which case
    the user's problem is a choice in Settings rather than a download.
    """
    for candidate in recommend_for(budget_bytes, path=path):
        if candidate.name in installed:
            continue
        if size_bytes is not None and candidate.size_bytes >= size_bytes:
            # Not smaller, so not a remedy. Offering it would be advice that
            # costs a download and changes nothing.
            continue
        return candidate
    return None
