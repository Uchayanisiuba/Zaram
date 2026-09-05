"""Whether Zaram can actually answer yet, and what to offer if it cannot.

A fresh install on a machine with no Ollama and no key is not broken, but it
looks broken, which is worse. Ingest works, the surfaces render, recall works
on keyword overlap — and the composer sits there answering nothing. Someone
opening that concludes the product does not work and never opens it again.

So this names the state and hands the interface something to offer. Three
findings, in the order they are worth acting on, and every one of them carries
what it would cost.

**Sizes are stated before anything is fetched.** Naming a fix without naming
its price is not a choice the user can make on a metered connection — the same
reasoning that makes the OCR extra quote 321 MB rather than say "install
Docling". A download is offered, never begun: rule 7g means no network call
happens before the user has consented to one, and that includes the check for
what is available.

**Nothing here downloads, installs or configures anything.** It reports. The
acting is the caller's, after a person has chosen — which keeps this testable
without a network and keeps consent at the surface where it belongs.

**The model offered is matched to the machine, from the dated manifest.** It
used to be one hardcoded name and one hardcoded number, offered to a 4 GB
laptop and a 24 GB workstation alike — a recommendation that was wrong in both
directions at once. `providers.model_manifest` answers *"what suits a machine
with this much room"*; the budget is measured by the caller and passed in, so
detection stays separate from recommendation exactly as `CLAUDE.md` requires,
and a stale manifest can name an old model but can never misreport hardware.

**An unmeasured machine gets the smallest tier**, because `budget_bytes` is
three-valued and `None` is a real answer: Apple and DirectML report no
capacity, and a discovery that has not run yet reports none either. A thin
recommendation the machine can certainly run beats a fat one it cannot.

*Recorded rather than decided here, and worth a maintainer's answer: at the top
tiers the manifest's pick is large — a 24 GB machine is now offered a 20 GB
first download, and `CLAUDE.md`'s first-run rule says a user asked to pull 7 GB
before their first answer closes the app. Below about 9 GB of budget the two
instructions agree; above it they pull apart, and this follows the manifest.
No ceiling is imposed here because inventing one would be a second
recommendation policy sitting beside the manifest, which is the thing the
manifest exists to stop.*
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

from providers.model_manifest import Recommendation, recommend_for

logger = logging.getLogger(__name__)

__all__ = ["Readiness", "Offer", "Diagnosis", "diagnose", "model_to_offer"]


class Readiness(str, Enum):
    """What the product can do right now."""

    #: A model is reachable. Chat answers.
    READY = "ready"
    #: An engine is installed but holds no model that can hold a conversation.
    ENGINE_WITHOUT_MODEL = "engine_without_model"
    #: No local engine and no cloud key. Everything except chat works.
    NO_ENGINE = "no_engine"


class OfferKind(str, Enum):
    INSTALL_ENGINE = "install_engine"
    PULL_MODEL = "pull_model"
    USE_CLOUD_KEY = "use_cloud_key"
    EXPLORE = "explore"


@dataclass(frozen=True)
class Offer:
    """Something the user can choose, with its cost stated up front."""

    kind: OfferKind
    #: The button, as a person would read it.
    label: str
    #: One sentence on what happens if they choose it.
    detail: str
    #: Bytes that would be downloaded, or None when nothing is fetched. Never
    #: 0 for "unknown" — 0 is a figure and it would read as free.
    download_bytes: Optional[int] = None
    #: The model this offer would fetch. Carried for whatever executes the
    #: offer, and never rendered: the primary path shows no model filenames,
    #: which is why the name is a field of its own rather than a word in the
    #: detail line above.
    model_name: Optional[str] = None
    #: The date on the list the recommendation came from, or None when it came
    #: from the fallback constant instead. `CLAUDE.md` asks for it to be
    #: visible — a recommendation is only as current as the list behind it, and
    #: a surface that shows the model but hides the date is claiming more
    #: currency than the manifest has.
    recommended_on: Optional[str] = None

    @property
    def download_label(self) -> str:
        if self.download_bytes is None:
            return ""
        megabytes = self.download_bytes / (1024 * 1024)
        if megabytes >= 1024:
            return f"{megabytes / 1024:.1f} GB"
        return f"{megabytes:.0f} MB"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "label": self.label,
            "detail": self.detail,
            "download_bytes": self.download_bytes,
            "download_label": self.download_label,
            "model_name": self.model_name,
            "recommended_on": self.recommended_on,
        }


@dataclass(frozen=True)
class Diagnosis:
    """The state, why it is that, and what to do about it."""

    readiness: Readiness
    #: One line for the user. Plain language, no model filenames.
    summary: str
    offers: Sequence[Offer] = field(default_factory=tuple)
    #: What still works while unready. Naming this is the difference between
    #: "unconfigured" and "broken" — rule: disabled capabilities are visible,
    #: not silent.
    still_works: Sequence[str] = field(default_factory=tuple)

    @property
    def can_chat(self) -> bool:
        return self.readiness is Readiness.READY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "readiness": self.readiness.value,
            "summary": self.summary,
            "can_chat": self.can_chat,
            "offers": [offer.to_dict() for offer in self.offers],
            "still_works": list(self.still_works),
        }


#: The smallest model that can hold a conversation, and its real download size.
#: A name and a number rather than a range, because the offer states a cost the
#: user is agreeing to.
#:
#: **The fallback, not the answer.** The manifest decides; this is what is
#: offered when it cannot — a file missing from the bundle, a corrupt one, a
#: tier holding nothing with a size on it. Never fail closed: a first run that
#: recommends an older model than it might have is a smaller problem than a
#: first run that offers nothing at all.
SMALLEST_CHAT_MODEL = "qwen2.5:0.5b"
SMALLEST_CHAT_BYTES = 397 * 1024 * 1024

#: The sentence that goes with the fallback. Every manifest entry carries its
#: own `why`; this stands in when there is no entry to read one from.
FALLBACK_WHY = (
    "The smallest one that works, so you get a real answer in minutes. "
    "Zaram can fetch a better one later."
)

#: Ollama's Windows installer. Approximate and deliberately rounded up — a
#: stated size that turns out larger is a broken promise; one that turns out
#: smaller is a pleasant surprise.
ENGINE_BYTES = 750 * 1024 * 1024

#: What works with no engine at all. Everything here is verified by the
#: fallback path in the bootstrapper: parsers are pure Python and bundled, and
#: the hash embedder keeps recall working on keyword overlap.
WORKS_WITHOUT_ENGINE = (
    "Add documents to Knowledge — reading and indexing them needs no model",
    "Browse Memory, Work, Projects and the egress log",
    "Search your documents by keyword",
)

_EXPLORE = Offer(
    kind=OfferKind.EXPLORE,
    label="Look around first",
    detail=(
        "Add a folder and explore what Zaram found. You can set up a model "
        "whenever you like."
    ),
)

_CLOUD = Offer(
    kind=OfferKind.USE_CLOUD_KEY,
    label="Use a cloud model instead",
    detail=(
        "Paste a key from a provider you already pay for. Zaram shows you "
        "exactly what leaves your machine before it does, every time."
    ),
)


def model_to_offer(budget_bytes: Optional[int]) -> Recommendation:
    """What to suggest for a machine with this much room, or the fallback.

    `recommend_for` is written not to raise and returns an empty list on every
    failure it anticipates. The guard is here anyway because it cannot
    anticipate all of them — a tier whose `max_budget_gb` is a word rather than
    a number reaches `float()` and raises `ValueError` from inside a module
    whose contract is that it never does. A malformed file in the bundle must
    cost a better recommendation, never the first-run screen.
    """
    try:
        candidates = recommend_for(budget_bytes)
    except Exception:  # noqa: BLE001 - never fail closed; see above.
        logger.warning("model manifest unusable; offering the fallback model")
        candidates = []

    if candidates:
        # The first of the tier. A tier is ordered best-first by the person who
        # wrote it, and choosing between entries here would be a second
        # recommendation policy competing with the manifest's own.
        return candidates[0]

    return Recommendation(
        name=SMALLEST_CHAT_MODEL,
        size_bytes=SMALLEST_CHAT_BYTES,
        why=FALLBACK_WHY,
        # Empty, and it stays empty rather than being filled with today's date.
        # A fallback has no list behind it, and stamping one would put a date on
        # the screen that nothing generated.
        generated="",
    )


def diagnose(
    *,
    engine_installed: bool,
    chat_models: Sequence[str] = (),
    cloud_key_configured: bool = False,
    budget_bytes: Optional[int] = None,
) -> Diagnosis:
    """Name the state and what to offer.

    Takes what was found rather than going and looking, so it is decidable
    without a network and so discovery stays where it already lives. The
    caller passes: whether a local engine responded, which chat-capable models
    it holds, and whether a cloud key is configured.

    ``budget_bytes`` is what a chat model may claim on this machine —
    `ProviderManager.resident_budget_bytes`, measured by the caller — and
    ``None`` is a real answer meaning it could not be measured, not a budget of
    zero. It is read only to pick which model to name; every other decision
    here is the same on any hardware.
    """
    if chat_models or cloud_key_configured:
        where = "on this machine" if chat_models else "through your cloud key"
        return Diagnosis(
            readiness=Readiness.READY,
            summary=f"Ready — Zaram can answer {where}.",
            offers=(),
            still_works=(),
        )

    recommended = model_to_offer(budget_bytes)

    if engine_installed:
        return Diagnosis(
            readiness=Readiness.ENGINE_WITHOUT_MODEL,
            summary=(
                "Almost there. The local engine is running but has no model "
                "that can hold a conversation yet."
            ),
            offers=(
                Offer(
                    kind=OfferKind.PULL_MODEL,
                    # Not "a small model". The manifest picks by machine, so on
                    # a large card this is not a small one and the label would
                    # be a promise the price beside it contradicts.
                    label="Download a model to start with",
                    # The manifest's own sentence, which is written for a
                    # person and names no model. Composing one here would put a
                    # second description of the same model in a second place.
                    detail=recommended.why or FALLBACK_WHY,
                    download_bytes=recommended.size_bytes,
                    model_name=recommended.name,
                    recommended_on=recommended.generated or None,
                ),
                _CLOUD,
                _EXPLORE,
            ),
            still_works=WORKS_WITHOUT_ENGINE,
        )

    return Diagnosis(
        readiness=Readiness.NO_ENGINE,
        summary=(
            "Zaram has nothing to answer with yet. Everything else works — "
            "you just need a model."
        ),
        offers=(
            Offer(
                kind=OfferKind.INSTALL_ENGINE,
                label="Set up a local model",
                detail=(
                    "Installs the engine that runs models on your own machine. "
                    "Nothing you type leaves the device."
                ),
                # Engine and first model together, because installing the
                # engine alone lands the user in the other unready state and
                # asks them to agree to a second download. One decision, one
                # number — and the model in that number is the same one the
                # other state would offer, so the price does not change under
                # the user between the two screens.
                download_bytes=ENGINE_BYTES + recommended.size_bytes,
                model_name=recommended.name,
                recommended_on=recommended.generated or None,
            ),
            _CLOUD,
            _EXPLORE,
        ),
        still_works=WORKS_WITHOUT_ENGINE,
    )
