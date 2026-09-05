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

**Smallest capable first, deliberately.** CLAUDE.md already settles it: a user
on metered data asked to pull 7 GB before their first answer closes the app.
The recommendation here is the smallest model that can hold a conversation, so
the first cited answer arrives in minutes; something better is fetched later,
in the background, once they have a reason to want it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

__all__ = ["Readiness", "Offer", "Diagnosis", "diagnose"]


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
#: user is agreeing to. Kept beside the manifest's reasoning: detection is
#: separate from recommendation, and this is recommendation.
SMALLEST_CHAT_MODEL = "qwen2.5:0.5b"
SMALLEST_CHAT_BYTES = 397 * 1024 * 1024

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


def diagnose(
    *,
    engine_installed: bool,
    chat_models: Sequence[str] = (),
    cloud_key_configured: bool = False,
) -> Diagnosis:
    """Name the state and what to offer.

    Takes what was found rather than going and looking, so it is decidable
    without a network and so discovery stays where it already lives. The
    caller passes: whether a local engine responded, which chat-capable models
    it holds, and whether a cloud key is configured.
    """
    if chat_models or cloud_key_configured:
        where = "on this machine" if chat_models else "through your cloud key"
        return Diagnosis(
            readiness=Readiness.READY,
            summary=f"Ready — Zaram can answer {where}.",
            offers=(),
            still_works=(),
        )

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
                    label="Download a small model to start with",
                    detail=(
                        "The smallest one that works, so you get a real answer "
                        "in minutes. Zaram can fetch a better one later."
                    ),
                    download_bytes=SMALLEST_CHAT_BYTES,
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
                # number.
                download_bytes=ENGINE_BYTES + SMALLEST_CHAT_BYTES,
            ),
            _CLOUD,
            _EXPLORE,
        ),
        still_works=WORKS_WITHOUT_ENGINE,
    )
