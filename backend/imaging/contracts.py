"""What an image generator is, independently of which one is installed.

Written 3 September 2026, and the first decision was where *not* to put it.

Why this does not register through ``backend/media/``
----------------------------------------------------
``media/`` is a complete, tested Media Runtime — registry, manager, sessions,
health, ``MediaType.IMAGE``, ``MediaLocality`` — and nothing imports it. The
question the handoff left open was whether image generation should become its
first real caller. It should not, and the reason is written in that package's
own source rather than inferred: ``MediaProvider`` is *"intentionally stripped
of any modality-specific method (no ``generate_audio``)"*, so it has no execute
path at all. Registering here would mean **inventing** one from imagination for
a single caller, which is the thing CLAUDE.md refuses when it says to build two
packs by hand before building the pack system.

It also duplicates concepts that already have live homes and live tests:
locality is ``CapabilityLocality``, health is ``HealthStatus``, model selection
and consent are ``ProviderManager``, and what leaves the device is
``EgressGate``. Routing an image through a second set of those would make image
generation a *third* path beside two that work — which is the outcome the
handoff was trying to avoid by asking the question.

So an image is what it actually is: **an artifact**. It goes down the path
documents already go down — a runtime, ``ArtifactService``, one output
directory, one record, provenance — and this module is only the narrow seam
where "which thing draws the picture" is replaceable, exactly as TTS is kept
behind an interface so Kokoro is a choice rather than an embedding.

Progress is measured, never estimated
-------------------------------------
:class:`ImageProgress` carries a step count and nothing resembling a time
remaining. A diffusion pipeline emits a callback per denoising step, so
"step 7 of 30" is a **measurement**; seconds-left is a guess until several
steps have run, and a confident wrong number is worse than no number. That is
the same discipline ``vram_bytes`` keeps by returning ``None`` rather than
``0``, and ``locality_of`` by refusing to say "local" for a model it cannot
place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, runtime_checkable

#: Hard ceiling on how many images one request may produce.
#:
#: Four, because that is what fits the 2x2 grid the card draws and because each
#: one costs seconds of GPU time the user is waiting through. A request for
#: twenty is a request to sit still for several minutes, which is not a thing
#: to discover after saying yes.
MAX_IMAGES = 4

#: Denoising steps when the caller does not say.
#:
#: **Four, because FLUX.1 [schnell] is distilled to finish in four.** The name
#: is German for "fast" and the distillation is the whole point of the variant:
#: it is trained to land its result in a handful of steps with no guidance. The
#: SDXL number here was 30, and running 30 on schnell is seven times the wait
#: for a picture that is no better and often slightly worse, because the extra
#: steps push past what the distillation was trained to produce.
DEFAULT_STEPS = 4


@dataclass(frozen=True)
class ImageRequest:
    """What to draw.

    Deliberately small. Every field here is one a caller can answer from what
    the user actually said; there is no sampler, scheduler or guidance knob,
    because CLAUDE.md keeps model filenames and quantisation settings out of
    the primary path and those are the same class of thing.
    """

    prompt: str
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    steps: int = DEFAULT_STEPS
    #: ``None`` means the provider picks and *reports* what it picked, so the
    #: same picture can be asked for again. An unreported seed is an image
    #: nobody can reproduce, including us.
    seed: Optional[int] = None
    count: int = 1

    def __post_init__(self) -> None:
        if not self.prompt.strip():
            raise ValueError("an image request with no prompt has nothing to draw")
        if not 1 <= self.count <= MAX_IMAGES:
            raise ValueError(f"count must be 1..{MAX_IMAGES}, not {self.count}")
        if self.steps < 1:
            raise ValueError("steps must be at least 1")
        # SDXL's UNet works in units of 8 pixels; a size that is not a multiple
        # is silently rounded by the pipeline, which means the image the user
        # gets is not the size the record says it is.
        if self.width % 8 or self.height % 8:
            raise ValueError("width and height must be multiples of 8")


@dataclass(frozen=True)
class ImageProgress:
    """How far along one image in a batch is. Measured, not predicted."""

    #: Completed denoising steps for the image currently being drawn.
    step: int
    total_steps: int
    #: Which image of the batch this is, 1-based, and how many there are.
    index: int = 1
    count: int = 1

    @property
    def percent(self) -> int:
        """Whole-batch progress, 0..100.

        Across the batch rather than per image, because that is the wait the
        user is actually sitting through: a bar that fills and resets four
        times reads as three failures and a success.
        """
        if self.total_steps < 1 or self.count < 1:
            return 0
        done = (self.index - 1) * self.total_steps + self.step
        return max(0, min(100, round(100 * done / (self.total_steps * self.count))))


@dataclass(frozen=True)
class GeneratedImage:
    """One picture, and what it took to make it."""

    png: bytes
    width: int
    height: int
    #: The seed actually used, never ``None``. See ``ImageRequest.seed``.
    seed: int


@dataclass(frozen=True)
class Availability:
    """Whether images can be drawn here, and if not, what would fix it.

    Mirrors ``artifacts.export.base.Availability`` on purpose: a capability
    that is off must say so and say what it costs, rather than failing at the
    moment of use. ``remedy`` names the size, because naming the fix without
    naming its cost is not a choice a user on metered data can make.
    """

    ok: bool
    reason: str = ""
    remedy: str = ""


AVAILABLE = Availability(ok=True)

#: Called once per denoising step. Must not raise — a progress callback that
#: throws would abort a generation that was working.
ProgressCallback = Callable[[ImageProgress], None]


@runtime_checkable
class ImageProvider(Protocol):
    """Something that can draw. One local implementation today, cloud later.

    The interface is what makes "local first, cloud when the user grants it" a
    routing decision rather than two codebases. It says nothing about diffusion
    because a cloud endpoint has no steps to report — a provider that cannot
    measure progress simply never calls the callback, and the card shows an
    indeterminate state instead of inventing a number.
    """

    #: Stable identifier, shown to the user as the model that answered.
    name: str

    def availability(self) -> Availability:
        """Whether this provider can run right now. Cheap; no model loading."""
        ...

    def generate(
        self,
        request: ImageRequest,
        on_progress: Optional[ProgressCallback] = None,
    ) -> List[GeneratedImage]:
        """Draw. Blocking; callers run it off the event loop."""
        ...
