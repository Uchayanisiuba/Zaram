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
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    #: What the manifest says this model can do, from a fixed vocabulary
    #: (`CAPABILITIES`). **Empty means "not stated", never "cannot"** — an entry
    #: lists a capability only where there is evidence for it (the model reports
    #: it, or the entry's own text says so), and a model the author knows nothing
    #: about carries no badges rather than an invented absence. Once a model is
    #: installed its own report is the better source; this is the claim about one
    #: that is not here yet.
    capabilities: Tuple[str, ...] = ()
    #: What serves it. ``"ollama"`` is the one Zaram can fetch (`stream_pull`);
    #: ``"tabby"`` is an EXL3 build, which is a revision of a repository that
    #: TabbyAPI loads from a folder only its owner knows. The browser lists and
    #: grades both, and offers a download for the first only.
    runtime: str = "ollama"
    repo: str = ""
    revision: str = ""

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "why": self.why,
            "generated": self.generated,
            "capabilities": list(self.capabilities),
            "runtime": self.runtime,
        }
        if self.runtime != "ollama":
            out["repo"] = self.repo
            out["revision"] = self.revision
            out["install_command"] = self.install_command()
        return out

    def install_command(self) -> str:
        """The command that fetches this build, for a person to run.

        Zaram does not run it: TabbyAPI loads from a model folder set in its own
        config, which Zaram cannot read, so a download into a guessed place
        would be a multi-gigabyte file in the wrong directory. The placeholder is
        said rather than filled.
        """
        if self.runtime == "ollama" or not self.repo:
            return ""
        return (
            f'hf download {self.repo} --revision {self.revision} '
            f'--local-dir "<your TabbyAPI models folder>/{self.name}"'
        )


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


#: The words a capability may be written in. A closed list so a typo in the
#: manifest costs a badge, not a screen that renders whatever it was handed.
#: These are the names Ollama's `/api/show` uses, which is what lets an
#: installed model's own report replace the manifest's claim without a mapping.
CAPABILITIES = ("vision", "tools", "thinking")


def _capabilities_of(entry: Dict[str, Any]) -> Tuple[str, ...]:
    raw = entry.get("capabilities")
    if not isinstance(raw, list):
        return ()
    return tuple(c for c in CAPABILITIES if c in raw)


def _tabby_models(data: Dict[str, Any], generated: str) -> List[Recommendation]:
    """The EXL3 builds the manifest lists, sized by arithmetic.

    `parameters_b` x `bits_per_weight` / 8 is the weights; the same sum
    `providers.discoverers.openai_compat.size_from_id` does from a served model's
    name, so a build listed here and the same build served agree about how big it
    is. An entry missing either figure has no size and is left out, for the reason
    `_models_in` leaves out a recommendation with no cost: an offer whose size is
    unstated is the one thing this must not make.
    """
    out: List[Recommendation] = []
    for entry in data.get("tabby") or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        params, bits = entry.get("parameters_b"), entry.get("bits_per_weight")
        if (
            not name
            or not isinstance(params, (int, float))
            or not isinstance(bits, (int, float))
            or params <= 0
            or bits <= 0
        ):
            continue
        out.append(
            Recommendation(
                name=name,
                size_bytes=int(params * 1e9 * bits / 8),
                why=str(entry.get("why") or ""),
                generated=generated,
                capabilities=_capabilities_of(entry),
                runtime="tabby",
                repo=str(entry.get("repo") or ""),
                revision=str(entry.get("revision") or ""),
            )
        )
    return out


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
                capabilities=_capabilities_of(entry),
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


