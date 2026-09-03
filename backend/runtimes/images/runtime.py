"""Images Runtime — the second generative tool, and the first that refuses.

Modelled on `DocumentsRuntime` line for line, because that is the path in this
codebase that demonstrably reaches a user: a runtime registered at boot, calling
`ArtifactService`, writing into one output directory that cannot be overwritten,
and handing back a card. An image that arrived by any other route would be a
file Work has never heard of and a download the egress log cannot account for.

Generative tier, and the safety is structural
---------------------------------------------
CLAUDE.md's risk table: a generative tool creates new artifacts and changes
nothing that already exists, so it needs no undo, no sandbox and no
confirmation dialog. None of that safety is promised here — it lives underneath
in `ArtifactStore`, which has no capability to delete or overwrite and confines
every path to the output root before opening anything.

The refusal is the feature
--------------------------
This runtime's most important behaviour is the one where it produces nothing.

"Draw me a logo" reaching an ordinary chat model produces a confident paragraph
about a picture that was never made — rule 9 in a new medium, and the silent
version of it, because nothing on screen says the image does not exist. So when
no provider can draw, this returns ``success: False`` with a reason and a
remedy, and the chat path is responsible for showing that instead of an answer.

That ordering is deliberate and it is the handoff's: **the refusal path first,
the offer second.** An offer is the nice part; the refusal is the part that
stops the product lying.

Progress is published, not predicted
------------------------------------
A diffusion pipeline emits a callback per denoising step, so the events carry a
step count and a percentage derived from it. There is no time remaining
anywhere in this file, and `ImageProgress` has no field that could hold one —
see `imaging/contracts.py`. With code you watch it being written and the wait
explains itself; an image is silent for its whole duration unless something
reports it, and a wrong number is worse than none.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from artifacts.contracts import Artifact
from artifacts.service import ArtifactService
from core.contracts import (
    Capability,
    CapabilityLocality,
    Runtime,
    RuntimeMetadata,
    RuntimeState,
)
from core.event_bus import EventBus
from imaging.contracts import (
    DEFAULT_STEPS,
    MAX_IMAGES,
    GeneratedImage,
    ImageProgress,
    ImageProvider,
    ImageRequest,
)

logger = logging.getLogger(__name__)

RUNTIME_ID = "images"
RUNTIME_VERSION = "1.0.0"

#: The capability the planner routes an `image` intent to.
GENERATE = "image.generate"

#: What the user is told when nothing on the machine can draw and no reason was
#: supplied. A fallback for a state that should not occur — the provider always
#: gives a reason — kept because a bare "failed" is the one message a user
#: cannot act on.
_UNAVAILABLE = "Zaram cannot draw images on this machine yet."


class ImagesRuntime(Runtime):
    """Turns a description into a picture, and records where it came from."""

    def __init__(
        self,
        service: ArtifactService,
        provider: Optional[ImageProvider] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self._service = service
        # Injected, and `None` is a supported state rather than a broken one:
        # most machines have no image model, and that is a thing to say rather
        # than a thing to crash on.
        self._provider = provider
        self._event_bus = event_bus
        self._state = RuntimeState.UNINITIALIZED
        self._start_time = time.time()
        self._generated = 0

    # ------------------------------------------------------------- lifecycle

    def get_runtime_id(self) -> str:
        return RUNTIME_ID

    def get_version(self) -> str:
        return RUNTIME_VERSION

    def get_metadata(self) -> RuntimeMetadata:
        return RuntimeMetadata(
            runtime_id=RUNTIME_ID,
            version=RUNTIME_VERSION,
            priority="normal",
            capabilities=[
                Capability(
                    id=GENERATE,
                    runtime_id=RUNTIME_ID,
                    category="image",
                    # Local without qualification, because the only provider
                    # that exists is. When a cloud one is added this becomes a
                    # property of the provider rather than a constant here, and
                    # the egress gate is what governs it — not this field.
                    locality=CapabilityLocality.LOCAL,
                )
            ],
            dependencies=[],
            auto_start=True,
        )

    def get_state(self) -> RuntimeState:
        return self._state

    async def initialize(self) -> None:
        self._state = RuntimeState.READY
        availability = self.availability()
        if availability.ok:
            logger.info("Images Runtime ready; %s", self.describe_provider())
        else:
            # Info, not a warning. No image model installed is the ordinary
            # state of a machine, not a fault, and logging it as one trains
            # people to ignore warnings.
            logger.info("Images Runtime ready; nothing can draw: %s", availability.reason)

    async def shutdown(self) -> None:
        self._state = RuntimeState.STOPPING
        unload = getattr(self._provider, "unload", None)
        if callable(unload):
            try:
                unload()
            except Exception:
                logger.debug("Image provider did not unload cleanly", exc_info=True)
        self._state = RuntimeState.STOPPED

    async def health_check(self) -> Dict[str, Any]:
        availability = self.availability()
        return {
            "status": "healthy" if self._state == RuntimeState.READY else "degraded",
            "runtime_id": RUNTIME_ID,
            "generated": self._generated,
            # Disabled capabilities are visible, not silent — and the remedy
            # carries its size, because naming a fix without naming its cost is
            # not a choice a user on metered data can make.
            "can_draw": availability.ok,
            "reason": availability.reason,
            "remedy": availability.remedy,
            "provider": self.describe_provider(),
        }

    # ------------------------------------------------------------- capability

    def availability(self):
        """Whether a picture can be drawn right now, and if not, why."""
        from imaging.contracts import Availability

        if self._provider is None:
            return Availability(
                ok=False,
                reason=_UNAVAILABLE,
                remedy="Install an image model, or connect a provider that can draw.",
            )
        return self._provider.availability()

    def describe_provider(self) -> str:
        if self._provider is None:
            return "none"
        describe = getattr(self._provider, "describe", None)
        return describe() if callable(describe) else self._provider.name

    # --------------------------------------------------------------- execute

    async def execute(
        self, capability_id: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if capability_id != GENERATE:
            return {"success": False, "error": f"unknown capability {capability_id}"}

        prompt = (input_data.get("prompt") or "").strip()
        if not prompt:
            return {
                "success": False,
                "error": "There was nothing to draw — say what the picture should be of.",
            }

        # The refusal, before anything else and before any model is asked
        # anything. This is the branch that stops a text model being handed a
        # request it will answer in prose.
        availability = self.availability()
        if not availability.ok:
            return {
                "success": False,
                "error": availability.reason or _UNAVAILABLE,
                "remedy": availability.remedy,
                # Named so the caller can tell "cannot" from "went wrong", and
                # offer rather than apologise.
                "unavailable": True,
            }

        try:
            request = ImageRequest(
                prompt=prompt,
                negative_prompt=(input_data.get("negative_prompt") or "").strip(),
                width=int(input_data.get("width") or 1024),
                height=int(input_data.get("height") or 1024),
                steps=int(input_data.get("steps") or DEFAULT_STEPS),
                seed=input_data.get("seed"),
                count=max(1, min(MAX_IMAGES, int(input_data.get("count") or 1))),
            )
        except (TypeError, ValueError) as error:
            return {"success": False, "error": f"I can't draw that: {error}"}

        # Where each step's progress goes, supplied by whoever is going to
        # show it. A plain callable on `input_data` rather than an event on
        # the bus, and that choice was made the other way round first.
        #
        # The bus version published `image.progress` and **nothing subscribed
        # to it** — the dispatcher blocks on this coroutine, so the one place
        # that could have forwarded it was not running while the events were
        # being sent. That is a complete, tested, unreachable channel, which is
        # the shape `CLAUDE.md` says has been found fifteen times here. A
        # callback cannot be in that state: if nobody passes one, nothing is
        # reported and no code exists pretending otherwise.
        sink = input_data.get("progress_sink")
        on_progress = None
        if callable(sink):

            def on_progress(progress: ImageProgress) -> None:  # noqa: F811
                # Called from the sampling thread. The sink is responsible for
                # being safe to call from one — the dispatcher's is a queue.
                sink(
                    {
                        "step": progress.step,
                        "total_steps": progress.total_steps,
                        "index": progress.index,
                        "count": progress.count,
                        "percent": progress.percent,
                    }
                )

        try:
            # Off the event loop. Sampling holds the GIL in short bursts and
            # runs for tens of seconds; on the loop it would stall every other
            # request in the backend, including the stream carrying its own
            # progress events.
            drawn: List[GeneratedImage] = await asyncio.to_thread(
                self._provider.generate, request, on_progress
            )
        except Exception as error:
            logger.exception("Image generation failed")
            return {"success": False, "error": f"could not draw that: {error}"}

        if not drawn:
            return {"success": False, "error": "the image model produced nothing"}

        locality = input_data.get("locality") or "on your machine — nothing left the device"
        model = self.describe_provider()
        title = input_data.get("title") or _title_from(prompt)

        artifacts: List[Artifact] = []
        for index, image in enumerate(drawn):
            try:
                artifacts.append(
                    self._service.create_image(
                        title=title if len(drawn) == 1 else f"{title} ({index + 1})",
                        png=image.png,
                        prompt=prompt,
                        model=model,
                        locality=locality,
                        seed=image.seed,
                        project_id=input_data.get("project_id", ""),
                        conversation_id=input_data.get("session_id", ""),
                        conversation_title=input_data.get("conversation_title", "")
                        or title,
                    )
                )
            except Exception as error:
                logger.exception("Wrote the image but could not record it")
                return {"success": False, "error": f"could not save the image: {error}"}

        self._generated += len(artifacts)
        logger.info("Drew %d image(s) with %s", len(artifacts), model)

        return {
            "success": True,
            # A list even when there is one, because the card that draws these
            # is the same card either way — one request is one card, and a
            # batch is one card with a grid in it rather than four cards.
            "artifacts": [_card(a) for a in artifacts],
            "artifact": _card(artifacts[0]),
        }

def _card(artifact: Artifact) -> Dict[str, Any]:
    """What the conversation shows. The same shape a document card uses.

    Deliberately identical, including the `exists` read rather than an
    assumption that the write succeeded — see `runtimes/documents/runtime.py`,
    where an absent field made a card for a file written one second earlier
    render "file not found where it was written".
    """
    import os

    payload = artifact.to_dict()
    payload["exists"] = bool(artifact.path) and os.path.isfile(artifact.path)
    payload["download_url"] = f"/artifacts/{artifact.id}/download"
    # The picture *was* the request — this capability only runs when somebody
    # asked for an image — so the preview may open itself. Transport only: not
    # a property of the file, never stored, and absent from `/artifacts`,
    # because "did the user ask for this" is a fact about one exchange rather
    # than about a document that outlives it.
    payload["deliberate"] = True
    return payload


def _title_from(prompt: str) -> str:
    """A short name for the file, from what was asked for.

    The prompt itself, trimmed. Not a model call: naming a picture is not worth
    a round trip, and a generated title would be a second thing that can be
    wrong about an image nobody has looked at yet.
    """
    cleaned = " ".join(prompt.split())
    for opener in (
        "draw me a picture of ",
        "draw me an image of ",
        "draw me ",
        "draw a picture of ",
        "draw an image of ",
        "generate an image of ",
        "generate a picture of ",
        "create an image of ",
        "create a picture of ",
        "make me an image of ",
        "make me a picture of ",
        "an illustration of ",
        "a picture of ",
    ):
        if cleaned.lower().startswith(opener):
            cleaned = cleaned[len(opener) :]
            break
    cleaned = cleaned.strip(" .,")
    return (cleaned[:60] or "image").strip()