@dataclass(frozen=True)
class CatalogueEntry:
    """One model in the browser, and how it stands on *this* machine.

    Separate from `Recommendation` deliberately. That record is the
    manifest's half and says so — *"whether it fits is a fact about the
    machine, measured by the caller"* — and merging the two would put a
    machine-dependent field on the thing that is read from a file. This is
    the caller's half, and it is the one the browser renders.
    """

    model: Recommendation
    #: Whether this is in the tier the manifest aims at *this* machine —
    #: what `recommend_for` would have returned.
    #:
    #: **Not the same question as `fits`, and conflating them was a real
    #: bug.** `max_budget_gb` is a tier's ceiling: which machines it is
    #: *aimed at*, not what its models require. Read as a requirement it
    #: made `qwen3:0.6b` — half a gigabyte — report "does not fit" on a
    #: 9 GB budget, because 9 is not `<= 3`. A small model runs anywhere; it
    #: is simply not what you would be told to download.
    recommended: bool
    #: **Three-valued, and the third value is the point.** `True` fits,
    #: `False` does not, and `None` means the machine could not be
    #: measured — Apple and DirectML report no VRAM, and `hardware.py`
    #: returns `None` rather than zero for exactly this reason. Rendering
    #: `None` as "does not fit" would grey out the whole catalogue on a Mac;
    #: rendering it as "fits" would promise something unmeasured.
    fits: Optional[bool]
    #: Already pulled, so the row offers a choice rather than a download.
    installed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.model.to_dict(),
            "recommended": self.recommended,
            "fits": self.fits,
            "installed": self.installed,
        }


def catalogue_for(
    budget_bytes: Optional[int],
    *,
    installed: Sequence[str] = (),
    path: str = MANIFEST_PATH,
) -> List[CatalogueEntry]:
    """Every model the manifest knows, graded against this machine.

    The browser's list, as opposed to `recommend_for`'s single tier.
    Asked for 4 October 2026 with a screenshot of LM Studio's model
    browser: the maintainer wants to *see* the options and choose, not be
    handed one.

    **Models that do not fit are listed, not hidden.** `CLAUDE.md` says the
    pack catalogue shows unavailable packs *"greyed out and honestly graded
    against the user's hardware, licence and installed apps"*, and the same
    argument holds here — a list that silently omits the 27B leaves someone
    wondering whether Zaram knows it exists, and a person who is about to
    buy a card has a reason to look. Hiding it would also make the
    *"disabled capabilities are visible, not silent"* rule false on the one
    screen where capability is the subject.

    **A model in several tiers is listed once, at the lowest.** `qwen3:8b`
    appears in the 9 GB tier and again in the 18 GB one; the first is what
    it actually needs, and showing it twice would read as two models.
    """
    data = _load(path)
    if not data:
        return []

    generated = str(data.get("generated") or "")
    tiers = data.get("tiers")
    if not isinstance(tiers, list):
        return []

    budget_gb = None if budget_bytes is None else budget_bytes / GB
    have = {str(name).strip() for name in installed}

    # What the manifest would recommend for this machine, by name. The
    # browser marks these rather than recomputing the tier rule, so the
    # badge cannot disagree with the offer first run makes.
    suggested = {r.name for r in recommend_for(budget_bytes, path=path)}

    seen: Dict[str, CatalogueEntry] = {}
    for tier in tiers:
        if not isinstance(tier, dict):
            continue
        for model in _models_in(tier, generated):
            if model.name in seen:
                # Already listed under a lower tier. One row per model: a
                # name in two tiers is one thing to download.
                continue
            # **Fit is arithmetic, not tier membership.** A model fits when
            # its weights fit the budget beside the embedder, which is the
            # same sum the residency gate does. `None` when the machine
            # could not be measured — rendering that as "does not fit"
            # would grey out the entire catalogue on a Mac, and as "fits"
            # would promise something nobody measured.
            fits: Optional[bool]
            if budget_bytes is None:
                fits = None
            else:
                fits = model.size_bytes <= budget_bytes
            seen[model.name] = CatalogueEntry(
                model=model,
                recommended=model.name in suggested,
                fits=fits,
                installed=model.name in have,
            )

    # EXL3 builds for TabbyAPI, listed beside the Ollama ones and graded by the
    # same arithmetic. **Never `recommended`**: that badge means "what first run
    # would offer", and first run offers only what Zaram can fetch.
    for model in _tabby_models(data, generated):
        if model.name in seen:
            continue
        fits = None if budget_bytes is None else model.size_bytes <= budget_bytes
        seen[model.name] = CatalogueEntry(
            model=model, recommended=False, fits=fits, installed=model.name in have
        )

    # Smallest first. The browser is read by somebody deciding what to
    # spend a download on, and the cheapest option is the one they are
    # most likely to take on a metered connection.
    return sorted(seen.values(), key=lambda entry: entry.model.size_bytes)
